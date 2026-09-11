"""
Ingestion API Endpoint: POST /api/v1/ingest
Accepts PDF/DOCX/TXT file uploads, extracts requests, normalizes fields,
assigns Application ID, and flags incomplete records.

Supports document types: maintenance request, train movement.

Phase 2 Final (v10):
- Postgres-safe string truncation for every string field.
- On re-upload, existing records are UPDATED with cycle_id reset to NULL
  so they re-enter the active pool and become eligible for the next optimizer run.
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import re
import uuid

from backend.database import get_db
from backend.models import (
    MaintenanceRequest,
    IngestResponse,
    DBMaintenanceRequest,
    DBTrainMovement,
    RequestStatusEnum,
)
from backend.ingestion.extractor import extract_document
from backend.ingestion.normalizer import process_document_content

router = APIRouter(prefix="/api/v1", tags=["Ingestion"])


def _safe(value, max_len: int, default: str = "") -> str:
    """
    Safely convert a value to a string and truncate it to fit the DB column
    width. Prevents psycopg2.errors.StringDataRightTruncation on Postgres.
    """
    if value is None:
        return default
    s = str(value)
    return s[:max_len] if len(s) > max_len else s


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    doc_type: Optional[str] = Query(None, enum=["request", "train_movement"]),
    db: Session = Depends(get_db)
):
    """
    Upload a document (PDF or DOCX).
    - doc_type == "request" (default): extract and store maintenance requests.
    - doc_type == "train_movement": extract and store train movements.

    Re-upload behavior:
      If a record already exists (matched by request_id / train_id+corridor+departure),
      it is UPDATED and its cycle_id is reset to NULL, so it re-enters the
      active pool and becomes eligible for the next optimizer run.
    """
    try:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        doc_content = extract_document(content_bytes, file.filename)
        ingest_res = process_document_content(doc_content, doc_type=doc_type)

        # ---------- 1. MAINTENANCE REQUESTS ----------
        if doc_type is None or doc_type == "request":
            seen_ids = set()
            for req in ingest_res.candidate_requests:
                clean_id = re.sub(r"\s+", "", str(req.request_id)).strip() if req.request_id else ""
                if not clean_id:
                    clean_id = f"REQ-{uuid.uuid4().hex[:6].upper()}"

                orig_id = clean_id
                counter = 1
                while clean_id in seen_ids:
                    clean_id = f"{orig_id}_{counter}"
                    counter += 1
                seen_ids.add(clean_id)
                req.request_id = clean_id

                existing = db.query(DBMaintenanceRequest).filter(
                    DBMaintenanceRequest.request_id == clean_id
                ).first()

                app_id = _safe(req.application_id or ingest_res.application_id, 128)

                if existing:
                    # ----- RESET cycle_id so the record becomes eligible again -----
                    existing.cycle_id = None
                    # ----- Refresh all other fields with the latest extraction -----
                    existing.application_id = app_id
                    existing.department = _safe(str(req.department), 64)
                    existing.corridor = _safe(req.corridor, 255)
                    existing.km_start = req.km_start
                    existing.km_end = req.km_end
                    existing.asset = _safe(req.asset, 255)
                    existing.work_type = _safe(req.work_type, 255)
                    existing.priority = req.priority
                    existing.priority_reason = _safe(req.priority_reason, 255)
                    existing.block_type = _safe(req.block_type.value, 32)
                    existing.duration_minutes = req.duration_minutes
                    existing.earliest_start = req.earliest_start
                    existing.latest_end = req.latest_end
                    existing.due_date = req.due_date
                    existing.required_resources = req.required_resources
                    existing.isolation_requirement = _safe(req.isolation_requirement, 128)
                    existing.block_shared_allowed = req.block_shared_allowed
                    existing.dependencies = req.dependencies
                    existing.status = _safe(req.status.value, 32)
                    existing.source_document = _safe(req.source_document, 255)
                    existing.missing_fields = req.missing_fields
                    existing.validation_notes = _safe(req.validation_notes, 500, "")
                    existing.document_type = "maintenance"
                else:
                    new_req = DBMaintenanceRequest(
                        request_id=_safe(clean_id, 128),
                        application_id=app_id,
                        department=_safe(str(req.department), 64),
                        corridor=_safe(req.corridor, 255),
                        km_start=req.km_start,
                        km_end=req.km_end,
                        asset=_safe(req.asset, 255),
                        work_type=_safe(req.work_type, 255),
                        priority=req.priority,
                        priority_reason=_safe(req.priority_reason, 255),
                        block_type=_safe(req.block_type.value, 32),
                        duration_minutes=req.duration_minutes,
                        earliest_start=req.earliest_start,
                        latest_end=req.latest_end,
                        due_date=req.due_date,
                        required_resources=req.required_resources,
                        isolation_requirement=_safe(req.isolation_requirement, 128),
                        block_shared_allowed=req.block_shared_allowed,
                        dependencies=req.dependencies,
                        status=_safe(req.status.value, 32),
                        source_document=_safe(req.source_document, 255),
                        missing_fields=req.missing_fields,
                        validation_notes=_safe(req.validation_notes, 500, ""),
                        document_type="maintenance",
                    )
                    db.add(new_req)

        # ---------- 2. TRAIN MOVEMENTS ----------
        if doc_type == "train_movement":
            for train in ingest_res.detected_trains:
                existing_train = db.query(DBTrainMovement).filter(
                    DBTrainMovement.train_id == train.train_id,
                    DBTrainMovement.corridor == train.corridor,
                    DBTrainMovement.departure_time == train.departure_time,
                ).first()

                if existing_train:
                    # ----- RESET cycle_id so the train becomes eligible again -----
                    existing_train.cycle_id = None
                    # ----- Refresh all other fields with the latest extraction -----
                    existing_train.train_number = _safe(getattr(train, "train_number", None), 64)
                    existing_train.train_name = _safe(getattr(train, "train_name", None), 255)
                    existing_train.speed_kmh = getattr(train, "speed_kmh", None)
                    existing_train.arrival_time = train.arrival_time
                    existing_train.km_start = train.km_start
                    existing_train.km_end = train.km_end
                    existing_train.train_type = _safe(train.train_type, 64)
                    existing_train.source_document = _safe(train.source_document, 255)
                else:
                    db_train = DBTrainMovement(
                        train_id=_safe(train.train_id, 128),
                        train_number=_safe(getattr(train, "train_number", None), 64),
                        train_name=_safe(getattr(train, "train_name", None), 255),
                        speed_kmh=getattr(train, "speed_kmh", None),
                        corridor=_safe(train.corridor, 255),
                        departure_time=train.departure_time,
                        arrival_time=train.arrival_time,
                        km_start=train.km_start,
                        km_end=train.km_end,
                        train_type=_safe(train.train_type, 64),
                        source_document=_safe(train.source_document, 255),
                    )
                    db.add(db_train)

        db.commit()
        return ingest_res

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {str(e)}")
    