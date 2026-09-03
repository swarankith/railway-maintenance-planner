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
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(maintenance_requests)"))}
            if "retry_count" not in columns:
                connection.execute(text("ALTER TABLE maintenance_requests ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"))
            if "application_id" not in columns:
                connection.execute(text("ALTER TABLE maintenance_requests ADD COLUMN application_id VARCHAR(64)"))

            # Check approval_audits columns
            audit_cols = {row[1] for row in connection.execute(text("PRAGMA table_info(approval_audits)"))}
            if "application_id" not in audit_cols:
                connection.execute(text("ALTER TABLE approval_audits ADD COLUMN application_id VARCHAR(64)"))


def get_db():
    """FastAPI Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
