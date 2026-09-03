"""
Comprehensive Unit & Scenario Tests for Phase 2 Deterministic Batch Engine and Features.
"""
import pytest
from datetime import datetime, timedelta, date
from backend.config import APP_TIMEZONE
from backend.models import (
    MaintenanceRequest,
    TrainMovement,
    BlockTypeEnum,
    RequestStatusEnum,
)
from backend.engine.batch_engine import (
    classify_work_type,
    needs_disconnection,
    resource_identity_clash,
    solve_maintenance_schedule,
)
from backend.engine.conflicts import parse_km_range_robust, normalize_resource_name


def test_fuzzy_work_type_classification():
    # Category A fuzzy matches
    cat, match, score = classify_work_type("rail replacement")
    assert cat == "A"
    assert score >= 85.0

    cat, match, score = classify_work_type("grinding rails")
    assert cat == "A"

    cat, match, score = classify_work_type("catenary ohe repair")
    assert cat == "A"

    # Category B fuzzy matches
    cat, match, score = classify_work_type("vegetation clearing trackside")
    assert cat == "B"
    assert score >= 85.0

    cat, match, score = classify_work_type("drain cleaning and desilting")
    assert cat == "B"


def test_robust_km_parsing():
    s, e = parse_km_range_robust("10-12 km")
    assert s == 10.0 and e == 12.0

    s, e = parse_km_range_robust("KM 10 to 12")
    assert s == 10.0 and e == 12.0

    s, e = parse_km_range_robust("10/12")
    assert s == 10.0 and e == 12.0

    s, e = parse_km_range_robust("10.5 – 12.3")
    assert s == 10.5 and e == 12.3


def test_resource_normalization():
    assert normalize_resource_name("Tower-Wagon_TW1") == "tower wagon tw1"
    assert normalize_resource_name("  TRACK   TAMPER--01 ") == "track tamper 01"


def test_emergency_lane_isolation_and_competing():
    base_t = datetime.now(APP_TIMEZONE) + timedelta(days=1)
    
    # 2 competing emergencies on same corridor & span
    e1 = MaintenanceRequest(
        request_id="EMERG-01",
        department="Engineering",
        corridor="NDLS-CNB",
        km_start=50.0,
        km_end=55.0,
        asset="Track Section",
        work_type="Broken Rail Emergency Welding",
        priority=1,
        block_type=BlockTypeEnum.EMERGENCY,
        duration_minutes=120,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    e2 = MaintenanceRequest(
        request_id="EMERG-02",
        department="Electrical",
        corridor="NDLS-CNB",
        km_start=52.0,
        km_end=58.0,
        asset="OHE Catenary",
        work_type="OHE Wire Snap Breakdown",
        priority=1,
        block_type=BlockTypeEnum.EMERGENCY,
        duration_minutes=90,
        earliest_start=base_t + timedelta(minutes=15),
        latest_end=base_t + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    plan = solve_maintenance_schedule([e1, e2], [])
    decisions = {d.request_id: d for d in plan.decisions}

    assert decisions["EMERG-01"].final_status == "Isolated-Emergency"
    assert decisions["EMERG-02"].final_status == "Isolated-Emergency"
    assert "Competing emergencies" in decisions["EMERG-01"].reason


def test_deferred_retry_cap():
    base_t = datetime.now(APP_TIMEZONE) + timedelta(days=1)
    
    # High Urgent priority blocking request (Priority 2)
    r_high = MaintenanceRequest(
        request_id="REQ-HIGH",
        department="Engineering",
        corridor="NDLS-CNB",
        km_start=10.0,
        km_end=15.0,
        asset="Track Section",
        work_type="Track Tamping",
        priority=2,
        duration_minutes=180,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=3),
        block_shared_allowed=False,
        status=RequestStatusEnum.CONFIRMED
    )

    # Conflicting normal request with retry_count = 2 (should hit cap -> Manual Review)
    r_retry2 = MaintenanceRequest(
        request_id="REQ-RETRY2",
        department="Electrical",
        corridor="NDLS-CNB",
        km_start=11.0,
        km_end=14.0,
        asset="OHE Catenary",
        work_type="OHE Wire Replacement",
        priority=3,
        duration_minutes=120,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=2),
        block_shared_allowed=False,
        retry_count=2,
        status=RequestStatusEnum.CONFIRMED
    )

    plan = solve_maintenance_schedule([r_high, r_retry2], [])
    decisions = {d.request_id: d for d in plan.decisions}

    assert decisions["REQ-HIGH"].final_status == "Approved"
    assert decisions["REQ-RETRY2"].final_status == "Manual Review"
    assert decisions["REQ-RETRY2"].retry_count == 3
    assert "retry cap of 3 reached" in decisions["REQ-RETRY2"].reason.lower()
