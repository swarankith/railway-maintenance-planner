"""
Deterministic Batch Decision Engine for Railway Maintenance Block Scheduling (Phase 2 Final v6).
Implements the exact 8-step specification:
- Step 0: Assemble batch preserving retry_count, duplicate detection, cycle creation.
- Step 1: Emergency lane (block_type == Emergency only, buffered reservation [isolated_at - 15m, latest_end + 15m], competing emergency detection).
- Step 2: Category split (RapidFuzz >= 85 catalog matching; unknown -> Manual Review; Cat B fast path with 3 checks).
- Step 3: Overlap grouping (Connected components on corridor + buffered time + min 0.1 KM).
- Step 4: Same-asset hard clash (Rule C: exact match on normalized work_type & asset -> exclude from bundling).
- Step 5: Strict capped bundling (size 1-3, all pairs compatible, quality score formula, bundle audit trail on deferral).
- Step 6: Priority walk (score = (4-prio)*100 + max(0, 7-due)*10, order: emergency -> train -> resource -> deps, greedy best fit 15m).
- Step 7: Deferred retry cap (< 3 -> Deferred + increment, >= 3 -> Manual Review).
"""
import itertools
import math
import uuid
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple, Set
from rapidfuzz import fuzz

from backend.config import (
    APP_TIMEZONE,
    EMERGENCY_ESCALATION_MINUTES,
    CATEGORY_A_CATALOG,
    CATEGORY_B_CATALOG,
    INCOMPATIBLE_CAT_A_PAIRS,
    is_department_pair_compatible,
)
from backend.models import (
    MaintenanceBlock,
    MaintenanceRequest,
    RequestDecision,
    SchedulePlan,
    TrainMovement,
    EscalationEvent,
    ConflictDetail,
    ConflictTypeEnum,
)
from backend.engine.conflicts import (
    buffered_intervals_overlap,
    raw_intervals_overlap,
    km_ranges_overlap,
    get_overlap_interval,
    get_km_overlap,
    normalize_resource_name,
    normalize_string_exact,
    is_duplicate_request,
    TIME_BUFFER,
    MIN_KM_OVERLAP,
)
from backend.engine.explainability import generate_block_explanation, generate_plan_summary
from backend.engine.optimizer import needs_disconnection, resource_identity_clash


def classify_work_type(work_type: str) -> Tuple[Optional[str], Optional[str], float]:
    """
    Classifies work type using RapidFuzz token_sort_ratio >= 85 against A.1 catalogs.
    Returns (category: 'A'|'B'|None, matched_canonical_name, score).
    """
    if not work_type:
        return None, None, 0.0

    norm_input = normalize_string_exact(work_type)
    if not norm_input:
        return None, None, 0.0

    best_cat = None
    best_match = None
    best_score = 0.0

    for item in CATEGORY_A_CATALOG:
        score = fuzz.token_sort_ratio(norm_input, normalize_string_exact(item))
        if score > best_score:
            best_score = score
            best_match = item
            best_cat = "A"

    for item in CATEGORY_B_CATALOG:
        score = fuzz.token_sort_ratio(norm_input, normalize_string_exact(item))
        if score > best_score:
            best_score = score
            best_match = item
            best_cat = "B"

    if best_score >= 85.0:
        return best_cat, best_match, best_score

    # Check common synonyms/abbreviations in Indian Railways parlance
    if any(k in norm_input for k in ["rail renewal", "rail replacement", "tamping", "welding", "sleeper", "ohe", "catenary", "point machine", "grinding", "grind"]):
        return "A", norm_input, 86.0
    if any(k in norm_input for k in ["vegetation", "cess", "relay room", "gate", "patrolling", "routine inspection", "drain", "desilt", "cleaning"]):
        return "B", norm_input, 86.0

    return None, None, best_score


def needs_disconnection(request: MaintenanceRequest) -> Optional[bool]:
    """Determines if request requires track/power disconnection (Category A). Unknown -> None."""
    cat, _, _ = classify_work_type(request.work_type)
    if cat == "A":
        return True
    elif cat == "B":
        return False
    return None


def are_work_types_compatible_cat_a(w1: str, w2: str) -> bool:
    """Checks the 4 incompatible Category A pairs (Part A.2)."""
    _, m1, _ = classify_work_type(w1)
    _, m2, _ = classify_work_type(w2)
    nm1 = normalize_string_exact(m1 or w1)
    nm2 = normalize_string_exact(m2 or w2)

    for p1, p2 in INCOMPATIBLE_CAT_A_PAIRS:
        np1 = normalize_string_exact(p1)
        np2 = normalize_string_exact(p2)
        if (nm1 == np1 and nm2 == np2) or (nm1 == np2 and nm2 == np1):
            return False
    return True


def requests_pairwise_compatible(r1: MaintenanceRequest, r2: MaintenanceRequest) -> bool:
    """
    Checks compatibility per Part A.2:
    - Cat B + anything -> combinable (subject to resource conflicts).
    - Cat A + Cat A -> combinable EXCEPT 4 pairs.
    - Departments must be compatible.
    """
    if not is_department_pair_compatible(r1.department, r2.department):
        return False

    cat1, _, _ = classify_work_type(r1.work_type)
    cat2, _, _ = classify_work_type(r2.work_type)

    if cat1 == "A" and cat2 == "A":
        if not are_work_types_compatible_cat_a(r1.work_type, r2.work_type):
            return False

    return True


def is_rule_c_clash(r1: MaintenanceRequest, r2: MaintenanceRequest) -> bool:
    """
    Rule C: same normalized work_type AND same normalized asset
    (lowercase, strip whitespace/punctuation, EXACT match) AND overlapping corridor+time+KM.
    """
    if r1.corridor.strip().upper() != r2.corridor.strip().upper():
        return False
    if not buffered_intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end):
        return False
    if not km_ranges_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end):
        return False

    w1 = normalize_string_exact(r1.work_type)
    w2 = normalize_string_exact(r2.work_type)
    a1 = normalize_string_exact(r1.asset)
    a2 = normalize_string_exact(r2.asset)
    return (w1 == w2) and (a1 == a2)


def has_resource_conflict(r1: MaintenanceRequest, r2: MaintenanceRequest) -> bool:
    """Checks resource overlap using normalized resource names."""
    res1 = {normalize_resource_name(x) for x in r1.required_resources if x}
    res2 = {normalize_resource_name(x) for x in r2.required_resources if x}
    if not res1.intersection(res2):
        return False
    return buffered_intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)


def build_connected_overlap_groups(requests: Sequence[MaintenanceRequest]) -> List[List[MaintenanceRequest]]:
    """Step 3: Connected components on corridor + overlapping (buffered) time + overlapping (>=0.1km) KM."""
    remaining = set(range(len(requests)))
    groups: List[List[MaintenanceRequest]] = []

    def overlaps(a: MaintenanceRequest, b: MaintenanceRequest) -> bool:
        if a.corridor.strip().upper() != b.corridor.strip().upper():
            return False
        if not buffered_intervals_overlap(a.earliest_start, a.latest_end, b.earliest_start, b.latest_end):
            return False
        return km_ranges_overlap(a.km_start, a.km_end, b.km_start, b.km_end)

    while remaining:
        root = remaining.pop()
        group = [requests[root]]
        todo = [requests[root]]
        while todo:
            curr = todo.pop()
            neighbors = [j for j in remaining if overlaps(curr, requests[j])]
            for j in neighbors:
                remaining.remove(j)
                group.append(requests[j])
                todo.append(requests[j])
        groups.append(group)
    return groups


def calculate_bundle_quality(bundle: Sequence[MaintenanceRequest]) -> float:
    """
    quality = (members*10) + (priority_weight/members if members>0 else 0) - (km_span*0.5) - (time_span_minutes/60)
    where priority_weight = sum of (4 - priority) across members.
    """
    members = len(bundle)
    if members == 0:
        return 0.0
    priority_weight = sum((4 - r.priority) for r in bundle)
    min_km = min(r.km_start for r in bundle)
    max_km = max(r.km_end for r in bundle)
    km_span = max(0.0, max_km - min_km)
    
    # Common or spanned time
    start = max(r.earliest_start for r in bundle)
    end = min(r.latest_end for r in bundle)
    if start >= end:
        # Feasible common window does not exist
        return -9999.0
    time_span_minutes = max(r.duration_minutes for r in bundle)

    quality = (members * 10.0) + (priority_weight / members) - (km_span * 0.5) - (time_span_minutes / 60.0)
    return quality


def construct_strict_capped_bundles(group: Sequence[MaintenanceRequest], allow_bundling: bool) -> List[List[MaintenanceRequest]]:
    """
    Step 5: Strict capped bundling (size 1 to 3).
    Candidates of size 1-3; valid only if:
    - all pairs compatible
    - no Rule C clash
    - no resource conflict
    - common feasible interval exists
    Highest quality wins.
    """
    unused = list(group)
    bundles: List[List[MaintenanceRequest]] = []

    while unused:
        best_candidate: Tuple[MaintenanceRequest, ...] = (unused[0],)
        best_quality = calculate_bundle_quality(best_candidate)

        if allow_bundling and len(unused) > 1:
            for size in (3, 2):
                for comb in itertools.combinations(unused, size):
                    # Validate all pairs
                    valid = True
                    for a, b in itertools.combinations(comb, 2):
                        if not (a.block_shared_allowed and b.block_shared_allowed):
                            valid = False
                            break
                        if not requests_pairwise_compatible(a, b):
                            valid = False
                            break
                        if is_rule_c_clash(a, b):
                            valid = False
                            break
                        if has_resource_conflict(a, b):
                            valid = False
                            break

                    if not valid:
                        continue

                    # Common feasible window check
                    common_start = max(r.earliest_start for r in comb)
                    common_end = min(r.latest_end for r in comb)
                    needed_dur = max(r.duration_minutes for r in comb)
                    if (common_end - common_start).total_seconds() / 60.0 < needed_dur:
                        continue

                    q = calculate_bundle_quality(comb)
                    if q > best_quality:
                        best_quality = q
                        best_candidate = comb

        bundles.append(list(best_candidate))
        for r in best_candidate:
            if r in unused:
                unused.remove(r)

    return bundles


def find_greedy_best_fit_gap(
    bundle: Sequence[MaintenanceRequest],
    corridor: str,
    duration_min: int,
    earliest_start: datetime,
    latest_end: datetime,
    reserved_slots: List[Dict],
    trains: List[TrainMovement]
) -> Optional[datetime]:
    """
    Sliding start in 15-min increments from earliest_start up to latest_end - duration.
    Greedy best-fit: smallest free gap fitting [earliest_start, latest_end - duration].
    Tie-break: equal-length gaps -> earliest start time wins.
    """
    step = timedelta(minutes=15)
    dur = timedelta(minutes=duration_min)
    max_start = latest_end - dur
    if earliest_start > max_start:
        return None

    min_km = min(r.km_start for r in bundle)
    max_km = max(r.km_end for r in bundle)
    needs_disc = any(needs_disconnection(r) for r in bundle)

    current = earliest_start
    best_start: Optional[datetime] = None

    while current <= max_start:
        c_end = current + dur

        # Check conflict with reserved slots (including emergency reservations)
        has_slot_conflict = False
        for slot in reserved_slots:
            if slot["corridor"].strip().upper() != corridor.strip().upper():
                continue
            # Slot buffer check
            slot_s = slot["buffer_start"]
            slot_e = slot["buffer_end"]
            if raw_intervals_overlap(current, c_end, slot_s, slot_e):
                if km_ranges_overlap(min_km, max_km, slot["km_start"], slot["km_end"]):
                    has_slot_conflict = True
                    break

        if not has_slot_conflict:
            # If Category A, check train movements
            has_train_conflict = False
            if needs_disc:
                for train in trains:
                    if train.corridor.strip().upper() != corridor.strip().upper():
                        continue
                    if buffered_intervals_overlap(current, c_end, train.departure_time, train.arrival_time):
                        if km_ranges_overlap(min_km, max_km, train.km_start, train.km_end):
                            has_train_conflict = True
                            break

            if not has_train_conflict:
                best_start = current
                break  # Earliest start wins tie-break

        current += step

    return best_start


def solve_maintenance_schedule(
    requests: List[MaintenanceRequest],
    train_movements: Optional[List[TrainMovement]] = None,
    mode: str = "recommended",
    cycle_id: Optional[str] = None
) -> SchedulePlan:
    """
    Executes the authoritative 8-step Deterministic Batch Engine (Phase 2 Final v6).
    """
    trains = train_movements or []
    cycle = cycle_id or f"CYC-{uuid.uuid4().hex[:8].upper()}"

    # Step 0: Assemble batch & deduplicate
    # Flagged unconfirmed duplicates never enter Step 1+
    eligible_raw = [r for r in requests if r.status.value not in {"Rejected", "Approved"}]
    eligible: List[MaintenanceRequest] = []
    unconfirmed_duplicates: Set[str] = set()

    for i, r1 in enumerate(eligible_raw):
        is_dup = False
        for j, r2 in enumerate(eligible_raw):
            if i != j and is_duplicate_request(r1, r2):
                # Unconfirmed duplicate
                if r1.status.value != "Confirmed":
                    is_dup = True
                    unconfirmed_duplicates.add(r1.request_id)
                    break
        if not is_dup:
            eligible.append(r1)

    decisions: Dict[str, RequestDecision] = {}
    blocks: List[MaintenanceBlock] = []
    # Reserved slots: list of dicts with corridor, buffer_start, buffer_end, true_start, true_end, km_start, km_end, is_emergency, emergency_ids
    reserved_slots: List[Dict] = []

    # Record unconfirmed duplicates as Needs-Review / Manual Review
    for dup_id in unconfirmed_duplicates:
        r = next(x for x in eligible_raw if x.request_id == dup_id)
        decisions[r.request_id] = RequestDecision(
            request_id=r.request_id,
            application_id=r.application_id,
            final_status="Manual Review",
            disconnection_required=needs_disconnection(r),
            priority=r.priority,
            retry_count=r.retry_count,
            reason="Flagged duplicate proposal (token similarity >= 90%). Requires human confirmation before batch inclusion.",
            train_window_checked=False
        )

    # ==========================================================================
    # Step 1 — Emergency Lane (block_type == Emergency, always first)
    # ==========================================================================
    # Note: priority == 1 with block_type != Emergency is NOT isolated here!
    emergencies = [r for r in eligible if r.block_type.value == "Emergency"]
    now_ist = datetime.now(APP_TIMEZONE)

    for em in emergencies:
        # Check competing emergencies: 2+ overlapping emergencies
        competing = [
            o.request_id for o in emergencies
            if o.request_id != em.request_id and
            o.corridor.strip().upper() == em.corridor.strip().upper() and
            buffered_intervals_overlap(em.earliest_start, em.latest_end, o.earliest_start, o.latest_end) and
            km_ranges_overlap(em.km_start, em.km_end, o.km_start, o.km_end)
        ]

        disconn = needs_disconnection(em)
        if competing:
            reason = f"Competing emergencies ({', '.join(competing)}) share this corridor/KM window; all isolated pending human sign-off."
        else:
            reason = "Emergency lane: Corridor/window isolated and reserved pending human sign-off."

        decisions[em.request_id] = RequestDecision(
            request_id=em.request_id,
            application_id=em.application_id,
            final_status="Isolated-Emergency",
            disconnection_required=disconn,
            priority=em.priority,
            retry_count=em.retry_count,
            reason=reason,
            train_window_checked=False
        )

        # Buffered reservation to BLOCK non-emergencies: [isolated_at - 15min, latest_end + 15min]
        res_start = (em.earliest_start if em.earliest_start < now_ist else now_ist) - TIME_BUFFER
        res_end = em.latest_end + TIME_BUFFER
        reserved_slots.append({
            "corridor": em.corridor,
            "buffer_start": res_start,
            "buffer_end": res_end,
            "true_start": em.earliest_start,
            "true_end": em.latest_end,
            "km_start": min(em.km_start, em.km_end),
            "km_end": max(em.km_start, em.km_end),
            "is_emergency": True,
            "emergency_ids": [em.request_id] + competing,
            "requests": [em]
        })

    # ==========================================================================
    # Step 2 — Category Split (with emergency-aware fast path)
    # ==========================================================================
    non_emergencies = [r for r in eligible if r.request_id not in decisions]
    step3_candidates: List[MaintenanceRequest] = []
    fast_path_approved_cat_b: List[MaintenanceRequest] = []

    for r in non_emergencies:
        cat, canonical_match, score = classify_work_type(r.work_type)

        # Unknown work type -> Manual Review, disconnection_required = None
        if cat is None:
            decisions[r.request_id] = RequestDecision(
                request_id=r.request_id,
                application_id=r.application_id,
                final_status="Manual Review",
                disconnection_required=None,
                priority=r.priority,
                retry_count=r.retry_count,
                reason=f"Manual Review: Unknown work type '{r.work_type}' (similarity score: {score:.1f}%). Requires manual safety classification.",
                train_window_checked=False
            )
            continue

        if cat == "B":
            # Condition (a): no resource conflict
            res_clash = any(
                has_resource_conflict(r, o)
                for o in non_emergencies if o.request_id != r.request_id
            )

            # Condition (b): no overlap (buffered) with any emergency reservation from Step 1
            em_clash = False
            for slot in reserved_slots:
                if slot.get("is_emergency") and slot["corridor"].strip().upper() == r.corridor.strip().upper():
                    if raw_intervals_overlap(r.earliest_start, r.latest_end, slot["buffer_start"], slot["buffer_end"]):
                        if km_ranges_overlap(r.km_start, r.km_end, slot["km_start"], slot["km_end"]):
                            em_clash = True
                            break

            # Condition (c): no overlap with any other Category B request already fast-path-approved in this batch
            b_overlap = any(
                o.corridor.strip().upper() == r.corridor.strip().upper() and
                buffered_intervals_overlap(r.earliest_start, r.latest_end, o.earliest_start, o.latest_end) and
                km_ranges_overlap(r.km_start, r.km_end, o.km_start, o.km_end)
                for o in fast_path_approved_cat_b
            )

            if (not res_clash) and (not em_clash) and (not b_overlap):
                fast_path_approved_cat_b.append(r)
                decisions[r.request_id] = RequestDecision(
                    request_id=r.request_id,
                    application_id=r.application_id,
                    final_status="Approved",
                    disconnection_required=False,
                    priority=r.priority,
                    retry_count=r.retry_count,
                    reason="Category B fast path approved (no resource clash, no emergency overlap, no conflicting Cat B).",
                    train_window_checked=False
                )
            else:
                # Any condition fails -> route to Step 3
                step3_candidates.append(r)
        else:
            # Category A -> Step 3
            step3_candidates.append(r)

    # ==========================================================================
    # Step 3, 4, 5, 6, 7 — Connected Overlap Groups, Rule C, Bundling, Walk & Retry
    # ==========================================================================
    for group in build_connected_overlap_groups(step3_candidates):
        # Step 4: Same-asset hard clash (Rule C) within each group
        rule_c_clashed_ids = set()
        for a, b in itertools.combinations(group, 2):
            if is_rule_c_clash(a, b):
                rule_c_clashed_ids.add(a.request_id)
                rule_c_clashed_ids.add(b.request_id)

        # Exclude hard-clashed requests from bundling
        bundling_pool = [r for r in group if r.request_id not in rule_c_clashed_ids]
        clashed_requests = [r for r in group if r.request_id in rule_c_clashed_ids]

        # Step 5: Strict capped bundles (size 1-3)
        bundles = construct_strict_capped_bundles(bundling_pool, allow_bundling=(mode == "recommended"))
        # Add single units for clashed requests so they enter Step 6 independently
        for cr in clashed_requests:
            bundles.append([cr])

        # Step 6: Priority Walk
        # score = (4 - priority)*100 + max(0, 7 - days_until_due)*10
        def get_unit_score(u: List[MaintenanceRequest]) -> Tuple[float, int, datetime, str]:
            prio = min(r.priority for r in u)
            # days until due
            days_until_due = 7
            for r in u:
                if r.due_date:
                    delta = (r.due_date - r.earliest_start.date()).days
                    days_until_due = min(days_until_due, delta)
            due_bonus = max(0, 7 - days_until_due) * 10
            score = (4 - prio) * 100 + due_bonus
            # Earliest start, corridor name ascending for tie breaker
            earliest_dt = min(r.earliest_start for r in u)
            return (score, -prio, -earliest_dt.timestamp(), u[0].corridor)

        # Sort descending by score
        bundles.sort(key=get_unit_score, reverse=True)

        for unit in bundles:
            unit_ids = [r.request_id for r in unit]
            is_bundled = len(unit) > 1
            bundle_id = f"BND-{uuid.uuid4().hex[:6].upper()}" if is_bundled else None
            corridor = unit[0].corridor

            # True tie check: same priority AND same due date AND actual overlap
            is_true_tie = False
            for other_unit in bundles:
                if other_unit != unit:
                    same_prio = min(r.priority for r in unit) == min(r.priority for r in other_unit)
                    same_due = min(r.due_date or r.earliest_start.date() for r in unit) == min(r.due_date or r.earliest_start.date() for r in other_unit)
                    actual_ov = any(
                        r1.corridor.strip().upper() == r2.corridor.strip().upper() and
                        buffered_intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end) and
                        km_ranges_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end)
                        for r1 in unit for r2 in other_unit
                    )
                    if same_prio and same_due and actual_ov:
                        is_true_tie = True
                        break

            # Rule C hard clash check
            has_rule_c = any(r.request_id in rule_c_clashed_ids for r in unit)

            # Check (a): Emergency reservations from Step 1
            overlapping_emergencies = set()
            for r in unit:
                for slot in reserved_slots:
                    if slot.get("is_emergency") and slot["corridor"].strip().upper() == r.corridor.strip().upper():
                        if raw_intervals_overlap(r.earliest_start, r.latest_end, slot["buffer_start"], slot["buffer_end"]):
                            if km_ranges_overlap(r.km_start, r.km_end, slot["km_start"], slot["km_end"]):
                                overlapping_emergencies.update(slot.get("emergency_ids", []))

            # Duration and start/end calculation
            duration = max(r.duration_minutes for r in unit)
            common_start = max(r.earliest_start for r in unit)
            common_end = min(r.latest_end for r in unit)

            scheduled_start = None
            train_conflict_names = []

            if not is_true_tie and not has_rule_c and not overlapping_emergencies:
                scheduled_start = find_greedy_best_fit_gap(
                    bundle=unit,
                    corridor=corridor,
                    duration_min=duration,
                    earliest_start=common_start,
                    latest_end=common_end,
                    reserved_slots=reserved_slots,
                    trains=trains
                )

            if scheduled_start is not None:
                # Successfully scheduled & Approved!
                scheduled_end = scheduled_start + timedelta(minutes=duration)
                min_km = min(r.km_start for r in unit)
                max_km = max(r.km_end for r in unit)
                needs_disc = any(needs_disconnection(r) for r in unit)
                saved_minutes = sum(r.duration_minutes for r in unit) - duration
                allocated_resources = list(dict.fromkeys(x for r in unit for x in r.required_resources if x))
                isolation_text = "Power & Track Disconnection Applied" if needs_disc else "None"

                block = MaintenanceBlock(
                    block_id=f"BLK-{uuid.uuid4().hex[:6].upper()}",
                    corridor=corridor,
                    scheduled_start=scheduled_start,
                    scheduled_end=scheduled_end,
                    duration_minutes=duration,
                    km_start=min_km,
                    km_end=max_km,
                    request_ids=unit_ids,
                    departments=list(dict.fromkeys(r.department for r in unit)),
                    resources_allocated=allocated_resources,
                    isolation_applied=isolation_text,
                    utilization_score=100.0,
                    time_saved_minutes=saved_minutes,
                    bundling_explanation=generate_block_explanation(
                        corridor, unit, duration, saved_minutes, isolation_text, allocated_resources
                    ),
                    requests=list(unit)
                )
                blocks.append(block)

                # Add to reserved slots
                reserved_slots.append({
                    "corridor": corridor,
                    "buffer_start": scheduled_start - TIME_BUFFER,
                    "buffer_end": scheduled_end + TIME_BUFFER,
                    "true_start": scheduled_start,
                    "true_end": scheduled_end,
                    "km_start": min_km,
                    "km_end": max_km,
                    "is_emergency": False,
                    "requests": list(unit)
                })

                for r in unit:
                    if is_bundled:
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
                        bundle_members=[x for x in unit_ids if x != r.request_id],
                        retry_count=r.retry_count,
                        reason=reason,
                        train_window_checked=needs_disconnection(r) or False
                    )
            else:
                # Deferral / Failure -> Step 7: Retry Cap
                for r in unit:
                    new_retry = r.retry_count + 1
                    if is_true_tie:
                        final_st = "Manual Review"
                        fail_reason = "Manual Review: Tied competitors have identical priority and due date."
                    elif has_rule_c:
                        final_st = "Manual Review"
                        fail_reason = "Manual Review: Same-asset hard clash (Rule C) on identical asset and work type."
                    elif overlapping_emergencies:
                        em_list_str = ", ".join(sorted(overlapping_emergencies))
                        if new_retry >= 3:
                            final_st = "Manual Review"
                            fail_reason = f"Manual Review: Retry cap of 3 reached; corridor slot conflict with emergency ({em_list_str}) unresolved."
                        else:
                            final_st = "Deferred"
                            fail_reason = f"Deferred: Overlaps active emergency reservation ({em_list_str}). Retried {new_retry}/3 times."
                    else:
                        if new_retry >= 3:
                            final_st = "Manual Review"
                            fail_reason = "Manual Review: Retry cap of 3 reached; corridor slot or train path conflict unresolved."
                        else:
                            final_st = "Deferred"
                            fail_reason = f"Deferred: Corridor slot occupied or train path conflict. Retried {new_retry}/3 times."

                    # Bundle audit trail: preserve bundle_id on each member even when deferred!
                    decisions[r.request_id] = RequestDecision(
                        request_id=r.request_id,
                        application_id=r.application_id,
                        final_status=final_st,
                        disconnection_required=needs_disconnection(r),
                        priority=r.priority,
                        bundle_id=bundle_id,
                        bundle_members=[x for x in unit_ids if x != r.request_id],
                        retry_count=new_retry,
                        reason=fail_reason,
                        train_window_checked=needs_disconnection(r) or False
                    )

    # Sort blocks by scheduled time
    blocks.sort(key=lambda b: b.scheduled_start)
    
    # Counters K.10
    total_requested = len(eligible)
    approved_count = sum(1 for d in decisions.values() if d.final_status == "Approved")
    isolated_emergency_count = sum(1 for d in decisions.values() if d.final_status == "Isolated-Emergency")
    deferred_count = sum(1 for d in decisions.values() if d.final_status == "Deferred")
    manual_review_count = sum(1 for d in decisions.values() if d.final_status == "Manual Review")
    
    total_completed = approved_count + isolated_emergency_count
    total_downtime = sum(b.duration_minutes for b in blocks)
    total_saved = sum(b.time_saved_minutes for b in blocks)
    efficiency = round((total_saved / (total_downtime + total_saved) * 100), 1) if (total_downtime + total_saved) > 0 else 0.0

    # Summary string per K.10
    summary_text = (
        f"{total_completed} of {total_requested} requests handled: "
        f"{approved_count} approved, {isolated_emergency_count} isolated-emergency, "
        f"{deferred_count} deferred, {manual_review_count} manual review."
    )

    unassigned_ids = [d.request_id for d in decisions.values() if d.final_status != "Approved"]
    infeasibility_reasons = [d.reason for d in decisions.values() if d.final_status != "Approved"]

    plan_name = "Plan A: Maximum Bundling & Line Efficiency" if mode == "recommended" else "Plan B: Rapid Earliest Turnaround"

    return SchedulePlan(
        schedule_id=f"SCHED-{uuid.uuid4().hex[:8].upper()}",
        cycle_id=cycle,
        plan_name=plan_name,
        is_recommended=(mode == "recommended"),
        blocks=blocks,
        unassigned_requests=unassigned_ids,
        infeasibility_reasons=infeasibility_reasons,
        total_corridor_downtime_minutes=total_downtime,
        total_jobs_completed=total_completed,
        total_jobs_requested=total_requested,
        bundling_efficiency_percentage=efficiency,
        summary_explanation=summary_text,
        decisions=list(decisions.values())
    )
