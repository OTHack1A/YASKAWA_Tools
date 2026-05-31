"""Parser for YASKAWA YRC1000 LOGDATA.DAT and multi-column PDF generator."""

import os
import re


def parse_logdata(filepath):
    """Parse LOGDATA.DAT → list of dicts, one per ///INDEX block.
    Each dict maps field names to values. Returns [] on error."""
    try:
        with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return []

    entries = []
    current = None

    for raw in lines:
        line = raw.rstrip('\r\n')
        stripped = line.strip()
        if stripped.startswith('///INDEX'):
            if current is not None:
                entries.append(current)
            current = {}
        elif current is not None and ':' in stripped:
            # Format: "FIELD_NAME          :value"
            colon_pos = stripped.index(':')
            key = stripped[:colon_pos].strip()
            val = stripped[colon_pos + 1:].strip()
            if key:
                current[key] = val

    if current is not None:
        entries.append(current)

    return entries


def generate_logdata_pdf(entries, output_path, lang="IT", log_fn=None):
    """Generate multi-column A4 PDF from LOGDATA entries.
    Returns True/False."""
    try:
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                         Paragraph, Spacer, Flowable)
        from reportlab.lib.pagesizes import A4, landscape
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

    if not entries:
        if log_fn:
            log_fn('log_error_generic', 'LogData: no entries to write')
        return False

    hdr_blue = HexColor('#D97757')
    row_gray  = HexColor('#EFEFEF')
    styles    = getSampleStyleSheet()

    # Collect all field names in order of appearance
    all_fields = []
    seen = set()
    for entry in entries:
        for k in entry:
            if k not in seen:
                all_fields.append(k)
                seen.add(k)

    # Key fields to always show first
    priority = ['DATE', 'EVENT', 'LOGIN NAME', 'TASK', 'JOB NAME',
                'LINE', 'STOP FACTOR', 'AFTER EDIT', 'CURR VALUE']
    ordered = [f for f in priority if f in seen] + [f for f in all_fields if f not in priority]

    def draw_page(canvas, doc):
        from docs.pdf_header import draw_page_header
        draw_page_header(canvas, doc)
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(HexColor('#888888'))
        pn = canvas.getPageNumber()
        canvas.drawCentredString(A4[0] / 2, 8 * mm, f'- {pn} -')
        canvas.drawRightString(A4[0] - 15 * mm, 8 * mm, 'LogData')
        canvas.restoreState()

    # ── Layout: 4 columns per page, each column = one event ──────────────────
    PAGE_W = A4[0] - 30 * mm   # 180 mm usable
    N_COLS = 4
    COL_W  = PAGE_W / N_COLS   # ~45 mm each column

    cell_s = ParagraphStyle('LC', parent=styles['Normal'],
        fontSize=6, fontName=fn, leading=8)
    key_s  = ParagraphStyle('LK', parent=styles['Normal'],
        fontSize=6, fontName=fn_b, leading=8)
    idx_s  = ParagraphStyle('LI', parent=styles['Normal'],
        fontSize=6, fontName='Courier', leading=8, textColor=HexColor('#D97757'))

    def _cell(text, style=cell_s):
        return Paragraph(xml_escape(text) if text else '', style)

    def _make_event_col(idx, entry):
        """Build column data list for one event entry."""
        col = [_cell(f'#{idx + 1}', idx_s)]
        for f in ordered:
            v = entry.get(f, '')
            if v:
                col.append(_cell(f'{f}:', key_s))
                col.append(_cell(v))
        return col

    story = []

    # Group entries into rows of N_COLS
    for row_start in range(0, len(entries), N_COLS):
        chunk = entries[row_start:row_start + N_COLS]
        # Build per-column data
        cols_data = [_make_event_col(row_start + i, e) for i, e in enumerate(chunk)]
        # Pad to N_COLS
        while len(cols_data) < N_COLS:
            cols_data.append([])

        # Find max height
        max_rows = max(len(c) for c in cols_data)
        for c in cols_data:
            while len(c) < max_rows:
                c.append(_cell(''))

        # Transpose: each row of the table has one cell per event-column
        tbl_data = list(zip(*cols_data))
        col_widths = [COL_W] * N_COLS

        tbl = Table(tbl_data, colWidths=col_widths)
        ts = TableStyle([
            ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING',(0, 0), (-1, -1), 2),
            ('TOPPADDING',  (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 1),
            ('LINEAFTER',   (0, 0), (-2, -1), 0.25, HexColor('#CCCCCC')),
            ('LINEBELOW',   (0, -1), (-1, -1), 0.5, HexColor('#AAAAAA')),
        ])
        tbl.setStyle(ts)
        story.append(tbl)
        story.append(Spacer(1, 2 * mm))

    try:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=22 * mm, bottomMargin=16 * mm,
        )
        doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
        if log_fn:
            log_fn('log_logdata_pdf_saved', output_path)
        return True
    except Exception as exc:
        if log_fn:
            log_fn('log_error_generic', f'LogData PDF: {exc}')
        return False
