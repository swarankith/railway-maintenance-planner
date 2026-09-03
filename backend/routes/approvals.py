"""
Approval History Portal API:
- GET /api/v1/approvals/history
Supports date range, application_id, and corridor filtering.
"""
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import DBApprovalAudit, DBSchedulePlan, DBMaintenanceRequest, DBUser
from backend.auth import get_current_user

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals Portal"])


@router.get("/history", response_model=List[Dict[str, Any]])
def get_approval_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    application_id: Optional[str] = None,
    corridor: Optional[str] = None,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns approval history records with joined schedule details and request lists.
    """
    query = db.query(DBApprovalAudit)

    if application_id:
        query = query.filter(DBApprovalAudit.application_id.ilike(f"%{application_id}%"))
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.filter(DBApprovalAudit.timestamp >= sd)
        except Exception:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.filter(DBApprovalAudit.timestamp <= ed)
        except Exception:
            pass

    audits = query.order_by(DBApprovalAudit.timestamp.desc()).all()
    results = []

    for a in audits:
        plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == a.schedule_id).first()
        blocks = plan.plan_data.get("blocks", []) if plan else []
        
        # Collect request IDs and corridors involved
        req_ids = []
        corridors = set()
        for blk in blocks:
            req_ids.extend(blk.get("request_ids", []))
            if blk.get("corridor"):
                corridors.add(blk.get("corridor"))

        if corridor and not any(corridor.upper() in c.upper() for c in corridors):
            continue

        results.append({
            "id": a.id,
            "schedule_id": a.schedule_id,
            "application_id": a.application_id or (plan.plan_data.get("decisions", [{}])[0].get("application_id") if plan and plan.plan_data.get("decisions") else "APP-HISTORICAL"),
            "action": a.action,
            "role": a.role,
            "user_name": a.user_name,
            "notes": a.notes,
            "timestamp": a.timestamp,
            "request_ids": req_ids,
            "corridors": list(corridors),
            "total_blocks": len(blocks),
            "total_jobs": len(req_ids)
        })

    return results
