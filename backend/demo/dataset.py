"""
In-Memory Demo Dataset for Railway Maintenance Planner (Part L).
This data is hardcoded in memory and is NEVER written to the database.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from backend.config import APP_TIMEZONE
from backend.models import MaintenanceRequest, TrainMovement, BlockTypeEnum, RequestStatusEnum


def get_demo_requests() -> list[MaintenanceRequest]:
    return [
        MaintenanceRequest(
            request_id="REQ-901",
            application_id="APP-DEMO-901",
            corridor="HYD-C1",
            department="Engineering",
            work_type="Rail renewal/replacement",
            earliest_start=datetime(2026, 9, 15, 22, 0, tzinfo=APP_TIMEZONE),
            latest_end=datetime(2026, 9, 16, 2, 0, tzinfo=APP_TIMEZONE),
            priority=1,
            block_type=BlockTypeEnum.NORMAL,
            isolation_requirement="Power & Track Disconnection Applied",
            due_date=datetime(2026, 9, 20).date(),
            km_start=10.0,
            km_end=14.0,
            duration_minutes=240,
            asset="Track Section",
            required_resources=["Flash Butt Welding Plant", "P-Way Gang"],
            block_shared_allowed=True,
            status=RequestStatusEnum.CONFIRMED,
            source_document="in_memory_demo"
        ),
        MaintenanceRequest(
            request_id="REQ-902",
            application_id="APP-DEMO-902",
            corridor="HYD-C1",
            department="S&T",
            work_type="Point machine maintenance/repair",
            earliest_start=datetime(2026, 9, 15, 22, 0, tzinfo=APP_TIMEZONE),
            latest_end=datetime(2026, 9, 16, 2, 0, tzinfo=APP_TIMEZONE),
            priority=2,
            block_type=BlockTypeEnum.NORMAL,
            isolation_requirement="Track Disconnection Applied",
            due_date=datetime(2026, 9, 21).date(),
            km_start=12.0,
            km_end=14.0,
            duration_minutes=240,
            asset="Point Machine 4B",
            required_resources=["S&T Testing Team"],
            block_shared_allowed=True,
            status=RequestStatusEnum.CONFIRMED,
            source_document="in_memory_demo"
        ),
        MaintenanceRequest(
            request_id="REQ-903",
            application_id="APP-DEMO-903",
            corridor="BLR-C1",
            department="Electrical",
            work_type="OHE replacement/repair",
            earliest_start=datetime(2026, 9, 16, 10, 0, tzinfo=APP_TIMEZONE),
            latest_end=datetime(2026, 9, 16, 14, 0, tzinfo=APP_TIMEZONE),
            priority=3,
            block_type=BlockTypeEnum.NORMAL,
            isolation_requirement="Power Block (OHE)",
            due_date=datetime(2026, 9, 22).date(),
            km_start=20.0,
            km_end=24.0,
            duration_minutes=240,
            asset="OHE 25kV Catenary",
            required_resources=["Tower Wagon TW-1", "OHE Maintenance Crew"],
            block_shared_allowed=True,
            status=RequestStatusEnum.CONFIRMED,
            source_document="in_memory_demo"
        ),
        MaintenanceRequest(
            request_id="REQ-904",
            application_id="APP-DEMO-904",
            corridor="HYD-C1",
            department="Engineering",
            work_type="Rail renewal/replacement",
            earliest_start=datetime(2026, 9, 15, 22, 0, tzinfo=APP_TIMEZONE),
            latest_end=datetime(2026, 9, 16, 2, 0, tzinfo=APP_TIMEZONE),
            priority=1,
            block_type=BlockTypeEnum.EMERGENCY,
            isolation_requirement="Power & Track Disconnection Applied",
            due_date=datetime(2026, 9, 15).date(),
            km_start=12.0,
            km_end=13.0,
            duration_minutes=240,
            asset="Track Section",
            required_resources=["P-Way Gang"],
            block_shared_allowed=True,
            status=RequestStatusEnum.CONFIRMED,
            source_document="in_memory_demo"
        ),
    ]


def get_demo_trains() -> list[TrainMovement]:
    return [
        TrainMovement(
            train_id="T-901",
            corridor="HYD-C1",
            departure_time=datetime(2026, 9, 15, 18, 0, tzinfo=APP_TIMEZONE),
            arrival_time=datetime(2026, 9, 15, 20, 0, tzinfo=APP_TIMEZONE),
            km_start=10.0,
            km_end=15.0,
            train_type="Express",
            source_document="in_memory_demo"
        ),
        TrainMovement(
            train_id="T-902",
            corridor="BLR-C1",
            departure_time=datetime(2026, 9, 16, 6, 0, tzinfo=APP_TIMEZONE),
            arrival_time=datetime(2026, 9, 16, 8, 0, tzinfo=APP_TIMEZONE),
            km_start=20.0,
            km_end=25.0,
            train_type="Express",
            source_document="in_memory_demo"
        ),
    ]
