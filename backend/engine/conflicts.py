"""
Conflict Detection Engine for Railway Maintenance Requests (Part A.3).
- Structured objects: ID, cycle ID, involved IDs, type (SpatialTimeKM, Resource, TrainMovement, Compatibility, SameAssetClash, CompetingEmergency)
- Time buffer: [start - 15min, end + 15min]
- Min KM overlap: min(kme1, kme2) - max(kms1, kms2) >= 0.1
- Resource normalization: lowercase, '-', '_', space equivalent
- Duplicate detection: rapidfuzz token_sort_ratio >= 90
- Rule C: exact match on normalized work_type and normalized asset (lowercase, strip whitespace/punctuation)

Fix (v7): Removed the department-whitelist gate from the compatibility check.
Compatibility now aligns with batch_engine.requests_pairwise_compatible:
Category B + anything -> compatible; Category A + Category A -> compatible
unless the pair is one of the 4 explicit INCOMPATIBLE_CAT_A_PAIRS.
"""
import re
import string
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from rapidfuzz import fuzz

from backend.config import INCOMPATIBLE_CAT_A_PAIRS
from backend.models import (
    MaintenanceRequest,
    TrainMovement,
    ConflictDetail,
    ConflictTypeEnum,
)

TIME_BUFFER = timedelta(minutes=15)
MIN_KM_OVERLAP = 0.1


def normalize_resource_name(res: str) -> str:
    """Normalizes resource strings: lowercase, -/_ to space, collapsed spaces."""
    if not res:
        return ""
    cleaned = re.sub(r"[-_]+", " ", res.strip().lower())
    return " ".join(cleaned.split())


def normalize_string_exact(val: str) -> str:
    """Lowercase, strip whitespace and punctuation for exact matching."""
    if not val:
        return ""
    val = "".join(c for c in val if c not in string.punctuation)
    return " ".join(val.lower().split())


def buffered_intervals_overlap(
    start1: datetime, end1: datetime,
    start2: datetime, end2: datetime,
    buffer: timedelta = TIME_BUFFER
) -> bool:
    """Applies [start - 15min, end + 15min] buffer to intervals."""
    b_s1, b_e1 = start1 - buffer, end1 + buffer
    b_s2, b_e2 = start2 - buffer, end2 + buffer
    return max(b_s1, b_s2) < min(b_e1, b_e2)


def raw_intervals_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
    """Strict interval overlap without buffer."""
    return max(start1, start2) < min(end1, end2)


intervals_overlap = buffered_intervals_overlap


def get_overlap_interval(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> Tuple[datetime, datetime]:
    return max(start1, start2), min(end1, end2)


def km_ranges_overlap(km_s1: float, km_e1: float, km_s2: float, km_e2: float) -> bool:
    """Conflict only if min(kme1, kme2) - max(kms1, kms2) >= 0.1."""
    s1, e1 = min(km_s1, km_e1), max(km_s1, km_e1)
    s2, e2 = min(km_s2, km_e2), max(km_s2, km_e2)
    overlap = min(e1, e2) - max(s1, s2)
    return overlap >= MIN_KM_OVERLAP - 1e-9


def get_km_overlap(km_s1: float, km_e1: float, km_s2: float, km_e2: float) -> Tuple[float, float]:
    s1, e1 = min(km_s1, km_e1), max(km_s1, km_e1)
    s2, e2 = min(km_s2, km_e2), max(km_s2, km_e2)
    return max(s1, s2), min(e1, e2)


def parse_km_range_robust(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parses KM ranges from diverse formats:
    - '10-12 km', '10 - 12 km', 'KM 10 to 12', 'KM: 10 to 12'
    - '10/12', '10.5 – 12.3', '10.5 - 12.3', '10.5/12.3'
    - 'KM 45.2', 'Chainage 120.0 to 125.5'
    """
    if not text:
        return None, None

    clean_txt = text.replace("–", "-").replace("—", "-").strip()

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

    m2 = re.search(r"(?:km|kilometer)\s*[:\s]?\s*(\d+(?:\.\d+)?)", clean_txt, re.IGNORECASE)
    if m2:
        try:
            k = float(m2.group(1))
            return k, round(k + 1.0, 2)
        except (ValueError, TypeError):
            pass

    return None, None


def is_duplicate_request(r1: MaintenanceRequest, r2: MaintenanceRequest) -> bool:
    """
    Duplicate detection: rapidfuzz.token_sort_ratio >= 90 on:
    corridor + department + work_type + km_range + start_time
    """
    s1 = (
        f"{r1.corridor} {r1.department} {r1.work_type} "
        f"{min(r1.km_start, r1.km_end):.1f}-{max(r1.km_start, r1.km_end):.1f} "
        f"{r1.earliest_start.strftime('%Y-%m-%d %H:%M')}"
    )
    s2 = (
        f"{r2.corridor} {r2.department} {r2.work_type} "
        f"{min(r2.km_start, r2.km_end):.1f}-{max(r2.km_start, r2.km_end):.1f} "
        f"{r2.earliest_start.strftime('%Y-%m-%d %H:%M')}"
    )
    ratio = fuzz.token_sort_ratio(s1, s2)
    return ratio >= 90


def _is_incompatible_cat_a_pair(work1: str, work2: str) -> bool:
    """Checks whether two work types form one of the 4 prohibited Category A pairs."""
    n1 = normalize_string_exact(work1)
    n2 = normalize_string_exact(work2)
    for p0, p1 in INCOMPATIBLE_CAT_A_PAIRS:
        np0 = normalize_string_exact(p0)
        np1 = normalize_string_exact(p1)
        if (n1 == np0 and n2 == np1) or (n1 == np1 and n2 == np0):
            return True
    return False


def detect_all_conflicts(
    requests: List[MaintenanceRequest],
    train_movements: Optional[List[TrainMovement]] = None,
    cycle_id: Optional[str] = None
) -> List[ConflictDetail]:
    """
    Evaluates all maintenance requests and train movements for conflicts using A.3 rules:
    - Time buffer: [start - 15min, end + 15min]
    - Min KM overlap: min(kme1, kme2) - max(kms1, kms2) >= 0.1
    """
    conflicts: List[ConflictDetail] = []
    if train_movements is None:
        train_movements = []

    n = len(requests)
    for i in range(n):
        r1 = requests[i]

        for j in range(i + 1, n):
            r2 = requests[j]

            same_corridor = r1.corridor.strip().upper() == r2.corridor.strip().upper()
            time_overlap = buffered_intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
            km_overlap = km_ranges_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end)

            if same_corridor and time_overlap and km_overlap:
                t_ov_start, t_ov_end = get_overlap_interval(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
                km_ov_start, km_ov_end = get_km_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end)

                # Rule C: same normalized work_type AND same normalized asset (exact match)
                norm_work1 = normalize_string_exact(r1.work_type)
                norm_work2 = normalize_string_exact(r2.work_type)
                norm_asset1 = normalize_string_exact(r1.asset)
                norm_asset2 = normalize_string_exact(r2.asset)

                if norm_work1 == norm_work2 and norm_asset1 == norm_asset2:
                    conflicts.append(ConflictDetail(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                        cycle_id=cycle_id,
                        conflict_type=ConflictTypeEnum.SAME_ASSET_CLASH,
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

                # Incompatible Category A pair check (Part A.2)
                # FIX (v7): department whitelist removed. Only the 4 exception pairs matter.
                is_incompatible_cat_a = _is_incompatible_cat_a_pair(r1.work_type, r2.work_type)
                both_shareable = r1.block_shared_allowed and r2.block_shared_allowed

                if not both_shareable or is_incompatible_cat_a:
                    conflicts.append(ConflictDetail(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                        cycle_id=cycle_id,
                        conflict_type=ConflictTypeEnum.COMPATIBILITY if is_incompatible_cat_a else ConflictTypeEnum.SPATIAL_TIME_KM,
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
                        cycle_id=cycle_id,
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
                            f"Both requests are compatible for bundling into a unified maintenance block."
                        ),
                        suggested_resolution="Bundle both jobs into a single combined corridor block to minimize line closure downtime."
                    ))

            # Resource Double-Booking Check (normalized comparison with 15min buffer)
            r1_norm_res = {normalize_resource_name(x): x for x in r1.required_resources if x}
            r2_norm_res = {normalize_resource_name(x): x for x in r2.required_resources if x}
            shared_keys = set(r1_norm_res.keys()).intersection(set(r2_norm_res.keys()))

            if shared_keys and time_overlap:
                t_ov_start, t_ov_end = get_overlap_interval(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
                for k in shared_keys:
                    res_display = r1_norm_res[k]
                    conflicts.append(ConflictDetail(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                        cycle_id=cycle_id,
                        conflict_type=ConflictTypeEnum.RESOURCE,
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

        # Train Movement Conflicts
        for train in train_movements:
            same_corr = r1.corridor.strip().upper() == train.corridor.strip().upper()
            t_overlap = buffered_intervals_overlap(r1.earliest_start, r1.latest_end, train.departure_time, train.arrival_time)
            k_overlap = km_ranges_overlap(r1.km_start, r1.km_end, train.km_start, train.km_end)

            if same_corr and t_overlap and k_overlap:
                t_s, t_e = get_overlap_interval(r1.earliest_start, r1.latest_end, train.departure_time, train.arrival_time)
                k_s, k_e = get_km_overlap(r1.km_start, r1.km_end, train.km_start, train.km_end)

                conflicts.append(ConflictDetail(
                    conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                    cycle_id=cycle_id,
                    conflict_type=ConflictTypeEnum.TRAIN_MOVEMENT,
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