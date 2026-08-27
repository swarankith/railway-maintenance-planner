"""
Ingestion API Endpoint: POST /api/v1/ingest
Accepts PDF/DOCX/TXT file uploads, extracts requests, normalizes fields, and flags incomplete records.
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

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


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a maintenance work request document (PDF or DOCX).
    Extracts text/tables, normalizes fields to canonical schema, and flags missing fields as Needs-Review.
    """
    try:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        doc_content = extract_document(content_bytes, file.filename)
        ingest_res = process_document_content(doc_content)

        # Persist extracted requests into database
        for req in ingest_res.candidate_requests:
            # Check if request_id already exists, else insert
            existing = db.query(DBMaintenanceRequest).filter(DBMaintenanceRequest.request_id == req.request_id).first()
            if not existing:
                db_req = DBMaintenanceRequest(
                    request_id=req.request_id,
                    department=req.department.value,
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
