"""Parser for Yaskawa robot position data in .JBI job files and PDF generator."""

import os
import re


def find_jbi_files(folder):
    """Return sorted list of .JBI file paths found directly in folder."""
    try:
        entries = os.listdir(folder)
    except OSError:
        return []
    return sorted(
        os.path.join(folder, f) for f in entries
        if f.upper().endswith('.JBI')
    )


def parse_jbi_points(filepath):
    """Parse a .JBI file and return list of (point_id, tool, pos_type, values).
    Searches the //POS section only; returns [] if no positions or no //POS.
    Raises RuntimeError on file access failure."""
    try:
        with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
            lines = f.readlines()
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc

    points = []
    in_pos = False
    current_tool = 0
    current_user = 0
    current_type = 'PULSE'

    for raw in lines:
        line = raw.rstrip('\r\n').strip()

        if line == '//POS':
            in_pos = True
            continue
        if not in_pos:
            continue
        # Another top-level section ends the //POS block
        if line.startswith('//') and not line.startswith('///'):
            break

        if line.startswith('///TOOL'):
            m = re.match(r'///TOOL\s+(\d+)', line)
            if m:
                current_tool = int(m.group(1))
        elif line.startswith('///USER'):
            m = re.match(r'///USER\s+(\d+)', line)
            if m:
                current_user = int(m.group(1))
        elif line in ('///POSTYPE PULSE', '///PULSE'):
            current_type = 'PULSE'
        elif line in ('///POSTYPE RECTAN', '///RECTAN',
                      '///POSTYPE BASE',   '///BASE',
                      '///POSTYPE STATION','///STATION'):
            current_type = line.replace('///POSTYPE ', '').replace('///', '')
        else:
            m = re.match(r'^(P\d+)=(.+)$', line)
            if m:
                pid = m.group(1)
                vals = []
                for v in m.group(2).split(','):
                    v = v.strip()
                    try:
                        vals.append(int(v))
                    except ValueError:
                        try:
                            vals.append(float(v))
                        except ValueError:
                            vals.append(v)
                points.append((pid, current_tool, current_user, current_type, vals))

    return points


def generate_points_pdf(jbi_data, output_path,
                        col_point='Point', col_tool='Tool', col_uf='UF#()',
                        col_uf_name='UF Name', col_type='Type',
                        msg_no_pos='No positions found',
                        uframe_names=None, lang="IT", log_fn=None):
    """Generate A4 portrait PDF: one section per JBI file, tabular positions.
    jbi_data : list of (filename_no_ext, points_list)
    Returns True/False."""
    try:
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                         PageBreak, Paragraph, Spacer, Flowable)
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor, white, black
    except ImportError as exc:
        if log_fn:
            log_fn('log_error_generic', f'reportlab: {exc}')
        return False
    from docs.utils import pdf_font, xml_escape
    fn   = pdf_font(lang)
    fn_b = pdf_font(lang, bold=True)

    if uframe_names is None:
        uframe_names = {}

    # Keep only files that have at least one position
    jbi_data = [(f, p) for f, p in jbi_data if p]
    if not jbi_data:
        if log_fn:
            log_fn('log_error_generic', 'No JBI data to write')
        return False

    accent = HexColor('#D97757')
    row_gray  = HexColor('#EFEFEF')
    styles    = getSampleStyleSheet()

    head_s = ParagraphStyle('PtHead', parent=styles['Normal'],
        fontSize=11, fontName=fn_b,
        textColor=black, leftIndent=4*mm)

    no_pos_s = ParagraphStyle('PtNoPos', parent=styles['Normal'],
        fontSize=8, fontName=fn,
        textColor=HexColor('#888888'), spaceAfter=3*mm, leftIndent=2*mm)

    # ── Footer tracker (pre-initialized for page 1 — onPage fires at page BEGIN)
    tracker = {'fname': jbi_data[0][0]}

    class _SetFile(Flowable):
        def __init__(self, name):
            """Initialise a zero-size flowable that records the current JBI filename for the footer."""
            Flowable.__init__(self)
            self._name = name
            self.width = self.height = 0
        def wrap(self, *a):
            """Take no layout space (this flowable is zero-size)."""
            return 0, 0
        def draw(self):
            """Record this flowable's filename as the current footer name."""
            tracker['fname'] = self._name

    def draw_page(canvas, doc):
        """ReportLab page callback: draw the shared header plus a footer with page number and current JBI filename."""
        from docs.pdf_header import draw_page_header
        draw_page_header(canvas, doc)
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(HexColor('#888888'))
        pn = canvas.getPageNumber()
        pw = A4[0]
        canvas.drawCentredString(pw / 2, 8 * mm, f'- {pn} -')
        fname = tracker.get('fname', '')
        if fname:
            canvas.drawRightString(pw - 15 * mm, 8 * mm, fname)
        canvas.restoreState()

    # ── Column widths: Point(18) Tool(9) UF#()(9) UF Name(22) Type(10) V1-V6(18,18,18,18,20,20) = 162pt + 18 = 180mm ──
    COL_W   = [18*mm, 9*mm, 9*mm, 22*mm, 10*mm, 18*mm, 18*mm, 18*mm, 18*mm, 20*mm, 20*mm]
    HDR_ROW = [col_point, col_tool, col_uf, col_uf_name, col_type,
               'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
    PAGE_W  = A4[0] - 30*mm  # 180 mm

    def _fmt(v):
        """Format a value: floats to 3 decimals, empty stays empty, otherwise string."""
        if isinstance(v, float):
            return f'{v:.3f}'
        return str(v) if v != '' else ''

    def _row_style(n):
        """Build the points-table TableStyle for n rows (header colour + alternating shading)."""
        ts = TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0), accent),
            ('TEXTCOLOR',   (0, 0), (-1, 0), black),
            ('FONTNAME',    (0, 0), (-1, 0), fn_b),
            ('FONTSIZE',    (0, 0), (-1, 0), 7),
            ('ALIGN',       (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME',    (0, 1), (-1, -1), 'Courier'),
            ('FONTSIZE',    (0, 1), (-1, -1), 7),
            ('ROWHEIGHT',   (0, 0), (0, 0), 12),
            ('ROWHEIGHT',   (0, 1), (-1, -1), 10),
            ('GRID',        (0, 0), (-1, -1), 0.25, HexColor('#CCCCCC')),
            ('ALIGN',       (0, 1), (2, -1), 'CENTER'),
            ('ALIGN',       (3, 1), (3, -1), 'LEFT'),
            ('ALIGN',       (4, 1), (4, -1), 'CENTER'),
            ('ALIGN',       (5, 1), (-1, -1), 'RIGHT'),
        ])
        for r in range(1, n + 1):
            if r % 2 == 0:
                ts.add('BACKGROUND', (0, r), (-1, r), row_gray)
        return ts

    # ── Story ─────────────────────────────────────────────────────────────────
    story = []
    n_files = len(jbi_data)

    for idx, (fname, points) in enumerate(jbi_data):
        head_tbl = Table([[Paragraph(xml_escape(fname), head_s)]], colWidths=[PAGE_W])
        head_tbl.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, -1), accent),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ]))
        story.append(head_tbl)
        story.append(Spacer(1, 2*mm))

        if not points:
            story.append(Paragraph(f'— {msg_no_pos} —', no_pos_s))
        else:
            rows = [HDR_ROW] + [
                [pid, str(tool), str(user),
                 ('BASE' if user == 0 else uframe_names.get(user, '')), ptype]
                + [_fmt(v) for v in (list(vals) + [''] * 6)[:6]]
                for pid, tool, user, ptype, vals in points
            ]
            tbl = Table(rows, colWidths=COL_W, repeatRows=1)
            tbl.setStyle(_row_style(len(points)))
            story.append(tbl)

        # Pre-set tracker for next file's page (placed before PageBreak)
        if idx < n_files - 1:
            story.append(_SetFile(jbi_data[idx + 1][0]))
            story.append(PageBreak())

    try:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=15*mm, rightMargin=15*mm,
            topMargin=22*mm, bottomMargin=20*mm,
        )
        doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
        if log_fn:
            log_fn('log_punti_pdf_saved', output_path)
        return True
    except Exception as exc:
        if log_fn:
            log_fn('log_error_generic', f'Points PDF: {exc}')
        return False
