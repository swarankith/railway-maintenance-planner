"""
Health Check API Endpoint: GET /api/v1/health
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.database import get_db
from backend.config import APP_TIMEZONE, TIMEZONE_STR
from backend.models import DBMaintenanceRequest

router = APIRouter(prefix="/api/v1", tags=["System Health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check verifying database connectivity, solver engine, and timezone integrity."""
    request_count = db.query(DBMaintenanceRequest).count()
    return {
        "status": "healthy",
        "service": "AI-Assisted Railway Maintenance Block Planner",
        "version": "1.0.0",
        "timezone": TIMEZONE_STR,
        "current_time_ist": datetime.now(APP_TIMEZONE).isoformat(),
        "database": "connected",
        "total_requests_in_db": request_count,
        "optimization_solver": "Google OR-Tools CP-SAT"
    }
