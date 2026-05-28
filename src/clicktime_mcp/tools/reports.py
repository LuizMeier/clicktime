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
    # ClickTime returns name as "LastName, FirstName"
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
    """
    Build a Vertical Timesheet PDF that mirrors the ClickTime web export format:
      - Portrait A4
      - One section per calendar day (including weekends with 0.00 Total)
      - Daily total rows + Grand Total on the last row
      - Footer: signature area + "Prepared by ClickTime on <date>" + Page X of Y
    """
    from datetime import date as dt_date

    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    # ── Palette ──────────────────────────────────────────────────────────────
    NAVY       = HexColor("#2d4059")   # column headers + day section headers
    LIGHT_BLUE = HexColor("#eaf0fb")   # alternating entry rows
    TOTAL_BG   = HexColor("#d5e3f5")   # daily total rows
    GRAND_BG   = HexColor("#c8d8ee")   # grand total row
    MID_GRAY   = HexColor("#cccccc")
    DARK_GRAY  = HexColor("#555555")
    WHITE      = white

    # ── Layout constants ─────────────────────────────────────────────────────
    PAGE  = A4                          # portrait 210 × 297 mm
    ML    = 1.5 * cm                    # left margin
    MR    = 1.5 * cm                    # right margin
    MT    = 1.5 * cm                    # top margin
    MB    = 2.8 * cm                    # bottom margin (reserved for footer)
    UW    = PAGE[0] - ML - MR           # usable width ≈ 18.0 cm

    # Date(3.0) + Hours(1.8) + Project/Activity(5.0) + Task(4.2) + Comment(4.0) = 18.0
    col_w = [3.0*cm, 1.8*cm, 5.0*cm, 4.2*cm, 4.0*cm]

    # ── Date helpers ─────────────────────────────────────────────────────────
    month_start  = dt_date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    month_end    = dt_date(year, month, last_day_num)
    range_str    = (
        f"{month_start.strftime('%B %-d %Y')} through "
        f"{month_end.strftime('%B %-d %Y')}"
    )
    today_str = date.today().strftime("%B %-d %Y")

    # ── Group entries by ISO date ─────────────────────────────────────────────
    by_date: dict = defaultdict(list)
    for e in entries:
        d = e.get("Date", "")
        if d:
            by_date[d].append(e)

    grand_total = sum(float(e.get("Hours", 0)) for e in entries)

    # ── Paragraph style helpers ───────────────────────────────────────────────
    def ps(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    title_style  = ps("VTitle",
        fontSize=15, fontName="Helvetica-BoldOblique",
        textColor=NAVY, alignment=TA_CENTER, spaceAfter=2)
    hdr_label    = ps("HLabel",
        fontSize=9, fontName="Helvetica-Bold", textColor=NAVY, leading=13)
    hdr_range    = ps("HRange",
        fontSize=9, fontName="Helvetica", textColor=DARK_GRAY,
        leading=13, alignment=TA_RIGHT)
    cell_hdr     = ps("CHdr",
        fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, leading=11)
    cell_hdr_c   = ps("CHdrC",
        fontSize=8, fontName="Helvetica-Bold", textColor=WHITE,
        leading=11, alignment=TA_CENTER)
    cell_day     = ps("CDay",
        fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, leading=11)
    cell_norm    = ps("CNorm",
        fontSize=8, fontName="Helvetica",
        textColor=HexColor("#222222"), leading=11)
    cell_bold    = ps("CBold",
        fontSize=8, fontName="Helvetica-Bold",
        textColor=HexColor("#222222"), leading=11)
    cell_ctr     = ps("CCtr",
        fontSize=8, fontName="Helvetica",
        textColor=HexColor("#222222"), leading=11, alignment=TA_CENTER)
    cell_bold_c  = ps("CBoldC",
        fontSize=8, fontName="Helvetica-Bold",
        textColor=HexColor("#222222"), leading=11, alignment=TA_CENTER)
    cell_grand   = ps("CGrand",
        fontSize=9, fontName="Helvetica-Bold", textColor=NAVY, leading=12)
    cell_grand_c = ps("CGrandC",
        fontSize=9, fontName="Helvetica-Bold", textColor=NAVY,
        leading=12, alignment=TA_CENTER)

    def p(text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(str(text) if text else "", style)

    # ── NumberedCanvas — defers "Page X of Y" until all pages are known ───────
    class _NumberedCanvas(pdf_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states: list = []

        def showPage(self) -> None:
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            total = len(self._saved_page_states)
            for i, state in enumerate(self._saved_page_states):
                self.__dict__.update(state)
                self._draw_footer(page_num=i + 1, total_pages=total)
                pdf_canvas.Canvas.showPage(self)
            pdf_canvas.Canvas.save(self)

        def _draw_footer(self, page_num: int, total_pages: int) -> None:
            w, _ = self._pagesize
            self.saveState()

            # Thin separator line above footer area
            self.setStrokeColor(MID_GRAY)
            self.setLineWidth(0.4)
            self.line(ML, MB - 0.15 * cm, w - MR, MB - 0.15 * cm)

            # Three signature sections (submitted by / approved by / for accounting use only)
            sec_w  = (w - ML - MR) / 3
            line_y = MB - 0.42 * cm   # underline baseline
            text_y = MB - 0.72 * cm   # label baseline
            self.setFont("Helvetica", 7)
            self.setFillColor(DARK_GRAY)
            labels = ["submitted by", "approved by", "for accounting use only"]
            for i, lbl in enumerate(labels):
                x = ML + i * sec_w
                self.setStrokeColor(MID_GRAY)
                self.line(x + 0.4 * cm, line_y, x + sec_w - 0.3 * cm, line_y)
                self.setFillColor(DARK_GRAY)
                self.drawString(x, text_y, lbl)

            # Bottom: ClickTime branding (left) + page number (right)
            brand_y = MB - 1.25 * cm
            self.setFont("Helvetica", 7)
            self.setFillColor(DARK_GRAY)
            self.drawString(
                ML, brand_y,
                f"Prepared by ClickTime on {today_str}    www.clicktime.com",
            )
            self.drawRightString(
                w - MR, brand_y,
                f"Page {page_num} of {total_pages}",
            )
            self.restoreState()

    # ── Document setup ────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=PAGE,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT,  bottomMargin=MB,
    )
    elements: list = []

    # Title
    elements.append(p("Vertical Timesheet", title_style))
    elements.append(Spacer(1, 0.15 * cm))

    # Header row: user name (left) | date range (right)
    hdr_tbl = Table(
        [[p(user_name, hdr_label), p(range_str, hdr_range)]],
        colWidths=[UW * 0.5, UW * 0.5],
    )
    hdr_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    elements.append(hdr_tbl)
    elements.append(Spacer(1, 0.3 * cm))

    # ── Timesheet table ───────────────────────────────────────────────────────
    # Row 0 is the column header (repeated on every page via repeatRows=1)
    rows: list = [[
        p("Date",             cell_hdr),
        p("Hours",            cell_hdr_c),
        p("Project/Activity", cell_hdr),
        p("Task",             cell_hdr),
        p("Comment",          cell_hdr),
    ]]
    styles: list = [
        ("BACKGROUND",    (0, 0),  (-1, 0),  NAVY),
        ("GRID",          (0, 0),  (-1, -1), 0.4, MID_GRAY),
        ("TOPPADDING",    (0, 0),  (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 4),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 5),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
    ]
    ri = 1  # next row index to write

    # Iterate every calendar day of the month
    for day_n in range(1, last_day_num + 1):
        cur_date    = dt_date(year, month, day_n)
        date_iso    = cur_date.isoformat()
        date_label  = cur_date.strftime("%-m/%-d/%Y")   # e.g. "4/1/2026"
        weekday     = cur_date.strftime("%A")            # e.g. "Wednesday"
        day_entries = by_date.get(date_iso, [])

        # Day section header — spans all columns
        rows.append([p(f"{date_label} - {weekday}", cell_day), "", "", "", ""])
        styles.extend([
            ("BACKGROUND", (0, ri), (-1, ri), NAVY),
            ("SPAN",       (0, ri), (-1, ri)),
        ])
        ri += 1

        # Entry rows (alternating background)
        day_total = 0.0
        for alt_i, e in enumerate(sorted(day_entries, key=lambda x: x.get("Date", ""))):
            job   = (e.get("Job")  or {}).get("Name") or e.get("JobID")  or ""
            task  = (e.get("Task") or {}).get("Name") or e.get("TaskID") or ""
            notes = e.get("Comment") or ""
            hrs   = float(e.get("Hours", 0))
            day_total += hrs

            bg = LIGHT_BLUE if alt_i % 2 == 0 else WHITE
            rows.append([
                p("",           cell_norm),
                p(f"{hrs:.2f}", cell_ctr),
                p(job,          cell_norm),
                p(task,         cell_norm),
                p(notes,        cell_norm),
            ])
            styles.append(("BACKGROUND", (0, ri), (-1, ri), bg))
            ri += 1

        # Daily total row
        rows.append([
            p("",                cell_norm),
            p(f"{day_total:.2f}", cell_bold_c),
            p("Total",           cell_bold),
            p("",                cell_norm),
            p("",                cell_norm),
        ])
        styles.append(("BACKGROUND", (0, ri), (-1, ri), TOTAL_BG))
        ri += 1

    # Grand Total row
    rows.append([
        p("",                             cell_norm),
        p(f"{grand_total:.2f}",           cell_grand_c),
        p(f"Grand Total for {user_name}", cell_grand),
        p("",                             cell_norm),
        p("",                             cell_norm),
    ])
    styles.extend([
        ("BACKGROUND",    (0, ri), (-1, ri), GRAND_BG),
        ("TOPPADDING",    (0, ri), (-1, ri), 6),
        ("BOTTOMPADDING", (0, ri), (-1, ri), 6),
    ])

    main_table = Table(rows, colWidths=col_w, repeatRows=1)
    main_table.setStyle(TableStyle(styles))
    elements.append(main_table)

    doc.build(elements, canvasmaker=_NumberedCanvas)
