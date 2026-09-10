import pytest
from datetime import datetime, timedelta
from backend.config import APP_TIMEZONE
from backend.models import (
    MaintenanceRequest,
    TrainMovement,
    BlockTypeEnum,
    RequestStatusEnum,
)
from backend.engine.batch_engine import solve_maintenance_schedule, is_rule_c_clash
from backend.ingestion.extractor import extract_document


def test_rule_c_fuzzy_matching():
    base_t = datetime.now(APP_TIMEZONE) + timedelta(days=1)
    # Similar work type (>= 85%), same asset
    req1 = MaintenanceRequest(
        request_id="R1",
        department="Engineering",
        corridor="DELHI-AGRA",
        km_start=10.0,
        km_end=20.0,
        asset="Switch-12A",
        work_type="Track Renewal",
        duration_minutes=60,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=3),
        status=RequestStatusEnum.CONFIRMED,
        disconnection_required=True
    )
    req2 = MaintenanceRequest(
        request_id="R2",
        department="Engineering",
        corridor="DELHI-AGRA",
        km_start=10.0,
        km_end=20.0,
        asset="Switch-12A",
        work_type="Track Renewals",  # fuzzy match
        duration_minutes=60,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=3),
        status=RequestStatusEnum.CONFIRMED,
        disconnection_required=True
    )
    assert is_rule_c_clash(req1, req2) is True

    # Missing asset should not clash under Rule C
    req3 = MaintenanceRequest(
        request_id="R3",
        department="Engineering",
        corridor="DELHI-AGRA",
        km_start=10.0,
        km_end=20.0,
        asset="",
        work_type="Track Renewal",
        duration_minutes=60,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=3),
        status=RequestStatusEnum.CONFIRMED,
        disconnection_required=True
    )
    assert is_rule_c_clash(req1, req3) is False


def test_emergency_block_created_and_counted():
    base_t = datetime.now(APP_TIMEZONE) + timedelta(days=1)
    req_emg = MaintenanceRequest(
        request_id="EMG-01",
        department="Engineering",
        corridor="DELHI-AGRA",
        km_start=10.0,
        km_end=15.0,
        asset="Track Section",
        work_type="Rail Fracture Repair",
        duration_minutes=120,
        priority=1,
        block_type=BlockTypeEnum.EMERGENCY,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )
    req_b = MaintenanceRequest(
        request_id="CATB-01",
        department="Engineering",
        corridor="DELHI-AGRA",
        km_start=30.0,
        km_end=35.0,
        asset="Cess Area",
        work_type="Vegetation Clearing",
        duration_minutes=60,
        priority=3,
        block_type=BlockTypeEnum.NORMAL,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    plan = solve_maintenance_schedule(
        requests=[req_emg, req_b],
        train_movements=[]
    )

    assert len(plan.isolated_emergency_requests) == 1
    assert plan.isolated_emergency_requests[0].request_id == "EMG-01"
    
    # Must have emergency block
    emg_blocks = [b for b in plan.blocks if b.block_id.startswith("EMG-BLK-")]
    assert len(emg_blocks) == 1
    assert emg_blocks[0].corridor == "DELHI-AGRA"
    assert "EMERGENCY ISOLATION:" in emg_blocks[0].bundling_explanation

    # Total completed should count approved + isolated emergencies
    assert plan.total_jobs_completed == 2


def test_true_tie_physical_overlap_requirement():
    base_t = datetime.now(APP_TIMEZONE) + timedelta(days=1)
    # Same priority (P2), same time window, but DIFFERENT corridors -> NO tie clash, both scheduled
    req1 = MaintenanceRequest(
        request_id="TIE-01",
        department="Engineering",
        corridor="CORRIDOR-NORTH",
        km_start=10.0,
        km_end=20.0,
        asset="Track Section 1",
        work_type="Welding",
        duration_minutes=60,
        priority=2,
        block_type=BlockTypeEnum.NORMAL,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=2),
        status=RequestStatusEnum.CONFIRMED
    )
    req2 = MaintenanceRequest(
        request_id="TIE-02",
        department="Engineering",
        corridor="CORRIDOR-SOUTH",
        km_start=10.0,
        km_end=20.0,
        asset="Track Section 2",
        work_type="Welding",
        duration_minutes=60,
        priority=2,
        block_type=BlockTypeEnum.NORMAL,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=2),
        status=RequestStatusEnum.CONFIRMED
    )

    plan = solve_maintenance_schedule(
        requests=[req1, req2],
        train_movements=[]
    )

    # Neither should be sent to manual review for tie clash because they are on different corridors
    assert len(plan.manual_review_requests) == 0
    approved_decisions = [d for d in plan.decisions if d.final_status == "Approved"]
    assert len(approved_decisions) == 2


def test_train_corridor_normalization():
    base_t = datetime.now(APP_TIMEZONE) + timedelta(days=1)
    req = MaintenanceRequest(
        request_id="NORM-01",
        department="Engineering",
        corridor="  delhi-agra  ",
        km_start=10.0,
        km_end=20.0,
        asset="Track Section",
        work_type="Track Renewal",
        duration_minutes=60,
        priority=2,
        block_type=BlockTypeEnum.NORMAL,
        earliest_start=base_t,
        latest_end=base_t + timedelta(hours=2),
        status=RequestStatusEnum.CONFIRMED
    )
    # Train spanning across the window on normalized matching corridor
    train = TrainMovement(
        train_id="TR-12001",
        train_number="12001",
        corridor="DELHI-AGRA ",
        origin="DELHI",
        destination="AGRA",
        departure_time=base_t,
        arrival_time=base_t + timedelta(hours=2),
        km_start=5.0,
        km_end=25.0,
        train_type="EXPRESS"
    )

    plan = solve_maintenance_schedule(
        requests=[req],
        train_movements=[train]
    )

    # Decision should indicate train window conflict / deferred
    assert len(plan.decisions) == 1
    assert plan.decisions[0].request_id == "NORM-01"


def test_plain_text_extraction():
    content = b"SAMPLE PLAIN TEXT RAILWAY LOG\nBlock needed at KM 45 to 50 on CNB-ALD corridor.\n"
    doc = extract_document(content, "log_file.txt")
    assert "SAMPLE PLAIN TEXT RAILWAY LOG" in doc.raw_text
    assert len(doc.tables) == 0
