"""
Conflict Detection Engine for Railway Maintenance Requests.
Implements the exact conflict detection specification from Section 5:
- Spatial-Time-KM Conflicts (Same corridor + Overlapping time + Overlapping KM)
- Resource Double-Booking Conflicts
- Train Movement Interference Conflicts
- Department Incompatibility Conflicts

Explicitly eliminates false-positive scenarios (Rule 5 & Section 5).
"""
import uuid
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from backend.config import is_department_pair_compatible
from backend.models import (
    MaintenanceRequest,
    TrainMovement,
    ConflictDetail,
    ConflictTypeEnum,
)


def intervals_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
    """Returns True if two datetime intervals strictly overlap."""
    return max(start1, start2) < min(end1, end2)


def get_overlap_interval(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> Tuple[datetime, datetime]:
    """Calculates the overlapping datetime range."""
    return max(start1, start2), min(end1, end2)


def km_ranges_overlap(km_s1: float, km_e1: float, km_s2: float, km_e2: float) -> bool:
    """Returns True if two kilometer spans strictly overlap."""
    return max(min(km_s1, km_e1), min(km_s2, km_e2)) < min(max(km_s1, km_e1), max(km_s2, km_e2))


def get_km_overlap(km_s1: float, km_e1: float, km_s2: float, km_e2: float) -> Tuple[float, float]:
    """Calculates the overlapping KM span."""
    s1, e1 = min(km_s1, km_e1), max(km_s1, km_e1)
    s2, e2 = min(km_s2, km_e2), max(km_s2, km_e2)
    return max(s1, s2), min(e1, e2)


def detect_all_conflicts(
    requests: List[MaintenanceRequest],
    train_movements: Optional[List[TrainMovement]] = None
) -> List[ConflictDetail]:
    """
    Evaluates all maintenance requests and train movements to find genuine conflicts.
    Strictly prevents false positives across different corridors, dates, and non-overlapping KM spans.
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

            # 1. Spatial-Time-KM Conflict (Section 5 rule)
            same_corridor = r1.corridor.strip().upper() == r2.corridor.strip().upper()
            time_overlap = intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
            km_overlap = km_ranges_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end)

            # A spatial conflict exists ONLY when ALL THREE hold:
            if same_corridor and time_overlap and km_overlap:
                t_ov_start, t_ov_end = get_overlap_interval(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
                km_ov_start, km_ov_end = get_km_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end)

                # Check if departments are compatible or if bundling is disallowed
                compatible = is_department_pair_compatible(r1.department.value, r2.department.value)
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
                            f"Incompatible work on {r1.corridor}: {r1.department.value} ({r1.work_type}) and "
                            f"{r2.department.value} ({r2.work_type}) both request track access between KM {km_ov_start:.1f} and {km_ov_end:.1f} "
                            f"during {t_ov_start.strftime('%H:%M')}-{t_ov_end.strftime('%H:%M IST')} but cannot be co-scheduled in the same block."
                        ),
                        suggested_resolution="Sequence requests into separate non-overlapping time blocks or assign to alternate maintenance slots."
                    ))
                else:
                    # Spatial overlap of compatible departments -> Opportunity for Bundling (or Warning if unbundled)
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
                            f"({r1.department.value}: {r1.work_type} and {r2.department.value}: {r2.work_type}). "
                            f"Both departments are compatible for bundling into a unified maintenance block."
                        ),
                        suggested_resolution="Bundle both jobs into a single combined corridor block to minimize line closure downtime."
                    ))

            # 2. Resource Double-Booking Conflict
            # Occurs when same machine/team is required at overlapping times, even across different corridors!
            shared_resources = set(r1.required_resources).intersection(set(r2.required_resources))
            if shared_resources and time_overlap:
                t_ov_start, t_ov_end = get_overlap_interval(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
                for res in shared_resources:
                    conflicts.append(ConflictDetail(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:6].upper()}",
                        conflict_type=ConflictTypeEnum.RESOURCE_OVERLAP,
                        severity="Hard",
                        request_ids=[r1.request_id, r2.request_id],
                        corridor=f"{r1.corridor} vs {r2.corridor}" if r1.corridor != r2.corridor else r1.corridor,
                        time_overlap_start=t_ov_start,
                        time_overlap_end=t_ov_end,
                        resource_involved=res,
                        explanation=(
                            f"Resource contention: Specialized resource '{res}' is double-booked by {r1.request_id} ({r1.corridor}) "
                            f"and {r2.request_id} ({r2.corridor}) between {t_ov_start.strftime('%H:%M')} and {t_ov_end.strftime('%H:%M IST')}."
                        ),
                        suggested_resolution=f"Shift {r2.request_id} to start after {r1.request_id} finishes using '{res}'."
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
                    suggested_resolution="Shift maintenance window to clear the train movement path or schedule in night traffic lull."
                ))

    return conflicts
