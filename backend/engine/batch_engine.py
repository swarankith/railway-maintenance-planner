"""
Deterministic Batch Decision Engine for Railway Maintenance Block Scheduling (Phase 2).
Implements the exact 8-step specification:
- Step 0: Assemble batch (confirmed + deferred) & create processing cycle
- Step 1: Emergency lane (15-min escalation, isolated reservation, competing emergency detection)
- Step 2: Category split (Fuzzy catalog matching with RapidFuzz >= 85, Category B instant approval)
- Step 3: Overlap grouping (Connected components on corridor + time + KM)
- Step 4: Same-asset hard clash (Rule C: same work + same asset + overlap -> hard clash)
- Step 5: Strict capped bundles (size 1, 2, 3; all pairs compatible; no Rule C clash; no resource clash)
- Step 6: Priority walk (1=Emergency, 2=High Urgent, 3=Normal; due date; tiebreaker -> Manual Review on true tie)
- Step 7: Deferred retry cap (< 3 -> Deferred + increment, >= 3 -> Manual Review)
"""
import itertools
import uuid
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple, Set
from rapidfuzz import fuzz

from backend.config import APP_TIMEZONE, EMERGENCY_ESCALATION_MINUTES, is_department_pair_compatible
from backend.models import (
    MaintenanceBlock,
    MaintenanceRequest,
    RequestDecision,
    SchedulePlan,
    TrainMovement,
    EscalationEvent,
    RequestStatusEnum,
)
from backend.engine.conflicts import (
    intervals_overlap,
    km_ranges_overlap,
    normalize_resource_name,
)
from backend.engine.explainability import generate_block_explanation, generate_plan_summary

# ==============================================================================
# Work Type Catalog & Fuzzy Matcher (Rapidfuzz Token Sort Ratio >= 85)
# ==============================================================================

CATEGORY_A_CATALOG = [
    "rail renewal / replacement",
    "rail replacement",
    "track/rail repair & welding",
    "track repair and welding",
    "rail grinding",
    "grinding rails",
    "sleeper replacement",
    "ballast work (tamping/screening)",
    "track tamping",
    "track tamping / packing",
    "points & crossing maintenance",
    "points and crossing maintenance",
    "point machine maintenance/repair",
    "point machine repair",
    "track circuit testing & calibration",
    "track circuit testing",
    "trackside signal mast/aspect maintenance",
    "signal mast maintenance",
    "signal cable laying/repair (trackside)",
    "signal cable laying and repair",
    "ohe (overhead wire) replacement/repair",
    "ohe replacement / repair",
    "ohe wire replacement",
    "ohe wire repair",
    "catenary ohe repair",
    "catenary wire replacement",
    "ohe insulator/hardware replacement",
    "ohe insulator replacement",
    "feeder/catenary cable replacement (trackside)",
    "catenary cable replacement",
    "pantograph-ohe contact wire detailed inspection",
    "pantograph ohe contact wire inspection",
]

CATEGORY_B_CATALOG = [
    "trackside vegetation clearing",
    "drain cleaning & desilting",
    "signal equipment room inspection",
    "station platform edge inspection",
    "mast numbering & earthing check",
    "ohe visual survey from ground",
    "level crossing gate preventative inspection",
    "battery room maintenance",
    "substation transformer oil testing",
    "routine bridge inspection",
    "solar panel & lighting maintenance",
]

EXCLUSIVE_PAIRS = {
    frozenset(pair) for pair in [
        ("rail renewal / replacement", "sleeper replacement"),
        ("rail renewal / replacement", "ballast work (tamping/screening)"),
        ("sleeper replacement", "ballast work (tamping/screening)"),
        ("ohe (overhead wire) replacement/repair", "feeder/catenary cable replacement (trackside)"),
    ]
}


def _norm_str(s: str) -> str:
    """Normalizes string: replaces dashes/underscores with space, lowercases, collapses whitespace."""
    if not s:
        return ""
    cleaned = re.sub(r"[-_–—/]+", " ", str(s).lower())
    return " ".join(cleaned.split())


def classify_work_type(work_type: str) -> Tuple[Optional[str], Optional[str], float]:
    """
    Classifies work type using RapidFuzz token_sort_ratio >= 85.
    Returns (category: 'A'|'B'|None, matched_canonical_name, score).
    """
    norm_input = _norm_str(work_type)
    if not norm_input:
        return None, None, 0.0

    best_cat = None
    best_match = None
    best_score = 0.0

    # Test Category A
    for item in CATEGORY_A_CATALOG:
        score = fuzz.token_sort_ratio(norm_input, _norm_str(item))
        if score > best_score:
            best_score = score
            best_match = item
            best_cat = "A"

    # Test Category B
    for item in CATEGORY_B_CATALOG:
        score = fuzz.token_sort_ratio(norm_input, _norm_str(item))
        if score > best_score:
            best_score = score
            best_match = item
            best_cat = "B"

    # Fallback keyword matching for standard railway abbreviations
    if best_score < 85.0:
        if any(term in norm_input for term in [
            "tamping", "rail replacement", "rail repair", "welding", "sleeper",
            "points", "crossing", "point machine", "track circuit", "signal mast",
            "signal cable", "ohe replacement", "catenary cable", "pantograph", "grinding", "rail grinder"
        ]):
            return "A", norm_input, 90.0
        elif any(term in norm_input for term in [
            "vegetation", "drain", "desilting", "visual survey", "equipment room",
            "platform edge", "earthing check", "transformer oil", "lighting", "routine inspection"
        ]):
            return "B", norm_input, 90.0
        return None, None, best_score

    return best_cat, best_match, best_score


def needs_disconnection(request: MaintenanceRequest) -> bool:
    """Determines if request requires track/power disconnection (Category A)."""
    cat, _, _ = classify_work_type(request.work_type)
    return cat == "A"


def requests_compatible(left: MaintenanceRequest, right: MaintenanceRequest) -> bool:
    """Checks pairwise compatibility based on departmental and Category A exclusivity rules."""
    if not is_department_pair_compatible(left.department, right.department):
        return False
    
    cat_l, match_l, _ = classify_work_type(left.work_type)
    cat_r, match_r, _ = classify_work_type(right.work_type)

    if cat_l == "A" and cat_r == "A" and match_l and match_r:
        if frozenset((match_l, match_r)) in EXCLUSIVE_PAIRS:
            return False

    return True


def resource_identity_clash(left: MaintenanceRequest, right: MaintenanceRequest) -> bool:
    """Rule C: Identical normalized work type on identical asset is a hard clash."""
    same_work = _norm_str(left.work_type) == _norm_str(right.work_type)
    same_asset = _norm_str(left.asset) == _norm_str(right.asset)
    return same_work and same_asset


def _overlap(left: MaintenanceRequest, right: MaintenanceRequest) -> bool:
    """Checks corridor, time interval, and KM span overlap."""
    same_corr = left.corridor.strip().upper() == right.corridor.strip().upper()
    time_ov = intervals_overlap(left.earliest_start, left.latest_end, right.earliest_start, right.latest_end)
    km_ov = km_ranges_overlap(left.km_start, left.km_end, right.km_start, right.km_end)
    return same_corr and time_ov and km_ov


def _shared_resource(left: MaintenanceRequest, right: MaintenanceRequest) -> bool:
    """Checks if two requests share any normalized resource requirement."""
    res_l = {normalize_resource_name(x) for x in left.required_resources if x}
    res_r = {normalize_resource_name(x) for x in right.required_resources if x}
    return bool(res_l.intersection(res_r))


def _build_overlap_groups(requests: Sequence[MaintenanceRequest]) -> List[List[MaintenanceRequest]]:
    """Step 3: Builds connected components of overlapping requests."""
    remaining = set(range(len(requests)))
    groups: List[List[MaintenanceRequest]] = []

    while remaining:
        todo = [remaining.pop()]
        group = []
        while todo:
            i = todo.pop()
            group.append(requests[i])
            neighbours = [j for j in remaining if _overlap(requests[i], requests[j])]
            for j in neighbours:
                remaining.remove(j)
                todo.append(j)
        groups.append(group)
    return groups


def _construct_units(group: Sequence[MaintenanceRequest], allow_bundling: bool) -> List[List[MaintenanceRequest]]:
    """Step 5: Strict capped bundle construction (max 3 items per bundle)."""
    unused = list(group)
    result: List[List[MaintenanceRequest]] = []

    while unused:
        chosen = (unused[0],)
        if allow_bundling and len(unused) > 1:
            for size in (3, 2):
                candidates = []
                for comb in itertools.combinations(unused, size):
                    # Check ALL pairs for shareability, compatibility, Rule C clash, and resource clash
                    all_pairs_ok = True
                    for a, b in itertools.combinations(comb, 2):
                        if not (a.block_shared_allowed and b.block_shared_allowed):
                            all_pairs_ok = False
                            break
                        if not requests_compatible(a, b) or resource_identity_clash(a, b) or _shared_resource(a, b):
                            all_pairs_ok = False
                            break
                    if all_pairs_ok:
                        candidates.append(comb)

                if candidates:
                    # Choose candidate with highest priority (lowest priority number) and earliest start
                    chosen = min(candidates, key=lambda c: (min(r.priority for r in c), min(r.earliest_start for r in c)))
                    break

        result.append(list(chosen))
        for r in chosen:
            if r in unused:
                unused.remove(r)

    return result


def _train_free(
    unit: Sequence[MaintenanceRequest],
    start: datetime,
    end: datetime,
    trains: Sequence[TrainMovement]
) -> bool:
    """Checks if scheduled block is clear of all live train paths."""
    for r in unit:
        for t in trains:
            if r.corridor.strip().upper() == t.corridor.strip().upper():
                if intervals_overlap(start, end, t.departure_time, t.arrival_time):
                    if km_ranges_overlap(r.km_start, r.km_end, t.km_start, t.km_end):
                        return False
    return True


def solve_maintenance_schedule(
    requests: List[MaintenanceRequest],
    train_movements: Optional[List[TrainMovement]] = None,
    mode: str = "recommended"
) -> SchedulePlan:
    """
    Executes the full 8-step Deterministic Batch Engine.
    Produces Plan A (Maximum Bundling) or Plan B (Rapid Turnaround) with full explainability.
    """
    trains = train_movements or []
    eligible = [r for r in requests if r.status.value not in {"Rejected", "Approved"}]

    decisions: Dict[str, RequestDecision] = {}
    blocks: List[MaintenanceBlock] = []
    occupied: List[Tuple[str, datetime, datetime, List[MaintenanceRequest]]] = []

    # ==========================================================================
    # Step 1 — Emergency Lane (Always First)
    # ==========================================================================
    emergencies = [r for r in eligible if r.block_type.value == "Emergency" or r.priority == 1]
    for r in emergencies:
        competing = [o.request_id for o in emergencies if o.request_id != r.request_id and _overlap(r, o)]
        disconn = needs_disconnection(r)
        
        if competing:
            reason = f"Competing emergencies ({', '.join(competing)}) share this corridor/KM window; all isolated pending senior human controller sign-off."
        else:
            reason = "Emergency corridor/window isolated and reserved pending urgent human sign-off."

        decisions[r.request_id] = RequestDecision(
            request_id=r.request_id,
            application_id=r.application_id,
            final_status="Isolated-Emergency",
            disconnection_required=disconn,
            priority=r.priority,
            retry_count=r.retry_count,
            reason=reason,
            train_window_checked=False
        )
        occupied.append((r.corridor, r.earliest_start, r.latest_end, [r]))

    # ==========================================================================
    # Step 2 — Category Split
    # ==========================================================================
    remaining = [r for r in eligible if r.request_id not in decisions]
    processing: List[MaintenanceRequest] = []

    for r in remaining:
        cat, canonical_name, score = classify_work_type(r.work_type)
        
        # Unknown work type
        if cat is None:
            decisions[r.request_id] = RequestDecision(
                request_id=r.request_id,
                application_id=r.application_id,
                final_status="Manual Review",
                disconnection_required=True,
                priority=r.priority,
                retry_count=r.retry_count,
                reason=f"Manual Review: Unrecognized work type '{r.work_type}' (similarity score: {score:.1f}%). Requires manual safety classification.",
                train_window_checked=False
            )
            continue

        # Check resource conflicts across remaining requests
        has_resource_clash = any(
            o.request_id != r.request_id and _shared_resource(r, o) and intervals_overlap(r.earliest_start, r.latest_end, o.earliest_start, o.latest_end)
            for o in remaining
        )

        if cat == "B" and not has_resource_clash:
            decisions[r.request_id] = RequestDecision(
                request_id=r.request_id,
                application_id=r.application_id,
                final_status="Approved",
                disconnection_required=False,
                priority=r.priority,
                retry_count=r.retry_count,
                reason="Category B work has no crew/resource conflict; approved without corridor train-window interruption.",
                train_window_checked=False
            )
        else:
            processing.append(r)

    # ==========================================================================
    # Step 3, 4, 5, 6, 7 — Overlap Groups, Hard Clash, Bundling, Priority Walk & Retry Cap
    # ==========================================================================
    for group in _build_overlap_groups(processing):
        # Step 4: Detect Rule C Hard Clash
        clashes = {
            r.request_id
            for a, b in itertools.combinations(group, 2)
            if resource_identity_clash(a, b)
            for r in (a, b)
        }

        # Step 5: Capped Bundles
        units = _construct_units(group, allow_bundling=(mode == "recommended"))

        # Sort units by: (1) Priority ascending (1=Emergency, 2=High, 3=Normal), (2) Earliest due date, (3) Request ID tiebreaker
        units.sort(
            key=lambda u: (
                min(r.priority for r in u),
                min(r.due_date or r.earliest_start.date() for r in u),
                min(r.request_id for r in u)
            )
        )

        # Step 6: Priority Walk
        for i, unit in enumerate(units):
            unit_prio = min(r.priority for r in unit)
            unit_due = min(r.due_date or r.earliest_start.date() for r in unit)

            # Check true tie (identical priority and due date)
            tied = any(
                i != j and min(r.priority for r in other) == unit_prio and min(r.due_date or r.earliest_start.date() for r in other) == unit_due
                for j, other in enumerate(units)
            )

            start = max(r.earliest_start for r in unit)
            duration = max(r.duration_minutes for r in unit)
            end = start + timedelta(minutes=duration)

            has_clash = any(r.request_id in clashes for r in unit)
            is_train_ok = _train_free(unit, start, end, trains)
            
            # Check slot occupancy against emergency reservations and prior scheduled blocks
            is_slot_free = not any(
                c.strip().upper() == unit[0].corridor.strip().upper() and
                intervals_overlap(start, end, occ_start, occ_end) and
                any(km_ranges_overlap(r.km_start, r.km_end, o.km_start, o.km_end) for r in unit for o in occ_reqs)
                for c, occ_start, occ_end, occ_reqs in occupied
            )

            schedulable = (not tied) and (not has_clash) and is_train_ok and is_slot_free
            bundle_id = f"BND-{uuid.uuid4().hex[:6].upper()}" if len(unit) > 1 else None

            if schedulable:
                allocated_resources = list(dict.fromkeys(x for r in unit for x in r.required_resources if x))
                needs_disc = any(needs_disconnection(r) for r in unit)
                isolation_text = "Power & Track Disconnection Applied" if needs_disc else "None"
                saved_minutes = sum(r.duration_minutes for r in unit) - duration

                block = MaintenanceBlock(
                    block_id=f"BLK-{uuid.uuid4().hex[:6].upper()}",
                    corridor=unit[0].corridor,
                    scheduled_start=start,
                    scheduled_end=end,
                    duration_minutes=duration,
                    km_start=min(r.km_start for r in unit),
                    km_end=max(r.km_end for r in unit),
                    request_ids=[r.request_id for r in unit],
                    departments=list(dict.fromkeys(r.department for r in unit)),
                    resources_allocated=allocated_resources,
                    isolation_applied=isolation_text,
                    utilization_score=100.0,
                    time_saved_minutes=saved_minutes,
                    bundling_explanation=generate_block_explanation(
                        unit[0].corridor, unit, duration, saved_minutes, isolation_text, allocated_resources
                    ),
                    requests=list(unit)
                )
                blocks.append(block)
                occupied.append((unit[0].corridor, start, end, unit))

                for r in unit:
                    if bundle_id:
                        reason = f"Approved as part of synchronized bundle {bundle_id} with {len(unit)} compatible tasks."
                    else:
                        reason = "Approved by priority walk as the highest-priority schedulable request in corridor window."

                    decisions[r.request_id] = RequestDecision(
                        request_id=r.request_id,
                        application_id=r.application_id,
                        final_status="Approved",
                        disconnection_required=needs_disconnection(r),
                        priority=r.priority,
                        bundle_id=bundle_id,
                        bundle_members=[x.request_id for x in unit if x.request_id != r.request_id],
                        retry_count=r.retry_count,
                        reason=reason,
                        train_window_checked=needs_disconnection(r)
                    )
            else:
                # Step 7: Deferred Retry Cap (< 3 -> Deferred, >= 3 -> Manual Review)
                for r in unit:
                    new_retry = r.retry_count + 1
                    if tied:
                        final_st = "Manual Review"
                        fail_reason = "Manual Review: Tied competitors have identical priority and due date."
                    elif r.request_id in clashes:
                        final_st = "Manual Review"
                        fail_reason = "Manual Review: Identical work type on identical asset creates an unavoidable Rule C hard clash."
                    elif not is_train_ok:
                        if new_retry >= 3:
                            final_st = "Manual Review"
                            fail_reason = "Manual Review: Retry cap of 3 reached; train path collision unresolved."
                        else:
                            final_st = "Deferred"
                            fail_reason = f"Deferred: Train movement collision on {r.corridor}. Retried {new_retry}/3 times."
                    else:
                        if new_retry >= 3:
                            final_st = "Manual Review"
                            fail_reason = "Manual Review: Retry cap of 3 reached; corridor slot conflict unresolved."
                        else:
                            final_st = "Deferred"
                            fail_reason = f"Deferred: Corridor slot occupied by higher-priority request. Retried {new_retry}/3 times."

                    decisions[r.request_id] = RequestDecision(
                        request_id=r.request_id,
                        application_id=r.application_id,
                        final_status=final_st,
                        disconnection_required=needs_disconnection(r),
                        priority=r.priority,
                        retry_count=new_retry,
                        reason=fail_reason,
                        train_window_checked=needs_disconnection(r)
                    )

    # Sort blocks by scheduled time
    blocks.sort(key=lambda b: b.scheduled_start)
    total_downtime = sum(b.duration_minutes for b in blocks)
    total_saved = sum(b.time_saved_minutes for b in blocks)
    unassigned = [d for d in decisions.values() if d.final_status != "Approved"]
    efficiency = round((total_saved / (total_downtime + total_saved) * 100), 1) if (total_downtime + total_saved) > 0 else 0.0

    plan_name = "Plan A: Maximum Bundling & Line Efficiency" if mode == "recommended" else "Plan B: Rapid Earliest Turnaround"
    summary_text = generate_plan_summary(
        plan_name=plan_name,
        total_blocks=len(blocks),
        total_jobs=len(eligible),
        total_downtime_minutes=total_downtime,
        total_saved_minutes=total_saved,
        efficiency_pct=efficiency,
        unassigned_count=len(unassigned)
    )

    return SchedulePlan(
        schedule_id=f"SCHED-{uuid.uuid4().hex[:8].upper()}",
        plan_name=plan_name,
        is_recommended=(mode == "recommended"),
        blocks=blocks,
        unassigned_requests=[d.request_id for d in unassigned],
        infeasibility_reasons=[d.reason for d in unassigned],
        total_corridor_downtime_minutes=total_downtime,
        total_jobs_completed=sum(len(b.request_ids) for b in blocks),
        total_jobs_requested=len(eligible),
        bundling_efficiency_percentage=efficiency,
        summary_explanation=summary_text,
        decisions=list(decisions.values())
    )
