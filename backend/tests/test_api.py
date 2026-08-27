"""
Integration tests for FastAPI REST API endpoints using TestClient.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from backend.main import app
from backend.database import init_db
from backend.config import APP_TIMEZONE

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    # Clear requests before each test
    client.delete("/api/v1/requests")
    yield


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["optimization_solver"] == "Google OR-Tools CP-SAT"


def test_full_maintenance_workflow_api():
    base_t = (datetime.now(APP_TIMEZONE) + timedelta(days=1)).replace(hour=1, minute=0, second=0, microsecond=0)
    
    # 1. Create two requests via POST /api/v1/requests
    req1_payload = {
        "request_id": "REQ-TEST-01",
        "department": "Engineering",
        "corridor": "NDLS-GZB",
        "km_start": 12.0,
        "km_end": 18.0,
        "asset": "Track Section",
        "work_type": "Track Tamping",
        "priority": 2,
        "priority_reason": "High priority track maintenance",
        "block_type": "Planned",
        "duration_minutes": 180,
        "earliest_start": base_t.isoformat(),
        "latest_end": (base_t + timedelta(hours=5)).isoformat(),
        "required_resources": ["TTM-01"],
        "isolation_requirement": "None",
        "block_shared_allowed": True
    }
    r1_res = client.post("/api/v1/requests", json=req1_payload)
    assert r1_res.status_code == 200

    req2_payload = {
        "request_id": "REQ-TEST-02",
        "department": "Electrical",
        "corridor": "NDLS-GZB",
        "km_start": 14.0,
        "km_end": 20.0,
        "asset": "OHE Catenary",
        "work_type": "OHE Periodic Overhaul",
        "priority": 3,
        "priority_reason": "Scheduled periodic overhaul",
        "block_type": "Normal",
        "duration_minutes": 150,
        "earliest_start": (base_t + timedelta(minutes=30)).isoformat(),
        "latest_end": (base_t + timedelta(hours=5)).isoformat(),
        "required_resources": ["Tower Wagon TW-3"],
        "isolation_requirement": "Power Block (OHE)",
        "block_shared_allowed": True
    }
    r2_res = client.post("/api/v1/requests", json=req2_payload)
    assert r2_res.status_code == 200

    # 2. List requests
    list_res = client.get("/api/v1/requests")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 2

    # 3. Check conflicts
    conf_res = client.post("/api/v1/conflicts/check", json=["REQ-TEST-01", "REQ-TEST-02"])
    assert conf_res.status_code == 200
    conflicts = conf_res.json()
    assert len(conflicts) >= 1
    assert conflicts[0]["conflict_type"] == "SpatialTimeKM"

    # 4. Trigger Optimization
    opt_res = client.post("/api/v1/schedules/optimize")
    assert opt_res.status_code == 200
    opt_data = opt_res.json()
    sched_id = opt_data["schedule_id"]
    assert len(opt_data["blocks"]) == 1
    assert opt_data["is_recommended"] is True
    assert "alternative_plan" in opt_data
    assert len(opt_data["blocks"][0]["bundling_explanation"]) > 10

    # 5. Get schedule by ID
    get_sched_res = client.get(f"/api/v1/schedules/{sched_id}")
    assert get_sched_res.status_code == 200
    assert get_sched_res.json()["schedule_id"] == sched_id

    # 6. Approve schedule
    app_res = client.post(f"/api/v1/schedules/{sched_id}/approve", json={
        "role": "Chief Controller",
        "user_name": "Senior Traffic Controller",
        "notes": "Verified track occupancy and power isolation. Approved for execution."
    })
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "Approved"
    assert app_res.json()["approved_by"] == "Senior Traffic Controller"

    # 7. Audit check
    audit_res = client.get(f"/api/v1/schedules/{sched_id}/audit")
    assert audit_res.status_code == 200
    audits = audit_res.json()
    assert len(audits) == 1
    assert audits[0]["action"] == "APPROVED"