"""
FastAPI Main Application Entrypoint.
Initializes database tables (empty initial state), registers API routes, and enables CORS for frontend.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from backend.database import init_db
from backend.routes import ingest, requests, conflicts, schedules, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup (no seed data)
    init_db()
    yield


app = FastAPI(
    title="AI-Assisted Railway Maintenance Block Planner API",
    description="Intelligent decision-support system for railway maintenance block scheduling, conflict detection, and bundling optimization.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend Vite development & preview servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(requests.router)
app.include_router(conflicts.router)
app.include_router(schedules.router)

# Mount production frontend build if present
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Don't intercept API or documentation routes
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
            "message": "Railway Maintenance Block Planner API is running.",
            "documentation": "/docs",
            "health": "/api/v1/health"
        }


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)

