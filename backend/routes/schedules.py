"""
Schedule Optimization & Approval API Endpoints (Phase 2 Final v6).
- Open API (Authentication removed per Part C)
- Part E: Eligibility & Upload Gating
- Part F: Approval Report PDF
- Part G & I: Cycle Resolution, Immutability & Audit Logging
"""
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
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
    TrainMovement,
    RequestStatusEnum,
    PlanStatusEnum,
    CycleStatusEnum,
)
from backend.routes.requests import db_to_pydantic
from backend.engine.batch_engine import solve_maintenance_schedule
from backend.services.pdf_report import generate_approval_report_pdf

router = APIRouter(prefix="/api/v1/schedules", tags=["Schedules"])


class OptimizationResult(SchedulePlan):
    alternative_plan: Optional[SchedulePlan] = None


def get_eligible_requests(db: Session, request_ids: Optional[List[str]] = None) -> List[DBMaintenanceRequest]:
    """
    Part E Eligibility rule:
    - cycle_id IS NULL (brand new), OR
    - referenced ProcessingCycle.status IN ('Approved', 'Rejected') AND final_status IN ('Confirmed', 'Deferred', 'Manual Review')
    - A request whose cycle is still 'Active' is NOT eligible.
    """
    # Find all completed cycle IDs (Approved or Rejected)
    completed_cycles = db.query(DBProcessingCycle.cycle_id).filter(
        DBProcessingCycle.status.in_([CycleStatusEnum.APPROVED.value, CycleStatusEnum.REJECTED.value])
    ).all()
    completed_cycle_ids = {c[0] for c in completed_cycles}

    all_reqs = db.query(DBMaintenanceRequest).all()
    eligible = []

    for r in all_reqs:
        if request_ids and r.request_id not in request_ids:
            continue

        if r.status in [RequestStatusEnum.REJECTED.value, RequestStatusEnum.APPROVED.value]:
            continue

        if r.cycle_id is None:
            # Brand new
            if r.status in [RequestStatusEnum.CONFIRMED.value, RequestStatusEnum.INGESTED.value]:
                eligible.append(r)
        elif r.cycle_id in completed_cycle_ids:
            # From a closed cycle
            if r.status in [RequestStatusEnum.CONFIRMED.value, RequestStatusEnum.DEFERRED.value, RequestStatusEnum.MANUAL_REVIEW.value, RequestStatusEnum.OPTIMIZED.value]:
                eligible.append(r)

    return eligible


def get_eligible_trains(db: Session) -> List[DBTrainMovement]:
    """
    Part E: Trains are eligible if cycle_id is NULL.
    Once a cycle finishes, trains in that cycle become ineligible for future cycles.
    """
    return db.query(DBTrainMovement).filter(DBTrainMovement.cycle_id == None).all()


@router.post("/optimize", response_model=OptimizationResult)
def optimize_schedules(
    request_ids: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    """
    Triggers Deterministic Batch Decision Engine across eligible requests & trains (Part E).
    Returns HTTP 400 if zero eligible maintenance requests or zero eligible train movements exist.
    """
    eligible_reqs = get_eligible_requests(db, request_ids)
    eligible_trains = get_eligible_trains(db)

    # Part E: Upload gating
    if len(eligible_reqs) == 0:
        raise HTTPException(
            status_code=400,
            detail="Maintenance request PDF not uploaded. Upload it first."
        )
    if len(eligible_trains) == 0:
        raise HTTPException(
            status_code=400,
            detail="Train movement PDF not uploaded. Upload it first."
        )

    requests = [db_to_pydantic(r) for r in eligible_reqs]
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
        for t in eligible_trains
    ]

    # Generate new cycle_id and create Active ProcessingCycle record (Step 0)
    cycle_id = f"CYC-{uuid.uuid4().hex[:8].upper()}"
    now_ist = datetime.now(APP_TIMEZONE)

    cycle_record = DBProcessingCycle(
        cycle_id=cycle_id,
        status=CycleStatusEnum.ACTIVE.value,
        total_requests=len(requests),
        created_at=now_ist
    )
    db.add(cycle_record)

    # Tag every entering request and train with this cycle_id
    for r in eligible_reqs:
        r.cycle_id = cycle_id
    for t in eligible_trains:
        t.cycle_id = cycle_id

    # Solve schedules
    plan_a = solve_maintenance_schedule(requests, train_movements, mode="recommended", cycle_id=cycle_id)
    plan_b = solve_maintenance_schedule(requests, train_movements, mode="alternative", cycle_id=cycle_id)

    # Persist decision states
    app_count = 0
    def_count = 0
    man_count = 0
    iso_count = 0

    for decision in plan_a.decisions:
        rec = next((r for r in eligible_reqs if r.request_id == decision.request_id), None)
        if rec:
            rec.retry_count = decision.retry_count
            if decision.final_status == "Approved":
                rec.status = RequestStatusEnum.OPTIMIZED.value
                app_count += 1
            elif decision.final_status == "Deferred":
                rec.status = RequestStatusEnum.DEFERRED.value
                def_count += 1
            elif decision.final_status == "Manual Review":
                rec.status = RequestStatusEnum.MANUAL_REVIEW.value
                man_count += 1
            elif decision.final_status == "Isolated-Emergency":
                rec.status = RequestStatusEnum.ISOLATED_EMERGENCY.value
                rec.isolated_at = now_ist
                iso_count += 1

    cycle_record.approved_count = app_count
    cycle_record.deferred_count = def_count
    cycle_record.manual_review_count = man_count
    cycle_record.isolated_emergency_count = iso_count

    db_plan_a = DBSchedulePlan(
        schedule_id=plan_a.schedule_id,
        cycle_id=cycle_id,
        plan_name=plan_a.plan_name,
        is_recommended=True,
        status=plan_a.status.value,
        plan_data=json.loads(plan_a.model_dump_json())
    )
    db.add(db_plan_a)

    db_plan_b = DBSchedulePlan(
        schedule_id=plan_b.schedule_id,
        cycle_id=cycle_id,
        plan_name=plan_b.plan_name,
        is_recommended=False,
        status=plan_b.status.value,
        plan_data=json.loads(plan_b.model_dump_json())
    )
    db.add(db_plan_b)

    db.commit()

    res_dict = plan_a.model_dump()
    res_dict["alternative_plan"] = plan_b
    return res_dict


@router.get("", response_model=List[Dict[str, Any]])
def list_schedules(db: Session = Depends(get_db)):
    """Lists all generated schedules (no auth)."""
    records = db.query(DBSchedulePlan).order_by(DBSchedulePlan.created_at.desc()).all()
    return [
        {
            "schedule_id": r.schedule_id,
            "cycle_id": r.cycle_id,
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
def get_schedule(schedule_id: str, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db)
):
    """
    Part G & I: Human controller approval.
    - Immutability check: cannot re-approve/re-reject an already finalized plan.
    - ProcessingCycle.status = 'Approved'.
    - Approved requests -> final status Approved (ineligible for next cycle).
    - Deferred / Manual Review requests remain eligible for next cycle.
    - Trains in this cycle become ineligible for future cycles.
    """
    db_plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == schedule_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found.")

    # Immutability check
    if db_plan.status in [PlanStatusEnum.APPROVED.value, PlanStatusEnum.REJECTED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Schedule '{schedule_id}' is permanently {db_plan.status}. Create a new schedule to record changes."
        )

    now_ist = datetime.now(APP_TIMEZONE)
    user_name = payload.user_name or "Senior Traffic Controller"
    role = payload.role or "Chief Controller"

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

    # Update ProcessingCycle status to Approved
    if db_plan.cycle_id:
        cycle_rec = db.query(DBProcessingCycle).filter(DBProcessingCycle.cycle_id == db_plan.cycle_id).first()
        if cycle_rec:
            cycle_rec.status = CycleStatusEnum.APPROVED.value

    # Extract application_id
    app_id = None
    blocks = plan_data.get("blocks", [])
    if blocks:
        for b in blocks:
            for req_id in b.get("request_ids", []):
                req_rec = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == req_id).first()
                if req_rec and req_rec.application_id:
                    app_id = req_rec.application_id
                    break
            if app_id:
                break

    report_url = f"/api/v1/schedules/{schedule_id}/approval-report"
    audit = DBApprovalAudit(
        schedule_id=schedule_id,
        application_id=app_id,
        cycle_id=db_plan.cycle_id,
        action="APPROVED",
        role=role,
        user_name=user_name,
        notes=payload.notes,
        timestamp=now_ist,
        report_url=report_url
    )
    db.add(audit)

    # Transition approved block requests to Approved
    for blk in blocks:
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
    db: Session = Depends(get_db)
):
    """
    Part G & I: Human controller rejection.
    - Immutability check.
    - ProcessingCycle.status = 'Rejected'.
    - Approved requests revert to 'Confirmed' -> re-enters Step 0 next cycle.
    - Deferred / Manual Review remain as-is (eligible for next cycle).
    - Trains in this cycle become ineligible for future cycles.
    """
    db_plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == schedule_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found.")

    if db_plan.status in [PlanStatusEnum.APPROVED.value, PlanStatusEnum.REJECTED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Schedule '{schedule_id}' is permanently {db_plan.status}."
        )

    now_ist = datetime.now(APP_TIMEZONE)
    user_name = payload.user_name or "Senior Traffic Controller"
    role = payload.role or "Chief Controller"

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

    # Update ProcessingCycle status to Rejected
    if db_plan.cycle_id:
        cycle_rec = db.query(DBProcessingCycle).filter(DBProcessingCycle.cycle_id == db_plan.cycle_id).first()
        if cycle_rec:
            cycle_rec.status = CycleStatusEnum.REJECTED.value

    # Extract application_id
    app_id = None
    blocks = plan_data.get("blocks", [])
    if blocks:
        for b in blocks:
            for req_id in b.get("request_ids", []):
                req_rec = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == req_id).first()
                if req_rec and req_rec.application_id:
                    app_id = req_rec.application_id
                    break
            if app_id:
                break

    report_url = f"/api/v1/schedules/{schedule_id}/approval-report"
    audit = DBApprovalAudit(
        schedule_id=schedule_id,
        application_id=app_id,
        cycle_id=db_plan.cycle_id,
        action="REJECTED",
        role=role,
        user_name=user_name,
        notes=payload.reason,
        timestamp=now_ist,
        report_url=report_url
    )
    db.add(audit)

    # Revert Approved requests back to Confirmed
    for blk in blocks:
        for req_id in blk.get("request_ids", []):
            req_rec = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == req_id).first()
            if req_rec:
                req_rec.status = RequestStatusEnum.CONFIRMED.value

    db.commit()
    db.refresh(db_plan)

    return SchedulePlan(**plan_data)


@router.get("/{schedule_id}/approval-report")
def download_approval_report_pdf(schedule_id: str, db: Session = Depends(get_db)):
    """
    Part F: Generates and streams Approval Report PDF for a schedule.
    Filename: approval_report_<schedule_id>_<YYYY-MM-DD_HHMMSS>.pdf in IST.
    """
    db_plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == schedule_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found.")

    # Fetch matching DBApprovalAudit if available
    audit = db.query(DBApprovalAudit).filter(DBApprovalAudit.schedule_id == schedule_id).order_by(DBApprovalAudit.timestamp.desc()).first()

    approver_role = audit.role if audit else (db_plan.approval_role or "—")
    approver_name = audit.user_name if audit else (db_plan.approved_by or "—")
    approval_time = audit.timestamp if audit else (db_plan.approval_timestamp or datetime.now(APP_TIMEZONE))

    pdf_bytes = generate_approval_report_pdf(
        schedule_id=schedule_id,
        plan_data=db_plan.plan_data,
        approver_role=approver_role,
        approver_name=approver_name,
        approval_time=approval_time
    )

    now_ist = datetime.now(APP_TIMEZONE)
    ts_str = now_ist.strftime("%Y-%m-%d_%H%M%S")
    filename = f"approval_report_{schedule_id}_{ts_str}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/{schedule_id}/audit", response_model=List[Dict[str, Any]])
def get_schedule_audit(schedule_id: str, db: Session = Depends(get_db)):
    """Retrieves full audit log history for a schedule."""
    audits = db.query(DBApprovalAudit).filter(DBApprovalAudit.schedule_id == schedule_id).order_by(DBApprovalAudit.timestamp.desc()).all()
    return [
        {
            "id": a.id,
            "schedule_id": a.schedule_id,
            "application_id": a.application_id,
            "cycle_id": a.cycle_id,
            "action": a.action,
            "role": a.role,
            "user_name": a.user_name,
            "notes": a.notes,
            "timestamp": a.timestamp,
            "report_url": a.report_url
        }
        for a in audits
    ]