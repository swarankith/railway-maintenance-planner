"""
Requests CRUD API:
- GET /api/v1/requests
- POST /api/v1/requests
- PUT /api/v1/requests/{request_id}
- POST /api/v1/requests/{request_id}/confirm
- DELETE /api/v1/requests/{request_id}
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.models import (
    MaintenanceRequest,
    MaintenanceRequestCreate,
    MaintenanceRequestUpdate,
    DBMaintenanceRequest,
    RequestStatusEnum,
    DepartmentEnum,
)

router = APIRouter(prefix="/api/v1/requests", tags=["Requests"])


def db_to_pydantic(db_req: DBMaintenanceRequest) -> MaintenanceRequest:
    return MaintenanceRequest(
        id=db_req.id,
        request_id=db_req.request_id,
        department=DepartmentEnum(db_req.department),
        corridor=db_req.corridor,
        km_start=db_req.km_start,
        km_end=db_req.km_end,
        asset=db_req.asset,
        work_type=db_req.work_type,
        priority=db_req.priority,
        priority_reason=db_req.priority_reason,
        block_type=db_req.block_type,
        duration_minutes=db_req.duration_minutes,
        earliest_start=db_req.earliest_start,
        latest_end=db_req.latest_end,
        due_date=db_req.due_date,
        required_resources=db_req.required_resources or [],
        isolation_requirement=db_req.isolation_requirement,
        block_shared_allowed=db_req.block_shared_allowed,
        dependencies=db_req.dependencies or [],
        status=RequestStatusEnum(db_req.status),
        source_document=db_req.source_document,
        missing_fields=db_req.missing_fields or [],
        validation_notes=db_req.validation_notes,
        created_at=db_req.created_at,
        updated_at=db_req.updated_at
    )


@router.get("", response_model=List[MaintenanceRequest])
def list_requests(
    corridor: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List and filter maintenance requests."""
    query = db.query(DBMaintenanceRequest)
    if corridor:
        query = query.filter(DBMaintenanceRequest.corridor.ilike(f"%{corridor}%"))
    if department:
        query = query.filter(DBMaintenanceRequest.department == department)
    if status:
        query = query.filter(DBMaintenanceRequest.status == status)
    if priority:
        query = query.filter(DBMaintenanceRequest.priority == priority)

    records = query.order_by(DBMaintenanceRequest.priority.asc(), DBMaintenanceRequest.earliest_start.asc()).all()
    return [db_to_pydantic(r) for r in records]


@router.post("", response_model=MaintenanceRequest)
def create_request(
    payload: MaintenanceRequestCreate,
    db: Session = Depends(get_db)
):
    """Manually create a new maintenance request or add a custom job."""
    req_id = payload.request_id or f"REQ-{datetime.now().strftime('%H%M%S')}"
    
    # Check duplicate
    existing = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == req_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Request ID '{req_id}' already exists.")

    db_req = DBMaintenanceRequest(
        request_id=req_id,
        department=payload.department.value,
        corridor=payload.corridor.strip().upper(),
        km_start=payload.km_start,
        km_end=payload.km_end,
        asset=payload.asset,
        work_type=payload.work_type,
        priority=payload.priority,
        priority_reason=payload.priority_reason or "Manually submitted request",
        block_type=payload.block_type.value,
        duration_minutes=payload.duration_minutes,
        earliest_start=payload.earliest_start,
        latest_end=payload.latest_end,
        due_date=payload.due_date,
        required_resources=payload.required_resources,
        isolation_requirement=payload.isolation_requirement,
        block_shared_allowed=payload.block_shared_allowed,
        dependencies=payload.dependencies,
        status=payload.status.value,
        source_document=payload.source_document,
        missing_fields=[],
        validation_notes="Manually verified and confirmed"
    )
    db.add(db_req)
    db.commit()
    db.refresh(db_req)
    return db_to_pydantic(db_req)


@router.put("/{request_id}", response_model=MaintenanceRequest)
def update_request(
    request_id: str,
    payload: MaintenanceRequestUpdate,
    db: Session = Depends(get_db)
):
    """Edit/complete an existing request (especially flagged Needs-Review records)."""
    db_req = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == request_id).first()
    if not db_req:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            if field == "department":
                setattr(db_req, field, val.value if hasattr(val, 'value') else str(val))
            elif field == "block_type":
                setattr(db_req, field, val.value if hasattr(val, 'value') else str(val))
            elif field == "status":
                setattr(db_req, field, val.value if hasattr(val, 'value') else str(val))
            elif field == "corridor":
                setattr(db_req, field, str(val).strip().upper())
            else:
                setattr(db_req, field, val)

    # Re-evaluate missing fields
    missing = []
    if not db_req.corridor or db_req.corridor == "UNSPECIFIED-CORRIDOR":
        missing.append("corridor")
    if db_req.km_start is None:
        missing.append("km_start")
    if db_req.km_end is None:
        missing.append("km_end")
    if not db_req.duration_minutes or db_req.duration_minutes <= 0:
        missing.append("duration_minutes")
    if not db_req.earliest_start:
        missing.append("earliest_start")
    if not db_req.latest_end:
        missing.append("latest_end")

    db_req.missing_fields = missing
    if not missing and db_req.status == RequestStatusEnum.NEEDS_REVIEW.value:
        db_req.status = RequestStatusEnum.CONFIRMED.value
        db_req.validation_notes = "Updated and confirmed by human planner"

    db.commit()
    db.refresh(db_req)
    return db_to_pydantic(db_req)


@router.post("/{request_id}/confirm", response_model=MaintenanceRequest)
def confirm_request(
    request_id: str,
    db: Session = Depends(get_db)
):
    """Manually confirms a request to Confirmed state."""
    db_req = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == request_id).first()
    if not db_req:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")

    db_req.status = RequestStatusEnum.CONFIRMED.value
    db_req.missing_fields = []
    db_req.validation_notes = "Manually confirmed by planner"
    db.commit()
    db.refresh(db_req)
    return db_to_pydantic(db_req)


@router.delete("/{request_id}")
def delete_request(
    request_id: str,
    db: Session = Depends(get_db)
):
    """Delete a single request."""
    db_req = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == request_id).first()
    if not db_req:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")
    db.delete(db_req)
    db.commit()
    return {"message": f"Request {request_id} deleted successfully."}


@router.delete("")
def clear_all_requests(db: Session = Depends(get_db)):
    """Deletes all maintenance requests and train movements for clean state testing."""
    db.query(DBMaintenanceRequest).delete()
    db.commit()
    return {"message": "All maintenance requests cleared."}
