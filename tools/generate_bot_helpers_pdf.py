"""Build BOT_HELPERS.pdf from BOT_HELPERS.md using ReportLab."""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "BOT_HELPERS.md"
OUTPUT = ROOT / "BOT_HELPERS.pdf"


def _escape(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)


def build_pdf() -> None:
    """Convert the reference's headings, paragraphs, lists, tables and code."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DocTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=27, alignment=TA_CENTER, textColor=colors.HexColor("#203649"),
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="Section", parent=styles["Heading2"], fontSize=15, leading=19,
        textColor=colors.HexColor("#203649"), spaceBefore=11, spaceAfter=5,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="BodyCopy", parent=styles["BodyText"], fontSize=9.5, leading=13,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BulletCopy", parent=styles["BodyCopy"], leftIndent=14, firstLineIndent=-8,
        bulletIndent=1, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="SmallTable", parent=styles["BodyText"], fontSize=7.4, leading=9.2,
    ))
    styles.add(ParagraphStyle(
        name="CodeBlock", parent=styles["Code"], fontName="Courier", fontSize=8.2,
        leading=10.3, leftIndent=8, rightIndent=8, borderColor=colors.HexColor("#dbe2e8"),
        borderWidth=0.5, borderPadding=6, backColor=colors.HexColor("#f4f6f8"),
        spaceBefore=3, spaceAfter=7,
    ))

    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    story = []
    paragraph: list[str] = []
    code_lines: list[str] = []
    in_code = False
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            story.append(Paragraph(_escape(" ".join(paragraph)), styles["BodyCopy"]))
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            flush_paragraph()
            if in_code:
                story.append(Preformatted("\n".join(code_lines), styles["CodeBlock"]))
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            rows = []
            for table_line in table_lines:
                if re.fullmatch(r"\|[\s:|-]+\|", table_line):
                    continue
                cells = [cell.strip() for cell in table_line.strip("|").split("|")]
                rows.append([Paragraph(_escape(cell), styles["SmallTable"]) for cell in cells])
            table = Table(rows, repeatRows=1, colWidths=[34 * mm, 44 * mm, 50 * mm, 45 * mm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce7ed")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#203649")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#aab8c0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.extend((table, Spacer(1, 7)))
            continue
        if not line.strip():
            flush_paragraph()
            index += 1
            continue
        if line.startswith("# "):
            flush_paragraph()
            story.append(Paragraph(_escape(line[2:]), styles["DocTitle"]))
        elif line.startswith("## "):
            flush_paragraph()
            story.append(Paragraph(_escape(line[3:]), styles["Section"]))
        elif line.startswith("- "):
            flush_paragraph()
            story.append(Paragraph("• " + _escape(line[2:]), styles["BulletCopy"]))
        elif re.match(r"\d+\. ", line):
            flush_paragraph()
            story.append(Paragraph(_escape(line), styles["BulletCopy"]))
        else:
            paragraph.append(line.strip())
        index += 1
    flush_paragraph()

    document = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm, title="Bot helpers",
        author="Chess AI Classroom",
    )
    document.build(story)


if __name__ == "__main__":
    build_pdf()
