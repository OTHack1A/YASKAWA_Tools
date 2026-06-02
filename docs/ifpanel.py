"""
IF Panel data model for YASKAWA YRC1000.

File format (per panel, 15 panels total):
  //IFPANEL N
  ///NAME groupname_lang1,groupname_lang2
  ARRANGE,SETUP,SHAPE,SUBTYPE,COLOR,N1_L1,N2_L1,N3_L1,TCOLOR,SEC,ILOCK,
          IN_TYPE,IN_ADDR,IN_SUB,OUT_TYPE,OUT_ADDR,OUT_SUB,0,0,N1_L2,N2_L2,N3_L2,0

Field indices in the 23-element row list (index 0 = ARRANGE):
"""

PANEL_COUNT = 15
ROWS = [1, 2, 3, 4]
COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

TEXT_MAX_LEN = 8

# ── Field indices ─────────────────────────────────────────────────────────────
F_ARRANGE   = 0   # str:  cell id, e.g. "1A"
F_SETUP     = 1   # int:  0=INVALID, 1=VALID
F_SHAPE     = 2   # int:  panel shape code
F_SUBTYPE   = 3   # int:  panel subtype code
F_COLOR     = 4   # int:  panel color code
F_N1_L1     = 5   # str:  name word 1, language 1 (max 8 chars)
F_N2_L1     = 6   # str:  name word 2, language 1
F_N3_L1     = 7   # str:  name word 3, language 1
F_TCOLOR    = 8   # int:  text color code
F_SECURITY  = 9   # int:  security level
F_INTERLOCK = 10  # int:  interlock (0=PROHIBIT, 1=PERMIT)
F_IN_TYPE   = 11  # int:  input signal type
F_IN_ADDR   = 12  # int:  input address / variable index
F_IN_SUB    = 13  # int:  input sub-field (always 0)
F_OUT_TYPE  = 14  # int:  output signal type
F_OUT_ADDR  = 15  # int:  output address / variable index
F_OUT_SUB   = 16  # int:  output sub-field (always 0)
F_UNK1      = 17  # int:  reserved (always 0)
F_UNK2      = 18  # int:  reserved (always 0)
F_N1_L2     = 19  # str:  name word 1, language 2
F_N2_L2     = 20  # str:  name word 2, language 2
F_N3_L2     = 21  # str:  name word 3, language 2
F_UNK3      = 22  # int:  reserved (always 0)
FIELD_COUNT = 23

_INT_FIELDS = frozenset({
    F_SETUP, F_SHAPE, F_SUBTYPE, F_COLOR, F_TCOLOR, F_SECURITY, F_INTERLOCK,
    F_IN_TYPE, F_IN_ADDR, F_IN_SUB,
    F_OUT_TYPE, F_OUT_ADDR, F_OUT_SUB,
    F_UNK1, F_UNK2, F_UNK3,
})
_STR_FIELDS = frozenset({F_N1_L1, F_N2_L1, F_N3_L1, F_N1_L2, F_N2_L2, F_N3_L2})

# ── Option lists ──────────────────────────────────────────────────────────────
# Each entry: (code, label_key)  — label_key resolved via TRANSLATIONS

SHAPE_OPTIONS = [
    (0,  "ifpanel_shape_0"),   # CIRCLE
    (1,  "ifpanel_shape_1"),   # SQUARE 1
    (7,  "ifpanel_shape_7"),   # SQUARE 2
    (14, "ifpanel_shape_14"),  # SELECTOR SW
    (18, "ifpanel_shape_18"),  # PRESET COUNTER
    (19, "ifpanel_shape_19"),  # COUNTER
]

# Subtype options per shape code
SUBTYPE_BY_SHAPE = {
    0:  [(2, "ifpanel_sub_2"), (1, "ifpanel_sub_1"), (3, "ifpanel_sub_3")],
    1:  [(2, "ifpanel_sub_2"), (1, "ifpanel_sub_1"), (3, "ifpanel_sub_3")],
    7:  [(2, "ifpanel_sub_2"), (1, "ifpanel_sub_1"), (3, "ifpanel_sub_3")],
    14: [(1, "ifpanel_sub_sel_1"), (2, "ifpanel_sub_sel_2"), (3, "ifpanel_sub_sel_3")],
    18: [(0, "ifpanel_sub_cnt_0"), (1, "ifpanel_sub_cnt_1")],
    19: [(0, "ifpanel_sub_cnt_0"), (1, "ifpanel_sub_cnt_1")],
}
SUBTYPE_FALLBACK = [(0, "ifpanel_sub_0"), (1, "1"), (2, "2"), (3, "3")]

COLOR_OPTIONS = [
    (0, "ifpanel_color_0"),
    (1, "ifpanel_color_1"),
    (2, "ifpanel_color_2"),
    (3, "ifpanel_color_3"),
    (4, "ifpanel_color_4"),
    (5, "ifpanel_color_5"),
    (6, "ifpanel_color_6"),
    (7, "ifpanel_color_7"),
    (8, "ifpanel_color_8"),
]

IO_TYPE_OPTIONS = [
    (0, "ifpanel_io_0"),
    (1, "ifpanel_io_1"),
    (2, "ifpanel_io_2"),
    (3, "ifpanel_io_3"),
    (4, "ifpanel_io_4"),
]

SECURITY_OPTIONS = [
    (0, "ifpanel_sec_0"),
    (1, "ifpanel_sec_1"),
    (2, "ifpanel_sec_2"),
]

INTERLOCK_OPTIONS = [
    (0, "ifpanel_ilock_0"),
    (1, "ifpanel_ilock_1"),
]

SETUP_OPTIONS = [
    (0, "ifpanel_setup_0"),
    (1, "ifpanel_setup_1"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def cell_ids():
    """Return all 32 cell IDs in order: 1A, 1B, ..., 4H."""
    return [f"{r}{c}" for r in ROWS for c in COLS]


def _empty_row(cid):
    """Return a default (all-zero) IF-panel cell row for the given cell id."""
    return [cid, 0, 0, 0, 0, '', '', '', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', '', 0]


def _empty_panel(idx):
    """Return a default IF panel (HOME or 'Panel N') with every cell empty."""
    name = 'HOME' if idx == 0 else f'Panel {idx + 1}'
    return {
        'name_l1': name,
        'name_l2': name,
        'cells':   {cid: _empty_row(cid) for cid in cell_ids()},
    }


def _coerce(val, is_int, default):
    """Coerce a value to int (with a default) or to string, tolerating bad input."""
    if is_int:
        try:
            return int(str(val).strip()) if str(val).strip() else default
        except (ValueError, TypeError):
            return default
    return str(val) if val is not None else ''


# ── Parse ─────────────────────────────────────────────────────────────────────

def parse_ifpanel(filepath):
    """Parse IFPANEL.DAT → list of PANEL_COUNT panel dicts."""
    panels = []
    current = None

    try:
        with open(filepath, 'r', encoding='latin-1', errors='replace') as fh:
            lines = fh.readlines()
    except OSError:
        return [_empty_panel(i) for i in range(PANEL_COUNT)]

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        upper = line.upper()

        if upper.startswith('//IFPANEL'):
            if current is not None:
                panels.append(current)
            current = _empty_panel(len(panels))

        elif current is not None and upper.startswith('///NAME'):
            name_part = line[len('///NAME'):].strip()
            parts = name_part.split(',', 1)
            current['name_l1'] = parts[0].strip()
            current['name_l2'] = parts[1].strip() if len(parts) > 1 else current['name_l1']

        elif current is not None and line and not line.startswith('/'):
            parts = line.split(',')
            if not parts:
                continue
            cid = parts[0].strip().upper()
            if not (len(cid) == 2 and cid[0].isdigit() and cid[1].isalpha()):
                continue

            row = [cid]
            for j in range(1, FIELD_COUNT):
                raw_v = parts[j].strip() if j < len(parts) else ''
                is_int = j in _INT_FIELDS
                row.append(_coerce(raw_v, is_int, 0))

            current['cells'][cid] = row

    if current is not None:
        panels.append(current)

    while len(panels) < PANEL_COUNT:
        panels.append(_empty_panel(len(panels)))

    return panels[:PANEL_COUNT]


# ── Write ─────────────────────────────────────────────────────────────────────

def _san_text(val, max_len=TEXT_MAX_LEN):
    """Sanitize a text field for the fixed CSV structure.

    Commas (the field delimiter) and CR/LF (the line delimiter) are stripped so
    that no user-entered text can ever shift the field/line count — that is the
    single thing the teach pendant will not tolerate. The result is also clamped
    to ``max_len`` characters.
    """
    s = '' if val is None else str(val)
    s = s.replace('\r', '').replace('\n', '').replace(',', '')
    return s.strip()[:max_len]


def write_ifpanel(filepath, panels):
    """Write panels list → IFPANEL.DAT (latin-1, CRLF line endings).

    The output structure is fixed and self-correcting regardless of the input:
    exactly ``PANEL_COUNT`` panels, each with a header line, a name line, and the
    32 cell rows in canonical order, every data row carrying exactly
    ``FIELD_COUNT`` comma-separated values. Text is sanitized so user input can
    never corrupt the row/field count. This guarantees the file loads on the
    teach pendant.
    """
    ids = cell_ids()

    # Normalize the panel list to exactly PANEL_COUNT entries.
    panels = list(panels or [])
    if len(panels) > PANEL_COUNT:
        panels = panels[:PANEL_COUNT]
    while len(panels) < PANEL_COUNT:
        panels.append(_empty_panel(len(panels)))

    lines = []
    for i, panel in enumerate(panels):
        panel = panel or {}
        cells = panel.get('cells') or {}
        lines.append(f'//IFPANEL {i + 1}\r\n')
        n1 = _san_text(panel.get('name_l1', ''))
        n2 = _san_text(panel.get('name_l2', n1))
        lines.append(f'///NAME {n1},{n2}\r\n')
        for cid in ids:
            row = cells.get(cid)
            if not isinstance(row, (list, tuple)) or len(row) < FIELD_COUNT:
                row = _empty_row(cid)
            parts = [cid]
            for j in range(1, FIELD_COUNT):
                v = row[j] if j < len(row) else (0 if j in _INT_FIELDS else '')
                if j in _INT_FIELDS:
                    parts.append(str(_coerce(v, True, 0)))
                else:
                    parts.append(_san_text(v))
            lines.append(','.join(parts) + '\r\n')
    with open(filepath, 'w', encoding='latin-1', errors='replace', newline='') as fh:
        fh.writelines(lines)


def resolve_options(opt_list, t):
    """Resolve (code, key) list → (code, label) list using translation dict t."""
    return [(code, t.get(key, key)) for code, key in opt_list]
