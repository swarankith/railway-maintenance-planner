"""
Robust Normalization Layer for Railway Maintenance Requests and Train Movements.
Converts arbitrary tables, key-value blocks, and prose into canonical MaintenanceRequest objects.
Flags incomplete or ambiguous records as Needs-Review.
Phase 2 Updates:
- Priority Convention: 1=Emergency, 2=High Urgent, 3=Normal (values > 3 flagged)
- Application ID assignment: APP-YYYYMMDD-XXXXXX per document
- Robust KM parsing and resource normalization
"""
import re
import uuid
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo

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

# Alias for backwards compatibility
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
    """
    Normalizes priority:
    1 = Emergency
    2 = High Urgent
    3 = Normal
    Returns (priority, reason, is_flagged_for_review).
    """
    t_lower = text.lower().strip()
    m_num = re.search(r"\b([1-9])\b", text)
    if m_num:
        p = int(m_num.group(1))
        if p in (1, 2, 3):
            labels = {1: "P1 - Emergency", 2: "P2 - High Urgent", 3: "P3 - Normal"}
            return p, labels[p], False
        else:
            # Value > 3 flagged for human review
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


def normalize_table_data(
    table: List[List[str]],
    source_filename: str,
    application_id: Optional[str] = None
) -> List[MaintenanceRequest]:
    if application_id is None:
        application_id = generate_application_id()
    if len(table) < 2:
        return []

    header_row = [c.lower().strip() for c in table[0]]
    col_map = {}
    for idx, col in enumerate(header_row):
        c_clean = col.strip().lower()
        if c_clean in ["corridor", "section", "route", "line", "block_section", "block section"]:
            col_map["corridor"] = idx
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
        elif c_clean in ["earliest", "start_time", "from_time", "start", "from"]:
            col_map["start_time"] = idx
        elif c_clean in ["latest", "end_time", "to_time", "end", "to"]:
            col_map["end_time"] = idx
        elif any(k in c_clean for k in ["window", "time_window", "slot", "timings", "permitted_window"]):
            col_map["time_window"] = idx
        elif any(k in c_clean for k in ["date", "target_date", "maintenance_date"]):
            col_map["date"] = idx
        elif any(k in c_clean for k in ["resource", "machinery", "plant", "machine", "team", "equipment_req"]):
            col_map["resources"] = idx
        elif any(k in c_clean for k in ["isolation", "power_block", "traffic_block", "shadow"]):
            col_map["isolation"] = idx

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

        status = RequestStatusEnum.NEEDS_REVIEW if missing else RequestStatusEnum.CONFIRMED

        f_km_s = km_s if km_s is not None else 0.0
        f_km_e = km_e if km_e is not None else 1.0
        f_corridor = corridor if corridor else "UNSPECIFIED-CORRIDOR"
        f_duration = duration if duration is not None and duration > 0 else 120
        f_t_start = t_start if t_start is not None else datetime.combine(row_date, datetime.min.time(), tzinfo=APP_TIMEZONE) + timedelta(hours=1)
        f_t_end = t_end if t_end is not None else f_t_start + timedelta(minutes=f_duration)

        req = MaintenanceRequest(
            request_id=req_id,
            application_id=application_id,
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
            validation_notes=f"Missing: {', '.join(missing)}" if missing else "Extracted successfully from structured table"
        )
        results.append(req)

    return results


def normalize_prose_text(
    raw_text: str,
    source_filename: str,
    application_id: Optional[str] = None
) -> Tuple[List[MaintenanceRequest], List[TrainMovement]]:
    if application_id is None:
        application_id = generate_application_id()
    requests: List[MaintenanceRequest] = []
    trains: List[TrainMovement] = []

    train_pattern = r"(?:train|express|freight|mail)\s*(?:no\.?|#)?\s*([A-Za-z0-9\s\-]+?)\s*on\s*(?:corridor\s*)?([A-Za-z0-9\-]+)\s*(?:from|dep|departing)?\s*(\d{1,2}:\d{2})\s*(?:to|arr|arriving)?\s*(\d{1,2}:\d{2})\s*(?:\(?km\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\)?)?"
    for m in re.finditer(train_pattern, raw_text, re.IGNORECASE):
        t_id = m.group(1).strip()
        corr = m.group(2).strip()
        dep_str = m.group(3)
        arr_str = m.group(4)
        k1 = float(m.group(5)) if m.group(5) else 0.0
        k2 = float(m.group(6)) if m.group(6) else 500.0
        base_d = date.today() + timedelta(days=1)
        t_dep = parse_datetime_flexible(dep_str, base_d)
        t_arr = parse_datetime_flexible(arr_str, base_d)
        if t_dep and t_arr:
            trains.append(TrainMovement(
                train_id=f"Train {t_id}",
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

        corridor = None
        corr_m = re.search(r"(?:corridor|section|route|line)\s*[:\s]\s*([A-Za-z0-9\-/\s]+?)(?:\n|,|\.|\s*between|\s*from)", chunk_clean, re.IGNORECASE)
        if corr_m:
            corridor = corr_m.group(1).strip()
        else:
            pair_m = re.search(r"\b([A-Z]{2,5}\s*[-–\/]\s*[A-Z]{2,5})\b", chunk_clean)
            if pair_m:
                corridor = re.sub(r"\s+", "", pair_m.group(1))

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
        for candidate in ["Rail Grinding", "Track Tamping", "Ballast Cleaning", "OHE Catenary Inspection", "Point Machine Replacement", "Track Circuit Testing", "Bridge Girder Inspection", "Turnout Overhaul", "Insulator Replacement"]:
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

        status = RequestStatusEnum.NEEDS_REVIEW if missing else RequestStatusEnum.CONFIRMED

        f_km_s = km_s if km_s is not None else 0.0
        f_km_e = km_e if km_e is not None else 1.0
        f_corridor = corridor if corridor else "UNSPECIFIED-CORRIDOR"
        f_duration = duration if duration is not None and duration > 0 else 120
        f_t_start = t_start if t_start is not None else datetime.combine(base_date, datetime.min.time(), tzinfo=APP_TIMEZONE) + timedelta(hours=1)
        f_t_end = t_end if t_end is not None else f_t_start + timedelta(minutes=f_duration)

        req = MaintenanceRequest(
            request_id=f"REQ-{uuid.uuid4().hex[:6].upper()}",
            application_id=application_id,
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
            validation_notes=f"Missing: {', '.join(missing)}" if missing else "Extracted from prose text successfully"
        )
        requests.append(req)

    return requests, trains


def process_document_content(doc: DocumentContent) -> IngestResponse:
    application_id = generate_application_id()
    all_requests: List[MaintenanceRequest] = []
    all_trains: List[TrainMovement] = []
    warnings: List[str] = []

    for table in doc.tables:
        table_reqs = normalize_table_data(table, doc.filename, application_id)
        all_requests.extend(table_reqs)

    if not all_requests or len(doc.raw_text.strip()) > 50:
        prose_reqs, prose_trains = normalize_prose_text(doc.raw_text, doc.filename, application_id)
        all_trains.extend(prose_trains)
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