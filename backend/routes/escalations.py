from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from backend.database import get_db
from backend.models import DBEscalationEvent, DBUser
from backend.auth import get_current_user

router = APIRouter(prefix="/api/v1/escalations", tags=["Escalations"])

@router.get("", response_model=List[Dict[str, Any]])
def list_escalations(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns all escalation events (pending and resolved)."""
    events = db.query(DBEscalationEvent).order_by(DBEscalationEvent.escalated_at.desc()).all()
    return [
        {
            "event_id": e.event_id,
            "request_id": e.request_id,
            "corridor": e.corridor,
            "reason": e.reason,
            "escalated_at": e.escalated_at,
            "status": e.status
        }
        for e in events
    ]