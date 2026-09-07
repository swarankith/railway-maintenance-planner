"""
Background service to check for emergency escalations.
Runs every 5 minutes and creates an escalation event if an emergency
has been isolated for more than 15 minutes without human sign-off.
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from backend.database import SessionLocal
from backend.models import DBMaintenanceRequest, DBEscalationEvent, RequestStatusEnum
from backend.config import APP_TIMEZONE

ESCALATION_THRESHOLD = timedelta(minutes=15)
CHECK_INTERVAL = 300  # 5 minutes (in seconds)

async def escalation_worker():
    """Loop forever, checking for emergencies that need escalation."""
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        await check_escalations()

async def check_escalations():
    db = SessionLocal()
    try:
        now = datetime.now(APP_TIMEZONE)
        # Find emergencies that are isolated and older than the threshold
        pending = db.query(DBMaintenanceRequest).filter(
            DBMaintenanceRequest.status == RequestStatusEnum.ISOLATED_EMERGENCY.value,
            DBMaintenanceRequest.isolated_at != None,
            DBMaintenanceRequest.isolated_at <= now - ESCALATION_THRESHOLD
        ).all()

        for req in pending:
            # Check if an escalation event already exists for this request
            exists = db.query(DBEscalationEvent).filter(
                DBEscalationEvent.request_id == req.request_id,
                DBEscalationEvent.status == "Pending"
            ).first()
            if not exists:
                event = DBEscalationEvent(
                    event_id=f"ESC-{uuid.uuid4().hex[:6].upper()}",
                    request_id=req.request_id,
                    corridor=req.corridor,
                    reason=f"Emergency {req.request_id} on {req.corridor} has been isolated for over 15 minutes without human sign-off.",
                    escalated_at=now,
                    status="Pending"
                )
                db.add(event)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Escalation check error: {e}")
    finally:
        db.close()