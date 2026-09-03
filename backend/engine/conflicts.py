"""
Conflict Detection Engine for Railway Maintenance Requests.
Phase 2 Enhancements & Bug Fixes:
- Bug Fix 3: Robust KM Range Parsing (handles '10-12 km', 'KM 10 to 12', '10/12', '10.5 – 12.3')
- Bug Fix 4: Resource Name Normalization (lowercase + hyphen/underscore -> space + collapse spaces)
- Bug Fix 5: Endpoint Touching Policy (exact boundary contact treated as NON-overlap)
- Same-Asset Hard Clash Detection (Rule C)
"""
import re
import uuid
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set

from backend.config import is_department_pair_compatible
from backend.models import (
    MaintenanceRequest,
    TrainMovement,
    ConflictDetail,
    ConflictTypeEnum,
)


def normalize_resource_name(res: str) -> str:
    """
    Bug Fix 4: Normalizes resource strings.
    Converts to lowercase, turns hyphens/underscores into spaces, collapses consecutive spaces.
    """
    if not res:
        return ""
    cleaned = re.sub(r"[-_]+", " ", res.strip().lower())
    return " ".join(cleaned.split())


def intervals_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
    """
    Returns True if two datetime intervals strictly overlap.
    Bug Fix 5: Endpoint boundary touching (e.g. end1 == start2) is NON-overlapping (< used).
    """
    return max(start1, start2) < min(end1, end2)


def get_overlap_interval(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> Tuple[datetime, datetime]:
    """Calculates the overlapping datetime range."""
    return max(start1, start2), min(end1, end2)


def km_ranges_overlap(km_s1: float, km_e1: float, km_s2: float, km_e2: float) -> bool:
    """
    Returns True if two kilometer spans strictly overlap.
    Bug Fix 5: Exact boundary touching (e.g. max(s1, s2) == min(e1, e2)) is NON-overlapping.
    """
    s1, e1 = min(km_s1, km_e1), max(km_s1, km_e1)
    s2, e2 = min(km_s2, km_e2), max(km_s2, km_e2)
    return max(s1, s2) < min(e1, e2)


def get_km_overlap(km_s1: float, km_e1: float, km_s2: float, km_e2: float) -> Tuple[float, float]:
    """Calculates the overlapping KM span."""
    s1, e1 = min(km_s1, km_e1), max(km_s1, km_e1)
    s2, e2 = min(km_s2, km_e2), max(km_s2, km_e2)
    return max(s1, s2), min(e1, e2)


def parse_km_range_robust(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Bug Fix 3: Parses KM ranges from diverse formats:
    - '10-12 km', '10 - 12 km', 'KM 10 to 12', 'KM: 10 to 12'
    - '10/12', '10.5 – 12.3', '10.5 - 12.3', '10.5/12.3'
    - 'KM 45.2', 'Chainage 120.0 to 125.5'
    """
    if not text:
        return None, None

    # Replace en-dash, em-dash, slashes with hyphens for clean matching
    clean_txt = text.replace("–", "-").replace("—", "-").strip()

    # Pattern: KM 10 to 12, 10-12 km, 10.5 - 12.3, 10/12
    m1 = re.search(
        r"(?:km|kilometer|chainage|ch)?\s*[:\s]?\s*(\d+(?:\.\d+)?)\s*(?:to|-|\/|and)\s*(?:km)?\s*(\d+(?:\.\d+)?)",
        clean_txt,
        re.IGNORECASE
    )
    if m1:
        try:
            k1 = float(m1.group(1))
            k2 = float(m1.group(2))
            return min(k1, k2), max(k1, k2)
        except (ValueError, TypeError):
            pass

    # Single KM point
    m2 = re.search(r"(?:km|kilometer)\s*[:\s]?\s*(\d+(?:\.\d+)?)", clean_txt, re.IGNORECASE)
    if m2:
        try:
            k = float(m2.group(1))
            return k, round(k + 1.0, 2)
        except (ValueError, TypeError):
            pass

    return None, None


def detect_all_conflicts(
    requests: List[MaintenanceRequest],
    train_movements: Optional[List[TrainMovement]] = None
) -> List[ConflictDetail]:
    """
    Evaluates all maintenance requests and train movements to find genuine conflicts.
    Strictly eliminates false positives across different corridors, dates, and non-overlapping KM spans.
    """
    conflicts: List[ConflictDetail] = []
    if train_movements is None:
        train_movements = []

    n = len(requests)
    for i in range(n):
        r1 = requests[i]

        # -------------------------------------------------------------
        # Pairwise Request Conflicts (i < j)
        # -------------------------------------------------------------
        for j in range(i + 1, n):
            r2 = requests[j]

            same_corridor = r1.corridor.strip().upper() == r2.corridor.strip().upper()
            time_overlap = intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
            km_overlap = km_ranges_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end)

            if same_corridor and time_overlap and km_overlap:
                t_ov_start, t_ov_end = get_overlap_interval(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
                km_ov_start, km_ov_end = get_km_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end)

                # Same-Asset Hard Clash (Rule C)
                norm_work1 = " ".join(r1.work_type.lower().split())
                norm_work2 = " ".join(r2.work_type.lower().split())
                norm_asset1 = " ".join(r1.asset.lower().split())
                norm_asset2 = " ".join(r2.asset.lower().split())

                if norm_work1 == norm_work2 and norm_asset1 == norm_asset2:
                    conflicts.append(ConflictDetail(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                        conflict_type=ConflictTypeEnum.SAME_ASSET_HARD_CLASH,
                        severity="Hard",
                        request_ids=[r1.request_id, r2.request_id],
                        corridor=r1.corridor,
                        time_overlap_start=t_ov_start,
                        time_overlap_end=t_ov_end,
                        km_overlap_start=km_ov_start,
                        km_overlap_end=km_ov_end,
                        explanation=(
                            f"Rule C Hard Clash: Identical work type '{r1.work_type}' on identical asset '{r1.asset}' "
                            f"simultaneously requested on {r1.corridor} between KM {km_ov_start:.1f}-{km_ov_end:.1f}. "
                            f"Cannot bundle duplicate operations on the same physical asset."
                        ),
                        suggested_resolution="Deduplicate work proposals or sequence into separate non-overlapping shifts."
                    ))
                    continue

                # Department Compatibility Check
                compatible = is_department_pair_compatible(r1.department, r2.department)
                both_shareable = r1.block_shared_allowed and r2.block_shared_allowed

                if not both_shareable or not compatible:
                    conflicts.append(ConflictDetail(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                        conflict_type=ConflictTypeEnum.DEPARTMENT_INCOMPATIBILITY if not compatible else ConflictTypeEnum.SPATIAL_TIME_KM,
                        severity="Hard",
                        request_ids=[r1.request_id, r2.request_id],
                        corridor=r1.corridor,
                        time_overlap_start=t_ov_start,
                        time_overlap_end=t_ov_end,
                        km_overlap_start=km_ov_start,
                        km_overlap_end=km_ov_end,
                        explanation=(
                            f"Incompatible work on {r1.corridor}: {r1.department} ({r1.work_type}) and "
                            f"{r2.department} ({r2.work_type}) both request track access between KM {km_ov_start:.1f} and {km_ov_end:.1f} "
                            f"during {t_ov_start.strftime('%H:%M')}-{t_ov_end.strftime('%H:%M IST')}."
                        ),
                        suggested_resolution="Sequence requests into separate non-overlapping time blocks."
                    ))
                else:
                    conflicts.append(ConflictDetail(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                        conflict_type=ConflictTypeEnum.SPATIAL_TIME_KM,
                        severity="ReviewRequired",
                        request_ids=[r1.request_id, r2.request_id],
                        corridor=r1.corridor,
                        time_overlap_start=t_ov_start,
                        time_overlap_end=t_ov_end,
                        km_overlap_start=km_ov_start,
                        km_overlap_end=km_ov_end,
                        explanation=(
                            f"Spatial & temporal overlap on corridor {r1.corridor} between KM {km_ov_start:.1f}-{km_ov_end:.1f} "
                            f"({r1.department}: {r1.work_type} and {r2.department}: {r2.work_type}). "
                            f"Both departments are compatible for bundling into a unified maintenance block."
                        ),
                        suggested_resolution="Bundle both jobs into a single combined corridor block to minimize line closure downtime."
                    ))

            # Resource Double-Booking Check (normalized comparison)
            r1_norm_res = {normalize_resource_name(x): x for x in r1.required_resources if x}
            r2_norm_res = {normalize_resource_name(x): x for x in r2.required_resources if x}
            shared_keys = set(r1_norm_res.keys()).intersection(set(r2_norm_res.keys()))

            if shared_keys and time_overlap:
                t_ov_start, t_ov_end = get_overlap_interval(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
                for k in shared_keys:
                    res_display = r1_norm_res[k]
                    conflicts.append(ConflictDetail(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                        conflict_type=ConflictTypeEnum.RESOURCE_OVERLAP,
                        severity="Hard",
                        request_ids=[r1.request_id, r2.request_id],
                        corridor=f"{r1.corridor} vs {r2.corridor}" if r1.corridor != r2.corridor else r1.corridor,
                        time_overlap_start=t_ov_start,
                        time_overlap_end=t_ov_end,
                        resource_involved=res_display,
                        explanation=(
                            f"Resource contention: Specialized resource '{res_display}' is double-booked by {r1.request_id} ({r1.corridor}) "
                            f"and {r2.request_id} ({r2.corridor}) between {t_ov_start.strftime('%H:%M')} and {t_ov_end.strftime('%H:%M IST')}."
                        ),
                        suggested_resolution=f"Shift {r2.request_id} to start after {r1.request_id} finishes using '{res_display}'."
                    ))

        # -------------------------------------------------------------
        # Maintenance vs Train Movement Conflicts (Hard Safety Constraint)
        # -------------------------------------------------------------
        for train in train_movements:
            same_corr = r1.corridor.strip().upper() == train.corridor.strip().upper()
            t_overlap = intervals_overlap(r1.earliest_start, r1.latest_end, train.departure_time, train.arrival_time)
            k_overlap = km_ranges_overlap(r1.km_start, r1.km_end, train.km_start, train.km_end)

            if same_corr and t_overlap and k_overlap:
                t_s, t_e = get_overlap_interval(r1.earliest_start, r1.latest_end, train.departure_time, train.arrival_time)
                k_s, k_e = get_km_overlap(r1.km_start, r1.km_end, train.km_start, train.km_end)

                conflicts.append(ConflictDetail(
                    conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                    conflict_type=ConflictTypeEnum.TRAIN_MOVEMENT_CONFLICT,
                    severity="Hard",
                    request_ids=[r1.request_id],
                    corridor=r1.corridor,
                    time_overlap_start=t_s,
                    time_overlap_end=t_e,
                    km_overlap_start=k_s,
                    km_overlap_end=k_e,
                    train_id_involved=train.train_id,
                    explanation=(
                        f"CRITICAL SAFETY CONFLICT: Maintenance request {r1.request_id} ({r1.work_type}) overlaps live train movement "
                        f"'{train.train_id}' on corridor {r1.corridor} between KM {k_s:.1f}-{k_e:.1f} from {t_s.strftime('%H:%M')} to {t_e.strftime('%H:%M IST')}."
                    ),
                    suggested_resolution="Shift maintenance window to clear train movement path or schedule during night traffic lull."
                ))

    return conflicts
