"""DD report → PDF using reportlab."""

import io
from datetime import datetime
from typing import Optional


def build_dd_pdf(task: dict) -> bytes:
    """Render a DD task dict as a formatted PDF. Returns raw bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    # Custom styles
    title_style = ParagraphStyle(
        "DDTitle", parent=styles["Title"],
        fontSize=22, textColor=colors.HexColor("#111827"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DDSubtitle", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#6B7280"),
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#2D4FD6"),
        spaceBefore=12, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#374151"),
        leading=14, spaceAfter=4,
    )
    risk_colors = {
        "critical": "#DC2626",
        "high":     "#EA580C",
        "medium":   "#D97706",
        "ok":       "#16A34A",
        "low":      "#6B7280",
    }

    report = task.get("report") or {}
    request = task.get("request") or {}

    elements = []

    # ── Header ──────────────────────────────────────────────────────────────
    elements.append(Paragraph("Due Diligence Report", title_style))
    target = report.get("target") or request.get("prompt", "")[:60]
    elements.append(Paragraph(f"Target: {target}", subtitle_style))
    elements.append(Paragraph(
        f"Jurisdiction: {report.get('jurisdiction', request.get('jurisdiction', 'JP+US'))}  "
        f"&nbsp;&nbsp;|&nbsp;&nbsp;  Date: {datetime.utcnow().strftime('%Y-%m-%d')}",
        subtitle_style,
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceAfter=8))

    # ── Risk summary table ───────────────────────────────────────────────────
    summary = report.get("summary") or {}
    risk_data = [
        ["Risk Level", "Count"],
        ["Critical", str(summary.get("critical", 0))],
        ["High",     str(summary.get("high", 0))],
        ["Medium",   str(summary.get("medium", 0))],
        ["Low",      str(summary.get("low", 0))],
    ]
    risk_table = Table(risk_data, colWidths=[80 * mm, 40 * mm])
    risk_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("ALIGN",      (1, 0), (1, -1), "CENTER"),
        ("TEXTCOLOR",  (0, 1), (0, 1), colors.HexColor(risk_colors["critical"])),
        ("TEXTCOLOR",  (0, 2), (0, 2), colors.HexColor(risk_colors["high"])),
        ("TEXTCOLOR",  (0, 3), (0, 3), colors.HexColor(risk_colors["medium"])),
    ]))
    elements.append(risk_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Recommendation ────────────────────────────────────────────────────────
    rec = summary.get("recommendation", "")
    if rec:
        elements.append(Paragraph("Executive Recommendation", section_style))
        elements.append(Paragraph(rec, body_style))
        elements.append(Spacer(1, 4 * mm))

    # ── Attorney notes ────────────────────────────────────────────────────────
    notes = task.get("attorney_notes") or ""
    if notes:
        elements.append(Paragraph("Attorney Notes", section_style))
        elements.append(Paragraph(notes, body_style))
        elements.append(Spacer(1, 4 * mm))

    # ── Report sections ───────────────────────────────────────────────────────
    sections = report.get("sections") or []
    for sec in sections:
        elements.append(Paragraph(
            f"§{sec.get('num', '')} — {sec.get('title', '')}",
            section_style,
        ))
        for item in sec.get("items", []):
            status = item.get("status", "ok")
            color_hex = risk_colors.get(status, risk_colors["ok"])
            badge = f'<font color="{color_hex}">[{status.upper()}]</font>'
            text = item.get("text", "")
            elements.append(Paragraph(f"{badge} {text}", body_style))
        elements.append(Spacer(1, 3 * mm))

    # ── Disclaimer ────────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB"), spaceBefore=8))
    elements.append(Paragraph(
        "<i>This report is generated by an AI system for internal research purposes only. "
        "It does not constitute legal advice. All findings must be reviewed and verified by "
        "a licensed attorney before reliance.</i>",
        ParagraphStyle("Disclaimer", parent=body_style, fontSize=8, textColor=colors.HexColor("#9CA3AF")),
    ))

    doc.build(elements)
    return buffer.getvalue()
