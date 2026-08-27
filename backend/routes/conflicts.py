"""
Conflict Detection API Endpoint: POST /api/v1/conflicts/check
Evaluates confirmed requests and train movements against exact conflict specifications.
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.models import (
    MaintenanceRequest,
    TrainMovement,
    ConflictDetail,
    DBMaintenanceRequest,
    DBTrainMovement,
    RequestStatusEnum,
)
from backend.routes.requests import db_to_pydantic
from backend.engine.conflicts import detect_all_conflicts

router = APIRouter(prefix="/api/v1/conflicts", tags=["Conflicts"])


@router.post("/check", response_model=List[ConflictDetail])
def check_conflicts(
    request_ids: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    """
    Runs multi-dimensional conflict detection across confirmed requests and known train movements.
    Detects Spatial-Time-KM overlap, resource contention, live train path collisions, and department incompatibilities.
    """
    # Fetch requests
    query = db.query(DBMaintenanceRequest)
    if request_ids:
        query = query.filter(DBMaintenanceRequest.request_id.in_(request_ids))
    else:
        # Check across confirmed and ingested requests
        query = query.filter(DBMaintenanceRequest.status.in_([
            RequestStatusEnum.CONFIRMED.value,
            RequestStatusEnum.INGESTED.value,
            RequestStatusEnum.OPTIMIZED.value
        ]))

    db_reqs = query.all()
    requests = [db_to_pydantic(r) for r in db_reqs]

    # Fetch train movements
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

    conflicts = detect_all_conflicts(requests, train_movements)
    return conflicts
