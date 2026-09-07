"""
Approval History API Endpoint.
Returns enriched audit history with optional filters.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.database import get_db
from backend.models import DBApprovalAudit, DBUser, DBSchedulePlan
from backend.auth import get_current_user

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])

@router.get("/history", response_model=List[Dict[str, Any]])
def get_approval_history(
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    application_id: Optional[str] = Query(None, description="Filter by application ID"),
    corridor: Optional[str] = Query(None, description="Filter by corridor name"),
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns approval/rejection audit history with corridor and job/block counts.
    """
    query = db.query(DBApprovalAudit)

    if application_id:
        query = query.filter(DBApprovalAudit.application_id == application_id)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(DBApprovalAudit.timestamp >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(DBApprovalAudit.timestamp <= end_dt)
        except ValueError:
            pass

    if corridor:
        # Filter by corridor requires joining with schedule data; we'll filter in Python
        # For prototype, we can retrieve all and filter later, but better to use plan_data
        audits = query.order_by(DBApprovalAudit.timestamp.desc()).all()
        filtered = []
        for a in audits:
            plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == a.schedule_id).first()
            if plan and plan.plan_data:
                blocks = plan.plan_data.get("blocks", [])
                corr_list = [b.get("corridor", "") for b in blocks if b.get("corridor")]
                if corridor.lower() in " ".join(corr_list).lower():
                    filtered.append(a)
        audits = filtered
    else:
        audits = query.order_by(DBApprovalAudit.timestamp.desc()).all()

    result = []
    for a in audits:
        plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == a.schedule_id).first()
        corridors = []
        total_jobs = 0
        total_blocks = 0
        request_ids = []
        if plan and plan.plan_data:
            blocks = plan.plan_data.get("blocks", [])
            total_blocks = len(blocks)
            total_jobs = sum(len(b.get("request_ids", [])) for b in blocks)
            corridors = list({b.get("corridor", "") for b in blocks if b.get("corridor")})
            request_ids = [rid for b in blocks for rid in b.get("request_ids", [])]

        result.append({
            "id": a.id,
            "schedule_id": a.schedule_id,
            "application_id": a.application_id,
            "action": a.action,
            "role": a.role,
            "user_name": a.user_name,
            "notes": a.notes,
            "timestamp": a.timestamp,
            "corridors": corridors,
            "total_jobs": total_jobs,
            "total_blocks": total_blocks,
            "request_ids": request_ids,
        })

    return result

