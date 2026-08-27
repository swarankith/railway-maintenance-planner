"""
Tests uploading actual PDF and DOCX documents to the /api/v1/ingest endpoint.
"""
import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import DepartmentEnum, RequestStatusEnum

client = TestClient(app)

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_documents")


def test_ingest_sample_docx():
    docx_path = os.path.join(SAMPLE_DIR, "Northern_Railway_Maintenance_Circular.docx")
    assert os.path.exists(docx_path), "Sample DOCX must exist"

    with open(docx_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest",
            files={"file": ("Northern_Railway_Maintenance_Circular.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total_extracted"] >= 7
    assert data["confirmed_count"] >= 5

    # Verify extracted corridor
    corridors = [r["corridor"] for r in data["candidate_requests"]]
    assert "NDLS-GZB" in corridors
    assert "NDLS-CNB" in corridors

    # Verify detected train movements
    assert len(data["detected_trains"]) >= 1
    assert "12004" in data["detected_trains"][0]["train_id"]


def test_ingest_sample_pdf():
    pdf_path = os.path.join(SAMPLE_DIR, "Western_Railway_Block_Requisition.pdf")
    assert os.path.exists(pdf_path), "Sample PDF must exist"

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest",
            files={"file": ("Western_Railway_Block_Requisition.pdf", f, "application/pdf")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total_extracted"] >= 5

    # Verify Rule 8: incomplete note flagged as Needs-Review
    needs_review = [r for r in data["candidate_requests"] if r["status"] == "Needs-Review"]
    assert len(needs_review) >= 1