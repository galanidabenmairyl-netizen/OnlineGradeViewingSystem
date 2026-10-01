"""Printable NEMSU-style report of grades PDF generation."""
import io
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

NEMSU_BLUE = colors.HexColor("#0B4C87")
NEMSU_GOLD = colors.HexColor("#F2B705")


def build_grade_slip_pdf(student, term, rows, gwa):
    """student: dict with full_name, student_id, program, year_level, section.
    term: (semester, school_year)
    rows: list of dicts with code, name, units, prelim, midterm, finals,
          final_grade, remarks.
    gwa: float or None.
    Returns bytes of the generated PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER, topMargin=0.38 * inch, bottomMargin=0.42 * inch,
        leftMargin=0.45 * inch, rightMargin=0.45 * inch,
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("Small", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=9)
    small_bold = ParagraphStyle("SmallBold", parent=small, fontName="Helvetica-Bold")
    header_style = ParagraphStyle("Header", parent=styles["Normal"], alignment=1, leading=11)

    logo_path = Path(__file__).resolve().parents[1] / "static" / "img" / "logo.jpg"
    logo = Image(str(logo_path), width=0.68 * inch, height=0.68 * inch)
    university_header = [
        Paragraph("<b>NORTH EASTERN MINDANAO STATE UNIVERSITY</b><br/>"
                  "<i>Cantilan Campus</i><br/><i>Cantilan, Surigao del Sur</i><br/><br/>"
                  "<b>Report of Grades</b><br/>"
                  f"SY: {term[1]} &nbsp; Term: {term[0]}", header_style),
    ]
    header_table = Table([[logo, university_header[0]]], colWidths=[1.0 * inch, 5.65 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    last_name, first_name, middle_name = _name_parts(student["full_name"])
    info_data = [
        ["IDNO", student["student_id"], "Last Name", last_name, "First Name", first_name, "Middle Name", middle_name, "Sex", ""],
        ["Course", student["program"], "Year Level", student["year_level"], "GPA", _fmt(gwa), "", "", "", ""],
    ]
    info_table = Table(info_data, colWidths=[0.48*inch, 0.75*inch, 0.58*inch, 0.92*inch, 0.58*inch, 0.98*inch, 0.72*inch, 1.0*inch, 0.3*inch, 0.25*inch])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTNAME", (4, 0), (4, -1), "Helvetica-Bold"),
        ("FONTNAME", (6, 0), (6, 0), "Helvetica-Bold"),
        ("FONTNAME", (8, 0), (8, 0), "Helvetica-Bold"),
        ("FONTNAME", (4, 1), (4, 1), "Helvetica-Bold"),
        ("LINEBELOW", (0, -1), (-1, -1), 0.7, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    header = ["Course No.", "Section", "Descriptive Title", "Time", "Days", "Room", "Grade", "GCompl", "Units"]
    data = [header]
    for r in rows:
        data.append([
            r["code"], "", r["name"], r["meeting_time"] or "", r["meeting_days"] or "",
            "", _fmt(r["final_grade"]), "", _fmt(r["units"], decimals=1),
        ])

    table = Table(data, colWidths=[0.62*inch, 0.48*inch, 2.55*inch, 0.72*inch, 0.42*inch, 0.42*inch, 0.45*inch, 0.52*inch, 0.42*inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "LEFT"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    total_units = sum(float(r["units"] or 0) for r in rows)
    total_table = Table([["", "", "", "", "", "Total Units:", _fmt(total_units, decimals=0)]],
                        colWidths=[0.62*inch, 0.48*inch, 2.55*inch, 0.72*inch, 0.42*inch, 1.39*inch, 0.42*inch])
    total_table.setStyle(TableStyle([("FONTNAME", (5, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("ALIGN", (5, 0), (-1, -1), "RIGHT")]))

    certification = Table([
        ["Certified by :", "RAMONA LIZA A. ESPENIDO, MST-SS", "Printed: " + datetime.now().strftime("%m/%d/%Y %I:%M %p")],
        ["", "Registrar III", ""],
    ], colWidths=[0.85*inch, 3.3*inch, 2.55*inch])
    certification.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (1, 0), (1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    elements = [header_table, Spacer(1, 13), info_table, Spacer(1, 6), table, total_table, Spacer(1, 34), certification]

    doc.build(elements)
    return buf.getvalue()


def _fmt(value, decimals=2):
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}"
    return str(value)


def _name_parts(full_name):
    parts = full_name.split()
    if len(parts) < 2:
        return full_name, "", ""
    return parts[-1], parts[0], " ".join(parts[1:-1])
