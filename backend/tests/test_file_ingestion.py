"""
Integration tests for PDF and DOCX document ingestion without auth.
"""
import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db

client = TestClient(app)
SAMPLE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sample_documents"))


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    client.delete("/api/v1/requests")
    yield


def test_ingest_sample_docx():
    docx_path = os.path.join(SAMPLE_DIR, "Northern_Railway_Maintenance_Circular.docx")
    if not os.path.exists(docx_path):
        pytest.skip("Sample DOCX not found")

    with open(docx_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest",
            files={"file": ("Northern_Railway_Maintenance_Circular.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total_extracted"] > 0
    assert data["application_id"].startswith("APP-")
    assert len(data["candidate_requests"]) > 0
    assert data["candidate_requests"][0]["application_id"] == data["application_id"]


def test_ingest_sample_pdf():
    pdf_path = os.path.join(SAMPLE_DIR, "Western_Railway_Block_Requisition.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip("Sample PDF not found")

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest",
            files={"file": ("Western_Railway_Block_Requisition.pdf", f, "application/pdf")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total_extracted"] > 0
    assert data["application_id"].startswith("APP-")
    assert len(data["candidate_requests"]) > 0