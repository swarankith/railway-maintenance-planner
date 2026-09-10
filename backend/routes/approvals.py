"""
Approval History API Endpoint (Part G).
Returns enriched audit history with optional filters (no auth).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.database import get_db
from backend.models import DBApprovalAudit, DBSchedulePlan

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


@router.get("/history", response_model=List[Dict[str, Any]])
def get_approval_history(
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    application_id: Optional[str] = Query(None, description="Filter by application ID"),
    corridor: Optional[str] = Query(None, description="Filter by corridor name"),
    db: Session = Depends(get_db)
):
    """
    Returns approval/rejection audit history with corridor, job/block counts, and download report links.
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

    audits = query.order_by(DBApprovalAudit.timestamp.desc()).all()

    if corridor:
        filtered = []
        for a in audits:
            plan = db.query(DBSchedulePlan).filter(DBSchedulePlan.schedule_id == a.schedule_id).first()
            if plan and plan.plan_data:
                blocks = plan.plan_data.get("blocks", [])
                corr_list = [b.get("corridor", "") for b in blocks if b.get("corridor")]
                if corridor.lower() in " ".join(corr_list).lower():
                    filtered.append(a)
        audits = filtered

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

        report_url = a.report_url or f"/api/v1/schedules/{a.schedule_id}/approval-report"
        result.append({
            "id": a.id,
            "schedule_id": a.schedule_id,
            "application_id": a.application_id,
            "cycle_id": a.cycle_id,
            "action": a.action,
            "role": a.role,
            "user_name": a.user_name,
            "notes": a.notes,
            "timestamp": a.timestamp,
            "report_url": report_url,
            "corridors": corridors,
            "total_jobs": total_jobs,
            "total_blocks": total_blocks,
            "request_ids": request_ids,
        })

    return result
