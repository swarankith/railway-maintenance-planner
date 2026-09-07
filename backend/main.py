"""
FastAPI Main Application Entrypoint (Phase 2).
Initializes database tables, registers all API routes, runs background emergency escalation audits,
and serves the React frontend build if present.
"""
import os
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from backend.config import APP_TIMEZONE, EMERGENCY_ESCALATION_MINUTES
from backend.database import init_db, SessionLocal
from backend.models import DBMaintenanceRequest, DBEscalationEvent, RequestStatusEnum
from backend.routes import auth, ingest, requests, conflicts, schedules, health, export, approvals, escalations
from backend.services.escalation import escalation_worker  # background worker


async def run_emergency_escalation_audit():
    """
    Background job: checks for isolated emergencies not signed off within the allowed time.
    Creates persisted EscalationEvents.
    """
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            db = SessionLocal()
            try:
                now_ist = datetime.now(APP_TIMEZONE)
                cutoff = now_ist - timedelta(minutes=EMERGENCY_ESCALATION_MINUTES)
                unresolved = db.query(DBMaintenanceRequest).filter(
                    DBMaintenanceRequest.status.in_([
                        RequestStatusEnum.ISOLATED_EMERGENCY.value,
                        "Isolated-Emergency"
                    ]),
                    DBMaintenanceRequest.isolated_at != None,
                    DBMaintenanceRequest.isolated_at <= cutoff
                ).all()

                for req in unresolved:
                    existing_esc = db.query(DBEscalationEvent).filter(
                        DBEscalationEvent.request_id == req.request_id,
                        DBEscalationEvent.status == "Pending"
                    ).first()

                    if not existing_esc:
                        esc = DBEscalationEvent(
                            event_id=f"ESC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{req.request_id[:6]}",
                            request_id=req.request_id,
                            corridor=req.corridor,
                            reason=f"Emergency request {req.request_id} has exceeded the {EMERGENCY_ESCALATION_MINUTES}-minute human sign-off timeout."
                        )
                        db.add(esc)
                db.commit()
            finally:
                db.close()
        except Exception:
            # Add logging in production; for prototype, silent catch is acceptable
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Create default users if none exist (necessary for login)
    from backend.database import SessionLocal
    from backend.models import DBUser
    from backend.auth import hash_password
    db = SessionLocal()
    try:
        if db.query(DBUser).count() == 0:
            users = [
                ("planner1", "planner123", "Planner"),
                ("ops1", "ops123", "Operations"),
                ("approver1", "approver123", "Approver"),
            ]
            for username, password, role in users:
                db.add(DBUser(
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                    department="Engineering"
                ))
            db.commit()
            print("✅ Default users created successfully.")
        else:
            print("ℹ️ Users already exist, skipping creation.")
    finally:
        db.close()

    # Start the emergency escalation background worker
    escalation_task = asyncio.create_task(escalation_worker())
    # Optionally start the audit worker here, but we already have escalation_worker
    # You can choose one; we'll keep the service worker

    yield

    # Cancel background task on shutdown
    escalation_task.cancel()
    try:
        await escalation_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Indian Railways AI Maintenance Block Planner API",
    description="Intelligent decision-support system for railway maintenance block scheduling, conflict detection, and deterministic bundling optimization.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(export.router)
app.include_router(approvals.router)
app.include_router(ingest.router)
app.include_router(requests.router)
app.include_router(conflicts.router)
app.include_router(schedules.router)
app.include_router(escalations.router)          # <-- NEW

# Mount production frontend build if present
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            return None
        file_path = os.path.join(frontend_dist, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    @app.get("/")
    def root():
        return {
            "message": "Indian Railways Maintenance Block Planner API is running.",
            "version": "2.0.0",
            "documentation": "/docs",
            "health": "/api/v1/health"
        }


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)