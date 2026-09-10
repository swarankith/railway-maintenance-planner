"""
Integration tests for FastAPI REST API endpoints without Authentication (Phase 2).
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from backend.main import app
from backend.database import init_db, SessionLocal
from backend.config import APP_TIMEZONE
from backend.models import DBTrainMovement

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    client.delete("/api/v1/requests")
    db = SessionLocal()
    try:
        db.query(DBTrainMovement).delete()
        db.commit()
    finally:
        db.close()
    yield


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_demo_endpoint_in_memory():
    res = client.post("/api/v1/demo/run")
    assert res.status_code == 200
    assert res.headers.get("X-Demo-Mode") == "true"
    data = res.json()
    assert "schedule_id" in data
    assert len(data["blocks"]) > 0
    assert data["total_jobs_completed"] > 0


def test_gating_400_when_missing_requests_or_trains():
    # 1. No requests or trains -> 400
    res = client.post("/api/v1/schedules/optimize")
    assert res.status_code == 400
    assert "Maintenance request PDF not uploaded. Upload it first." in res.json()["detail"]

    # 2. Add request but no trains -> 400
    base_t = (datetime.now(APP_TIMEZONE) + timedelta(days=1)).replace(hour=1, minute=0, second=0, microsecond=0)
    req1_payload = {
        "request_id": "REQ-GATE-01",
        "department": "Engineering",
        "corridor": "NDLS-GZB",
        "km_start": 12.0,
        "km_end": 18.0,
        "asset": "Track Section",
        "work_type": "Track Tamping",
        "priority": 2,
        "duration_minutes": 180,
        "earliest_start": base_t.isoformat(),
        "latest_end": (base_t + timedelta(hours=5)).isoformat(),
        "required_resources": ["TTM-01"],
    }
    client.post("/api/v1/requests", json=req1_payload)
    res2 = client.post("/api/v1/schedules/optimize")
    assert res2.status_code == 400
    assert "Train movement PDF not uploaded. Upload it first." in res2.json()["detail"]


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
        "duration_minutes": 180,
        "earliest_start": base_t.isoformat(),
        "latest_end": (base_t + timedelta(hours=5)).isoformat(),
        "required_resources": ["TTM-01"],
    }
    r1_res = client.post("/api/v1/requests", json=req1_payload)
    assert r1_res.status_code == 200
    assert r1_res.json()["application_id"].startswith("APP-")

    req2_payload = {
        "request_id": "REQ-TEST-02",
        "department": "Electrical",
        "corridor": "NDLS-GZB",
        "km_start": 14.0,
        "km_end": 20.0,
        "asset": "OHE Catenary",
        "work_type": "OHE Insulator Replacement",
        "priority": 3,
        "duration_minutes": 150,
        "earliest_start": (base_t + timedelta(minutes=30)).isoformat(),
        "latest_end": (base_t + timedelta(hours=5)).isoformat(),
        "required_resources": ["Tower Wagon TW-3"],
    }
    r2_res = client.post("/api/v1/requests", json=req2_payload)
    assert r2_res.status_code == 200

    # 2. Add a scheduled train movement
    db = SessionLocal()
    try:
        t = DBTrainMovement(
            train_id="TR-TEST-12004",
            train_number="12004",
            train_name="Lucknow Shatabdi",
            corridor="NDLS-GZB",
            departure_time=base_t + timedelta(hours=6),
            arrival_time=base_t + timedelta(hours=7),
            km_start=0.0,
            km_end=25.0,
            speed_kmh=110.0,
            train_type="Passenger",
            source_document="SCHEDULE_2026.pdf"
        )
        db.add(t)
        db.commit()
    finally:
        db.close()

    # 3. List trains
    trains_res = client.get("/api/v1/trains")
    assert trains_res.status_code == 200
    assert len(trains_res.json()) >= 1

    # 4. List requests
    list_res = client.get("/api/v1/requests")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 2

    # 5. Check conflicts
    conf_res = client.post("/api/v1/conflicts/check", json=["REQ-TEST-01", "REQ-TEST-02"])
    assert conf_res.status_code == 200
    conflicts = conf_res.json()
    assert len(conflicts) >= 1

    # 6. Trigger Batch Optimization
    opt_res = client.post("/api/v1/schedules/optimize")
    assert opt_res.status_code == 200
    opt_data = opt_res.json()
    sched_id = opt_data["schedule_id"]
    assert len(opt_data["blocks"]) >= 1
    assert opt_data["is_recommended"] is True

    # 7. Get schedule by ID
    get_sched_res = client.get(f"/api/v1/schedules/{sched_id}")
    assert get_sched_res.status_code == 200
    assert get_sched_res.json()["schedule_id"] == sched_id

    # 8. Approve schedule
    app_res = client.post(f"/api/v1/schedules/{sched_id}/approve", json={
        "role": "Chief Controller",
        "user_name": "Senior Traffic Controller",
        "notes": "Verified track occupancy and power isolation. Approved for execution."
    })
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "Approved"
    assert app_res.json()["approved_by"] == "Senior Traffic Controller"

    # 9. Download Approval Report PDF (Part F)
    pdf_res = client.get(f"/api/v1/schedules/{sched_id}/approval-report")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 500

    # 10. Audit check & history portal
    hist_res = client.get("/api/v1/approvals/history")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1

    # 11. Bulk delete requests
    del_res = client.post("/api/v1/requests/bulk-delete", json={"request_ids": ["REQ-TEST-01", "REQ-TEST-02"]})
    assert del_res.status_code == 200
    assert del_res.json()["deleted_count"] >= 0

    # 12. Export requests to Excel and PDF
    exp_excel = client.get("/api/v1/export/requests?format=excel")
    assert exp_excel.status_code == 200

    exp_pdf = client.get("/api/v1/export/requests?format=pdf")
    assert exp_pdf.status_code == 200