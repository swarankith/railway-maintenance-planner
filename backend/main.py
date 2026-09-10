"""
FastAPI Main Application Entrypoint (Phase 2 Final v6).
Initializes database tables, registers all API routes, runs background emergency escalation audits,
and serves the React frontend build if present.
Authentication removed per Part C.
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
from backend.routes import ingest, requests, conflicts, schedules, health, export, approvals, escalations, trains, demo
from backend.services.escalation import escalation_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Start emergency escalation background worker
    escalation_task = asyncio.create_task(escalation_worker())

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
app.include_router(export.router)
app.include_router(approvals.router)
app.include_router(ingest.router)
app.include_router(requests.router)
app.include_router(conflicts.router)
app.include_router(schedules.router)
app.include_router(escalations.router)
app.include_router(trains.router)
app.include_router(demo.router)

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