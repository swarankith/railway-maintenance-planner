"""
Train Movements API Endpoints (Part E).
- GET /api/v1/trains (no auth)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import DBTrainMovement, TrainMovement

router = APIRouter(prefix="/api/v1/trains", tags=["Trains"])


@router.get("", response_model=List[TrainMovement])
def list_train_movements(
    corridor: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List scheduled train movements (no auth)."""
    query = db.query(DBTrainMovement)
    if corridor:
        query = query.filter(DBTrainMovement.corridor.ilike(f"%{corridor}%"))
    records = query.order_by(DBTrainMovement.departure_time.asc()).all()
    return [
        TrainMovement(
            train_id=t.train_id,
            corridor=t.corridor,
            departure_time=t.departure_time,
            arrival_time=t.arrival_time,
            km_start=t.km_start,
            km_end=t.km_end,
            train_type=t.train_type,
            source_document=t.source_document,
            cycle_id=t.cycle_id
        )
        for t in records
    ]
