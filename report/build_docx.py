"""Build report/report.docx from report/draft.md and check the page count.

Supported draft syntax (a small subset of Markdown):
  front matter between '---' lines: title, group, members (one 'name | pct' per line)
  '## Heading'      -> IEEE section heading (Roman numeral, small caps)
  '### Heading'     -> IEEE subsection heading (A., B., italic)
  '- item'          -> bullet
  'Table: caption'  followed by a pipe table -> captioned table
  '![caption](path)' -> figure 3.5 in wide with 'Fig. n.' caption
  '**bold**', '*italic*' inline
  '[n] text' lines under '## References' -> reference list
Usage: python report/build_docx.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "report" / "draft.md"
OUT = ROOT / "report" / "report.docx"
FONT = "Times New Roman"
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")


def set_font(run, size: float, bold=False, italic=False, small_caps=False) -> None:
    """Apply Times New Roman at a size to a run."""
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.small_caps = small_caps


def add_inline(par, text: str, size: float = 10, italic_all=False) -> None:
    """Add text with **bold** and *italic* spans to a paragraph."""
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text):
        if not part:
            continue
        if part.startswith("**"):
            set_font(par.add_run(part[2:-2]), size, bold=True, italic=italic_all)
        elif part.startswith("*"):
            set_font(par.add_run(part[1:-1]), size, italic=True)
        else:
            set_font(par.add_run(part), size, italic=italic_all)


def fmt(par, before=0, after=2, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.0, line=1.0):
    """Set paragraph spacing and alignment."""
    pf = par.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    pf.first_line_indent = Inches(indent) if indent else None
    par.alignment = align


def set_columns(section, num: int, space_in: float = 0.25) -> None:
    """Set the number of text columns of a section."""
    sect = section._sectPr
    cols = sect.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sect.append(cols)
    cols.set(qn("w:num"), str(num))
    cols.set(qn("w:space"), str(int(space_in * 1440)))


def page_setup(section) -> None:
    """US Letter with IEEE conference margins."""
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin, section.bottom_margin = Inches(0.75), Inches(1.0)
    section.left_margin = section.right_margin = Inches(0.625)


def parse_front(lines: list[str]) -> tuple[dict, list[str]]:
    """Split '---' front matter from the body."""
    meta: dict = {"members": []}
    if lines and lines[0].strip() == "---":
        end = lines.index("---", 1) if "---" in lines[1:] else 0
        key = None
        for ln in lines[1:end]:
            if re.match(r"^\w+:", ln):
                key, val = ln.split(":", 1)
                key = key.strip()
                if val.strip():
                    meta[key] = val.strip()
            elif key == "members" and ln.strip().startswith("-"):
                meta["members"].append(ln.strip()[1:].strip())
        return meta, lines[end + 1:]
    return meta, lines


def title_block(doc, meta: dict) -> None:
    """Title, group and members with contribution percentages, one column."""
    p = doc.add_paragraph()
    fmt(p, after=6, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run(meta.get("title", "")), 22)
    if meta.get("group"):
        p = doc.add_paragraph()
        fmt(p, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
        set_font(p.add_run(meta["group"]), 11, italic=True)
    if meta["members"]:
        p = doc.add_paragraph()
        fmt(p, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
        set_font(p.add_run("    ".join(m.replace(" | ", ", ") for m in meta["members"])), 11)
    if meta.get("course"):
        p = doc.add_paragraph()
        fmt(p, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)
        set_font(p.add_run(meta["course"]), 9)


def add_table(doc, caption: str, rows: list[list[str]], tno: int) -> None:
    """Add a captioned table (IEEE: caption above, 'TABLE n' in Roman numerals)."""
    p = doc.add_paragraph()
    fmt(p, before=4, after=0, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run(f"TABLE {ROMAN[tno - 1]}"), 8, small_caps=False)
    p = doc.add_paragraph()
    fmt(p, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run(caption.upper() if len(caption) < 60 else caption), 8, small_caps=True)
    header, body = rows[0], rows[1:]
    t = doc.add_table(rows=len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    # Fixed layout, one column wide: first column takes the remaining width.
    total = 3.4
    ncol = len(header)
    first_share = 0.62 if ncol == 2 else 0.46 if ncol <= 4 else 0.26
    widths = [total * first_share] + [total * (1 - first_share) / (ncol - 1)] * (ncol - 1)
    tbl_pr = t._tbl.tblPr
    if tbl_pr.find(qn("w:tblLayout")) is None:
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        tbl_pr.append(layout)
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(int(total * 1440)))
    tbl_w.set(qn("w:type"), "dxa")
    grid = t._tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(int(w * 1440)))
    for i, row in enumerate([header, *body]):
        for j, cell in enumerate(row):
            c = t.cell(i, j)
            c.width = Inches(widths[j])
            c.text = ""
            par = c.paragraphs[0]
            fmt(par, after=0, align=WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER)
            add_inline(par, cell.strip(), size=7)
            if i == 0:
                for r in par.runs:
                    r.bold = True
    spacer = doc.add_paragraph()
    fmt(spacer, after=2)


def add_figure(doc, caption: str, path: str, fno: int) -> None:
    """Add a figure 3.5 in wide with an IEEE caption below."""
    p = doc.add_paragraph()
    fmt(p, before=4, after=0, align=WD_ALIGN_PARAGRAPH.CENTER)
    p.add_run().add_picture(str(ROOT / path), width=Inches(3.45))
    p = doc.add_paragraph()
    fmt(p, after=4, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    set_font(p.add_run(f"Fig. {fno}. "), 8)
    add_inline(p, caption, size=8)


def build() -> Path:
    """Convert the draft to docx. Output: path to report.docx."""
    lines = DRAFT.read_text(encoding="utf-8").splitlines()
    meta, body = parse_front(lines)
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(10)
    page_setup(doc.sections[0])
    set_columns(doc.sections[0], 1)
    title_block(doc, meta)
    sec = doc.add_section(WD_SECTION.CONTINUOUS)
    page_setup(sec)
    set_columns(sec, 2)

    sec_no, sub_no, fig_no, tab_no = 0, 0, 0, 0
    in_refs = False
    i = 0
    while i < len(body):
        ln = body[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("## "):
            title = ln[3:].strip()
            in_refs = title.lower() == "references"
            p = doc.add_paragraph()
            fmt(p, before=6, after=3, align=WD_ALIGN_PARAGRAPH.CENTER)
            if title.lower() in ("abstract", "references"):
                if title.lower() == "abstract":
                    # IEEE abstract: bold italic run-in heading handled in next paragraph.
                    p._element.getparent().remove(p._element)
                    i += 1
                    while i < len(body) and not body[i].strip():
                        i += 1
                    p = doc.add_paragraph()
                    fmt(p, after=4)
                    set_font(p.add_run("Abstract. "), 9, bold=True, italic=True)
                    add_inline(p, body[i].strip(), size=9)
                    for r in p.runs:
                        r.bold = True
                    i += 1
                    continue
                set_font(p.add_run(title), 10, small_caps=True)
            else:
                sec_no += 1
                sub_no = 0
                set_font(p.add_run(f"{ROMAN[sec_no - 1]}. {title}"), 10, small_caps=True)
            i += 1
            continue
        if ln.startswith("### "):
            sub_no += 1
            p = doc.add_paragraph()
            fmt(p, before=4, after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
            set_font(p.add_run(f"{chr(64 + sub_no)}. {ln[4:].strip()}"), 10, italic=True)
            i += 1
            continue
        m = re.match(r"^!\[(.*)\]\((.*)\)\s*$", ln)
        if m:
            fig_no += 1
            add_figure(doc, m.group(1), m.group(2), fig_no)
            i += 1
            continue
        if ln.startswith("Table: "):
            caption = ln[7:].strip()
            i += 1
            rows = []
            while i < len(body) and body[i].strip().startswith("|"):
                cells = [c for c in body[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells):
                    rows.append(cells)
                i += 1
            tab_no += 1
            add_table(doc, caption, rows, tab_no)
            continue
        if in_refs and re.match(r"^\[\d+\]", ln):
            p = doc.add_paragraph()
            fmt(p, after=1, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.first_line_indent = Inches(-0.25)
            add_inline(p, ln.strip(), size=8)
            i += 1
            continue
        if ln.startswith("- "):
            p = doc.add_paragraph()
            fmt(p, after=1)
            p.paragraph_format.left_indent = Inches(0.18)
            p.paragraph_format.first_line_indent = Inches(-0.12)
            add_inline(p, "• " + ln[2:].strip())
            i += 1
            continue
        # Plain paragraph: join following non-special lines.
        text = [ln.strip()]
        i += 1
        while i < len(body) and body[i].strip() and not re.match(
                r"^(#|- |!\[|Table: |\||\[\d+\])", body[i]):
            text.append(body[i].strip())
            i += 1
        p = doc.add_paragraph()
        fmt(p, after=2, indent=0.15)
        add_inline(p, " ".join(text))
    doc.save(OUT)
    return OUT


WORD_PS = """
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {{ $d = $w.Documents.Open('{docx}', $false, $true); $n = $d.ComputeStatistics(2)
  $d.ExportAsFixedFormat('{pdf}', 17); $d.Close(0); Write-Output $n }} finally {{ $w.Quit() }}
"""


def page_count_word(docx: Path) -> int | None:
    """Count pages with Microsoft Word (the target format) and export a PDF. None if no Word."""
    pdf = docx.with_suffix(".pdf")
    pdf.unlink(missing_ok=True)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            WORD_PS.format(docx=docx, pdf=pdf)],
                           check=False, capture_output=True, text=True, timeout=180)
        return int(r.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        return None


def page_count(docx: Path) -> int | None:
    """Return the page count, from Word if available, else from a LibreOffice PDF."""
    n = page_count_word(docx)
    if n is not None or not SOFFICE.exists():
        return n
    pdf = docx.with_suffix(".pdf")
    pdf.unlink(missing_ok=True)  # never count pages of a stale PDF
    # A private profile avoids a lock held by another LibreOffice instance.
    profile = (docx.parent / ".lo_profile").resolve().as_uri()
    subprocess.run([str(SOFFICE), f"-env:UserInstallation={profile}", "--headless",
                    "--norestore", "--convert-to", "pdf", "--outdir", str(docx.parent),
                    str(docx)], check=True, capture_output=True, timeout=240)
    if not pdf.exists() or pdf.stat().st_mtime < docx.stat().st_mtime:
        raise RuntimeError("LibreOffice did not write a new PDF")
    from pypdf import PdfReader
    return len(PdfReader(pdf).pages)


if __name__ == "__main__":
    out = build()
    n = page_count(out)
    print(f"wrote {out}, pages: {n}")
    if n is not None and n > 10:
        print("OVER the 10-page limit", file=sys.stderr)
        sys.exit(1)
