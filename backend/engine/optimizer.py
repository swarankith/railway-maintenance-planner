"""Deterministic batch decision engine defined in the domain logic specification."""
import itertools
import uuid
from datetime import timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from backend.models import MaintenanceBlock, MaintenanceRequest, RequestDecision, SchedulePlan, TrainMovement
from backend.engine.conflicts import intervals_overlap, km_ranges_overlap
from backend.engine.explainability import generate_block_explanation, generate_plan_summary

# Category A work touches running rail and needs a disconnection. Labels are normalized
# only for matching; requests retain their submitted plain-text work type.
CATEGORY_A = {
    "rail renewal / replacement", "track/rail repair & welding", "sleeper replacement", "ballast work (tamping/screening)", "points & crossing maintenance", "point machine maintenance/repair", "track circuit testing & calibration", "trackside signal mast/aspect maintenance", "signal cable laying/repair (trackside)", "ohe (overhead wire) replacement/repair", "ohe insulator/hardware replacement", "feeder/catenary cable replacement (trackside)", "pantograph-ohe contact wire detailed inspection",
}
EXCLUSIVE_PAIRS = {frozenset(pair) for pair in [
    ("rail renewal / replacement", "sleeper replacement"),
    ("rail renewal / replacement", "ballast work (tamping/screening)"),
    ("sleeper replacement", "ballast work (tamping/screening)"),
    ("ohe (overhead wire) replacement/repair", "feeder/catenary cable replacement (trackside)"),
]}

def _norm(value: str) -> str:
    return " ".join((value or "").lower().replace("–", "-").split())

def needs_disconnection(request: MaintenanceRequest) -> bool:
    work = _norm(request.work_type)
    # These common uploaded-document variants map to the catalog wording without
    # changing what is stored on the request.
    return work in CATEGORY_A or any(term in work for term in ("tamping", "rail replacement", "rail repair", "welding", "sleeper", "points", "crossing", "point machine", "track circuit", "signal mast", "signal cable", "ohe", "catenary", "pantograph"))

def requests_compatible(left: MaintenanceRequest, right: MaintenanceRequest) -> bool:
    """Rules A/B: Category B is always combinable; Category A has four exceptions."""
    return not (needs_disconnection(left) and needs_disconnection(right)) or frozenset((_norm(left.work_type), _norm(right.work_type))) not in EXCLUSIVE_PAIRS

def resource_identity_clash(left: MaintenanceRequest, right: MaintenanceRequest) -> bool:
    return _norm(left.work_type) == _norm(right.work_type) and _norm(left.asset) == _norm(right.asset)

def _overlap(left: MaintenanceRequest, right: MaintenanceRequest) -> bool:
    return left.corridor.strip().upper() == right.corridor.strip().upper() and intervals_overlap(left.earliest_start, left.latest_end, right.earliest_start, right.latest_end) and km_ranges_overlap(left.km_start, left.km_end, right.km_start, right.km_end)

def _shared_resource(left: MaintenanceRequest, right: MaintenanceRequest) -> bool:
    return bool(set(map(_norm, left.required_resources)) & set(map(_norm, right.required_resources)))

def _groups(requests: Sequence[MaintenanceRequest]) -> List[List[MaintenanceRequest]]:
    remaining = set(range(len(requests))); groups = []
    while remaining:
        todo = [remaining.pop()]; group = []
        while todo:
            i = todo.pop(); group.append(requests[i])
            neighbours = [j for j in remaining if _overlap(requests[i], requests[j])]
            for j in neighbours: remaining.remove(j); todo.append(j)
        groups.append(group)
    return groups

def _units(group: Sequence[MaintenanceRequest], allow_bundling: bool) -> List[List[MaintenanceRequest]]:
    unused, result = list(group), []
    while unused:
        chosen = (unused[0],)
        if allow_bundling:
            for size in (3, 2):
                candidates = [c for c in itertools.combinations(unused, size) if all(requests_compatible(a, b) and not resource_identity_clash(a, b) for a, b in itertools.combinations(c, 2))]
                if candidates:
                    chosen = min(candidates, key=lambda c: (min(r.priority for r in c), min(r.earliest_start for r in c))); break
        result.append(list(chosen)); unused = [r for r in unused if r not in chosen]
    return result

def _train_free(unit: Sequence[MaintenanceRequest], start, end, trains: Sequence[TrainMovement]) -> bool:
    return not any(r.corridor.strip().upper() == t.corridor.strip().upper() and intervals_overlap(start, end, t.departure_time, t.arrival_time) and km_ranges_overlap(r.km_start, r.km_end, t.km_start, t.km_end) for r in unit for t in trains)

def solve_maintenance_schedule(requests: List[MaintenanceRequest], train_movements: Optional[List[TrainMovement]] = None, mode: str = "recommended") -> SchedulePlan:
    """Run the specified batch cycle. This produces recommendations, never finalizes a schedule."""
    trains = train_movements or []
    eligible = [r for r in requests if r.status.value not in {"Rejected", "Approved"}]
    decisions: Dict[str, RequestDecision] = {}; blocks: List[MaintenanceBlock] = []
    occupied: List[Tuple[str, object, object, List[MaintenanceRequest]]] = []

    emergencies = [r for r in eligible if r.block_type.value == "Emergency"]
    for r in emergencies:
        competing = any(o.request_id != r.request_id and _overlap(r, o) for o in emergencies)
        decisions[r.request_id] = RequestDecision(request_id=r.request_id, final_status="Isolated-Emergency", disconnection_required=needs_disconnection(r), priority=r.priority, retry_count=r.retry_count, reason="Competing emergencies share this corridor/window; both are isolated for human review." if competing else "Emergency corridor/window isolated pending urgent human sign-off.", train_window_checked=False)
        occupied.append((r.corridor, r.earliest_start, r.latest_end, [r]))

    remaining = [r for r in eligible if r.request_id not in decisions]; processing = []
    for r in remaining:
        resource_conflict = any(o.request_id != r.request_id and _shared_resource(r, o) and intervals_overlap(r.earliest_start, r.latest_end, o.earliest_start, o.latest_end) for o in remaining)
        if not needs_disconnection(r) and not resource_conflict:
            decisions[r.request_id] = RequestDecision(request_id=r.request_id, final_status="Approved", disconnection_required=False, priority=r.priority, retry_count=r.retry_count, reason="Category B work has no crew/resource conflict, so it is approved without a train-window check.", train_window_checked=False)
        else: processing.append(r)

    for group in _groups(processing):
        clashes = {r.request_id for a, b in itertools.combinations(group, 2) if resource_identity_clash(a, b) for r in (a, b)}
        units = _units(group, mode == "recommended")
        units.sort(key=lambda u: (min(r.priority for r in u), min(r.due_date or r.earliest_start.date() for r in u), min(r.request_id for r in u)))  # 1 = highest priority
        for i, unit in enumerate(units):
            priority, due = min(r.priority for r in unit), min(r.due_date or r.earliest_start.date() for r in unit)
            tied = any(i != j and min(r.priority for r in other) == priority and min(r.due_date or r.earliest_start.date() for r in other) == due for j, other in enumerate(units))
            start = max(r.earliest_start for r in unit); duration = max(r.duration_minutes for r in unit); end = start + timedelta(minutes=duration)
            free = not tied and not any(r.request_id in clashes for r in unit) and _train_free(unit, start, end, trains)
            if free:
                free = not any(c.strip().upper() == unit[0].corridor.strip().upper() and intervals_overlap(start, end, other_start, other_end) and any(km_ranges_overlap(r.km_start, r.km_end, o.km_start, o.km_end) for r in unit for o in other) for c, other_start, other_end, other in occupied)
            bundle_id = f"BND-{uuid.uuid4().hex[:6].upper()}" if len(unit) > 1 else None
            if free:
                resources = list(dict.fromkeys(x for r in unit for x in r.required_resources)); isolation = "Disconnection required" if any(needs_disconnection(r) for r in unit) else "None"; saved = sum(r.duration_minutes for r in unit) - duration
                blocks.append(MaintenanceBlock(block_id=f"BLK-{uuid.uuid4().hex[:6].upper()}", corridor=unit[0].corridor, scheduled_start=start, scheduled_end=end, duration_minutes=duration, km_start=min(r.km_start for r in unit), km_end=max(r.km_end for r in unit), request_ids=[r.request_id for r in unit], departments=list(dict.fromkeys(r.department for r in unit)), resources_allocated=resources, isolation_applied=isolation, utilization_score=100, time_saved_minutes=saved, bundling_explanation=generate_block_explanation(unit[0].corridor, unit, duration, saved, isolation, resources), requests=list(unit)))
                occupied.append((unit[0].corridor, start, end, unit))
                for r in unit: decisions[r.request_id] = RequestDecision(request_id=r.request_id, final_status="Approved", disconnection_required=needs_disconnection(r), priority=r.priority, bundle_id=bundle_id, bundle_members=[x.request_id for x in unit if x != r], retry_count=r.retry_count, reason="Approved as part of a strict mutually-compatible bundle capped at three requests." if bundle_id else "Approved by the priority walk as the available highest-priority request.", train_window_checked=needs_disconnection(r))
            else:
                for r in unit:
                    retry = r.retry_count + 1; status = "Manual Review" if tied or r.request_id in clashes or retry >= 3 else "Deferred"
                    reason = "Manual Review: tied competitors have identical priority and due date." if tied else ("Manual Review: identical work type on the identical asset is an unavoidable resource-identity clash." if r.request_id in clashes else ("Manual Review: retry cap of three reached." if retry >= 3 else "Deferred: no safe corridor/train window remained after higher-priority grants."))
                    decisions[r.request_id] = RequestDecision(request_id=r.request_id, final_status=status, disconnection_required=needs_disconnection(r), priority=r.priority, retry_count=retry, reason=reason, train_window_checked=needs_disconnection(r))

    blocks.sort(key=lambda b: b.scheduled_start); saved = sum(b.time_saved_minutes for b in blocks); downtime = sum(b.duration_minutes for b in blocks); unresolved = [d for d in decisions.values() if d.final_status != "Approved"]
    efficiency = round(saved / (downtime + saved) * 100, 1) if downtime + saved else 0.0
    return SchedulePlan(schedule_id=f"SCHED-{uuid.uuid4().hex[:8].upper()}", plan_name="Plan A: Maximum Bundling & Minimal Line Disruption" if mode == "recommended" else "Plan B: Rapid Earliest Execution", is_recommended=mode == "recommended", blocks=blocks, unassigned_requests=[d.request_id for d in unresolved], infeasibility_reasons=[d.reason for d in unresolved], total_corridor_downtime_minutes=downtime, total_jobs_completed=sum(len(b.request_ids) for b in blocks), total_jobs_requested=len(eligible), bundling_efficiency_percentage=efficiency, summary_explanation=generate_plan_summary("Batch decision recommendation", len(blocks), len(eligible), downtime, saved, efficiency, len(unresolved)), decisions=list(decisions.values()))
