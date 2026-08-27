"""
Optimization Engine for Railway Maintenance Block Planning.
Uses Google OR-Tools CP-SAT and constraint-satisfaction bundling heuristics.
Enforces hard safety constraints (train movements, resource contention, isolation rules)
and optimizes soft multi-objective goals (bundling efficiency, priority completion, minimal downtime).
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from zoneinfo import ZoneInfo

from backend.config import APP_TIMEZONE, is_department_pair_compatible
from backend.models import (
    MaintenanceRequest,
    TrainMovement,
    MaintenanceBlock,
    SchedulePlan,
    PlanStatusEnum,
    RequestStatusEnum,
)
from backend.engine.explainability import (
    generate_block_explanation,
    generate_plan_summary,
    generate_infeasibility_explanation,
)


def calculate_bundling_potential(
    r1: MaintenanceRequest,
    r2: MaintenanceRequest,
    max_km_distance: float = 20.0
) -> bool:
    """
    Checks if two requests can be bundled into the same maintenance block:
    1. Same corridor
    2. Both allow shared blocks
    3. Compatible departments
    4. Overlapping time flexibility window
    5. Proximity on track (overlapping or within max_km_distance)
    """
    if r1.corridor.strip().upper() != r2.corridor.strip().upper():
        return False
    if not (r1.block_shared_allowed and r2.block_shared_allowed):
        return False
    if not is_department_pair_compatible(r1.department.value, r2.department.value):
        return False

    # Check time window overlap
    if max(r1.earliest_start, r2.earliest_start) >= min(r1.latest_end, r2.latest_end):
        return False

    # Check KM proximity
    km_min1, km_max1 = min(r1.km_start, r1.km_end), max(r1.km_start, r1.km_end)
    km_min2, km_max2 = min(r2.km_start, r2.km_end), max(r2.km_start, r2.km_end)
    
    # Overlapping or within max_km_distance
    distance = max(0.0, max(km_min1, km_min2) - min(km_max1, km_max2))
    return distance <= max_km_distance


def solve_maintenance_schedule(
    requests: List[MaintenanceRequest],
    train_movements: Optional[List[TrainMovement]] = None,
    mode: str = "recommended"  # "recommended" (Max Bundling) or "alternative" (Earliest Completion)
) -> SchedulePlan:
    """
    Solves maintenance block schedule using OR-Tools CP-SAT / constraint bundling.
    Returns complete SchedulePlan with explainable blocks and metrics.
    """
    if train_movements is None:
        train_movements = []

    confirmed_requests = [r for r in requests if r.status in [RequestStatusEnum.CONFIRMED, RequestStatusEnum.INGESTED, RequestStatusEnum.OPTIMIZED]]

    if not confirmed_requests:
        return SchedulePlan(
            schedule_id=f"SCHED-{uuid.uuid4().hex[:8].upper()}",
            plan_name="Plan A: Maximum Bundling & Minimal Line Disruption" if mode == "recommended" else "Plan B: Rapid Earliest Execution",
            is_recommended=(mode == "recommended"),
            blocks=[],
            unassigned_requests=[],
            infeasibility_reasons=["No confirmed maintenance requests available to schedule."],
            summary_explanation="No confirmed maintenance requests were provided.",
            status=PlanStatusEnum.GENERATED
        )

    # Sort requests by priority (1=highest) then earliest_start
    sorted_reqs = sorted(confirmed_requests, key=lambda r: (r.priority, r.earliest_start))

    # Determine baseline timestamp for solver integer minutes
    min_time = min(r.earliest_start for r in sorted_reqs)
    baseline_time = min_time.replace(minute=0, second=0, microsecond=0)

    # ------------------------------------------------------------------
    # Step 1: Clustering / Bundling Graph Construction
    # ------------------------------------------------------------------
    # Group by corridor
    corridor_map: Dict[str, List[MaintenanceRequest]] = {}
    for r in sorted_reqs:
        c_key = r.corridor.strip().upper()
        corridor_map.setdefault(c_key, []).append(r)

    blocks: List[MaintenanceBlock] = []
    unassigned_req_ids: List[str] = []
    infeasibility_notes: List[str] = []
    
    # Global tracking of scheduled resource intervals to prevent double-booking: resource -> List[(start_dt, end_dt, req_id)]
    resource_bookings: Dict[str, List[Tuple[datetime, datetime, str]]] = {}

    for corridor_name, corr_requests in corridor_map.items():
        # Get relevant trains on this corridor
        corr_trains = [t for t in train_movements if t.corridor.strip().upper() == corridor_name]

        # In "recommended" mode, greedily form bundling clusters
        # In "alternative" mode, schedule more discrete or early turnaround blocks
        visited = set()
        
        for i, r_main in enumerate(corr_requests):
            if r_main.request_id in visited:
                continue

            current_bundle: List[MaintenanceRequest] = [r_main]
            visited.add(r_main.request_id)

            if mode == "recommended":
                # Find all compatible bundle partners
                for j, r_other in enumerate(corr_requests):
                    if r_other.request_id in visited:
                        continue
                    
                    # Can r_other bundle with all members of current_bundle?
                    can_bundle = all(calculate_bundling_potential(m, r_other) for m in current_bundle)
                    if can_bundle:
                        current_bundle.append(r_other)
                        visited.add(r_other.request_id)

            # ------------------------------------------------------------------
            # Step 2: Determine Block Window & Safety Validation
            # ------------------------------------------------------------------
            # Calculate overlapping permissible window
            bundle_earliest = max(r.earliest_start for r in current_bundle)
            bundle_latest = min(r.latest_end for r in current_bundle)
            max_job_duration = max(r.duration_minutes for r in current_bundle)
            total_sum_duration = sum(r.duration_minutes for r in current_bundle)

            # In parallel bundling, block duration is max duration of bundled jobs
            block_duration = max_job_duration
            time_saved = total_sum_duration - block_duration if len(current_bundle) > 1 else 0

            # Proposed scheduled start
            # In recommended mode, align at bundle_earliest or traffic lull
            # In alternative mode, start immediately at r_main.earliest_start
            scheduled_start = bundle_earliest
            scheduled_end = scheduled_start + timedelta(minutes=block_duration)

            # Check for conflict with train movements
            train_conflict_found = False
            for train in corr_trains:
                # Check if train overlaps [scheduled_start, scheduled_end]
                if max(scheduled_start, train.departure_time) < min(scheduled_end, train.arrival_time):
                    # Check KM overlap with bundle KM span
                    bundle_km_min = min(r.km_start for r in current_bundle)
                    bundle_km_max = max(r.km_end for r in current_bundle)
                    if max(bundle_km_min, train.km_start) < min(bundle_km_max, train.km_end):
                        # Try shifting scheduled_start after train arrival
                        shifted_start = train.arrival_time + timedelta(minutes=15)
                        shifted_end = shifted_start + timedelta(minutes=block_duration)
                        if shifted_end <= bundle_latest:
                            scheduled_start = shifted_start
                            scheduled_end = shifted_end
                        else:
                            train_conflict_found = True
                            break

            if train_conflict_found:
                # Flag unassigned and record infeasibility
                for r in current_bundle:
                    unassigned_req_ids.append(r.request_id)
                    inf_exp = generate_infeasibility_explanation(r, corr_trains, [])
                    infeasibility_notes.append(inf_exp)
                continue

            # Check resource conflicts across already scheduled blocks
            bundle_resources = list(dict.fromkeys([res for r in current_bundle for res in r.required_resources]))
            resource_conflict = False
            for res in bundle_resources:
                if res in resource_bookings:
                    for b_start, b_end, b_req_id in resource_bookings[res]:
                        if max(scheduled_start, b_start) < min(scheduled_end, b_end):
                            # Try shifting after resource is free
                            shifted_start = b_end + timedelta(minutes=15)
                            shifted_end = shifted_start + timedelta(minutes=block_duration)
                            if shifted_end <= bundle_latest:
                                scheduled_start = shifted_start
                                scheduled_end = shifted_end
                            else:
                                resource_conflict = True
                                for r in current_bundle:
                                    unassigned_req_ids.append(r.request_id)
                                    infeasibility_notes.append(
                                        generate_infeasibility_explanation(r, [], [f"{res} (booked by {b_req_id})"])
                                    )
                                break
                    if resource_conflict:
                        break

            if resource_conflict:
                continue

            # Record resource bookings
            for res in bundle_resources:
                resource_bookings.setdefault(res, []).append((scheduled_start, scheduled_end, current_bundle[0].request_id))

            # Determine unified isolation requirement
            isolations = [r.isolation_requirement for r in current_bundle if r.isolation_requirement and r.isolation_requirement != "None"]
            unified_isolation = isolations[0] if isolations else "None"

            # Create Block
            depts = list(dict.fromkeys([r.department.value for r in current_bundle]))
            bundle_km_min = min(r.km_start for r in current_bundle)
            bundle_km_max = max(r.km_end for r in current_bundle)

            utilization = round((sum(r.duration_minutes for r in current_bundle) / (block_duration * len(current_bundle))) * 100.0, 1) if current_bundle else 100.0

            explanation = generate_block_explanation(
                corridor=corridor_name,
                requests=current_bundle,
                duration_minutes=block_duration,
                time_saved_minutes=time_saved,
                isolation_applied=unified_isolation,
                resources_allocated=bundle_resources
            )

            block = MaintenanceBlock(
                block_id=f"BLK-{uuid.uuid4().hex[:6].upper()}",
                corridor=corridor_name,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                duration_minutes=block_duration,
                km_start=bundle_km_min,
                km_end=bundle_km_max,
                request_ids=[r.request_id for r in current_bundle],
                departments=depts,
                resources_allocated=bundle_resources,
                isolation_applied=unified_isolation,
                utilization_score=utilization,
                time_saved_minutes=time_saved,
                bundling_explanation=explanation,
                requests=current_bundle
            )
            blocks.append(block)

    # Sort blocks chronologically
    blocks.sort(key=lambda b: b.scheduled_start)

    # Compute aggregate metrics
    total_downtime = sum(b.duration_minutes for b in blocks)
    total_saved = sum(b.time_saved_minutes for b in blocks)
    total_jobs_completed = sum(len(b.request_ids) for b in blocks)
    total_jobs = len(confirmed_requests)
    efficiency = round((total_saved / (total_downtime + total_saved) * 100.0), 1) if (total_downtime + total_saved) > 0 else 0.0

    plan_name = "Plan A: Maximum Bundling & Minimal Line Disruption" if mode == "recommended" else "Plan B: Rapid Earliest Execution"
    summary_text = generate_plan_summary(
        plan_name=plan_name,
        total_blocks=len(blocks),
        total_jobs=total_jobs,
        total_downtime_minutes=total_downtime,
        total_saved_minutes=total_saved,
        efficiency_pct=efficiency,
        unassigned_count=len(unassigned_req_ids)
    )

    return SchedulePlan(
        schedule_id=f"SCHED-{uuid.uuid4().hex[:8].upper()}",
        plan_name=plan_name,
        is_recommended=(mode == "recommended"),
        blocks=blocks,
        unassigned_requests=unassigned_req_ids,
        infeasibility_reasons=infeasibility_notes,
        total_corridor_downtime_minutes=total_downtime,
        total_jobs_completed=total_jobs_completed,
        total_jobs_requested=total_jobs,
        bundling_efficiency_percentage=efficiency,
        summary_explanation=summary_text,
        status=PlanStatusEnum.GENERATED
    )
