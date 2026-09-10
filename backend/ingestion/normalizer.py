"""
Robust Normalization Layer for Railway Maintenance Requests and Train Movements.
Converts arbitrary tables, key-value blocks, and prose into canonical MaintenanceRequest and TrainMovement objects.
Flags incomplete or ambiguous records as Needs-Review.
Phase 2 Final (v6) Updates:
- Priority Convention: 1=Emergency, 2=High Urgent, 3=Normal
- Application ID assignment: APP-YYYYMMDD-XXXXXX per document
- doc_type parameter support ('request' | 'train_movement')
- normalize_train_table() for train movement tables
- KM Sanity check: km_end - km_start > 100 -> Needs-Review
- Dedicated confidence_score calculation per K.9
"""
import re
import uuid
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from rapidfuzz import fuzz

from backend.config import APP_TIMEZONE
from backend.models import (
    MaintenanceRequest,
    DepartmentEnum,
    BlockTypeEnum,
    RequestStatusEnum,
    TrainMovement,
    IngestResponse,
    generate_application_id,
)
from backend.ingestion.extractor import DocumentContent
from backend.engine.conflicts import parse_km_range_robust, normalize_resource_name
from backend.engine.batch_engine import classify_work_type

parse_km_range = parse_km_range_robust

DEPT_PATTERNS = {
    DepartmentEnum.ENGINEERING: [
        r"engineering", r"civil", r"track", r"p-?way", r"permanent\s*way", r"bridge", r"works", r"den", r"aen", r"sse/pway"
    ],
    DepartmentEnum.ST: [
        r"s\s*&\s*t", r"signal", r"telecom", r"interlocking", r"point\s*machine", r"axle\s*counter", r"track\s*circuit", r"sse/sig", r"sse/tele"
    ],
    DepartmentEnum.ELECTRICAL: [
        r"electrical", r"traction", r"ohe", r"trd", r"power", r"catenary", r"pantograph", r"substation", r"tss", r"sse/trd"
    ],
    DepartmentEnum.OPERATIONS: [
        r"operations", r"traffic", r"optg", r"operating", r"station\s*master"
    ]
}

ASSET_KEYWORDS = {
    "Track Section": ["track", "rail", "sleeper", "ballast", "turnout", "cross-over", "diamond"],
    "OHE 25kV Catenary": ["ohe", "catenary", "contact wire", "dropper", "cantilever", "insulator", "mast", "feeder"],
    "Signal & Interlocking": ["signal", "point machine", "interlocking", "relay", "axle counter", "track circuit", "ei"],
    "Bridge & Culvert": ["bridge", "girder", "pier", "abutment", "culvert", "waterway"],
    "Traction Substation (TSS)": ["substation", "tss", "transformer", "circuit breaker", "isolator"],
}

RESOURCE_KEYWORDS = [
    "TTM", "Track Tamper", "CSM", "BCM", "Ballast Cleaner", "BRM", "Regulator",
    "Speno", "Rail Grinder", "Tower Wagon", "TW", "Crane", "Work Train", "Utility Vehicle",
    "Wiring Train", "Derrick", "Flash Butt Welding Plant", "Gang 1", "Gang 2", "Gang 3",
    "S&T Testing Team", "OHE Maintenance Crew", "P-Way Gang", "Traction Crew"
]


def detect_department(text: str) -> Optional[DepartmentEnum]:
    t_lower = text.lower()
    for dept, patterns in DEPT_PATTERNS.items():
        for pat in patterns:
            if re.search(r"\b" + pat + r"\b", t_lower):
                return dept
    return None


def parse_duration_minutes(text: str) -> Optional[int]:
    t_lower = text.lower()
    m_hm = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\s*(?:(\d+)\s*(?:mins?|minutes?|m))?", t_lower)
    if m_hm:
        hours = float(m_hm.group(1))
        mins = float(m_hm.group(2)) if m_hm.group(2) else 0.0
        return int(hours * 60 + mins)

    m_m = re.search(r"(\d+)\s*(?:mins?|minutes?|min)", t_lower)
    if m_m:
        return int(m_m.group(1))

    m_int = re.search(r"^(\d+)$", text.strip())
    if m_int:
        val = int(m_int.group(1))
        return val * 60 if val <= 12 else val

    return None


def parse_datetime_flexible(text: str, default_date: Optional[date] = None) -> Optional[datetime]:
    text = text.strip()
    if not text:
        return None

    if default_date is None:
        default_date = date.today() + timedelta(days=1)

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=APP_TIMEZONE)
        return dt.astimezone(APP_TIMEZONE)
    except Exception:
        pass

    for fmt in [
        "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S",
        "%b %d, %Y %H:%M", "%d %b %Y %H:%M",
        "%d-%b-%Y %H:%M", "%d-%b-%Y %H:%M:%S"
    ]:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=APP_TIMEZONE)
        except ValueError:
            continue

    time_clean = re.sub(r"\s*ist\s*", "", text, flags=re.IGNORECASE).strip()
    time_clean = re.sub(r"^from\s+", "", time_clean, flags=re.IGNORECASE).strip()
    for fmt in ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"]:
        try:
            t = datetime.strptime(time_clean, fmt).time()
            return datetime.combine(default_date, t, tzinfo=APP_TIMEZONE)
        except ValueError:
            continue

    return None


def parse_time_window(text: str, default_date: Optional[date] = None) -> Tuple[Optional[datetime], Optional[datetime]]:
    if default_date is None:
        default_date = date.today() + timedelta(days=1)

    date_match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}[-\/]\d{2}[-\/]\d{4}|\d{2}-[A-Za-z]{3}-\d{4})", text)
    if date_match:
        try:
            d_str = date_match.group(1)
            for dfmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y"]:
                try:
                    default_date = datetime.strptime(d_str, dfmt).date()
                    break
                except ValueError:
                    pass
        except Exception:
            pass

    m_tw = re.search(r"(?:from\s+)?(\d{1,2}:\d{2}(?:\s*(?:am|pm))?)\s*(?:to|-|\/|until|till)\s*(\d{1,2}:\d{2}(?:\s*(?:am|pm))?)", text, re.IGNORECASE)
    if m_tw:
        t1 = parse_datetime_flexible(m_tw.group(1), default_date)
        t2 = parse_datetime_flexible(m_tw.group(2), default_date)
        if t1 and t2:
            if t2 < t1:
                t2 = t2 + timedelta(days=1)
            return t1, t2

    return None, None


def normalize_priority(text: str) -> Tuple[int, Optional[str], bool]:
    t_lower = text.lower().strip()
    m_num = re.search(r"\b([1-9])\b", text)
    if m_num:
        p = int(m_num.group(1))
        if p in (1, 2, 3):
            labels = {1: "P1 - Emergency", 2: "P2 - High Urgent", 3: "P3 - Normal"}
            return p, labels[p], False
        else:
            return 3, f"Priority {p} specified exceeds Phase 2 range (1-3); normalized to Normal (P3) and flagged for review", True

    if any(w in t_lower for w in ["critical", "emergency", "urgent", "safety defect", "derailment risk", "immediate", "p1"]):
        return 1, "P1 - Emergency (Safety defect / derailment risk)", False
    elif any(w in t_lower for w in ["high", "speed restriction", "psr", "tsr removal", "p2"]):
        return 2, "P2 - High Urgent (Speed restriction removal)", False
    elif any(w in t_lower for w in ["planned", "standard", "scheduled", "periodic", "medium", "normal", "p3", "p4", "p5"]):
        return 3, "P3 - Normal (Standard maintenance)", False

    return 3, "P3 - Normal (Default)", False


def normalize_block_type(text: str) -> BlockTypeEnum:
    t_lower = text.lower()
    if "emergency" in t_lower or "urgent" in t_lower or "breakdown" in t_lower:
        return BlockTypeEnum.EMERGENCY
    elif "mega" in t_lower or "planned" in t_lower or "scheduled" in t_lower or "annual" in t_lower:
        return BlockTypeEnum.PLANNED
    return BlockTypeEnum.NORMAL


def extract_resources(text: str) -> List[str]:
    found = []
    for r in RESOURCE_KEYWORDS:
        if re.search(r"\b" + re.escape(r) + r"\b", text, re.IGNORECASE):
            found.append(normalize_resource_name(r).title())
    return list(dict.fromkeys(found))


def compute_confidence_score(
    required_fields_count: int,
    total_required_fields: int,
    work_type_matched: bool,
    km_and_time_unambiguous: bool
) -> float:
    """
    Confidence score calculation (Part K.9):
    0.5 * required_fields_present + 0.3 * work_type_matched_catalog + 0.2 * km_and_time_unambiguous
    """
    f_ratio = min(1.0, required_fields_count / max(1, total_required_fields))
    w_score = 1.0 if work_type_matched else 0.0
    u_score = 1.0 if km_and_time_unambiguous else 0.0
    score = (0.5 * f_ratio) + (0.3 * w_score) + (0.2 * u_score)
    return round(score, 2)


def extract_corridor_from_string(text: Any) -> Optional[str]:
    """
    Robustly extracts railway corridor or station pair from arbitrary text or cell.
    Supports:
    - 2-6 letter uppercase or title-case codes: NDLS-GZB, MMCT-BVI, HWH-KGP, BVI-ST, AGC-JHS, MAS-GDR, SBC-MYS
    - Words with hyphens/slashes: Mumbai-Surat, Delhi-Ghaziabad, Howrah-Kharagpur
    - Words separated by 'to' or '/': NDLS to CNB, MMCT to BVI, NDLS/GZB
    """
    if not text:
        return None
    clean = " ".join(str(text).split()).strip()

    # 1. Explicit keyword: Corridor: XXX-YYY or Section: XXX-YYY
    m_key = re.search(r"(?:corridor|section|route|line|sector)\s*[:\s-]\s*([A-Za-z0-9\-/\s–]{3,25}?)(?:\n|,|\.|\s*between|\s*from|\s*km|\s*dep|\s*arr|$)", clean, re.IGNORECASE)
    if m_key:
        cand = re.sub(r"\s+", "", m_key.group(1)).replace("–", "-").replace("/", "-").strip("-").upper()
        if "-" in cand and len(cand) >= 4:
            return cand

    # 2. Station code pair: e.g. NDLS-GZB, MMCT-BVI, BVI-ST, HWH-KGP
    m_pair = re.search(r"\b([A-Za-z]{2,6}\s*[-–\/]\s*[A-Za-z]{2,6})\b", clean)
    if m_pair:
        cand = re.sub(r"\s+", "", m_pair.group(1)).replace("–", "-").replace("/", "-").strip("-").upper()
        non_corridors = ["P-WAY", "S-T", "KM-SPAN", "SL-NO", "JOB-ID", "REQ-ID", "W35", "W-35"]
        if cand not in non_corridors and not any(cand.startswith(pfx) for pfx in ["JOB-", "REQ-", "APP-", "TASK-", "WO-"]):
            if "-" in cand and len(cand) >= 4:
                return cand

    # 3. 'From X to Y' or 'X to Y'
    m_to = re.search(r"\b([A-Za-z]{2,12})\s+(?:to|-|–)\s+([A-Za-z]{2,12})\b", clean, re.IGNORECASE)
    if m_to:
        s1, s2 = m_to.group(1).upper(), m_to.group(2).upper()
        if s1 not in ["KM", "FROM", "UP", "DN", "MIN", "HOURS", "DEP", "ARR"] and s2 not in ["KM", "TO", "UP", "DN", "MIN", "HOURS", "DEP", "ARR"]:
            return f"{s1}-{s2}"

    # 4. Long station names with hyphen: e.g. Mumbai-Surat, Delhi-Kanpur
    m_names = re.search(r"\b([A-Z][a-z]{2,15})\s*[-–]\s*([A-Z][a-z]{2,15})\b", clean)
    if m_names:
        return f"{m_names.group(1).upper()}-{m_names.group(2).upper()}"

    return None


def detect_document_corridor(raw_text: str, filename: str = "") -> Optional[str]:
    """Scans top of document, title, and filename to find default dominant corridor."""
    header_sample = f"{filename} {raw_text[:2500]}"

    # Check for explicit keywords first
    m = re.search(r"(?:corridor|section|route|line)\s*[:\s-]\s*([A-Za-z0-9\-/\s–]{3,25}?)(?:\n|,|\.|\s*between|\s*from|\s*km|$)", header_sample, re.IGNORECASE)
    if m:
        cand = re.sub(r"\s+", "", m.group(1)).replace("–", "-").replace("/", "-").strip("-").upper()
        if "-" in cand and len(cand) >= 4:
            return cand

    # Find all station pairs
    pairs = re.findall(r"\b([A-Za-z]{2,6}\s*[-–\/]\s*[A-Za-z]{2,6})\b", header_sample)
    for p in pairs:
        cand = re.sub(r"\s+", "", p).replace("–", "-").replace("/", "-").strip("-").upper()
        if cand not in ["P-WAY", "S-T", "KM-SPAN", "SL-NO", "JOB-ID", "REQ-ID", "W35", "W-35"] and not any(cand.startswith(pfx) for pfx in ["JOB-", "REQ-", "APP-", "TASK-", "WO-"]):
            if "-" in cand and len(cand) >= 4:
                return cand

    return None


def normalize_train_table(
    table: List[List[str]],
    source_filename: str,
    doc_corridor: Optional[str] = None
) -> List[TrainMovement]:
    """
    Part D: Normalizes train movement tables.
    Train headers (case-insensitive):
    - train_id|train no|id
    - corridor|section|route|line
    - from_stn / to_stn (or From / To)
    - departure_time|dep|from|start_time
    - arrival_time|arr|to|end_time
    - km_start|km_from
    - km_end|km_to
    - train_type|type
    - train_name|name
    - speed|speed_kmh
    """
    if len(table) < 2:
        return []

    header = [c.lower().strip() for c in table[0]]
    col_map = {}
    for idx, col in enumerate(header):
        c = col.strip().lower()
        if any(k in c for k in ["train_number", "train_no", "train no", "train number", "train #", "train_id", "train id", "service no", "train", "id"]):
            if "train_id" not in col_map:
                col_map["train_id"] = idx
        elif any(k in c for k in ["corridor", "section", "route", "line", "block_section", "block section", "sector"]):
            col_map["corridor"] = idx
        elif any(k == c or k in c for k in ["from_station", "origin", "source", "source_station", "src", "station_from", "station from"]):
            col_map["from_stn"] = idx
        elif any(k == c or k in c for k in ["to_station", "destination", "dest", "dest_station", "station_to", "station to"]):
            col_map["to_stn"] = idx
        elif any(k in c for k in ["departure_time", "dep_time", "departure", "dep", "start_time", "from_time", "origin time"]):
            col_map["dep"] = idx
        elif any(k in c for k in ["arrival_time", "arr_time", "arrival", "arr", "end_time", "to_time", "dest time"]):
            col_map["arr"] = idx
        elif any(k in c for k in ["window", "time_window", "time window", "timings", "timing", "slot", "schedule"]):
            col_map["time_window"] = idx
        elif any(k in c for k in ["km_start", "km_from", "from_km", "start_km", "from km", "start km"]):
            col_map["km_start"] = idx
        elif any(k in c for k in ["km_end", "km_to", "to_km", "end_km", "to km", "end km"]):
            col_map["km_end"] = idx
        elif any(k in c for k in ["km", "chainage", "km_range", "km range", "span", "km span", "distance"]):
            col_map["km_range"] = idx
        elif any(k in c for k in ["train_name", "train name", "name", "service name", "title", "description"]):
            col_map["train_name"] = idx
        elif any(k in c for k in ["speed", "speed_kmh", "speed kmh", "mps", "max speed", "kmph"]):
            col_map["speed"] = idx
        elif any(k in c for k in ["train_type", "type", "category", "class"]):
            col_map["type"] = idx

    # If From and To columns exist as standalone headers
    if "from_stn" not in col_map and "to_stn" not in col_map:
        from_idx = [i for i, c in enumerate(header) if c in ["from", "origin", "source"]]
        to_idx = [i for i, c in enumerate(header) if c in ["to", "destination", "dest"]]
        if from_idx and to_idx:
            col_map["from_stn"] = from_idx[0]
            col_map["to_stn"] = to_idx[0]

    trains = []
    base_date = date.today() + timedelta(days=1)

    for row in table[1:]:
        if not any(str(c).strip() for c in row):
            continue

        def get_val(key: str) -> str:
            if key in col_map and col_map[key] < len(row):
                return str(row[col_map[key]]).strip()
            return ""

        raw_tid = get_val("train_id")
        corridor = get_val("corridor")
        t_name = get_val("train_name")
        t_type = get_val("type") or "Express"
        raw_speed = get_val("speed")

        # 1. Check if From/To columns provide corridor
        if not corridor and "from_stn" in col_map and "to_stn" in col_map:
            f_stn = get_val("from_stn")
            t_stn = get_val("to_stn")
            if f_stn and t_stn:
                corridor = f"{f_stn}-{t_stn}".replace(" ", "").upper()

        # 2. Check all cells in row for a corridor/station pair
        if not corridor:
            for cell in row:
                c_cand = extract_corridor_from_string(str(cell))
                if c_cand:
                    corridor = c_cand
                    break

        # 3. Fallback to document dominant corridor
        if not corridor and doc_corridor:
            corridor = doc_corridor

        # 4. Fallback to clean default derived from document if still unspecified
        if not corridor:
            clean_fn = re.sub(r"[_\-]+", " ", os.path.splitext(source_filename)[0]).upper()
            fn_corridor = extract_corridor_from_string(clean_fn)
            corridor = fn_corridor if fn_corridor else "SECTION-1"

        # Clean train id and number
        t_num = None
        if raw_tid:
            num_m = re.search(r"\b(\d{4,5})\b", raw_tid)
            if num_m:
                t_num = num_m.group(1)
        if not t_num and t_name:
            num_m = re.search(r"\b(\d{4,5})\b", t_name)
            if num_m:
                t_num = num_m.group(1)
        if not t_num:
            for cell in row:
                num_m = re.search(r"\b(\d{4,5})\b", str(cell))
                if num_m:
                    t_num = num_m.group(1)
                    break

        tid = raw_tid or (f"Train {t_num}" if t_num else f"T-{uuid.uuid4().hex[:4].upper()}")

        k_s, k_e = 0.0, 250.0
        if "km_start" in col_map and "km_end" in col_map:
            try:
                k_s = float(re.sub(r"[^\d.]", "", get_val("km_start")))
                k_e = float(re.sub(r"[^\d.]", "", get_val("km_end")))
            except Exception:
                pass
        elif "km_range" in col_map:
            k1, k2 = parse_km_range_robust(get_val("km_range"))
            if k1 is not None and k2 is not None:
                k_s, k_e = k1, k2
        else:
            for cell in row:
                k1, k2 = parse_km_range_robust(str(cell))
                if k1 is not None and k2 is not None:
                    k_s, k_e = k1, k2
                    break

        dep = parse_datetime_flexible(get_val("dep"), base_date)
        arr = parse_datetime_flexible(get_val("arr"), base_date)

        if (not dep or not arr) and "time_window" in col_map:
            w_s, w_e = parse_time_window(get_val("time_window"), base_date)
            if not dep:
                dep = w_s
            if not arr:
                arr = w_e

        if not dep or not arr:
            for cell in row:
                w_s, w_e = parse_time_window(str(cell), base_date)
                if w_s and w_e:
                    if not dep:
                        dep = w_s
                    if not arr:
                        arr = w_e
                    break

        if not dep:
            all_times = []
            for cell in row:
                tm = re.findall(r"\b(\d{1,2}:\d{2})\b", str(cell))
                all_times.extend(tm)
            if len(all_times) >= 2:
                dep = parse_datetime_flexible(all_times[0], base_date)
                arr = parse_datetime_flexible(all_times[1], base_date)

        if not dep:
            dep = datetime.combine(base_date, datetime.min.time(), tzinfo=APP_TIMEZONE) + timedelta(hours=6)
        if not arr:
            arr = dep + timedelta(hours=2)
        elif arr < dep:
            arr = arr + timedelta(days=1)

        speed_val = 100.0
        if raw_speed:
            try:
                speed_val = float(re.sub(r"[^\d.]", "", raw_speed))
            except Exception:
                pass

        trains.append(TrainMovement(
            train_id=tid,
            train_number=t_num or tid,
            train_name=t_name or f"Scheduled Train {t_num or tid}",
            speed_kmh=speed_val,
            corridor=corridor,
            departure_time=dep,
            arrival_time=arr,
            km_start=min(k_s, k_e),
            km_end=max(k_s, k_e),
            train_type=t_type,
            source_document=source_filename
        ))

    return trains


def extract_trains_from_text(
    raw_text: str,
    source_filename: str,
    doc_corridor: Optional[str] = None
) -> List[TrainMovement]:
    """
    Robust fallback to extract Train Movements line-by-line from unstructured text,
    PDF text streams, circulars, or CSV logs.
    """
    trains: List[TrainMovement] = []
    base_date = date.today() + timedelta(days=1)
    seen = set()

    # Pattern 1: Narrative / Circular format (e.g., Note 45, Section 2, or Memo)
    p1 = r"(?:train|express|freight|mail|passenger)\s*(?:no\.?|#)?\s*([A-Za-z0-9\s\-]+?)\s*(?:on\s*(?:corridor\s*)?([A-Za-z0-9\-–/]+))?\s*(?:from|dep|departing)?\s*(\d{1,2}:\d{2})\s*(?:to|arr|arriving|-)\s*(\d{1,2}:\d{2})\s*(?:\(?km\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\)?)?"
    for m in re.finditer(p1, raw_text, re.IGNORECASE):
        tid = m.group(1).strip()
        matched_corr = extract_corridor_from_string(m.group(2)) if m.group(2) else None
        corr = matched_corr or doc_corridor or "SECTION-1"
        dep = parse_datetime_flexible(m.group(3), base_date)
        arr = parse_datetime_flexible(m.group(4), base_date)
        k1 = float(m.group(5)) if m.group(5) else 0.0
        k2 = float(m.group(6)) if m.group(6) else 250.0
        if dep and arr:
            if arr < dep:
                arr = arr + timedelta(days=1)
            num_m = re.search(r"\b(\d{4,5})\b", tid)
            t_num = num_m.group(1) if num_m else tid
            key = (t_num, corr, dep.isoformat())
            if key not in seen:
                seen.add(key)
                trains.append(TrainMovement(
                    train_id=tid if "train" in tid.lower() else f"Train {tid}",
                    train_number=t_num,
                    train_name=tid,
                    speed_kmh=110.0,
                    corridor=corr,
                    departure_time=dep,
                    arrival_time=arr,
                    km_start=min(k1, k2),
                    km_end=max(k1, k2),
                    train_type="Scheduled Passenger",
                    source_document=source_filename
                ))

    # Pattern 2: Line-based tabular parsing
    lines = raw_text.splitlines()
    for line in lines:
        line_clean = line.strip()
        if len(line_clean) < 12:
            continue

        if re.search(r"^(?:train\s*no|corridor|section|sl\s*no|date|window)\b", line_clean, re.IGNORECASE):
            continue

        num_m = re.search(r"\b(\d{4,5})\b", line_clean)
        line_corr = extract_corridor_from_string(line_clean)
        times = re.findall(r"\b(\d{1,2}:\d{2})\b", line_clean)

        if (num_m or line_corr) and len(times) >= 2:
            t_num = num_m.group(1) if num_m else f"T-{len(trains)+1}"
            corr = line_corr or doc_corridor or "SECTION-1"
            dep = parse_datetime_flexible(times[0], base_date)
            arr = parse_datetime_flexible(times[1], base_date)
            k1, k2 = parse_km_range_robust(line_clean)
            if k1 is None or k2 is None:
                k1, k2 = 0.0, 250.0

            if dep and arr:
                if arr < dep:
                    arr = arr + timedelta(days=1)
                key = (t_num, corr, dep.isoformat())
                if key not in seen:
                    seen.add(key)
                    trains.append(TrainMovement(
                        train_id=f"Train {t_num}",
                        train_number=t_num,
                        train_name=f"Express {t_num}",
                        speed_kmh=100.0,
                        corridor=corr,
                        departure_time=dep,
                        arrival_time=arr,
                        km_start=min(k1, k2),
                        km_end=max(k1, k2),
                        train_type="Scheduled Passenger",
                        source_document=source_filename
                    ))

    return trains


def normalize_table_data(
    table: List[List[str]],
    source_filename: str,
    application_id: Optional[str] = None,
    doc_corridor: Optional[str] = None
) -> List[MaintenanceRequest]:
    if application_id is None:
        application_id = generate_application_id()
    if len(table) < 2:
        return []

    header_row = [c.lower().strip() for c in table[0]]
    col_map = {}
    for idx, col in enumerate(header_row):
        c_clean = col.strip().lower()
        if c_clean in ["corridor", "section", "route", "line", "block_section", "block section", "sector"]:
            col_map["corridor"] = idx
        elif any(k == c_clean or k in c_clean for k in ["from_station", "origin", "source", "source_station", "src", "station_from", "station from"]):
            col_map["from_stn"] = idx
        elif any(k == c_clean or k in c_clean for k in ["to_station", "destination", "dest", "dest_station", "station_to", "station to"]):
            col_map["to_stn"] = idx
        elif c_clean in ["id", "job id", "job_id", "request id", "request_id", "req id", "req_id", "request no", "sl no", "sl_no", "item"]:
            col_map["id"] = idx
        elif any(k in c_clean for k in ["dept", "department", "branch", "discipline"]):
            col_map["dept"] = idx
        elif c_clean in ["km_start", "km_from", "from_km", "start_km", "km from", "start km"]:
            col_map["km_start"] = idx
        elif c_clean in ["km_end", "km_to", "to_km", "end_km", "km to", "end km"]:
            col_map["km_end"] = idx
        elif any(k in c_clean for k in ["km", "location", "chainage", "km_range", "km span"]):
            col_map["km_range"] = idx
        elif any(k in c_clean for k in ["asset", "equipment", "asset_type", "structure"]):
            col_map["asset"] = idx
        elif any(k in c_clean for k in ["work", "activity", "nature_of_work", "work_type", "description", "job"]):
            col_map["work_type"] = idx
        elif any(k in c_clean for k in ["priority", "urgency"]):
            col_map["priority"] = idx
        elif any(k in c_clean for k in ["block_type", "category"]):
            col_map["block_type"] = idx
        elif any(k in c_clean for k in ["duration", "hours", "duration_mins", "time_req", "duration_minutes"]):
            col_map["duration"] = idx
        elif c_clean in ["earliest", "start_time", "from_time", "start"]:
            col_map["start_time"] = idx
        elif c_clean in ["latest", "end_time", "to_time", "end"]:
            col_map["end_time"] = idx
        elif any(k in c_clean for k in ["window", "time_window", "slot", "timings", "permitted_window"]):
            col_map["time_window"] = idx
        elif any(k in c_clean for k in ["date", "target_date", "maintenance_date"]):
            col_map["date"] = idx
        elif any(k in c_clean for k in ["resource", "machinery", "plant", "machine", "team", "equipment_req"]):
            col_map["resources"] = idx
        elif any(k in c_clean for k in ["isolation", "power_block", "traffic_block", "shadow"]):
            col_map["isolation"] = idx

    # If From and To columns exist as standalone headers
    if "from_stn" not in col_map and "to_stn" not in col_map:
        from_idx = [i for i, c in enumerate(header_row) if c in ["from", "origin", "source"]]
        to_idx = [i for i, c in enumerate(header_row) if c in ["to", "destination", "dest"]]
        if from_idx and to_idx:
            col_map["from_stn"] = from_idx[0]
            col_map["to_stn"] = to_idx[0]

    results = []
    base_date = date.today() + timedelta(days=1)

    for row_idx, row in enumerate(table[1:]):
        if not any(c.strip() for c in row):
            continue

        def get_col(key: str) -> str:
            if key in col_map and col_map[key] < len(row):
                val = row[col_map[key]]
                if val:
                    return " ".join(str(val).split()).strip()
            return ""

        raw_id = get_col("id")
        req_id = re.sub(r"\s+", "", raw_id) if raw_id else f"REQ-{uuid.uuid4().hex[:6].upper()}"
        corridor = get_col("corridor")

        # 1. From / To columns combination
        if not corridor and "from_stn" in col_map and "to_stn" in col_map:
            f_stn = get_col("from_stn")
            t_stn = get_col("to_stn")
            if f_stn and t_stn:
                corridor = f"{f_stn}-{t_stn}".replace(" ", "").upper()

        # 2. Check other cells in row for a corridor/station pair (only if no dedicated corridor column)
        if not corridor and "corridor" not in col_map:
            for idx, cell in enumerate(row):
                if idx == col_map.get("id"):
                    continue
                c_cand = extract_corridor_from_string(str(cell))
                if c_cand:
                    corridor = c_cand
                    break

        # 3. Fallback to document dominant corridor (only if no dedicated corridor column)
        if not corridor and "corridor" not in col_map and doc_corridor:
            corridor = doc_corridor

        dept_str = get_col("dept")
        work_str = get_col("work_type") or "Track Maintenance"
        asset_str = get_col("asset") or "Track Infrastructure"

        dept = detect_department(dept_str) or detect_department(work_str) or detect_department(asset_str) or DepartmentEnum.ENGINEERING

        km_s, km_e = None, None
        if "km_start" in col_map and "km_end" in col_map:
            try:
                km_s = float(re.sub(r"[^\d.]", "", get_col("km_start")))
                km_e = float(re.sub(r"[^\d.]", "", get_col("km_end")))
            except (ValueError, TypeError):
                pass

        if (km_s is None or km_e is None) and ("km_range" in col_map or "corridor" in col_map):
            combined_km_txt = f"{get_col('km_range')} {get_col('corridor')}"
            km_s, km_e = parse_km_range_robust(combined_km_txt)

        row_date = base_date
        if "date" in col_map and get_col("date"):
            parsed_d = parse_datetime_flexible(get_col("date"))
            if parsed_d:
                row_date = parsed_d.date()

        t_start, t_end = None, None
        if "start_time" in col_map and "end_time" in col_map:
            t_start = parse_datetime_flexible(get_col("start_time"), row_date)
            t_end = parse_datetime_flexible(get_col("end_time"), row_date)
        elif "time_window" in col_map:
            t_start, t_end = parse_time_window(get_col("time_window"), row_date)

        duration = None
        if "duration" in col_map:
            duration = parse_duration_minutes(get_col("duration"))

        if duration is None and t_start and t_end:
            duration = max(15, int((t_end - t_start).total_seconds() / 60))
        elif duration and t_start and not t_end:
            t_end = t_start + timedelta(minutes=duration)
        elif duration and not t_start:
            t_start = datetime.combine(row_date, datetime.min.time(), tzinfo=APP_TIMEZONE) + timedelta(hours=1)
            t_end = t_start + timedelta(hours=5)

        priority_val, prio_reason, prio_flagged = normalize_priority(get_col("priority") or work_str)
        block_type = normalize_block_type(get_col("block_type") or work_str)

        res_str = get_col("resources")
        resources = extract_resources(f"{res_str} {work_str}")
        isolation = get_col("isolation") or ("Power Block Required" if dept == DepartmentEnum.ELECTRICAL else "None")

        # Validation & Sanity checks
        missing = []
        if not corridor:
            missing.append("corridor")
        if km_s is None:
            missing.append("km_start")
        if km_e is None:
            missing.append("km_end")
        if duration is None or duration <= 0:
            missing.append("duration_minutes")
        if t_start is None:
            missing.append("earliest_start")
        if t_end is None:
            missing.append("latest_end")
        if prio_flagged:
            missing.append("priority_review")

        # KM Sanity check per Part K.9: km_end - km_start > 100 -> Needs-Review
        f_km_s = km_s if km_s is not None else 0.0
        f_km_e = km_e if km_e is not None else 1.0
        if abs(f_km_e - f_km_s) > 100.0:
            missing.append("km_span_exceeds_100km")

        # Work type catalog match check per Part D
        cat, _, cat_score = classify_work_type(work_str)
        if cat is None:
            missing.append("unmatched_work_type")

        status = RequestStatusEnum.NEEDS_REVIEW if missing else RequestStatusEnum.CONFIRMED

        f_corridor = corridor if corridor else "UNSPECIFIED-CORRIDOR"
        f_duration = duration if duration is not None and duration > 0 else 120
        f_t_start = t_start if t_start is not None else datetime.combine(row_date, datetime.min.time(), tzinfo=APP_TIMEZONE) + timedelta(hours=1)
        f_t_end = t_end if t_end is not None else f_t_start + timedelta(minutes=f_duration)

        # Dedicated confidence_score column per K.9
        total_req_fields = 6
        present_fields = total_req_fields - len([m for m in missing if m in ["corridor", "km_start", "km_end", "duration_minutes", "earliest_start", "latest_end"]])
        conf_score = compute_confidence_score(
            required_fields_count=present_fields,
            total_required_fields=total_req_fields,
            work_type_matched=(cat is not None),
            km_and_time_unambiguous=(abs(f_km_e - f_km_s) <= 100.0 and f_duration > 0 and t_start is not None)
        )

        req = MaintenanceRequest(
            request_id=req_id,
            application_id=application_id,
            document_type="maintenance",
            department=dept.value,
            corridor=f_corridor,
            km_start=f_km_s,
            km_end=f_km_e,
            asset=asset_str,
            work_type=work_str,
            priority=priority_val,
            priority_reason=prio_reason,
            block_type=block_type,
            duration_minutes=f_duration,
            earliest_start=f_t_start,
            latest_end=f_t_end,
            due_date=row_date,
            required_resources=resources,
            isolation_requirement=isolation,
            block_shared_allowed=True,
            status=status,
            source_document=source_filename,
            missing_fields=missing,
            confidence_score=conf_score,
            validation_notes=f"Missing/Flagged: {', '.join(missing)}" if missing else "Extracted successfully from structured table"
        )
        results.append(req)

    return results


def normalize_prose_text(
    raw_text: str,
    source_filename: str,
    application_id: Optional[str] = None,
    doc_corridor: Optional[str] = None
) -> Tuple[List[MaintenanceRequest], List[TrainMovement]]:
    if application_id is None:
        application_id = generate_application_id()
    requests: List[MaintenanceRequest] = []
    trains: List[TrainMovement] = []

    train_pattern = r"(?:train|express|freight|mail)\s*(?:no\.?|#)?\s*([A-Za-z0-9\s\-]+?)\s*on\s*(?:corridor\s*)?([A-Za-z0-9\-–/]+)\s*(?:from|dep|departing)?\s*(\d{1,2}:\d{2})\s*(?:to|arr|arriving)?\s*(\d{1,2}:\d{2})\s*(?:\(?km\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\)?)?"
    for m in re.finditer(train_pattern, raw_text, re.IGNORECASE):
        t_id = m.group(1).strip()
        matched_corr = extract_corridor_from_string(m.group(2)) if m.group(2) else None
        corr = matched_corr or doc_corridor or "SECTION-1"
        dep_str = m.group(3)
        arr_str = m.group(4)
        k1 = float(m.group(5)) if m.group(5) else 0.0
        k2 = float(m.group(6)) if m.group(6) else 500.0
        base_d = date.today() + timedelta(days=1)
        t_dep = parse_datetime_flexible(dep_str, base_d)
        t_arr = parse_datetime_flexible(arr_str, base_d)
        if t_dep and t_arr:
            num_m = re.search(r"\b(\d{4,5})\b", t_id)
            t_num = num_m.group(1) if num_m else t_id
            trains.append(TrainMovement(
                train_id=f"Train {t_id}",
                train_number=t_num,
                train_name=t_id,
                speed_kmh=110.0,
                corridor=corr,
                departure_time=t_dep,
                arrival_time=t_arr,
                km_start=min(k1, k2),
                km_end=max(k1, k2),
                train_type="Scheduled Passenger/Freight",
                source_document=source_filename
            ))

    chunks = re.split(r"(?:\n\s*\n|\n(?=(?:Request|Job|Item|Note|Memo|Maintenance|Block\s*Request|P-Way|OHE|S&T|\d+[\.\)])(?:\s*[A-Za-z0-9\-_]+)?\s*[:\-])|\n(?=\s*[-*]\s*))", raw_text, flags=re.IGNORECASE)
    base_date = date.today() + timedelta(days=1)

    for chunk in chunks:
        chunk_clean = chunk.strip()
        if len(chunk_clean) < 25:
            continue

        if re.search(r"^railway\s*maintenance\s*plan|^daily\s*block\s*summary", chunk_clean, re.IGNORECASE) and len(chunk_clean) < 100:
            continue

        corridor = extract_corridor_from_string(chunk_clean) or doc_corridor

        km_s, km_e = parse_km_range_robust(chunk_clean)
        dept = detect_department(chunk_clean) or DepartmentEnum.ENGINEERING
        duration = parse_duration_minutes(chunk_clean)
        t_start, t_end = parse_time_window(chunk_clean, base_date)

        if duration is None and t_start and t_end:
            duration = max(15, int((t_end - t_start).total_seconds() / 60))
        elif duration and t_start and not t_end:
            t_end = t_start + timedelta(minutes=duration)

        priority_val, prio_reason, prio_flagged = normalize_priority(chunk_clean)
        block_type = normalize_block_type(chunk_clean)
        resources = extract_resources(chunk_clean)
        isolation = "Power Block (OHE)" if ("power block" in chunk_clean.lower() or dept == DepartmentEnum.ELECTRICAL) else "None"

        work_type = "Track & Asset Maintenance"
        for candidate in [
            "Rail renewal/replacement", "Track/rail repair & welding", "Sleeper replacement",
            "Ballast work (tamping/screening)", "Points & crossing maintenance", "Point machine maintenance/repair",
            "Signalling cable testing", "OHE catenary wire adjustment", "OHE insulator replacement",
            "Track circuit testing & calibration", "Trackside signal mast/aspect maintenance",
            "OHE replacement/repair", "Bridge/tunnel routine inspection"
        ]:
            if re.search(r"\b" + re.escape(candidate) + r"\b", chunk_clean, re.IGNORECASE):
                work_type = candidate
                break

        asset = "Track Infrastructure"
        for a_name, keywords in ASSET_KEYWORDS.items():
            if any(re.search(r"\b" + re.escape(kw) + r"\b", chunk_clean, re.IGNORECASE) for kw in keywords):
                asset = a_name
                break

        missing = []
        if not corridor:
            missing.append("corridor")
        if km_s is None:
            missing.append("km_start")
        if km_e is None:
            missing.append("km_end")
        if duration is None or duration <= 0:
            missing.append("duration_minutes")
        if t_start is None:
            missing.append("earliest_start")
        if t_end is None:
            missing.append("latest_end")
        if prio_flagged:
            missing.append("priority_review")

        f_km_s = km_s if km_s is not None else 0.0
        f_km_e = km_e if km_e is not None else 1.0
        if abs(f_km_e - f_km_s) > 100.0:
            missing.append("km_span_exceeds_100km")

        cat, _, _ = classify_work_type(work_type)
        if cat is None:
            missing.append("unmatched_work_type")

        status = RequestStatusEnum.NEEDS_REVIEW if missing else RequestStatusEnum.CONFIRMED

        f_corridor = corridor if corridor else "UNSPECIFIED-CORRIDOR"
        f_duration = duration if duration is not None and duration > 0 else 120
        f_t_start = t_start if t_start is not None else datetime.combine(base_date, datetime.min.time(), tzinfo=APP_TIMEZONE) + timedelta(hours=1)
        f_t_end = t_end if t_end is not None else f_t_start + timedelta(minutes=f_duration)

        total_req_fields = 6
        present_fields = total_req_fields - len([m for m in missing if m in ["corridor", "km_start", "km_end", "duration_minutes", "earliest_start", "latest_end"]])
        conf_score = compute_confidence_score(
            required_fields_count=present_fields,
            total_required_fields=total_req_fields,
            work_type_matched=(cat is not None),
            km_and_time_unambiguous=(abs(f_km_e - f_km_s) <= 100.0 and f_duration > 0 and t_start is not None)
        )

        req = MaintenanceRequest(
            request_id=f"REQ-PR-{uuid.uuid4().hex[:6].upper()}",
            application_id=application_id,
            document_type="maintenance",
            department=dept.value,
            corridor=f_corridor,
            km_start=f_km_s,
            km_end=f_km_e,
            asset=asset,
            work_type=work_type,
            priority=priority_val,
            priority_reason=prio_reason,
            block_type=block_type,
            duration_minutes=f_duration,
            earliest_start=f_t_start,
            latest_end=f_t_end,
            due_date=base_date,
            required_resources=resources,
            isolation_requirement=isolation,
            block_shared_allowed=True,
            status=status,
            source_document=source_filename,
            missing_fields=missing,
            confidence_score=conf_score,
            validation_notes=f"Missing/Flagged: {', '.join(missing)}" if missing else "Extracted from prose text successfully"
        )
        requests.append(req)

    return requests, trains


def process_document_content(doc: DocumentContent, doc_type: str = "request") -> IngestResponse:
    """
    Part D: Processes document content based on doc_type ('request' | 'train_movement').
    Dynamically identifies corridor from document header and tables.
    """
    application_id = generate_application_id()
    doc_corridor = detect_document_corridor(doc.raw_text, doc.filename)
    all_requests: List[MaintenanceRequest] = []
    all_trains: List[TrainMovement] = []
    warnings: List[str] = []

    if doc_type == "train_movement":
        for table in doc.tables:
            table_trains = normalize_train_table(table, doc.filename, doc_corridor=doc_corridor)
            all_trains.extend(table_trains)

        # Robust extraction from raw text/prose lines
        text_trains = extract_trains_from_text(doc.raw_text, doc.filename, doc_corridor=doc_corridor)
        for tt in text_trains:
            if not any(
                t.train_id == tt.train_id or (
                    t.corridor == tt.corridor and
                    abs((t.departure_time - tt.departure_time).total_seconds()) < 600
                )
                for t in all_trains
            ):
                all_trains.append(tt)

        if not all_trains:
            warnings.append(f"No train movements could be extracted from {doc.filename}. Check column headers or text format.")

        return IngestResponse(
            application_id=application_id,
            filename=doc.filename,
            total_extracted=len(all_trains),
            confirmed_count=len(all_trains),
            needs_review_count=0,
            candidate_requests=[],
            detected_trains=all_trains,
            warnings=warnings
        )

    # Default: doc_type == 'request'
    for table in doc.tables:
        table_reqs = normalize_table_data(table, doc.filename, application_id, doc_corridor=doc_corridor)
        all_requests.extend(table_reqs)

    if not all_requests or len(doc.raw_text.strip()) > 50:
        prose_reqs, prose_trains = normalize_prose_text(doc.raw_text, doc.filename, application_id, doc_corridor=doc_corridor)
        all_trains.extend(prose_trains)
        # Also check extract_trains_from_text
        text_trains = extract_trains_from_text(doc.raw_text, doc.filename, doc_corridor=doc_corridor)
        for tt in text_trains:
            if not any(t.train_id == tt.train_id for t in all_trains):
                all_trains.append(tt)
        if not all_requests:
            all_requests.extend(prose_reqs)
        else:
            for pr in prose_reqs:
                is_duplicate = any(
                    r.corridor == pr.corridor and abs(r.km_start - pr.km_start) < 0.5 and r.department == pr.department
                    for r in all_requests
                )
                if not is_duplicate:
                    all_requests.append(pr)

    confirmed = [r for r in all_requests if r.status == RequestStatusEnum.CONFIRMED]
    needs_review = [r for r in all_requests if r.status == RequestStatusEnum.NEEDS_REVIEW]

    if not all_requests:
        warnings.append(f"No maintenance requests could be extracted from {doc.filename}. Please check file layout.")

    return IngestResponse(
        application_id=application_id,
        filename=doc.filename,
        total_extracted=len(all_requests),
        confirmed_count=len(confirmed),
        needs_review_count=len(needs_review),
        candidate_requests=all_requests,
        detected_trains=all_trains,
        warnings=warnings
    )