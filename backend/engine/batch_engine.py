"""
Deterministic Batch Decision Engine for Railway Maintenance Block Scheduling (Phase 2 Final v7).

Fixes applied (v7):
1. Removed the import of `needs_disconnection` and `resource_identity_clash` from optimizer.py.
   Local, correct versions are used instead.
2. `requests_pairwise_compatible` no longer uses the department whitelist gate.
   It matches the compatibility verdict used by `conflicts.py`:
   Category B + anything -> compatible; Category A + Category A -> compatible EXCEPT the 4 pairs.
3. True-tie rule now requires that two overlapping units CANNOT be bundled
   (i.e., they fail every compatibility check). Physical overlap + same priority + same due
   date is NOT enough to declare a tie.
4. Emergency reservation window is now based on the emergency request's own
   [earliest_start - 15min, latest_end + 15min] instead of stretching from "now".
   This stops emergencies from over-reserving large swaths of corridor time.
5. Category B fast path now also checks overlap with emergency reservations before
   approving. If it overlaps an active emergency reservation, it is routed to Step 3.
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


# ==========================================================================
# Category classification (Step 2)
# ==========================================================================

def classify_work_type(work_type: str) -> Tuple[Optional[str], Optional[str], float]:
    """
    Classifies work type using RapidFuzz token_sort_ratio >= 85 against catalogs.
    Returns (category: 'A' | 'B' | None, matched_canonical_name, score).
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

    # Common Indian Railways synonym fallback
    if any(k in norm_input for k in [
        "rail renewal", "rail replacement", "tamping", "welding", "sleeper",
        "ohe", "catenary", "point machine", "grinding", "grind",
    ]):
        return "A", norm_input, 86.0
    if any(k in norm_input for k in [
        "vegetation", "cess", "relay room", "gate", "patrolling",
        "routine inspection", "drain", "desilt", "cleaning",
    ]):
        return "B", norm_input, 86.0

    return None, None, best_score


def needs_disconnection(request: MaintenanceRequest) -> Optional[bool]:
    """
    Returns True if the request requires track/power disconnection (Category A),
    False if it does not (Category B), None if the work type is unknown.
    """
    cat, _, _ = classify_work_type(request.work_type)
    if cat == "A":
        return True
    if cat == "B":
        return False
    return None


# ==========================================================================
# Compatibility (Part A.2)
# ==========================================================================

def are_work_types_compatible_cat_a(w1: str, w2: str) -> bool:
    """Checks whether two Category A work types are compatible (i.e., not in the 4 exception pairs)."""
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


def requests_pairwise_compatible(
    r1: MaintenanceRequest,
    r2: MaintenanceRequest,
) -> bool:
    """
    Part A.2 compatibility check, aligned with conflicts.py:
    - Category B + anything -> compatible (resource conflicts still apply, checked elsewhere).
    - Category A + Category A -> compatible UNLESS the pair is one of the 4 exceptions.
    - Departments are NOT gated by a whitelist here; the only department-level blocker
      is the work-type exception rule above, matching the conflict-analysis verdict.
    """
    cat1, _, _ = classify_work_type(r1.work_type)
    cat2, _, _ = classify_work_type(r2.work_type)

    # Unknown category on either side -> cannot be safely bundled automatically.
    if cat1 is None or cat2 is None:
        return False

    if cat1 == "A" and cat2 == "A":
        if not are_work_types_compatible_cat_a(r1.work_type, r2.work_type):
            return False

    return True


# ==========================================================================
# Rule C — same-asset hard clash (Step 4)
# ==========================================================================

def is_rule_c_clash(r1: MaintenanceRequest, r2: MaintenanceRequest) -> bool:
    """
    Rule C: same normalized work_type AND same normalized asset
    (exact match after lowercasing + stripping punctuation) AND
    overlapping corridor + buffered time + overlapping KM.
    """
    if not r1.work_type or not r2.work_type or not r1.asset or not r2.asset:
        return False

    w1 = normalize_string_exact(r1.work_type)
    w2 = normalize_string_exact(r2.work_type)
    a1 = normalize_string_exact(r1.asset)
    a2 = normalize_string_exact(r2.asset)

    if not w1 or not w2 or not a1 or not a2:
        return False

    if r1.corridor.strip().upper() != r2.corridor.strip().upper():
        return False
    if not buffered_intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end):
        return False
    if not km_ranges_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end):
        return False

    return w1 == w2 and a1 == a2


def has_resource_conflict(r1: MaintenanceRequest, r2: MaintenanceRequest) -> bool:
    """Checks overlapping buffered times AND shared normalized resource names."""
    res1 = {normalize_resource_name(x) for x in r1.required_resources if x}
    res2 = {normalize_resource_name(x) for x in r2.required_resources if x}
    if not res1.intersection(res2):
        return False
    return buffered_intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)


# ==========================================================================
# Step 3 — Connected overlap groups
# ==========================================================================

def build_connected_overlap_groups(
    requests: Sequence[MaintenanceRequest],
) -> List[List[MaintenanceRequest]]:
    """Connected components on same corridor + overlapping buffered time + overlapping KM (>= 0.1)."""
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


# ==========================================================================
# Step 5 — Strict capped bundling (quality-score winner)
# ==========================================================================

def calculate_bundle_quality(bundle: Sequence[MaintenanceRequest]) -> float:
    """
    quality = members*10 + priority_weight/members - km_span*0.5 - time_span_minutes/60
    """
    members = len(bundle)
    if members == 0:
        return 0.0
    priority_weight = sum((4 - r.priority) for r in bundle)
    min_km = min(r.km_start for r in bundle)
    max_km = max(r.km_end for r in bundle)
    km_span = max(0.0, max_km - min_km)

    start = max(r.earliest_start for r in bundle)
    end = min(r.latest_end for r in bundle)
    if start >= end:
        return -9999.0

    time_span_minutes = max(r.duration_minutes for r in bundle)
    return (members * 10.0) + (priority_weight / members) - (km_span * 0.5) - (time_span_minutes / 60.0)


def construct_strict_capped_bundles(
    group: Sequence[MaintenanceRequest],
    allow_bundling: bool,
) -> List[List[MaintenanceRequest]]:
    """
    Build candidate bundles of size 1 to 3.
    Valid bundle requires: all pairs compatible, no Rule C clash, no resource conflict,
    common feasible window of at least the max member duration.
    Highest quality-score bundle wins.
    """
    unused = list(group)
    bundles: List[List[MaintenanceRequest]] = []

    while unused:
        best_candidate: Tuple[MaintenanceRequest, ...] = (unused[0],)
        best_quality = calculate_bundle_quality(best_candidate)

        if allow_bundling and len(unused) > 1:
            for size in (3, 2):
                for comb in itertools.combinations(unused, size):
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


# ==========================================================================
# Step 6 — Greedy best-fit slot finder
# ==========================================================================

def find_greedy_best_fit_gap(
    bundle: Sequence[MaintenanceRequest],
    corridor: str,
    duration_min: int,
    earliest_start: datetime,
    latest_end: datetime,
    reserved_slots: List[Dict],
    trains: List[TrainMovement],
) -> Optional[datetime]:
    """
    Slide start time in 15-min increments from earliest_start to latest_end - duration.
    Return the first (earliest) slot that has no corridor/KM overlap with a reserved slot
    and no train conflict (for Category A work).
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
    while current <= max_start:
        c_end = current + dur

        has_slot_conflict = False
        for slot in reserved_slots:
            if slot["corridor"].strip().upper() != corridor.strip().upper():
                continue
            if raw_intervals_overlap(current, c_end, slot["buffer_start"], slot["buffer_end"]):
                if km_ranges_overlap(min_km, max_km, slot["km_start"], slot["km_end"]):
                    has_slot_conflict = True
                    break

        if not has_slot_conflict:
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
                return current

        current += step

    return None


# ==========================================================================
# Main deterministic batch engine
# ==========================================================================

def solve_maintenance_schedule(
    requests: List[MaintenanceRequest],
    train_movements: Optional[List[TrainMovement]] = None,
    mode: str = "recommended",
    cycle_id: Optional[str] = None,
) -> SchedulePlan:
    """
    Executes the deterministic 8-step batch engine (Phase 2 Final v7).
    """
    trains = train_movements or []
    cycle = cycle_id or f"CYC-{uuid.uuid4().hex[:8].upper()}"

    # ----------------------------------------------------------------------
    # Step 0 — Assemble batch + deduplicate
    # ----------------------------------------------------------------------
    eligible_raw = [r for r in requests if r.status.value not in {"Rejected", "Approved"}]
    eligible: List[MaintenanceRequest] = []
    unconfirmed_duplicates: Set[str] = set()

    for i, r1 in enumerate(eligible_raw):
        is_dup = False
        for j, r2 in enumerate(eligible_raw):
            if i != j and is_duplicate_request(r1, r2):
                if r1.status.value != "Confirmed":
                    is_dup = True
                    unconfirmed_duplicates.add(r1.request_id)
                    break
        if not is_dup:
            eligible.append(r1)

    decisions: Dict[str, RequestDecision] = {}
    blocks: List[MaintenanceBlock] = []
    reserved_slots: List[Dict] = []

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
            train_window_checked=False,
        )

    # ----------------------------------------------------------------------
    # Step 1 — Emergency lane (block_type == Emergency only)
    # ----------------------------------------------------------------------
    emergencies = [r for r in eligible if r.block_type.value == "Emergency"]
    now_ist = datetime.now(APP_TIMEZONE)

    for em in emergencies:
        competing = [
            o.request_id for o in emergencies
            if o.request_id != em.request_id
            and o.corridor.strip().upper() == em.corridor.strip().upper()
            and buffered_intervals_overlap(em.earliest_start, em.latest_end, o.earliest_start, o.latest_end)
            and km_ranges_overlap(em.km_start, em.km_end, o.km_start, o.km_end)
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
            train_window_checked=False,
        )

        em_start = em.earliest_start
        em_end = em.earliest_start + timedelta(minutes=em.duration_minutes)
        em_block = MaintenanceBlock(
            block_id=f"EMG-BLK-{uuid.uuid4().hex[:6].upper()}",
            corridor=em.corridor,
            scheduled_start=em_start,
            scheduled_end=em_end,
            duration_minutes=em.duration_minutes,
            km_start=min(em.km_start, em.km_end),
            km_end=max(em.km_start, em.km_end),
            request_ids=[em.request_id],
            departments=[em.department],
            resources_allocated=list(dict.fromkeys(x for x in em.required_resources if x)),
            isolation_applied="Emergency Track & Power Isolation",
            utilization_score=100.0,
            time_saved_minutes=0,
            bundling_explanation=f"EMERGENCY ISOLATION: {reason}",
            requests=[em],
        )
        blocks.append(em_block)

        # FIX (v7): buffered reservation based on the emergency's own window, NOT "now".
        res_start = em.earliest_start - TIME_BUFFER
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
            "requests": [em],
        })

    # ----------------------------------------------------------------------
    # Step 2 — Category split (emergency-aware fast path)
    # ----------------------------------------------------------------------
    non_emergencies = [r for r in eligible if r.request_id not in decisions]
    step3_candidates: List[MaintenanceRequest] = []

    def overlaps_active_emergency(r: MaintenanceRequest) -> List[str]:
        """Return IDs of emergency reservations this request overlaps (buffered)."""
        hit_ids: List[str] = []
        for slot in reserved_slots:
            if not slot.get("is_emergency"):
                continue
            if slot["corridor"].strip().upper() != r.corridor.strip().upper():
                continue
            if raw_intervals_overlap(r.earliest_start, r.latest_end, slot["buffer_start"], slot["buffer_end"]):
                if km_ranges_overlap(r.km_start, r.km_end, slot["km_start"], slot["km_end"]):
                    hit_ids.extend(slot.get("emergency_ids", []))
        return list(dict.fromkeys(hit_ids))

    for r in non_emergencies:
        cat, canonical_match, score = classify_work_type(r.work_type)

        if cat is None:
            decisions[r.request_id] = RequestDecision(
                request_id=r.request_id,
                application_id=r.application_id,
                final_status="Manual Review",
                disconnection_required=True,
                priority=r.priority,
                retry_count=r.retry_count,
                reason=f"Manual Review: Unrecognised work type '{r.work_type}' (similarity score: {score:.1f}%). Safety classification required.",
                train_window_checked=False,
            )
            continue

        if cat == "B":
            res_clash = any(
                has_resource_conflict(r, o)
                for o in non_emergencies if o.request_id != r.request_id
            )
            em_overlap = overlaps_active_emergency(r)

            # FIX (v7): Category B fast path also blocks if it overlaps an emergency reservation.
            if not res_clash and not em_overlap:
                b_start = r.earliest_start
                b_end = r.earliest_start + timedelta(minutes=r.duration_minutes)
                block_b = MaintenanceBlock(
                    block_id=f"BLK-{uuid.uuid4().hex[:6].upper()}",
                    corridor=r.corridor,
                    scheduled_start=b_start,
                    scheduled_end=b_end,
                    duration_minutes=r.duration_minutes,
                    km_start=min(r.km_start, r.km_end),
                    km_end=max(r.km_start, r.km_end),
                    request_ids=[r.request_id],
                    departments=[r.department],
                    resources_allocated=list(dict.fromkeys(x for x in r.required_resources if x)),
                    isolation_applied="None (Category B Fast Path)",
                    utilization_score=100.0,
                    time_saved_minutes=0,
                    bundling_explanation="Category B off-track routine work approved on fast path.",
                    requests=[r],
                )
                blocks.append(block_b)
                reserved_slots.append({
                    "corridor": r.corridor,
                    "buffer_start": b_start - TIME_BUFFER,
                    "buffer_end": b_end + TIME_BUFFER,
                    "true_start": b_start,
                    "true_end": b_end,
                    "km_start": min(r.km_start, r.km_end),
                    "km_end": max(r.km_start, r.km_end),
                    "is_emergency": False,
                    "requests": [r],
                })

                decisions[r.request_id] = RequestDecision(
                    request_id=r.request_id,
                    application_id=r.application_id,
                    final_status="Approved",
                    disconnection_required=False,
                    priority=r.priority,
                    retry_count=r.retry_count,
                    reason="Category B fast path approved: no resource clash and no emergency overlap. Disconnection not required.",
                    train_window_checked=False,
                )
            else:
                step3_candidates.append(r)
        else:
            step3_candidates.append(r)

    # ----------------------------------------------------------------------
    # Steps 3–7 for Category A and conflicted Category B
    # ----------------------------------------------------------------------
    for group in build_connected_overlap_groups(step3_candidates):
        rule_c_clashed_ids = set()
        for a, b in itertools.combinations(group, 2):
            if is_rule_c_clash(a, b):
                rule_c_clashed_ids.add(a.request_id)
                rule_c_clashed_ids.add(b.request_id)

        bundling_pool = [r for r in group if r.request_id not in rule_c_clashed_ids]
        clashed_requests = [r for r in group if r.request_id in rule_c_clashed_ids]

        bundles = construct_strict_capped_bundles(
            bundling_pool, allow_bundling=(mode == "recommended")
        )
        for cr in clashed_requests:
            bundles.append([cr])

        def get_unit_score(u: List[MaintenanceRequest]) -> Tuple[float, int, float, str]:
            prio = min(r.priority for r in u)
            days_until_due = 7
            for r in u:
                if r.due_date:
                    delta = (r.due_date - r.earliest_start.date()).days
                    days_until_due = min(days_until_due, delta)
            due_bonus = max(0, 7 - days_until_due) * 10
            score = (4 - prio) * 100 + due_bonus
            earliest_dt = min(r.earliest_start for r in u)
            return (score, -prio, -earliest_dt.timestamp(), u[0].corridor)

        bundles.sort(key=get_unit_score, reverse=True)

        for unit in bundles:
            unit_ids = [r.request_id for r in unit]
            is_bundled = len(unit) > 1
            bundle_id = f"BND-{uuid.uuid4().hex[:6].upper()}" if is_bundled else None
            corridor = unit[0].corridor

            # FIX (v7): true tie now requires that the units CANNOT be bundled.
            is_true_tie = False
            for other_unit in bundles:
                if other_unit == unit:
                    continue
                same_prio = min(r.priority for r in unit) == min(r.priority for r in other_unit)
                same_due = (
                    min(r.due_date or r.earliest_start.date() for r in unit)
                    == min(r.due_date or r.earliest_start.date() for r in other_unit)
                )
                physical_ov = any(
                    r1.corridor.strip().upper() == r2.corridor.strip().upper()
                    and raw_intervals_overlap(r1.earliest_start, r1.latest_end, r2.earliest_start, r2.latest_end)
                    and km_ranges_overlap(r1.km_start, r1.km_end, r2.km_start, r2.km_end)
                    for r1 in unit for r2 in other_unit
                )
                if same_prio and same_due and physical_ov:
                    can_merge = all(
                        requests_pairwise_compatible(r1, r2)
                        and not is_rule_c_clash(r1, r2)
                        and not has_resource_conflict(r1, r2)
                        for r1 in unit for r2 in other_unit
                    )
                    if not can_merge:
                        is_true_tie = True
                        break

            has_rule_c = any(r.request_id in rule_c_clashed_ids for r in unit)

            overlapping_emergencies: Set[str] = set()
            for r in unit:
                overlapping_emergencies.update(overlaps_active_emergency(r))

            duration = max(r.duration_minutes for r in unit)
            common_start = max(r.earliest_start for r in unit)
            common_end = min(r.latest_end for r in unit)

            scheduled_start = None
            if not is_true_tie and not has_rule_c and not overlapping_emergencies:
                scheduled_start = find_greedy_best_fit_gap(
                    bundle=unit,
                    corridor=corridor,
                    duration_min=duration,
                    earliest_start=common_start,
                    latest_end=common_end,
                    reserved_slots=reserved_slots,
                    trains=trains,
                )

            if scheduled_start is not None:
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
                    requests=list(unit),
                )
                blocks.append(block)

                reserved_slots.append({
                    "corridor": corridor,
                    "buffer_start": scheduled_start - TIME_BUFFER,
                    "buffer_end": scheduled_end + TIME_BUFFER,
                    "true_start": scheduled_start,
                    "true_end": scheduled_end,
                    "km_start": min_km,
                    "km_end": max_km,
                    "is_emergency": False,
                    "requests": list(unit),
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
                        train_window_checked=bool(needs_disconnection(r)),
                    )
            else:
                for r in unit:
                    new_retry = r.retry_count + 1
                    if is_true_tie:
                        final_st = "Manual Review"
                        fail_reason = "Manual Review: Tied competitors have identical priority, due date, and cannot be bundled (Rule C, resource, or work-type exception)."
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
                        train_window_checked=bool(needs_disconnection(r)),
                    )

    # ----------------------------------------------------------------------
    # Final assembly + counters (K.10)
    # ----------------------------------------------------------------------
    blocks.sort(key=lambda b: b.scheduled_start)

    total_requested = len(eligible)
    approved_count = sum(1 for d in decisions.values() if d.final_status == "Approved")
    isolated_emergency_count = sum(1 for d in decisions.values() if d.final_status == "Isolated-Emergency")
    deferred_count = sum(1 for d in decisions.values() if d.final_status == "Deferred")
    manual_review_count = sum(1 for d in decisions.values() if d.final_status == "Manual Review")

    total_completed = approved_count + isolated_emergency_count
    total_downtime = sum(b.duration_minutes for b in blocks if not b.block_id.startswith("EMG-"))
    total_saved = sum(b.time_saved_minutes for b in blocks)
    efficiency = (
        round((total_saved / (total_downtime + total_saved) * 100), 1)
        if (total_downtime + total_saved) > 0 else 0.0
    )

    summary_text = (
        f"{total_completed} of {total_requested} requests handled: "
        f"{approved_count} approved, {isolated_emergency_count} isolated-emergency, "
        f"{deferred_count} deferred, {manual_review_count} manual review."
    )

    unassigned_ids = [
        d.request_id for d in decisions.values()
        if d.final_status in ("Deferred", "Manual Review")
    ]
    infeasibility_reasons = [
        d.reason for d in decisions.values()
        if d.final_status in ("Deferred", "Manual Review")
    ]

    plan_name = (
        "Plan A: Maximum Bundling & Line Efficiency"
        if mode == "recommended"
        else "Plan B: Rapid Earliest Turnaround"
    )

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
        decisions=list(decisions.values()),
        deferred_requests=[d for d in decisions.values() if d.final_status == "Deferred"],
        manual_review_requests=[d for d in decisions.values() if d.final_status == "Manual Review"],
        isolated_emergency_requests=[d for d in decisions.values() if d.final_status == "Isolated-Emergency"],
    )