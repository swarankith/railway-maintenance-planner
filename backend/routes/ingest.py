"""
Ingestion API Endpoint: POST /api/v1/ingest
Accepts PDF/DOCX/TXT file uploads, extracts requests, normalizes fields, assigns Application ID, and flags incomplete records.
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import re
import uuid

from backend.database import get_db
from backend.models import (
    MaintenanceRequest,
    IngestResponse,
    DBMaintenanceRequest,
    DBTrainMovement,
    DBUser,
    RequestStatusEnum,
)
from backend.auth import get_current_user
from backend.ingestion.extractor import extract_document
from backend.ingestion.normalizer import process_document_content

router = APIRouter(prefix="/api/v1", tags=["Ingestion"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a maintenance work request document (PDF or DOCX).
    Assigns unique Application ID (APP-YYYYMMDD-XXXXXX).
    Extracts text/tables, normalizes fields to canonical schema, and flags missing fields as Needs-Review.
    """
    try:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        doc_content = extract_document(content_bytes, file.filename)
        ingest_res = process_document_content(doc_content)

        # Persist extracted requests into database safely
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

            existing = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == req.request_id).first()
            if existing:
                existing.application_id = req.application_id or ingest_res.application_id
                existing.department = str(req.department)
                existing.corridor = req.corridor
                existing.km_start = req.km_start
                existing.km_end = req.km_end
                existing.asset = req.asset
                existing.work_type = req.work_type
                existing.priority = req.priority
                existing.priority_reason = req.priority_reason
                existing.block_type = req.block_type.value
                existing.duration_minutes = req.duration_minutes
                existing.earliest_start = req.earliest_start
                existing.latest_end = req.latest_end
                existing.due_date = req.due_date
                existing.required_resources = req.required_resources
                existing.isolation_requirement = req.isolation_requirement
                existing.block_shared_allowed = req.block_shared_allowed
                existing.dependencies = req.dependencies
                existing.status = req.status.value
                existing.source_document = req.source_document
                existing.missing_fields = req.missing_fields
                existing.validation_notes = req.validation_notes
            else:
                db_req = DBMaintenanceRequest(
                    request_id=req.request_id,
                    application_id=req.application_id or ingest_res.application_id,
                    department=str(req.department),
                    corridor=req.corridor,
                    km_start=req.km_start,
                    km_end=req.km_end,
                    asset=req.asset,
                    work_type=req.work_type,
                    priority=req.priority,
                    priority_reason=req.priority_reason,
                    block_type=req.block_type.value,
                    duration_minutes=req.duration_minutes,
                    earliest_start=req.earliest_start,
                    latest_end=req.latest_end,
                    due_date=req.due_date,
                    required_resources=req.required_resources,
                    isolation_requirement=req.isolation_requirement,
                    block_shared_allowed=req.block_shared_allowed,
                    dependencies=req.dependencies,
                    status=req.status.value,
                    source_document=req.source_document,
                    missing_fields=req.missing_fields,
                    validation_notes=req.validation_notes
                )
                db.add(db_req)

        # Persist detected train movements
        for train in ingest_res.detected_trains:
            existing_train = db.query(DBTrainMovement).filter(
                DBTrainMovement.train_id == train.train_id,
                DBTrainMovement.corridor == train.corridor,
                DBTrainMovement.departure_time == train.departure_time
            ).first()
            if not existing_train:
                db_train = DBTrainMovement(
                    train_id=train.train_id,
                    corridor=train.corridor,
                    departure_time=train.departure_time,
                    arrival_time=train.arrival_time,
                    km_start=train.km_start,
                    km_end=train.km_end,
                    train_type=train.train_type,
                    source_document=train.source_document
                )
                db.add(db_train)

        db.commit()
        return ingest_res

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {str(e)}")
