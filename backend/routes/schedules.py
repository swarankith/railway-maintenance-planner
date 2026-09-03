"""
Schedule Optimization & Approval API Endpoints:
- POST /api/v1/schedules/optimize
- GET /api/v1/schedules/{id}
- POST /api/v1/schedules/{id}/approve
- POST /api/v1/schedules/{id}/reject
- GET /api/v1/schedules
- GET /api/v1/schedules/{id}/audit
Protected by JWT Authentication.
"""
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.config import APP_TIMEZONE
from backend.database import get_db
from backend.models import (
    SchedulePlan,
    ApprovalRequest,
    RejectionRequest,
    DBSchedulePlan,
    DBApprovalAudit,
    DBMaintenanceRequest,
    DBTrainMovement,
    DBProcessingCycle,
    DBUser,
    TrainMovement,
    RequestStatusEnum,
    PlanStatusEnum,
)
from backend.auth import get_current_user
from backend.routes.requests import db_to_pydantic
from backend.engine.batch_engine import solve_maintenance_schedule

router = APIRouter(prefix="/api/v1/schedules", tags=["Schedules"])


class OptimizationResult(SchedulePlan):
    alternative_plan: Optional[SchedulePlan] = None


@router.post("/optimize", response_model=OptimizationResult)
def optimize_schedules(
    request_ids: Optional[List[str]] = None,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers Deterministic Batch Decision Engine across confirmed maintenance requests.
    Produces Recommended Plan (Maximum Bundling) and Alternative Plan (Rapid Turnaround),
    with explainability text for every block.
    """
    query = db.query(DBMaintenanceRequest)
    if request_ids:
        query = query.filter(DBMaintenanceRequest.request_id.in_(request_ids))
    else:
        query = query.filter(DBMaintenanceRequest.status.in_([
            RequestStatusEnum.CONFIRMED.value,
            RequestStatusEnum.INGESTED.value,
            RequestStatusEnum.OPTIMIZED.value,
            RequestStatusEnum.DEFERRED.value
        ]))

    db_reqs = query.all()
    requests = [db_to_pydantic(r) for r in db_reqs]

    if not requests:
        raise HTTPException(
            status_code=400,
            detail="No confirmed maintenance requests available to optimize. Please upload or confirm requests first."
        )

    db_trains = db.query(DBTrainMovement).all()
    train_movements = [
        TrainMovement(
            train_id=t.train_id,
            corridor=t.corridor,
            departure_time=t.departure_time,
            arrival_time=t.arrival_time,
            km_start=t.km_start,
            km_end=t.km_end,
            train_type=t.train_type,
            source_document=t.source_document
        )
        for t in db_trains
    ]

    plan_a = solve_maintenance_schedule(requests, train_movements, mode="recommended")
    plan_b = solve_maintenance_schedule(requests, train_movements, mode="alternative")

    # Persist decision states & retry counts back to DB
    for decision in plan_a.decisions:
        record = next((r for r in db_reqs if r.request_id == decision.request_id), None)
        if record:
            record.retry_count = decision.retry_count
            if decision.final_status in {"Deferred", "Manual Review", "Isolated-Emergency"}:
                record.status = decision.final_status

    # Record Processing Cycle
    app_count = sum(1 for d in plan_a.decisions if d.final_status == "Approved")
    def_count = sum(1 for d in plan_a.decisions if d.final_status == "Deferred")
    man_count = sum(1 for d in plan_a.decisions if d.final_status == "Manual Review")
    iso_count = sum(1 for d in plan_a.decisions if d.final_status == "Isolated-Emergency")

    cycle = DBProcessingCycle(
        cycle_id=f"CYCLE-{uuid.uuid4().hex[:6].upper()}",
        total_requests=len(requests),
        approved_count=app_count,
        deferred_count=def_count,
        manual_review_count=man_count,
        isolated_emergency_count=iso_count
    )
    db.add(cycle)

    db_plan_a = DBSchedulePlan(
        schedule_id=plan_a.schedule_id,
        plan_name=plan_a.plan_name,
        is_recommended=True,
        status=plan_a.status.value,
        plan_data=json.loads(plan_a.model_dump_json())
    )
    db.add(db_plan_a)

    db_plan_b = DBSchedulePlan(
        schedule_id=plan_b.schedule_id,
        plan_name=plan_b.plan_name,
        is_recommended=False,
        status=plan_b.status.value,
        plan_data=json.loads(plan_b.model_dump_json())
    )
    db.add(db_plan_b)

    for r in db_reqs:
        if r.status in [RequestStatusEnum.CONFIRMED.value, RequestStatusEnum.INGESTED.value]:
            r.status = RequestStatusEnum.OPTIMIZED.value

    db.commit()

    res_dict = plan_a.model_dump()
    res_dict["alternative_plan"] = plan_b
    return res_dict


@router.get("", response_model=List[Dict[str, Any]])
def list_schedules(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all generated schedules."""
    records = db.query(DBSchedulePlan).order_by(DBSchedulePlan.created_at.desc()).all()
    return [
        {
            "schedule_id": r.schedule_id,
            "plan_name": r.plan_name,
            "is_recommended": r.is_recommended,
            "status": r.status,
            "approved_by": r.approved_by,
            "approval_role": r.approval_role,
            "approval_timestamp": r.approval_timestamp,
            "created_at": r.created_at,
            "total_blocks": len(r.plan_data.get("blocks", [])),
            "total_jobs": r.plan_data.get("total_jobs_completed", 0),
            "bundling_efficiency": r.plan_data.get("bundling_efficiency_percentage", 0.0)
        }
        for r in records
    ]


@router.get("/{schedule_id}", response_model=SchedulePlan)
def get_schedule(
    schedule_id: str,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve saved schedule plan by ID."""
    db_plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == schedule_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found.")

    plan_data = dict(db_plan.plan_data)
    plan_data["status"] = db_plan.status
    plan_data["approved_by"] = db_plan.approved_by
    plan_data["approval_role"] = db_plan.approval_role
    plan_data["approval_timestamp"] = db_plan.approval_timestamp
    plan_data["approval_notes"] = db_plan.approval_notes
    return SchedulePlan(**plan_data)


@router.post("/{schedule_id}/approve", response_model=SchedulePlan)
def approve_schedule(
    schedule_id: str,
    payload: ApprovalRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Records human planner approval for a schedule plan.
    Transitions status to Approved with role, user name, and timestamp.
    """
    db_plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == schedule_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found.")

    now_ist = datetime.now(APP_TIMEZONE)
    user_name = payload.user_name or current_user.username
    role = payload.role or current_user.role

    db_plan.status = PlanStatusEnum.APPROVED.value
    db_plan.approved_by = user_name
    db_plan.approval_role = role
    db_plan.approval_timestamp = now_ist
    db_plan.approval_notes = payload.notes

    plan_data = dict(db_plan.plan_data)
    plan_data["status"] = PlanStatusEnum.APPROVED.value
    plan_data["approved_by"] = user_name
    plan_data["approval_role"] = role
    plan_data["approval_timestamp"] = now_ist.isoformat()
    plan_data["approval_notes"] = payload.notes
    db_plan.plan_data = plan_data
    flag_modified(db_plan, "plan_data")

    # Find application_id if available
    first_app_id = None
    decisions = plan_data.get("decisions", [])
    if decisions:
        first_app_id = decisions[0].get("application_id")

    audit = DBApprovalAudit(
        schedule_id=schedule_id,
        application_id=first_app_id,
        action="APPROVED",
        role=role,
        user_name=user_name,
        notes=payload.notes,
        timestamp=now_ist
    )
    db.add(audit)

    for blk in plan_data.get("blocks", []):
        for req_id in blk.get("request_ids", []):
            req_rec = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == req_id).first()
            if req_rec:
                req_rec.status = RequestStatusEnum.APPROVED.value

    db.commit()
    db.refresh(db_plan)

    return SchedulePlan(**plan_data)


@router.post("/{schedule_id}/reject", response_model=SchedulePlan)
def reject_schedule(
    schedule_id: str,
    payload: RejectionRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Records human planner rejection for a schedule plan.
    Requires mandatory rejection reason.
    """
    db_plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == schedule_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found.")

    now_ist = datetime.now(APP_TIMEZONE)
    user_name = payload.user_name or current_user.username
    role = payload.role or current_user.role

    db_plan.status = PlanStatusEnum.REJECTED.value
    db_plan.approved_by = user_name
    db_plan.approval_role = role
    db_plan.approval_timestamp = now_ist
    db_plan.approval_notes = f"REJECTED: {payload.reason}"

    plan_data = dict(db_plan.plan_data)
    plan_data["status"] = PlanStatusEnum.REJECTED.value
    plan_data["approved_by"] = user_name
    plan_data["approval_role"] = role
    plan_data["approval_timestamp"] = now_ist.isoformat()
    plan_data["approval_notes"] = f"REJECTED: {payload.reason}"
    db_plan.plan_data = plan_data
    flag_modified(db_plan, "plan_data")

    first_app_id = None
    decisions = plan_data.get("decisions", [])
    if decisions:
        first_app_id = decisions[0].get("application_id")

    audit = DBApprovalAudit(
        schedule_id=schedule_id,
        application_id=first_app_id,
        action="REJECTED",
        role=role,
        user_name=user_name,
        notes=payload.reason,
        timestamp=now_ist
    )
    db.add(audit)

    for blk in plan_data.get("blocks", []):
        for req_id in blk.get("request_ids", []):
            req_rec = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == req_id).first()
            if req_rec:
                req_rec.status = RequestStatusEnum.CONFIRMED.value

    db.commit()
    db.refresh(db_plan)

    return SchedulePlan(**plan_data)


@router.get("/{schedule_id}/audit", response_model=List[Dict[str, Any]])
def get_schedule_audit(
    schedule_id: str,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves full audit log history for a schedule."""
    audits = db.query(DBApprovalAudit).filter(DBApprovalAudit.schedule_id == schedule_id).order_by(DBApprovalAudit.timestamp.desc()).all()
    return [
        {
            "id": a.id,
            "schedule_id": a.schedule_id,
            "application_id": a.application_id,
            "action": a.action,
            "role": a.role,
            "user_name": a.user_name,
            "notes": a.notes,
            "timestamp": a.timestamp
        }
        for a in audits
    ]
