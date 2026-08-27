"""
Unit tests for Optimization and Explainability Engine.
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
)
from backend.engine.optimizer import solve_maintenance_schedule


@pytest.fixture
def base_time():
    return datetime(2026, 9, 1, 1, 0, tzinfo=APP_TIMEZONE)


def test_joint_bundling_and_explainability(base_time):
    """Bundles compatible Engineering & Electrical jobs and verifies plain-language explanation."""
    r1 = MaintenanceRequest(
        request_id="REQ-ENG-01",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=12.0,
        km_end=18.0,
        asset="Track Section",
        work_type="Track Tamping",
        priority=2,
        duration_minutes=180,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=5),
        status=RequestStatusEnum.CONFIRMED
    )
    r2 = MaintenanceRequest(
        request_id="REQ-ELE-02",
        department=DepartmentEnum.ELECTRICAL,
        corridor="NDLS-GZB",
        km_start=14.0,
        km_end=20.0,
        asset="OHE 25kV Catenary",
        work_type="OHE Annual Overhaul",
        priority=3,
        duration_minutes=150,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=5),
        status=RequestStatusEnum.CONFIRMED
    )

    plan = solve_maintenance_schedule([r1, r2], [], mode="recommended")
    assert len(plan.blocks) == 1, "Compatible jobs should be bundled into a single block"
    block = plan.blocks[0]
    assert "REQ-ENG-01" in block.request_ids
    assert "REQ-ELE-02" in block.request_ids
    assert block.duration_minutes == 180  # Max of 180 and 150
    assert block.time_saved_minutes == 150  # 150 min saved
    assert len(block.bundling_explanation) > 20
    assert "Bundled 2 compatible maintenance tasks" in block.bundling_explanation
    assert "saving 150 minutes" in block.bundling_explanation


def test_alternative_plan_generation(base_time):
    """Verifies alternative plan can be generated with different characteristics."""
    r1 = MaintenanceRequest(
        request_id="REQ-1",
        department=DepartmentEnum.ENGINEERING,
        corridor="NDLS-GZB",
        km_start=10.0,
        km_end=20.0,
        asset="Track",
        work_type="Rail Grinding",
        duration_minutes=120,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )
    r2 = MaintenanceRequest(
        request_id="REQ-2",
        department=DepartmentEnum.ST,
        corridor="NDLS-GZB",
        km_start=12.0,
        km_end=15.0,
        asset="Signal",
        work_type="Point Machine Check",
        duration_minutes=60,
        earliest_start=base_time,
        latest_end=base_time + timedelta(hours=4),
        status=RequestStatusEnum.CONFIRMED
    )

    plan_a = solve_maintenance_schedule([r1, r2], [], mode="recommended")
    plan_b = solve_maintenance_schedule([r1, r2], [], mode="alternative")

    assert plan_a.is_recommended is True
    assert plan_b.is_recommended is False
    assert len(plan_a.blocks) > 0
    assert len(plan_b.blocks) > 0
