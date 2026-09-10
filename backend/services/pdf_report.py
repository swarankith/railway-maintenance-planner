"""
Approval Report PDF Generator (Part F).
Generates an authoritative PDF report for a schedule using ReportLab:
- Header: "Indian Railways — Maintenance Block Approval Report"
- Schedule ID, Approver Role + Name, Timestamp (IST)
- Section 1: Approved Requests (or "No approved requests in this schedule.")
- Section 2: Non-Approved Requests
- Footer: "Prototype — human approval only. Not an operational authorization."
"""
import io
from datetime import datetime
from typing import Dict, Any, Optional, List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from backend.config import APP_TIMEZONE


def generate_approval_report_pdf(
    schedule_id: str,
    plan_data: Dict[str, Any],
    approver_role: str = "—",
    approver_name: str = "—",
    approval_time: Optional[datetime] = None
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#000080")
    )
    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#333333")
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#FF9933")
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#222222")
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#000080")
    )
    header_cell = ParagraphStyle(
        "HeaderCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.white
    )
    footer_style = ParagraphStyle(
        "FooterText",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#666666"),
        alignment=1  # Centered
    )

    story = []

    # Title & Header
    story.append(Paragraph("Indian Railways — Maintenance Block Approval Report", title_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#FF9933"), spaceAfter=8))

    time_str = (approval_time or datetime.now(APP_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S IST")
    meta_text = (
        f"<b>Schedule ID:</b> {schedule_id} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Approver:</b> {approver_name} ({approver_role}) &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Timestamp:</b> {time_str}"
    )
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 12))

    blocks = plan_data.get("blocks", [])
    decisions = plan_data.get("decisions", [])

    # Map decisions by request_id
    dec_map = {d.get("request_id"): d for d in decisions}

    # Section 1: Approved Requests
    story.append(Paragraph("Section 1 — Approved Maintenance Requests", h2_style))
    story.append(Spacer(1, 6))

    approved_rows = []
    # Header
    approved_rows.append([
        Paragraph("Request ID", header_cell),
        Paragraph("Corridor & KM", header_cell),
        Paragraph("Work Nature", header_cell),
        Paragraph("Window (IST)", header_cell),
        Paragraph("Bundling / Safety Rationale", header_cell)
    ])

    approved_count = 0
    for blk in blocks:
        scheduled_window = f"{blk.get('scheduled_start', '')[11:16]} - {blk.get('scheduled_end', '')[11:16]}"
        b_expl = blk.get("bundling_explanation") or "Approved in synchronized corridor maintenance block."
        for req in blk.get("requests", []):
            approved_count += 1
            km_span = f"KM {req.get('km_start', 0):.1f} - {req.get('km_end', 0):.1f}"
            approved_rows.append([
                Paragraph(str(req.get("request_id", "")), cell_bold),
                Paragraph(f"{req.get('corridor', '')}<br/>{km_span}", cell_style),
                Paragraph(f"{req.get('department', '')}<br/>{req.get('work_type', '')}", cell_style),
                Paragraph(f"{scheduled_window}<br/>{req.get('duration_minutes', 0)} mins", cell_style),
                Paragraph(b_expl, cell_style)
            ])

    if approved_count == 0:
        # Part F requirement: single row
        approved_rows.append([
            Paragraph("No approved requests in this schedule.", cell_style),
            Paragraph("—", cell_style),
            Paragraph("—", cell_style),
            Paragraph("—", cell_style),
            Paragraph("—", cell_style)
        ])

    t1 = Table(approved_rows, colWidths=[1.1 * inch, 1.2 * inch, 1.4 * inch, 1.1 * inch, 2.7 * inch])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#000080")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t1)
    story.append(Spacer(1, 14))

    # Section 2: Non-Approved Requests
    story.append(Paragraph("Section 2 — Non-Approved Requests (Isolated / Deferred / Manual Review)", h2_style))
    story.append(Spacer(1, 6))

    non_approved_decisions = [d for d in decisions if d.get("final_status") != "Approved"]
    non_approved_rows = []
    non_approved_rows.append([
        Paragraph("Request ID", header_cell),
        Paragraph("Status", header_cell),
        Paragraph("Priority", header_cell),
        Paragraph("Retry #", header_cell),
        Paragraph("Operational Infeasibility / Conflict Reason", header_cell)
    ])

    if not non_approved_decisions:
        non_approved_rows.append([
            Paragraph("None", cell_style),
            Paragraph("—", cell_style),
            Paragraph("—", cell_style),
            Paragraph("—", cell_style),
            Paragraph("All candidate maintenance requests were successfully approved.", cell_style)
        ])
    else:
        for d in non_approved_decisions:
            reason = d.get("reason") or "Reason not available"
            prio_label = f"P{d.get('priority', 3)}"
            non_approved_rows.append([
                Paragraph(str(d.get("request_id", "")), cell_bold),
                Paragraph(str(d.get("final_status", "")), cell_style),
                Paragraph(prio_label, cell_style),
                Paragraph(str(d.get("retry_count", 0)), cell_style),
                Paragraph(reason, cell_style)
            ])

    t2 = Table(non_approved_rows, colWidths=[1.1 * inch, 1.2 * inch, 0.7 * inch, 0.6 * inch, 3.9 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#000080")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 16))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC"), spaceAfter=6))
    story.append(Paragraph("Prototype — human approval only. Not an operational authorization.", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
