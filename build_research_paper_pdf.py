import os
import sys
import re
from pathlib import Path
from PIL import Image as PILImage

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "Secure_Document_Authentication_Academic_Research_Paper.pdf"
ROC_IMG_PATH = BASE_DIR / "results" / "component_a_roc_curve.png"
ABLATION_IMG_PATH = BASE_DIR / "results" / "ablation_comparison_chart.png"
SAMPLE_DOC_PATH = BASE_DIR / "dataset" / "008cec36-ecae-4646-850f-b7119b944abf.png"

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print total page count,
    running headers, running footers, and decorative dividing rules.
    """
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(36, 11 * inch - 26, "BCSE323L: Digital Watermarking & Steganography — Academic Research Paper")
            self.drawRightString(8.5 * inch - 36, 11 * inch - 26, "Bishal Paul (23BCI0224)")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(36, 11 * inch - 30, 8.5 * inch - 36, 11 * inch - 30)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 32, 8.5 * inch - 36, 32)
        self.drawString(36, 20, "Secure Document Authentication Using Hybrid QR Codes & Multi-Tier Verification")
        self.drawRightString(8.5 * inch - 36, 20, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def clean_math(text):
    """Replaces common LaTeX constructs with clean unicode / HTML for ReportLab."""
    if not text:
        return ""
    text = text.replace(r"\text{", "").replace(r"\operatorname{", "").replace(r"}", "")
    text = text.replace(r"\ge", "&ge;").replace(r"\le", "&le;").replace(r"\approx", "&asymp;")
    text = text.replace(r"\pm", "&plusmn;").replace(r"\times", "&times;").replace(r"\cdot", "&middot;")
    text = text.replace(r"\alpha", "&alpha;").replace(r"\psi", "&psi;").replace(r"\tau", "&tau;")
    text = text.replace(r"\sigma", "&sigma;").replace(r"\mu", "&mu;").replace(r"\Delta", "&Delta;")
    text = text.replace(r"\in", "&isin;").replace(r"\rightarrow", "&rarr;").replace(r"\to", "&rarr;")
    text = text.replace(r"\sum", "&Sigma;").replace(r"\sqrt", "&radic;")
    text = text.replace(r"\exp", "exp").replace(r"\min", "min").replace(r"\max", "max")
    text = text.replace(r"\cos", "cos").replace(r"\pi", "&pi;")
    text = text.replace(r"^\circ", "&deg;").replace(r"^2", "&sup2;").replace(r"^{*}", "*")
    text = text.replace(r"\operatorname", "").replace(r"\quad", " ")
    return text


def md_to_html(text):
    if not text:
        return ""
    # Pre-clean markdown links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'<b>\1</b>', text)

    # Escape HTML special chars that aren't tags
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Handle inline math $...$
    def math_repl(m):
        raw = m.group(1)
        cleaned = clean_math(raw)
        return f"<i>{cleaned}</i>"
    text = re.sub(r'\$(.+?)\$', math_repl, text)

    # Bold **text** -> <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic *text* -> <i>text</i>
    text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<i>\1</i>', text)
    # Inline code `text` -> Courier font
    text = re.sub(r'`(.+?)`', r'<font face="Courier">\1</font>', text)

    return text


def get_custom_col_widths(first_header_text, num_cols):
    """Returns tailored column widths for each specific table in the research paper."""
    h = first_header_text.lower()
    total_w = 7.5 * inch  # 540 pt

    if "criterion" in h:  # Table 1: Comparative Analysis
        return [1.5 * inch, 1.15 * inch, 1.15 * inch, 1.2 * inch, 1.15 * inch, 1.35 * inch]
    elif "research gap" in h:  # Table 2: Gap Mapping
        return [1.8 * inch, 3.1 * inch, 2.6 * inch]
    elif "configuration parameter" in h:  # Table 3: Operational Parameters
        return [2.0 * inch, 1.1 * inch, 1.1 * inch, 3.3 * inch]
    elif "document class" in h:  # Table 4: Dataset Structural Statistics
        return [1.6 * inch, 0.9 * inch, 1.1 * inch, 1.1 * inch, 1.4 * inch, 1.4 * inch]
    elif "subsystem" in h:  # Table 5: Subsystem Benchmarks
        return [1.8 * inch, 1.5 * inch, 1.3 * inch, 2.0 * inch, 0.9 * inch]
    elif "configuration scheme" in h:  # Table 6: 5-Stage Ablation Matrix
        return [1.7 * inch, 1.1 * inch, 1.2 * inch, 1.3 * inch, 1.2 * inch, 1.0 * inch]
    elif "script" in h:  # Table 7: Cross-Condition Performance
        return [0.75 * inch, 0.95 * inch, 1.35 * inch, 1.35 * inch, 0.85 * inch, 0.95 * inch, 1.3 * inch]
    elif "performance metric" in h:  # Table 8: Quantitative Comparison with SOTA
        return [1.7 * inch, 0.9 * inch, 0.9 * inch, 1.0 * inch, 0.9 * inch, 1.0 * inch, 1.1 * inch]
    elif "operational capability" in h:  # Table 9: Qualitative Capability Comparison
        return [1.8 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 1.0 * inch, 1.1 * inch]
    else:
        return [total_w / num_cols] * num_cols


def build_table_flowable(table_lines, styles, navy_color, border_color):
    """
    Parses contiguous markdown table lines into a unified ReportLab Table flowable
    with styled dark headers, alternating striped rows, custom column widths, and clean grid borders.
    """
    parsed_rows = []
    header_found = False

    for line in table_lines:
        s = line.strip()
        if "---" in s:
            header_found = True
            continue
        cells = [c.strip() for c in s.split("|")[1:-1]]
        if cells:
            parsed_rows.append(cells)

    if not parsed_rows:
        return None

    num_cols = len(parsed_rows[0])
    first_header_text = parsed_rows[0][0] if parsed_rows else ""
    col_widths = get_custom_col_widths(first_header_text, num_cols)

    cell_flowables = []
    for r_idx, row in enumerate(parsed_rows):
        row_flowables = []
        is_header = (r_idx == 0 and header_found)
        for c_idx, cell in enumerate(row):
            html = md_to_html(cell)
            if is_header:
                p_text = f"<font size='6.5' color='white'><b>{html}</b></font>"
                align = 1  # Centered
            else:
                p_text = f"<font size='6.5' color='#1e293b'>{html}</font>"
                align = 0  # Left

            p_style = ParagraphStyle(
                f'TableCell_{r_idx}_{c_idx}_{hash(cell)%10000}',
                parent=styles['Normal'],
                fontName='Helvetica-Bold' if is_header else 'Helvetica',
                fontSize=6.5,
                leading=8.5,
                alignment=align
            )
            row_flowables.append(Paragraph(p_text, p_style))
        cell_flowables.append(row_flowables)

    # Table styling
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), navy_color if header_found else colors.HexColor("#f1f5f9")),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 3.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3.5),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
    ]

    # Alternate row striping
    if header_found:
        for r_idx in range(1, len(parsed_rows)):
            bg = colors.HexColor("#ffffff") if r_idx % 2 != 0 else colors.HexColor("#f8fafc")
            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), bg))

    table_widget = Table(cell_flowables, colWidths=col_widths, style=TableStyle(t_style), repeatRows=1 if header_found else 0)
    return table_widget


def generate_paper_pdf():
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    navy_color = colors.HexColor("#0f2942")
    teal_color = colors.HexColor("#0f766e")
    dark_body = colors.HexColor("#1e293b")
    code_bg = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#cbd5e1")

    title_style = ParagraphStyle(
        'PaperTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15.5,
        leading=19.5,
        textColor=navy_color,
        alignment=1,
        spaceAfter=7
    )

    author_style = ParagraphStyle(
        'PaperAuthor',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        alignment=1,
        spaceAfter=9
    )

    abstract_title = ParagraphStyle(
        'AbstractTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=navy_color,
        spaceBefore=2,
        spaceAfter=3,
        alignment=1
    )

    abstract_body = ParagraphStyle(
        'AbstractBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.8,
        textColor=dark_body,
        alignment=4,  # Justified
        spaceAfter=5
    )

    keywords_style = ParagraphStyle(
        'KeywordsBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.8,
        textColor=navy_color,
        alignment=0,
        spaceAfter=2
    )

    h1_style = ParagraphStyle(
        'PaperH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=navy_color,
        spaceBefore=11,
        spaceAfter=4,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'PaperH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=teal_color,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'PaperH3',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=6,
        spaceAfter=2,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'PaperBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.2,
        leading=11.2,
        textColor=dark_body,
        alignment=4,  # Justified
        spaceAfter=3.5
    )

    bullet_style = ParagraphStyle(
        'PaperBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.2,
        leading=11.2,
        textColor=dark_body,
        leftIndent=14,
        firstLineIndent=-9,
        spaceAfter=2
    )

    code_style = ParagraphStyle(
        'PaperCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=5.2,
        leading=6.8,
        textColor=colors.HexColor("#0f172a")
    )

    math_box_style = ParagraphStyle(
        'MathBox',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.0,
        leading=11.0,
        textColor=navy_color,
        alignment=1,  # Centered
        spaceBefore=1,
        spaceAfter=1
    )

    caption_style = ParagraphStyle(
        'FigureCaption',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#475569"),
        alignment=1,  # Centered
        spaceBefore=3,
        spaceAfter=7
    )

    story = []

    # Title & Metadata Header
    story.append(Spacer(1, 4))
    story.append(Paragraph("Secure Document Authentication Using Hybrid QR Codes, Transform-Domain Invisible Watermarking, and Multi-Tier Verification", title_style))
    story.append(Paragraph(
        "<b>Bishal Paul</b> (Registration Number: 23BCI0224)<br/>"
        "School of Computer Science and Engineering, Vellore Institute of Technology, Vellore, Tamil Nadu, India<br/>"
        "Course: Digital Watermarking and Steganography (BCSE323L) | Fall Semester 2026–2027",
        author_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=navy_color, spaceAfter=8))

    # Read RESEARCH_PAPER.md
    with open(BASE_DIR / "RESEARCH_PAPER.md", "r", encoding="utf-8") as f:
        md_text = f.read()

    # Extract Abstract & Keywords
    abs_start = md_text.find("## Abstract")
    intro_start = md_text.find("## 1. Introduction")

    if abs_start != -1 and intro_start != -1:
        abs_section = md_text[abs_start + len("## Abstract"):intro_start].strip()
        # Separate Keywords
        kw_start = abs_section.find("**Keywords:**")
        if kw_start != -1:
            abs_text = abs_section[:kw_start].strip()
            kw_text = abs_section[kw_start:].strip()
        else:
            abs_text = abs_section
            kw_text = ""

        # Build Abstract Callout Box
        abs_flowables = [
            Paragraph("<b>ABSTRACT</b>", abstract_title),
            Spacer(1, 2)
        ]
        for p in abs_text.split("\n\n"):
            p_clean = p.strip()
            if p_clean:
                abs_flowables.append(Paragraph(md_to_html(p_clean), abstract_body))

        if kw_text:
            abs_flowables.append(Spacer(1, 2))
            abs_flowables.append(Paragraph(md_to_html(kw_text), keywords_style))

        abs_table = Table([[abs_flowables]], colWidths=[7.5 * inch],
                          style=[
                              ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                              ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
                              ('LINEBEFORE', (0, 0), (-1, -1), 3.0, teal_color),
                              ('TOPPADDING', (0, 0), (-1, -1), 6),
                              ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                              ('LEFTPADDING', (0, 0), (-1, -1), 10),
                              ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                          ])
        story.append(abs_table)
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceAfter=8))

    # Process Sections from 1. Introduction onwards
    main_content = md_text[intro_start:]
    lines = main_content.splitlines()

    in_code_block = False
    code_lines = []
    in_table = False
    table_lines = []
    current_sec = ""

    eq_counter = 1

    for line in lines:
        line_s = line.strip()

        # Handle Code Block Start / End
        if line_s.startswith("```"):
            if in_code_block:
                in_code_block = False
                # Render code block
                code_text = "<br/>".join([
                    clean_math(c).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")
                    for c in code_lines
                ])
                c_p = Paragraph(f"<font face='Courier'>{code_text}</font>", code_style)
                story.append(Table([[c_p]], colWidths=[7.5 * inch],
                                   style=[
                                       ('BACKGROUND', (0, 0), (-1, -1), code_bg),
                                       ('BOX', (0, 0), (-1, -1), 0.5, border_color),
                                       ('TOPPADDING', (0, 0), (-1, -1), 4),
                                       ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                                       ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                       ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                   ]))
                story.append(Spacer(1, 3))
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Handle Tables
        if line_s.startswith("|"):
            in_table = True
            table_lines.append(line_s)
            continue
        else:
            if in_table:
                # Flush table
                t_flowable = build_table_flowable(table_lines, styles, navy_color, border_color)
                if t_flowable:
                    story.append(Spacer(1, 2))
                    story.append(t_flowable)
                    story.append(Spacer(1, 4))
                table_lines = []
                in_table = False

        if not line_s:
            story.append(Spacer(1, 2))
            continue

        # Check for Math Block $$...$$
        if line_s.startswith("$$") and line_s.endswith("$$"):
            raw_eq = line_s[2:-2].strip()
            clean_eq = clean_math(raw_eq)
            # Render equation in styled table with equation number
            eq_p = Paragraph(f"<i>{clean_eq}</i>", math_box_style)
            num_p = Paragraph(f"<font size='7' color='#64748b'>(Eq. {eq_counter})</font>", ParagraphStyle('EqNum', parent=styles['Normal'], alignment=2))
            eq_table = Table([[eq_p, num_p]], colWidths=[6.7 * inch, 0.8 * inch],
                             style=[
                                 ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                 ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                                 ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                                 ('TOPPADDING', (0, 0), (-1, -1), 2),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                 ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                             ])
            story.append(Spacer(1, 1))
            story.append(eq_table)
            story.append(Spacer(1, 2))
            eq_counter += 1
            continue

        # Check for Headings
        if line_s.startswith("## "):
            sec_title = md_to_html(line_s[3:].strip())
            current_sec = sec_title
            story.append(Spacer(1, 5))
            story.append(Paragraph(sec_title, h1_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=teal_color, spaceAfter=4))
        elif line_s.startswith("### "):
            subsec_title = md_to_html(line_s[4:].strip())
            story.append(Paragraph(subsec_title, h2_style))
        elif line_s.startswith("#### "):
            sub3_title = md_to_html(line_s[5:].strip())
            story.append(Paragraph(sub3_title, h3_style))

        # Check for Captions (*Figure X:* or *Table X:*)
        elif line_s.startswith("*Figure ") or line_s.startswith("*Table "):
            cap_text = md_to_html(line_s.replace("*", "").strip())
            story.append(Paragraph(f"<i>{cap_text}</i>", caption_style))

        # Check for Bullet Points
        elif line_s.startswith("- ") or line_s.startswith("* "):
            b_text = md_to_html(line_s[2:].strip())
            story.append(Paragraph(f"&bull;&nbsp;&nbsp;{b_text}", bullet_style))

        # Check for Numbered Lists
        elif re.match(r'^\d+\.\s', line_s):
            m = re.match(r'^(\d+\.)\s*(.*)', line_s)
            num_str = m.group(1)
            b_text = md_to_html(m.group(2).strip())
            story.append(Paragraph(f"<b>{num_str}</b>&nbsp;&nbsp;{b_text}", bullet_style))

        # Normal Paragraphs
        else:
            p_text = md_to_html(line_s)
            story.append(Paragraph(p_text, body_style))

        # Strategic Empirical Figure Insertions
        # 1. Figure 6: Authentic Sample Document in Section 4.3
        if "4.3 Dataset Creation and Crafting" in line_s and SAMPLE_DOC_PATH.exists():
            story.append(Spacer(1, 4))
            story.append(RLImage(str(SAMPLE_DOC_PATH), width=5.2 * inch, height=3.64 * inch))
            story.append(Paragraph("<i>Figure 6: Sample procedurally generated authentic credential (Certificate template) featuring high-density CBOR/ZLIB QR code and DWT-SVD transform watermark substrate.</i>", caption_style))
            story.append(Spacer(1, 4))

        # 2. Figure 4: Empirical ROC Curve in Section 5.9
        elif "Table 5 documents the measured performance" in line_s and ROC_IMG_PATH.exists():
            story.append(Spacer(1, 4))
            story.append(RLImage(str(ROC_IMG_PATH), width=4.8 * inch, height=3.8 * inch))
            story.append(Paragraph("<i>Figure 4: Empirical Receiver Operating Characteristic (ROC) Curve for Component A Print-Channel Microtexture Copy Detection (1,000 Monte Carlo evaluations, AUC = 0.9988).</i>", caption_style))
            story.append(Spacer(1, 4))

        # 3. Figure 5: Ablation Benchmark Chart in Section 5.10
        elif "Systematic 5-Stage Ablation Benchmark Matrix" in line_s and ABLATION_IMG_PATH.exists():
            story.append(Spacer(1, 4))
            story.append(RLImage(str(ABLATION_IMG_PATH), width=5.8 * inch, height=3.5 * inch))
            story.append(Paragraph("<i>Figure 5: Systematic 5-Stage Ablation Benchmark Comparison across Schemes A through E showing detection performance under Clean, Reprint, Tamper, and Typosquatting attacks.</i>", caption_style))
            story.append(Spacer(1, 4))

    # Flush any remaining table
    if in_table and table_lines:
        t_flowable = build_table_flowable(table_lines, styles, navy_color, border_color)
        if t_flowable:
            story.append(t_flowable)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Academic Research Paper PDF successfully generated at: {PDF_PATH}")
    print(f"Final File Size: {os.path.getsize(PDF_PATH)} bytes")

if __name__ == "__main__":
    generate_paper_pdf()
