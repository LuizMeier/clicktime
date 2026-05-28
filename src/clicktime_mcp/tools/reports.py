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
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    NAVY = HexColor("#1a1a2e")
    LIGHT_GRAY = HexColor("#f5f5f5")
    MID_GRAY = HexColor("#cccccc")
    DARK_GRAY = HexColor("#e0e0e0")

    month_name = datetime(year, month, 1).strftime("%B %Y")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    title_style = ParagraphStyle(
        "ReportTitle", fontSize=20, fontName="Helvetica-Bold",
        textColor=NAVY, spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", fontSize=11, fontName="Helvetica",
        textColor=HexColor("#555555"), spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "SectionHeader", fontSize=13, fontName="Helvetica-Bold",
        textColor=NAVY, spaceBefore=14, spaceAfter=6,
    )

    elements = []

    elements.append(Paragraph("ClickTime Monthly Report", title_style))
    elements.append(Paragraph(f"{user_name}  —  {month_name}", subtitle_style))
    elements.append(Paragraph(f"Generated on {date.today().isoformat()}", subtitle_style))
    elements.append(Spacer(1, 0.6 * cm))

    # --- Summary by project ---
    by_job: dict = defaultdict(float)
    for e in entries:
        job = (e.get("Job") or {}).get("Name") or e.get("JobID") or "Unknown"
        by_job[job] += float(e.get("Hours", 0))
    total_hours = sum(by_job.values())

    elements.append(Paragraph("Summary by Project", section_style))

    summary_rows = [["Project", "Hours", "%"]]
    for job, hours in sorted(by_job.items()):
        pct = (hours / total_hours * 100) if total_hours else 0
        summary_rows.append([job, f"{hours:.2f}", f"{pct:.1f}%"])
    summary_rows.append(["TOTAL", f"{total_hours:.2f}", "100%"])

    col_widths = [10 * cm, 3 * cm, 3 * cm]
    summary_table = Table(summary_rows, colWidths=col_widths)
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [LIGHT_GRAY, white]),
            ("BACKGROUND", (0, -1), (-1, -1), DARK_GRAY),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4 * cm))

    # --- Daily detail ---
    elements.append(Paragraph("Daily Detail", section_style))

    detail_rows = [["Date", "Project / Phase", "Task", "Hours", "Notes"]]
    for e in sorted(entries, key=lambda x: x.get("Date", "")):
        job = (e.get("Job") or {}).get("Name") or e.get("JobID") or ""
        phase = (e.get("Phase") or {}).get("Name") or ""
        subphase = (e.get("SubPhase") or {}).get("Name") or ""
        project_cell = " › ".join(filter(None, [job, phase, subphase]))
        task = (e.get("Task") or {}).get("Name") or e.get("TaskID") or ""
        detail_rows.append([
            e.get("Date", ""),
            project_cell,
            task,
            f"{float(e.get('Hours', 0)):.2f}",
            e.get("Comment") or "",
        ])

    detail_col_widths = [2.5 * cm, 5 * cm, 3 * cm, 1.5 * cm, 4.5 * cm]
    detail_table = Table(detail_rows, colWidths=detail_col_widths)
    detail_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, white]),
            ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("WORDWRAP", (4, 1), (4, -1), "CJK"),
        ])
    )
    elements.append(detail_table)

    doc.build(elements)
