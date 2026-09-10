import pytest
from backend.database import init_db, SessionLocal
from backend.models import (
    DBMaintenanceRequest,
    DBTrainMovement,
    DBSchedulePlan,
    DBApprovalAudit,
    DBProcessingCycle,
    DBEscalationEvent,
)

def clear_all_test_data():
    init_db()
    db = SessionLocal()
    try:
        db.query(DBMaintenanceRequest).delete()
        db.query(DBTrainMovement).delete()
        db.query(DBSchedulePlan).delete()
        db.query(DBApprovalAudit).delete()
        db.query(DBProcessingCycle).delete()
        db.query(DBEscalationEvent).delete()
        db.commit()
    finally:
        db.close()

@pytest.fixture(scope="session", autouse=True)
def clean_database_session_lifecycle():
    clear_all_test_data()
    yield
    clear_all_test_data()
