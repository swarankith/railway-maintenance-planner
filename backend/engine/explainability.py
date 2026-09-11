"""
Explainability Generator for Railway Maintenance Blocks.
Produces human-readable, domain-specific rationale for every scheduling decision,
bundling synergy, conflict resolution, and infeasibility diagnostic.

Signatures match batch_engine.py's call sites exactly:
- generate_block_explanation(corridor, requests, duration_minutes,
    time_saved_minutes, isolation_applied, resources_allocated) -> str
- generate_plan_summary(plan_name, total_blocks, total_jobs,
    total_downtime_minutes, total_saved_minutes, efficiency_pct,
    unassigned_count) -> str
- generate_infeasibility_explanation(request, conflicting_trains,
    conflicting_resources) -> str
"""
from typing import List
from backend.models import MaintenanceRequest, TrainMovement


PRIORITY_LABELS = {
    1: "P1 - Emergency",
    2: "P2 - High Urgent",
    3: "P3 - Normal",
}


def _priority_label(p: int) -> str:
    return PRIORITY_LABELS.get(p, f"P{p}")


def generate_block_explanation(
    corridor: str,
    requests: List[MaintenanceRequest],
    duration_minutes: int,
    time_saved_minutes: int,
    isolation_applied: str,
    resources_allocated: List[str],
) -> str:
    """Generates a factual plain-language explanation for a maintenance block."""
    if not requests:
        return f"Empty block on {corridor}."

    if len(requests) == 1:
        req = requests[0]
        prio_label = _priority_label(req.priority)
        res_text = f" utilizing {', '.join(resources_allocated)}" if resources_allocated else ""
        iso_text = (
            f" under {isolation_applied} isolation"
            if isolation_applied and isolation_applied != "None"
            else ""
        )
        return (
            f"Dedicated single-job block on {corridor} (KM {req.km_start:.1f}-{req.km_end:.1f}) "
            f"for {req.department} ({req.work_type}, {prio_label}){res_text}{iso_text}. "
            f"Scheduled standalone as no compatible co-located work was requested within this time window."
        )

    # Multi-request bundle
    depts = list(dict.fromkeys([r.department for r in requests]))
    member_ids = ", ".join(r.request_id for r in requests)
    jobs_summary = ", ".join(
        f"{r.department} {r.work_type} (KM {r.km_start:.1f}-{r.km_end:.1f}, {_priority_label(r.priority)})"
        for r in requests
    )
    res_text = (
        f" Shared plant/resources: {', '.join(resources_allocated)}."
        if resources_allocated else ""
    )
    iso_text = (
        f" Unified under {isolation_applied}."
        if isolation_applied and isolation_applied != "None"
        else ""
    )

    km_min = min(r.km_start for r in requests)
    km_max = max(r.km_end for r in requests)

    return (
        f"Bundled {len(requests)} compatible maintenance tasks ({member_ids}) across "
        f"{', '.join(depts)} on {corridor} (overall span KM {km_min:.1f}-{km_max:.1f}). "
        f"Included work: {jobs_summary}. "
        f"Combining these departments into a single {duration_minutes}-minute block eliminated "
        f"separate corridor shutdowns, saving {time_saved_minutes} minutes of track downtime "
        f"and preventing train path cancellations.{iso_text}{res_text}"
    )


def generate_plan_summary(
    plan_name: str,
    total_blocks: int,
    total_jobs: int,
    total_downtime_minutes: int,
    total_saved_minutes: int,
    efficiency_pct: float,
    unassigned_count: int,
) -> str:
    """
    Generates executive summary for the complete schedule plan.
    total_jobs = total eligible requests entering the batch.
    unassigned_count = requests not scheduled (Deferred + Manual Review).
    """
    if total_jobs == 0:
        return "No maintenance requests were submitted for scheduling."

    scheduled = total_jobs - unassigned_count
    hours_downtime = round(total_downtime_minutes / 60, 1)
    hours_saved = round(total_saved_minutes / 60, 1)

    if unassigned_count == 0:
        return (
            f"{plan_name}: Successfully scheduled 100% of requested maintenance tasks "
            f"({scheduled} jobs) into {total_blocks} synchronized corridor blocks. "
            f"Total corridor closure: {hours_downtime} hrs ({total_downtime_minutes} min). "
            f"Joint multi-department bundling achieved {efficiency_pct:.1f}% efficiency, "
            f"saving {hours_saved} hrs ({total_saved_minutes} min) of line downtime compared to isolated single-department blocks."
        )

    return (
        f"{plan_name}: Scheduled {scheduled} of {total_jobs} maintenance tasks across "
        f"{total_blocks} blocks with {unassigned_count} jobs flagged as unassigned due to "
        f"train traffic, emergency reservations, or resource contention. "
        f"Bundling efficiency achieved: {efficiency_pct:.1f}%."
    )


def generate_infeasibility_explanation(
    request: MaintenanceRequest,
    conflicting_trains: List[TrainMovement],
    conflicting_resources: List[str],
) -> str:
    """Explains why a specific request could not be safely scheduled."""
    reasons = []
    if conflicting_trains:
        train_names = ", ".join(t.train_id for t in conflicting_trains)
        reasons.append(
            f"Corridor {request.corridor} is occupied by scheduled train movements "
            f"({train_names}) throughout the requested window."
        )
    if conflicting_resources:
        res_names = ", ".join(conflicting_resources)
        reasons.append(
            f"Required specialized resources ({res_names}) are fully booked by "
            f"higher-priority maintenance tasks."
        )
    if not reasons:
        reasons.append(
            "Requested duration exceeds the available corridor maintenance window "
            "between operational shifts."
        )

    return (
        f"Request {request.request_id} ({request.work_type} on {request.corridor}): "
        f"Cannot schedule safely. " + " ".join(reasons)
    )