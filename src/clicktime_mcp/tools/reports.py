import calendar
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from clicktime_mcp.client import ClickTimeClient
from clicktime_mcp.config import REPORT_OUTPUT_DIR


async def get_weekly_summary(client: ClickTimeClient) -> str:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    date_from, date_to = monday.isoformat(), sunday.isoformat()

    entries = await client.get_all(
        "/Me/TimeEntries",
        params={"startDate": date_from, "endDate": date_to, "verbose": "true"},
    )

    if not entries:
        return f"No entries for the week of {date_from}."

    by_job: dict = defaultdict(float)
    by_day: dict = defaultdict(float)
    for e in entries:
        job = (e.get("Job") or {}).get("Name") or e.get("JobID") or "Unknown"
        by_job[job] += float(e.get("Hours", 0))
        by_day[e.get("Date", "")] += float(e.get("Hours", 0))

    total = sum(by_day.values())
    lines = [f"Weekly summary  {date_from} → {date_to}\n", f"Total: {total:.2f}h\n"]

    lines.append("By project:")
    for job, hours in sorted(by_job.items(), key=lambda x: -x[1]):
        lines.append(f"  {job:<40}  {hours:.2f}h")

    lines.append("\nBy day:")
    for d in sorted(by_day):
        bar = "█" * int(by_day[d] * 2)
        lines.append(f"  {d}  {by_day[d]:5.2f}h  {bar}")

    return "\n".join(lines)


async def get_monthly_report(
    client: ClickTimeClient,
    year: int,
    month: int,
    output_path: Optional[str] = None,
) -> str:
    last_day = calendar.monthrange(year, month)[1]
    date_from = f"{year}-{month:02d}-01"
    date_to = f"{year}-{month:02d}-{last_day:02d}"

    me = await client.get("/Me")
    me_data = me.get("data", me) if isinstance(me, dict) else me
    # ClickTime returns name as "LastName, FirstName" in the Name field
    user_name = me_data.get("Name", "Unknown User")

    entries = await client.get_all(
        "/Me/TimeEntries",
        params={"startDate": date_from, "endDate": date_to, "verbose": "true"},
    )

    if output_path is None:
        os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
        month_label = datetime(year, month, 1).strftime("%B_%Y")
        output_path = os.path.join(REPORT_OUTPUT_DIR, f"clicktime_report_{month_label}.pdf")

    _build_pdf(entries, user_name, year, month, output_path)

    total = sum(float(e.get("Hours", 0)) for e in entries)
    month_name = datetime(year, month, 1).strftime("%B %Y")
    return (
        f"Report generated: {output_path}\n"
        f"Period: {month_name}\n"
        f"Total hours: {total:.2f}h  |  Entries: {len(entries)}"
    )


def _build_pdf(entries: list, user_name: str, year: int, month: int, output_path: str) -> None:
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak,
    )

    # ── Palette ──────────────────────────────────────────────────────────────
    NAVY       = HexColor("#1a1a2e")
    LIGHT_GRAY = HexColor("#f5f5f5")
    MID_GRAY   = HexColor("#cccccc")
    DARK_GRAY  = HexColor("#e0e0e0")
    WHITE      = white

    month_name = datetime(year, month, 1).strftime("%B %Y")

    # ── Styles ───────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "RTitle", fontSize=20, fontName="Helvetica-Bold",
        textColor=NAVY, spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "RSubtitle", fontSize=11, fontName="Helvetica",
        textColor=HexColor("#555555"), spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "RSection", fontSize=13, fontName="Helvetica-Bold",
        textColor=NAVY, spaceBefore=14, spaceAfter=6,
    )
    # Cell styles used inside tables — Paragraph objects respect column width
    cell_normal = ParagraphStyle(
        "CellNormal", fontSize=9, fontName="Helvetica",
        textColor=HexColor("#222222"), leading=12,
    )
    cell_bold = ParagraphStyle(
        "CellBold", fontSize=9, fontName="Helvetica-Bold",
        textColor=HexColor("#222222"), leading=12,
    )
    cell_center = ParagraphStyle(
        "CellCenter", fontSize=9, fontName="Helvetica",
        textColor=HexColor("#222222"), leading=12, alignment=TA_CENTER,
    )
    cell_header = ParagraphStyle(
        "CellHeader", fontSize=9, fontName="Helvetica-Bold",
        textColor=WHITE, leading=12,
    )
    cell_header_center = ParagraphStyle(
        "CellHeaderCenter", fontSize=9, fontName="Helvetica-Bold",
        textColor=WHITE, leading=12, alignment=TA_CENTER,
    )

    def p(text: str, style: ParagraphStyle) -> Paragraph:
        """Wrap text in a Paragraph so ReportLab respects column width."""
        return Paragraph(str(text) if text else "", style)

    # ── Document — portrait for the summary, landscape for the detail ────────
    # We use a single landscape document so the wide detail table fits cleanly.
    # A4 landscape: 297mm × 210mm → usable ≈ 25.7cm after 2cm margins each side.
    PAGE = landscape(A4)
    MARGIN = 2 * cm
    USABLE_W = PAGE[0] - 2 * MARGIN  # ≈ 25.7 cm

    doc = SimpleDocTemplate(
        output_path,
        pagesize=PAGE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    elements: list = []

    # ── Header ───────────────────────────────────────────────────────────────
    elements.append(Paragraph("ClickTime Monthly Report", title_style))
    elements.append(Paragraph(f"{user_name}  —  {month_name}", subtitle_style))
    elements.append(Paragraph(f"Generated on {date.today().isoformat()}", subtitle_style))
    elements.append(Spacer(1, 0.6 * cm))

    # ── Summary by project ───────────────────────────────────────────────────
    by_job: dict = defaultdict(float)
    for e in entries:
        job = (e.get("Job") or {}).get("Name") or e.get("JobID") or "Unknown"
        by_job[job] += float(e.get("Hours", 0))
    total_hours = sum(by_job.values())

    elements.append(Paragraph("Summary by Project", section_style))

    # Summary table: Project(wide) | Hours | %
    sum_col = [14 * cm, 3 * cm, 3 * cm]
    summary_rows = [
        [p("Project", cell_header), p("Hours", cell_header_center), p("%", cell_header_center)]
    ]
    for job, hours in sorted(by_job.items()):
        pct = (hours / total_hours * 100) if total_hours else 0
        summary_rows.append([
            p(job, cell_normal),
            p(f"{hours:.2f}", cell_center),
            p(f"{pct:.1f}%", cell_center),
        ])
    summary_rows.append([
        p("TOTAL", cell_bold),
        p(f"{total_hours:.2f}", cell_center),
        p("100%", cell_center),
    ])

    summary_table = Table(summary_rows, colWidths=sum_col)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  NAVY),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -2), [LIGHT_GRAY, WHITE]),
        ("BACKGROUND",    (0, -1), (-1, -1), DARK_GRAY),
        ("GRID",          (0, 0),  (-1, -1), 0.5, MID_GRAY),
        ("TOPPADDING",    (0, 0),  (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 6),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 8),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.6 * cm))

    # ── Detail table ─────────────────────────────────────────────────────────
    # Columns: Date | Job | Phase | SubPhase | Task | Hours | Notes
    # Total = USABLE_W ≈ 25.7cm
    # Date(2.2) + Job(4.5) + Phase(4.5) + SubPhase(3.5) + Task(3.0) + Hours(1.5) + Notes(6.5) = 25.7
    det_col = [2.2*cm, 4.5*cm, 4.5*cm, 3.5*cm, 3.0*cm, 1.5*cm, 6.5*cm]

    elements.append(Paragraph("Daily Detail", section_style))

    detail_rows = [[
        p("Date",     cell_header),
        p("Job",      cell_header),
        p("Phase",    cell_header),
        p("SubPhase", cell_header),
        p("Task",     cell_header),
        p("Hrs",      cell_header_center),
        p("Notes",    cell_header),
    ]]

    for e in sorted(entries, key=lambda x: x.get("Date", "")):
        job      = (e.get("Job")      or {}).get("Name") or e.get("JobID")      or ""
        phase    = (e.get("Phase")    or {}).get("Name") or ""
        subphase = (e.get("SubPhase") or {}).get("Name") or ""
        task     = (e.get("Task")     or {}).get("Name") or e.get("TaskID")     or ""
        notes    = e.get("Comment") or ""
        hours    = float(e.get("Hours", 0))

        detail_rows.append([
            p(e.get("Date", ""), cell_normal),
            p(job,      cell_normal),
            p(phase,    cell_normal),
            p(subphase, cell_normal),
            p(task,     cell_normal),
            p(f"{hours:.2f}", cell_center),
            p(notes,    cell_normal),
        ])

    detail_table = Table(detail_rows, colWidths=det_col, repeatRows=1)
    detail_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  NAVY),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [LIGHT_GRAY, WHITE]),
        ("GRID",          (0, 0),  (-1, -1), 0.5, MID_GRAY),
        ("TOPPADDING",    (0, 0),  (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 5),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 6),
        ("VALIGN",        (0, 0),  (-1, -1), "TOP"),
    ]))
    elements.append(detail_table)

    doc.build(elements)
