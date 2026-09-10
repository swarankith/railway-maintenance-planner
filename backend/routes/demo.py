"""
In-Memory Demo Runner Endpoint (Part L).
Runs the complete Step 0-7 deterministic pipeline on the hardcoded demo dataset entirely in memory.
Never persists to database under any circumstance.
"""
from fastapi import APIRouter, Response
from backend.demo.dataset import get_demo_requests, get_demo_trains
from backend.engine.batch_engine import solve_maintenance_schedule
from backend.models import SchedulePlan

router = APIRouter(prefix="/api/v1/demo", tags=["Demo"])


@router.post("/run", response_model=SchedulePlan)
def run_in_memory_demo(response: Response):
    """
    Executes Step 0-7 pipeline purely in memory with hardcoded demo data.
    Sets X-Demo-Mode: true response header.
    Does NOT touch the database.
    """
    demo_requests = get_demo_requests()
    demo_trains = get_demo_trains()

    plan = solve_maintenance_schedule(
        requests=demo_requests,
        train_movements=demo_trains,
        mode="recommended",
        cycle_id="CYC-DEMO-INMEMORY"
    )

    response.headers["X-Demo-Mode"] = "true"
    return plan
