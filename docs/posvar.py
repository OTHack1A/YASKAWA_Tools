"""Parser, lossless writer and PDF generator for YASKAWA position variables (P).

The robot back-up stores position variables in the ``///P`` section of
``VAR.DAT``.  Each P variable occupies exactly one line, in order, starting from
P000.  An unused slot is the literal line ``"UNUSED"``.  A used slot looks like::

    "PULSE"0,0,1,000000000000000000000000,0,0,-75007,-89458,0,-29036,96372,0,0
    "RECTAN"0,1,1,001010000000000000000000,0,19,68.284,68.284,394.000,178.4740,...

Line layout (used slots)::

    "<TYPE>" h0 , h1 , h2 , <config24> , h4 , <tool> , v1 , v2 , ... , vN

    TYPE       PULSE  -> encoder pulse counts (S,L,U,R,B,T,E1,E2)
               RECTAN -> Cartesian coordinates (X,Y,Z,Rx,Ry,Rz,E1,E2)
    h0         reserved (always 0 in observed data)
    h1         coordinate kind flag (0/1)
    h2         user-coordinate / user-frame number (0 = BASE)
    config24   24-char binary string = RCONF configuration bits
    h4         reserved (always 0 in observed data)
    tool       tool number (0..63)
    v1..vN     axis values (8 in observed data; integers for PULSE,
               decimals for RECTAN — X/Y/Z 3 dp, rotations/ext 4 dp)

Friendly names for the slots come from the ``///P`` section of ``VARNAME.DAT``.

Design goal: *never corrupt the file*.  The writer keeps every original line
byte-for-byte and only rebuilds the lines of the points the user actually
edited, so an untouched export is identical to the input.
"""

import os
import re

VAR_FILE     = 'VAR.DAT'
VARNAME_FILE = 'VARNAME.DAT'

# A config field is a long run of 0/1 (24 bits in practice). Used to validate
# that a line really matches the expected 6-field header layout.
_CONFIG_RE = re.compile(r'^[01]{8,}$')
CONFIG_LEN = 24

# Axis labels by type (first six are robot axes, the rest external axes).
PULSE_AXES  = ['S', 'L', 'U', 'R', 'B', 'T', 'E1', 'E2']
RECTAN_AXES = ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz', 'E1', 'E2']

# Number of decimal places per RECTAN axis position (X/Y/Z vs rotations/ext).
_RECTAN_DECIMALS = [3, 3, 3, 4, 4, 4, 4, 4]


# ── Parsing ───────────────────────────────────────────────────────────────────

def _read_lines(path):
    """Read a DAT file preserving exact line endings; return list of raw lines.

    Reads as latin-1 (the controller charset) with newline='' so each element
    keeps its trailing CR/LF — this is what lets the writer round-trip exactly.
    """
    with open(path, 'r', encoding='latin-1', errors='replace', newline='') as fh:
        text = fh.read()
    return text.splitlines(keepends=True)


def parse_varname_p(folder):
    """Return {p_index: name} parsed from the ///P section of VARNAME.DAT.

    Lines look like ``0127 1,0,TRASPORTO`` → {127: 'TRASPORTO'}.  Any failure
    yields an empty mapping (names are optional, never fatal).
    """
    names = {}
    path = os.path.join(folder, VARNAME_FILE)
    if not os.path.isfile(path):
        return names
    try:
        lines = _read_lines(path)
    except OSError:
        return names

    in_p = False
    for raw in lines:
        line = raw.rstrip('\r\n')
        stripped = line.strip()
        if stripped.startswith('///'):
            in_p = (stripped == '///P')
            continue
        if not in_p or not stripped:
            continue
        # "<idx> <flag>,<flag>,<name>"
        m = re.match(r'^(\d+)\s+\d+,\d+,(.*)$', line)
        if m:
            try:
                names[int(m.group(1))] = m.group(2).rstrip()
            except ValueError:
                pass
    return names


def _parse_pulse_or_rectan(ptype, body):
    """Parse the comma body of a used P line into header bytes + values.

    Returns a dict of decoded fields, or None if the layout does not match the
    expected ``h0,h1,h2,config,h4,tool,values...`` shape (caller keeps it raw).
    """
    parts = body.split(',')
    if len(parts) < 7:
        return None
    config = parts[3].strip()
    if not _CONFIG_RE.match(config):
        return None
    try:
        h0   = int(parts[0]); h1 = int(parts[1]); h2 = int(parts[2])
        h4   = int(parts[4]); tool = int(parts[5])
    except ValueError:
        return None
    values = [p.strip() for p in parts[6:]]
    return {
        'h0': h0, 'h1': h1, 'h2': h2, 'h4': h4, 'tool': tool,
        'config': config, 'values': values,
    }


def parse_var_dat(folder):
    """Parse VAR.DAT in ``folder`` → dict describing the ///P section.

    Returns::

        {
          'path':       <abs path to VAR.DAT>,
          'raw_lines':  [<every original line, endings preserved>],
          'p_start':    <index of first P slot line in raw_lines>,
          'p_end':      <index just past the last P slot line>,
          'pfnum':      <robot axis count from ///PFNUM, or 6>,
          'points':     [<point dict>, ...],   # one per slot, ordered P000..
        }

    Each point dict::

        {'index','line_index','name','used','type','h0','h1','h2','h4',
         'tool','config','values'(list[str]),'raw'(str),'dirty'(bool)}

    ``type`` is 'PULSE', 'RECTAN', 'UNUSED' or 'RAW' (line that did not match the
    known layout — preserved verbatim, never editable).

    Raises ``RuntimeError`` on read failure or when no ///P section is present.
    """
    path = os.path.join(folder, VAR_FILE)
    try:
        raw_lines = _read_lines(path)
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc

    # Locate the ///P section and the section that follows it.
    p_start = None
    p_end = len(raw_lines)
    pfnum = 6
    for i, raw in enumerate(raw_lines):
        s = raw.rstrip('\r\n').strip()
        if s.startswith('///PFNUM'):
            m = re.match(r'///PFNUM\s+(\d+)', s)
            if m:
                try:
                    pfnum = int(m.group(1))
                except ValueError:
                    pfnum = 6
        if p_start is None:
            if s == '///P':
                p_start = i + 1
        else:
            # First line that starts a new section ends the P block.
            if s.startswith('//'):
                p_end = i
                break

    if p_start is None:
        raise RuntimeError('VAR.DAT has no ///P section')

    names = parse_varname_p(folder)

    points = []
    for offset, li in enumerate(range(p_start, p_end)):
        raw = raw_lines[li]
        line = raw.rstrip('\r\n')
        stripped = line.strip()
        pt = {
            'index': offset, 'line_index': li,
            'name': names.get(offset, ''),
            'raw': raw, 'dirty': False,
            'h0': 0, 'h1': 0, 'h2': 0, 'h4': 0, 'tool': 0,
            'config': '0' * CONFIG_LEN, 'values': [],
        }
        m = re.match(r'^"([^"]*)"(.*)$', stripped)
        if not m:
            pt['used'] = False
            pt['type'] = 'RAW' if stripped else 'UNUSED'
            points.append(pt)
            continue
        ptype = m.group(1).upper()
        body = m.group(2)
        if ptype == 'UNUSED' or body == '':
            pt['used'] = False
            pt['type'] = 'UNUSED'
            points.append(pt)
            continue
        if ptype in ('PULSE', 'RECTAN'):
            decoded = _parse_pulse_or_rectan(ptype, body)
            if decoded is not None:
                pt.update(decoded)
                pt['used'] = True
                pt['type'] = ptype
                points.append(pt)
                continue
        # Unknown / malformed -> keep raw, never edit.
        pt['used'] = False
        pt['type'] = 'RAW'
        points.append(pt)

    return {
        'path': path, 'raw_lines': raw_lines,
        'p_start': p_start, 'p_end': p_end,
        'pfnum': pfnum, 'points': points,
    }


# ── Derived display helpers ───────────────────────────────────────────────────

def frame_label(point):
    """Return a human label for a point's coordinate frame.

    PULSE -> 'PULSE'; RECTAN with user frame -> 'USER#NN'; RECTAN base -> 'BASE'.
    """
    t = point.get('type')
    if t == 'PULSE':
        return 'PULSE'
    if t != 'RECTAN':
        return t or ''
    h2 = point.get('h2', 0)
    if h2 and h2 >= 1:
        return 'USER#%02d' % h2
    return 'BASE'


def axis_labels(point):
    """Return the axis label list appropriate to the point's type."""
    if point.get('type') == 'RECTAN':
        return RECTAN_AXES
    return PULSE_AXES


# ── Value formatting ──────────────────────────────────────────────────────────

def format_value(ptype, col, text):
    """Format one axis value string for writing, by type and column.

    PULSE -> integer; RECTAN -> fixed decimals (X/Y/Z 3 dp, rest 4 dp).
    Empty / unparseable input becomes the type's zero. Returns a string.
    """
    s = (text or '').strip().replace(',', '.')
    if ptype == 'RECTAN':
        dec = _RECTAN_DECIMALS[col] if col < len(_RECTAN_DECIMALS) else 4
        try:
            return f'{float(s):.{dec}f}'
        except (ValueError, TypeError):
            return f'{0.0:.{dec}f}'
    # PULSE / default → integer
    try:
        return str(int(round(float(s))))
    except (ValueError, TypeError):
        return '0'


def format_point_line(point):
    """Rebuild the exact VAR.DAT line (no trailing newline) for a point."""
    t = point.get('type')
    if not point.get('used') or t in ('UNUSED', None):
        if t == 'RAW':
            return point.get('raw', '').rstrip('\r\n')
        return '"UNUSED"'
    if t == 'RAW':
        return point.get('raw', '').rstrip('\r\n')

    config = (point.get('config') or '').strip()
    if not _CONFIG_RE.match(config):
        config = '0' * CONFIG_LEN

    header = [
        str(int(point.get('h0', 0))),
        str(int(point.get('h1', 0))),
        str(int(point.get('h2', 0))),
        config,
        str(int(point.get('h4', 0))),
        str(int(point.get('tool', 0))),
    ]
    vals = [format_value(t, i, v) for i, v in enumerate(point.get('values', []))]
    return '"%s"%s' % (t, ','.join(header + vals))


# ── Writing ───────────────────────────────────────────────────────────────────

def _detect_newline(raw_lines):
    """Return the dominant line ending used in the file ('\\r\\n' or '\\n')."""
    for raw in raw_lines:
        if raw.endswith('\r\n'):
            return '\r\n'
        if raw.endswith('\n'):
            return '\n'
    return '\r\n'


def write_var_dat(data, out_path, log_fn=None):
    """Write the (possibly edited) P data back to ``out_path``.

    Every non-edited line is written byte-for-byte from the original; only the
    points whose ``dirty`` flag is set are regenerated.  This guarantees an
    unmodified export is identical to the input.  Returns the number of points
    rewritten.  Raises on I/O failure (caller logs/handles).
    """
    raw_lines = list(data['raw_lines'])
    nl = _detect_newline(raw_lines)
    rewritten = 0

    for pt in data['points']:
        if not pt.get('dirty'):
            continue
        li = pt['line_index']
        new_line = format_point_line(pt) + nl
        raw_lines[li] = new_line
        rewritten += 1
        if log_fn:
            log_fn('log_posvar_line_written', 'P%03d' % pt['index'],
                   format_point_line(pt))

    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='latin-1', errors='replace', newline='') as fh:
        fh.write(''.join(raw_lines))
    os.replace(tmp, out_path)
    return rewritten


# ── PDF generation ────────────────────────────────────────────────────────────

def generate_posvar_pdf(points, output_path, file_label='',
                        headers=None, lang='IT', log_fn=None,
                        used_only=True):
    """Generate an A4-landscape PDF table of position variables.

    ``points`` is the list of point dicts from :func:`parse_var_dat`.
    ``headers`` optionally overrides the localized column titles dict with keys
    ``point,name,type,tool,config,axes``.  Returns True/False.
    """
    try:
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                         Paragraph, Spacer)
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor, black
    except ImportError as exc:
        if log_fn:
            log_fn('log_error_generic', f'reportlab: {exc}')
        return False
    from docs.utils import pdf_font, xml_escape
    fn   = pdf_font(lang)
    fn_b = pdf_font(lang, bold=True)

    h = {'point': 'P', 'name': 'Nome', 'type': 'Tipo', 'tool': 'Tool',
         'config': 'Config', 'axes': ['S/X', 'L/Y', 'U/Z', 'R/Rx',
                                      'B/Ry', 'T/Rz', 'E1', 'E2']}
    if headers:
        h.update(headers)

    rows_src = [p for p in points if (p.get('used') if used_only else True)]
    if not rows_src:
        if log_fn:
            log_fn('log_posvar_pdf_empty', file_label or '')
        return False

    accent   = HexColor('#D97757')
    row_gray = HexColor('#EFEFEF')
    styles   = getSampleStyleSheet()
    head_s = ParagraphStyle('PvHead', parent=styles['Normal'], fontSize=11,
                            fontName=fn_b, textColor=black, leftIndent=4 * mm)

    PAGE = landscape(A4)
    page_w = PAGE[0] - 20 * mm

    def draw_page(canvas, doc):
        """Draw the shared page header and a footer with the page number."""
        from docs.pdf_header import draw_page_header
        draw_page_header(canvas, doc)
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(HexColor('#888888'))
        canvas.drawCentredString(PAGE[0] / 2, 7 * mm, f'- {canvas.getPageNumber()} -')
        if file_label:
            canvas.drawRightString(PAGE[0] - 12 * mm, 7 * mm, file_label)
        canvas.restoreState()

    # Column widths (sum ≈ page_w on landscape A4 ≈ 277 mm usable)
    col_w = [16, 40, 24, 12, 0, 0, 0, 0, 0, 0, 0, 0]  # last 8 axis cols filled below
    fixed = [16, 40, 24, 12]                            # P, Name, Type, Tool (mm)
    axis_w = (page_w / mm - sum(fixed)) / 8
    COL_W = [c * mm for c in fixed] + [axis_w * mm] * 8

    hdr_row = [h['point'], h['name'], h['type'], h['tool']] + list(h['axes'])

    def _fmt_vals(p):
        """Return 8 display strings for a point's axis values, padded/trimmed."""
        vals = list(p.get('values', []))
        vals = (vals + [''] * 8)[:8]
        return [v if v not in (None,) else '' for v in vals]

    table_rows = [hdr_row]
    for p in rows_src:
        label = frame_label(p) if p.get('used') else (p.get('type') or '')
        name = p.get('name', '')
        table_rows.append(
            ['P%03d' % p['index'], name, label, str(p.get('tool', ''))]
            + _fmt_vals(p)
        )

    def _style(n):
        """Build the table style for n data rows (header colour + zebra)."""
        ts = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), accent),
            ('TEXTCOLOR',  (0, 0), (-1, 0), black),
            ('FONTNAME',   (0, 0), (-1, 0), fn_b),
            ('FONTSIZE',   (0, 0), (-1, 0), 7),
            ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME',   (0, 1), (-1, -1), 'Courier'),
            ('FONTSIZE',   (0, 1), (-1, -1), 6.5),
            ('GRID',       (0, 0), (-1, -1), 0.25, HexColor('#CCCCCC')),
            ('ALIGN',      (0, 1), (0, -1), 'CENTER'),
            ('ALIGN',      (2, 1), (3, -1), 'CENTER'),
            ('ALIGN',      (4, 1), (-1, -1), 'RIGHT'),
        ])
        for r in range(1, n + 1):
            if r % 2 == 0:
                ts.add('BACKGROUND', (0, r), (-1, r), row_gray)
        return ts

    story = []
    if file_label:
        head_tbl = Table([[Paragraph(xml_escape(file_label), head_s)]],
                         colWidths=[page_w])
        head_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), accent),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ]))
        story.append(head_tbl)
        story.append(Spacer(1, 2 * mm))

    tbl = Table(table_rows, colWidths=COL_W, repeatRows=1)
    tbl.setStyle(_style(len(table_rows) - 1))
    story.append(tbl)

    try:
        doc = SimpleDocTemplate(
            output_path, pagesize=PAGE,
            leftMargin=10 * mm, rightMargin=10 * mm,
            topMargin=22 * mm, bottomMargin=14 * mm,
        )
        doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
        if log_fn:
            log_fn('log_posvar_pdf_saved', output_path)
        return True
    except Exception as exc:
        if log_fn:
            log_fn('log_error_generic', f'PosVar PDF: {exc}')
        return False
