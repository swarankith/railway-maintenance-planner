"""
Unit tests for Ingestion and Normalization Layer.
"""
from backend.ingestion.normalizer import (
    normalize_table_data,
    normalize_prose_text,
    detect_department,
    parse_km_range,
    parse_duration_minutes,
)
from backend.models import DepartmentEnum, RequestStatusEnum


def test_table_normalization_complete():
    sample_table = [
        ["Job ID", "Dept", "Corridor", "KM Range", "Work Type", "Duration", "Time Window", "Priority"],
        ["JOB-101", "Engineering", "NDLS-GZB", "KM 14.5 to 22.0", "Track Tamping", "3 hours", "01:00 to 04:00", "1"],
        ["JOB-102", "Electrical", "NDLS-GZB", "KM 15.0 - 20.0", "OHE Inspection", "2h 30m", "01:30 to 04:00", "2"],
    ]

    reqs = normalize_table_data(sample_table, "test_file.docx")
    assert len(reqs) == 2
    assert reqs[0].request_id == "JOB-101"
    assert reqs[0].department == DepartmentEnum.ENGINEERING
    assert reqs[0].corridor == "NDLS-GZB"
    assert reqs[0].km_start == 14.5
    assert reqs[0].km_end == 22.0
    assert reqs[0].duration_minutes == 180
    assert reqs[0].priority == 1
    assert reqs[0].status == RequestStatusEnum.CONFIRMED


def test_table_normalization_incomplete_needs_review():
    """Incomplete record with missing corridor and KM range flagged as Needs-Review (Rule 8)."""
    incomplete_table = [
        ["Job ID", "Dept", "Corridor", "KM Range", "Work Type", "Duration", "Time Window"],
        ["JOB-INC", "Engineering", "", "", "Rail Grinding", "2 hours", "02:00 to 04:00"],
    ]

    reqs = normalize_table_data(incomplete_table, "incomplete.pdf")
    assert len(reqs) == 1
    req = reqs[0]
    assert req.status == RequestStatusEnum.NEEDS_REVIEW
    assert "corridor" in req.missing_fields
    assert "km_start" in req.missing_fields


def test_prose_extraction():
    prose_sample = """
    Department of Signal & Telecom requests maintenance window for Point Machine Replacement on corridor AGC-JHS between KM 45.0 and 52.5 from 02:00 to 04:30 IST using S&T Testing Team. Urgent priority required.
    """
    reqs, trains = normalize_prose_text(prose_sample, "memo.docx")
    assert len(reqs) >= 1
    r = reqs[0]
    assert r.department == DepartmentEnum.ST
    assert "AGC-JHS" in r.corridor
    assert r.km_start == 45.0
    assert r.km_end == 52.5
    assert r.duration_minutes == 150
