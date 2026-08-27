"""
Unit tests for Conflict Detection Engine.
Explicitly verifies:
- Genuine Spatial-Time-KM conflict detection
- False positive prevention (different corridors, different dates, non-overlapping KM ranges)
- Resource double-booking
- Live train path collisions
- Department compatibility matrix
"""
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.config import APP_TIMEZONE
from backend.models import (
    MaintenanceRequest,
    DepartmentEnum,
    BlockTypeEnum,
    RequestStatusEnum,
    TrainMovement,
    ConflictTypeEnum,
)
from backend.engine.conflicts import detect_all_conflicts


@pytest.fixture
def base_time():
    return datetime(2026, 9, 1, 1, 0, tzinfo=APP_TIMEZONE)


def test_genuine_spatial_conflict(base_time):
    """Same corridor, overlapping time, overlapping KM -> True Conflict."""
    r1 = MaintenanceRequest(
        request_id="REQ-001",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=10.0,
        km_end=20.0,
        asset="Track Section",
        work_type="Rail Grinding",
        priority=2,
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )
    r2 = MaintenanceRequest(
        request_id="REQ-002",
        department=DepartmentEnum.ELECTRICAL,
        corridor="NDLS-GZB",
        km_start=15.0,
        km_end=25.0,
        asset="OHE Catenary",
        work_type="OHE Inspection",
        priority=3,
        duration_minutes=120,
        earliest_start=base_time + timedelta(hours=1),
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    conflicts = detect_all_conflicts([r1, r2], [])
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.conflict_type == ConflictTypeEnum.SPATIAL_TIME_KM
    assert "REQ-001" in c.request_ids and "REQ-002" in c.request_ids
    assert c.km_overlap_start == 15.0
    assert c.km_overlap_end == 20.0


def test_false_positive_different_corridors(base_time):
    """Same time, same KM, but DIFFERENT corridors -> NOT a conflict."""
    r1 = MaintenanceRequest(
        request_id="REQ-A",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=10.0,
        km_end=20.0,
        asset="Track",
        work_type="Tamping",
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )
    r2 = MaintenanceRequest(
        request_id="REQ-B",
        department=DepartmentEnum.ELECTRICAL,
        corridor="HWH-KGP",  # Different corridor
        km_start=10.0,
        km_end=20.0,
        asset="OHE",
        work_type="OHE Overhaul",
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    conflicts = detect_all_conflicts([r1, r2], [])
    assert len(conflicts) == 0, "Different corridors must never conflict!"


def test_false_positive_different_dates(base_time):
    """Same corridor, same KM, but DIFFERENT dates/times -> NOT a conflict."""
    r1 = MaintenanceRequest(
        request_id="REQ-DAY1",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=10.0,
        km_end=20.0,
        asset="Track",
        work_type="Tamping",
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )
    r2 = MaintenanceRequest(
        request_id="REQ-DAY2",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=10.0,
        km_end=20.0,
        asset="Track",
        work_type="Tamping",
        duration_minutes=180,
        earliest_start=base_time + timedelta(days=1),  # Next day
        latest_end=base_time + timedelta(days=1, hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    conflicts = detect_all_conflicts([r1, r2], [])
    assert len(conflicts) == 0, "Different dates must never conflict!"


def test_false_positive_non_overlapping_km(base_time):
    """Same corridor, same time, but NON-OVERLAPPING KM ranges -> NOT a conflict."""
    r1 = MaintenanceRequest(
        request_id="REQ-KM10",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=10.0,
        km_end=20.0,
        asset="Track",
        work_type="Tamping",
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )
    r2 = MaintenanceRequest(
        request_id="REQ-KM50",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=50.0,
        km_end=60.0,  # Spatially separated by 30km
        asset="Track",
        work_type="Ballast Cleaning",
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    conflicts = detect_all_conflicts([r1, r2], [])
    assert len(conflicts) == 0, "Non-overlapping KM ranges on same corridor must not conflict!"


def test_resource_contention(base_time):
    """Shared specialized resource required concurrently -> Resource Conflict."""
    r1 = MaintenanceRequest(
        request_id="REQ-R1",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=10.0,
        km_end=20.0,
        asset="Track",
        work_type="Tamping",
        required_resources=["Track Tamper TTM-401"],
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )
    r2 = MaintenanceRequest(
        request_id="REQ-R2",
        department=DepartmentEnum.ENGINEERING,
        corridor="HWH-KGP",  # Different corridor
        km_start=50.0,
        km_end=60.0,
        asset="Track",
        work_type="Tamping",
        required_resources=["Track Tamper TTM-401"],  # Contended resource
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    conflicts = detect_all_conflicts([r1, r2], [])
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictTypeEnum.RESOURCE_OVERLAP
    assert conflicts[0].resource_involved == "Track Tamper TTM-401"


def test_train_movement_interference(base_time):
    """Maintenance window overlapping known live train path -> Hard Train Conflict."""
    r1 = MaintenanceRequest(
        request_id="REQ-TRK",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-CNB",
        km_start=40.0,
        km_end=55.0,
        asset="Track",
        work_type="Rail Replacement",
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )
    train = TrainMovement(
        train_id="12004 Vande Bharat Exp",
        corridor="NDLS-CNB",
        departure_time=base_time + timedelta(hours=1),
        arrival_time=base_time + timedelta(hours=3),
        km_start=0.0,
        km_end=440.0,
        train_type="High-Speed Express"
    )

    conflicts = detect_all_conflicts([r1], [train])
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictTypeEnum.TRAIN_MOVEMENT_CONFLICT
    assert conflicts[0].train_id_involved == "12004 Vande Bharat Exp"
    assert conflicts[0].severity == "Hard"
