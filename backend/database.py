"""
Database session management and schema initialization.
Includes lightweight backwards-compatible migration for SQLite prototype DBs.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from backend.config import DATABASE_URL
from backend.models import Base

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes tables in database and applies lightweight migrations."""
    Base.metadata.create_all(bind=engine)
    
    # Lightweight backwards-compatible migration for existing SQLite DBs
    if "sqlite" in DATABASE_URL:
        with engine.begin() as connection:
            # Check maintenance_requests columns
            req_cols = {row[1] for row in connection.execute(text("PRAGMA table_info(maintenance_requests)"))}
            if "retry_count" not in req_cols:
                connection.execute(text("ALTER TABLE maintenance_requests ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"))
            if "application_id" not in req_cols:
                connection.execute(text("ALTER TABLE maintenance_requests ADD COLUMN application_id VARCHAR(64)"))
            if "document_type" not in req_cols:
                connection.execute(text("ALTER TABLE maintenance_requests ADD COLUMN document_type VARCHAR(32) NOT NULL DEFAULT 'maintenance'"))
            if "confidence_score" not in req_cols:
                connection.execute(text("ALTER TABLE maintenance_requests ADD COLUMN confidence_score FLOAT"))
            if "cycle_id" not in req_cols:
                connection.execute(text("ALTER TABLE maintenance_requests ADD COLUMN cycle_id VARCHAR(64)"))
            if "isolated_at" not in req_cols:
                connection.execute(text("ALTER TABLE maintenance_requests ADD COLUMN isolated_at TIMESTAMP"))

            # Check train_movements columns
            train_cols = {row[1] for row in connection.execute(text("PRAGMA table_info(train_movements)"))}
            if "cycle_id" not in train_cols:
                connection.execute(text("ALTER TABLE train_movements ADD COLUMN cycle_id VARCHAR(64)"))
            if "train_number" not in train_cols:
                connection.execute(text("ALTER TABLE train_movements ADD COLUMN train_number VARCHAR(32)"))
            if "train_name" not in train_cols:
                connection.execute(text("ALTER TABLE train_movements ADD COLUMN train_name VARCHAR(128)"))
            if "speed_kmh" not in train_cols:
                connection.execute(text("ALTER TABLE train_movements ADD COLUMN speed_kmh FLOAT"))

            # Check processing_cycles columns
            cycle_cols = {row[1] for row in connection.execute(text("PRAGMA table_info(processing_cycles)"))}
            if "status" not in cycle_cols:
                connection.execute(text("ALTER TABLE processing_cycles ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'Active'"))

            # Check schedule_plans columns
            plan_cols = {row[1] for row in connection.execute(text("PRAGMA table_info(schedule_plans)"))}
            if "cycle_id" not in plan_cols:
                connection.execute(text("ALTER TABLE schedule_plans ADD COLUMN cycle_id VARCHAR(64)"))

            # Check approval_audits columns
            audit_cols = {row[1] for row in connection.execute(text("PRAGMA table_info(approval_audits)"))}
            if "application_id" not in audit_cols:
                connection.execute(text("ALTER TABLE approval_audits ADD COLUMN application_id VARCHAR(64)"))
            if "cycle_id" not in audit_cols:
                connection.execute(text("ALTER TABLE approval_audits ADD COLUMN cycle_id VARCHAR(64)"))
            if "report_url" not in audit_cols:
                connection.execute(text("ALTER TABLE approval_audits ADD COLUMN report_url VARCHAR(255)"))
    elif "postgresql" in DATABASE_URL:
        with engine.begin() as connection:
            for stmt in [
                "ALTER TABLE IF EXISTS maintenance_requests ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;",
                "ALTER TABLE IF EXISTS maintenance_requests ADD COLUMN IF NOT EXISTS application_id VARCHAR(64);",
                "ALTER TABLE IF EXISTS maintenance_requests ADD COLUMN IF NOT EXISTS document_type VARCHAR(32) NOT NULL DEFAULT 'maintenance';",
                "ALTER TABLE IF EXISTS maintenance_requests ADD COLUMN IF NOT EXISTS confidence_score FLOAT;",
                "ALTER TABLE IF EXISTS maintenance_requests ADD COLUMN IF NOT EXISTS cycle_id VARCHAR(64);",
                "ALTER TABLE IF EXISTS maintenance_requests ADD COLUMN IF NOT EXISTS isolated_at TIMESTAMP WITH TIME ZONE;",
                "ALTER TABLE IF EXISTS train_movements ADD COLUMN IF NOT EXISTS cycle_id VARCHAR(64);",
                "ALTER TABLE IF EXISTS train_movements ADD COLUMN IF NOT EXISTS train_number VARCHAR(32);",
                "ALTER TABLE IF EXISTS train_movements ADD COLUMN IF NOT EXISTS train_name VARCHAR(128);",
                "ALTER TABLE IF EXISTS train_movements ADD COLUMN IF NOT EXISTS speed_kmh FLOAT;",
                "ALTER TABLE IF EXISTS processing_cycles ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'Active';",
                "ALTER TABLE IF EXISTS schedule_plans ADD COLUMN IF NOT EXISTS cycle_id VARCHAR(64);",
                "ALTER TABLE IF EXISTS approval_audits ADD COLUMN IF NOT EXISTS application_id VARCHAR(64);",
                "ALTER TABLE IF EXISTS approval_audits ADD COLUMN IF NOT EXISTS cycle_id VARCHAR(64);",
                "ALTER TABLE IF EXISTS approval_audits ADD COLUMN IF NOT EXISTS report_url VARCHAR(255);"
            ]:
                try:
                    connection.execute(text(stmt))
                except Exception:
                    pass


def get_db():
    """FastAPI Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
