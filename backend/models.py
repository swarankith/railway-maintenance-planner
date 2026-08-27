"""
Canonical Data Models, Pydantic Schemas, and SQLAlchemy Database Entities.
All timestamps are timezone-aware (IST, Asia/Kolkata, UTC+5:30).
"""
import uuid
import json
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Date, Text, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

from backend.config import APP_TIMEZONE

Base = declarative_base()


class DepartmentEnum(str, Enum):
    ENGINEERING = "Engineering"
    ST = "S&T"
    ELECTRICAL = "Electrical"
    OPERATIONS = "Operations"
    OTHER = "Other"


class BlockTypeEnum(str, Enum):
    NORMAL = "Normal"
    EMERGENCY = "Emergency"
    PLANNED = "Planned"


class RequestStatusEnum(str, Enum):
    INGESTED = "Ingested"
    NEEDS_REVIEW = "Needs-Review"
    CONFIRMED = "Confirmed"
    OPTIMIZED = "Optimized"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class ConflictTypeEnum(str, Enum):
    SPATIAL_TIME_KM = "SpatialTimeKM"
    RESOURCE_OVERLAP = "ResourceOverlap"
    TRAIN_MOVEMENT_CONFLICT = "TrainMovementConflict"
    DEPARTMENT_INCOMPATIBILITY = "DepartmentIncompatibility"


class PlanStatusEnum(str, Enum):
    GENERATED = "Generated"
    APPROVED = "Approved"
    REJECTED = "Rejected"


# ==========================================
# Pydantic Canonical Schemas
# ==========================================

class MaintenanceRequestBase(BaseModel):
    request_id: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:6].upper()}")
    department: DepartmentEnum = DepartmentEnum.ENGINEERING
    corridor: str
    km_start: float
    km_end: float
    asset: str
    work_type: str
    priority: int = Field(default=3, ge=1, le=5, description="1=Highest urgency, 5=Lowest urgency")
    priority_reason: Optional[str] = None
    block_type: BlockTypeEnum = BlockTypeEnum.NORMAL
    duration_minutes: int = Field(gt=0, description="Required block duration in minutes")
    earliest_start: datetime
    latest_end: datetime
    due_date: Optional[date] = None
    required_resources: List[str] = Field(default_factory=list)
    isolation_requirement: Optional[str] = "None"
    block_shared_allowed: bool = True
    dependencies: List[str] = Field(default_factory=list)
    status: RequestStatusEnum = RequestStatusEnum.INGESTED
    source_document: str = "manual_entry"
    missing_fields: List[str] = Field(default_factory=list)
    validation_notes: Optional[str] = None

    @field_validator("earliest_start", "latest_end", mode="before")
    def ensure_timezone_aware(cls, v):
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError(f"Invalid datetime format: {v}")

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=APP_TIMEZONE)
        else:
            dt = dt.astimezone(APP_TIMEZONE)
        return dt

    @field_validator("km_end")
    def validate_km_range(cls, v, values):
        if "km_start" in values.data and v < values.data["km_start"]:
            # Swap if inverted or adjust
            pass
        return v


class MaintenanceRequestCreate(BaseModel):
    request_id: Optional[str] = None
    department: DepartmentEnum
    corridor: str
    km_start: float
    km_end: float
    asset: str
    work_type: str
    priority: int = 3
    priority_reason: Optional[str] = None
    block_type: BlockTypeEnum = BlockTypeEnum.NORMAL
    duration_minutes: int
    earliest_start: datetime
    latest_end: datetime
    due_date: Optional[date] = None
    required_resources: List[str] = Field(default_factory=list)
    isolation_requirement: Optional[str] = "None"
    block_shared_allowed: bool = True
    dependencies: List[str] = Field(default_factory=list)
    status: RequestStatusEnum = RequestStatusEnum.CONFIRMED
    source_document: str = "manual_entry"


class MaintenanceRequestUpdate(BaseModel):
    department: Optional[DepartmentEnum] = None
    corridor: Optional[str] = None
    km_start: Optional[float] = None
    km_end: Optional[float] = None
    asset: Optional[str] = None
    work_type: Optional[str] = None
    priority: Optional[int] = None
    priority_reason: Optional[str] = None
    block_type: Optional[BlockTypeEnum] = None
    duration_minutes: Optional[int] = None
    earliest_start: Optional[datetime] = None
    latest_end: Optional[datetime] = None
    due_date: Optional[date] = None
    required_resources: Optional[List[str]] = None
    isolation_requirement: Optional[str] = None
    block_shared_allowed: Optional[bool] = None
    dependencies: Optional[List[str]] = None
    status: Optional[RequestStatusEnum] = None
    validation_notes: Optional[str] = None


class MaintenanceRequest(MaintenanceRequestBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TrainMovement(BaseModel):
    train_id: str
    corridor: str
    departure_time: datetime
    arrival_time: datetime
    km_start: float
    km_end: float
    train_type: str = "Express"
    source_document: Optional[str] = "manual"

    @field_validator("departure_time", "arrival_time", mode="before")
    def ensure_tz(cls, v):
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError(f"Invalid datetime format: {v}")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=APP_TIMEZONE)
        return dt.astimezone(APP_TIMEZONE)


class ConflictDetail(BaseModel):
    conflict_id: str = Field(default_factory=lambda: f"CONF-{uuid.uuid4().hex[:6].upper()}")
    conflict_type: ConflictTypeEnum
    severity: str = "Hard"  # Hard, Warning, ReviewRequired
    request_ids: List[str]
    corridor: Optional[str] = None
    time_overlap_start: Optional[datetime] = None
    time_overlap_end: Optional[datetime] = None
    km_overlap_start: Optional[float] = None
    km_overlap_end: Optional[float] = None
    resource_involved: Optional[str] = None
    train_id_involved: Optional[str] = None
    explanation: str
    suggested_resolution: str


class MaintenanceBlock(BaseModel):
    block_id: str = Field(default_factory=lambda: f"BLK-{uuid.uuid4().hex[:6].upper()}")
    corridor: str
    scheduled_start: datetime
    scheduled_end: datetime
    duration_minutes: int
    km_start: float
    km_end: float
    request_ids: List[str]
    departments: List[str]
    resources_allocated: List[str] = Field(default_factory=list)
    isolation_applied: Optional[str] = "None"
    utilization_score: float = 100.0  # %
    time_saved_minutes: int = 0
    bundling_explanation: str
    requests: List[MaintenanceRequest] = Field(default_factory=list)


class SchedulePlan(BaseModel):
    schedule_id: str = Field(default_factory=lambda: f"SCHED-{uuid.uuid4().hex[:8].upper()}")
    plan_name: str
    is_recommended: bool = True
    blocks: List[MaintenanceBlock] = Field(default_factory=list)
    unassigned_requests: List[str] = Field(default_factory=list)
    infeasibility_reasons: List[str] = Field(default_factory=list)
    total_corridor_downtime_minutes: int = 0
    total_jobs_completed: int = 0
    total_jobs_requested: int = 0
    bundling_efficiency_percentage: float = 0.0
    summary_explanation: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(APP_TIMEZONE))
    status: PlanStatusEnum = PlanStatusEnum.GENERATED
    approved_by: Optional[str] = None
    approval_role: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    approval_notes: Optional[str] = None


class ApprovalRequest(BaseModel):
    role: str = Field(default="Chief Controller", description="Planner / Operations Manager / Chief Controller")
    user_name: str = Field(default="Senior Traffic Controller")
    notes: Optional[str] = "Approved after reviewing corridor availability and bundling explanations."


class RejectionRequest(BaseModel):
    role: str = Field(default="Chief Controller")
    user_name: str = Field(default="Senior Traffic Controller")
    reason: str = Field(..., description="Mandatory reason for rejection")


class IngestResponse(BaseModel):
    filename: str
    total_extracted: int
    confirmed_count: int
    needs_review_count: int
    candidate_requests: List[MaintenanceRequest]
    detected_trains: List[TrainMovement] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ==========================================
# SQLAlchemy Persistence Tables
# ==========================================

class DBMaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), unique=True, index=True, nullable=False)
    department = Column(String(32), nullable=False)
    corridor = Column(String(64), index=True, nullable=False)
    km_start = Column(Float, nullable=False)
    km_end = Column(Float, nullable=False)
    asset = Column(String(128), nullable=False)
    work_type = Column(String(128), nullable=False)
    priority = Column(Integer, nullable=False, default=3)
    priority_reason = Column(Text, nullable=True)
    block_type = Column(String(32), nullable=False, default="Normal")
    duration_minutes = Column(Integer, nullable=False)
    earliest_start = Column(DateTime(timezone=True), nullable=False)
    latest_end = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(Date, nullable=True)
    required_resources = Column(JSON, nullable=False, default=list)
    isolation_requirement = Column(String(64), nullable=True, default="None")
    block_shared_allowed = Column(Boolean, nullable=False, default=True)
    dependencies = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="Ingested")
    source_document = Column(String(255), nullable=False, default="manual_entry")
    missing_fields = Column(JSON, nullable=False, default=list)
    validation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(APP_TIMEZONE))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(APP_TIMEZONE), onupdate=lambda: datetime.now(APP_TIMEZONE))


class DBTrainMovement(Base):
    __tablename__ = "train_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    train_id = Column(String(64), index=True, nullable=False)
    corridor = Column(String(64), index=True, nullable=False)
    departure_time = Column(DateTime(timezone=True), nullable=False)
    arrival_time = Column(DateTime(timezone=True), nullable=False)
    km_start = Column(Float, nullable=False)
    km_end = Column(Float, nullable=False)
    train_type = Column(String(64), nullable=False, default="Express")
    source_document = Column(String(255), nullable=True)


class DBSchedulePlan(Base):
    __tablename__ = "schedule_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(String(64), unique=True, index=True, nullable=False)
    plan_name = Column(String(128), nullable=False)
    is_recommended = Column(Boolean, default=True)
    status = Column(String(32), default="Generated")
    plan_data = Column(JSON, nullable=False)  # Full JSON payload of SchedulePlan
    approved_by = Column(String(128), nullable=True)
    approval_role = Column(String(128), nullable=True)
    approval_timestamp = Column(DateTime(timezone=True), nullable=True)
    approval_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(APP_TIMEZONE))


class DBApprovalAudit(Base):
    __tablename__ = "approval_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(String(64), index=True, nullable=False)
    action = Column(String(32), nullable=False)  # APPROVED or REJECTED
    role = Column(String(128), nullable=False)
    user_name = Column(String(128), nullable=False)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(APP_TIMEZONE))
