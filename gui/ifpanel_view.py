import re as _re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QComboBox,
    QFrame, QLineEdit, QHeaderView, QFileDialog, QStackedWidget,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont

from translations import TRANSLATIONS
import logger
from docs.ifpanel import (
    PANEL_COUNT, FIELD_COUNT, TEXT_MAX_LEN,
    F_ARRANGE, F_SETUP, F_SHAPE, F_SUBTYPE, F_COLOR,
    F_N1_L1, F_N2_L1, F_N3_L1, F_TCOLOR, F_SECURITY, F_INTERLOCK,
    F_IN_TYPE, F_IN_ADDR, F_IN_SUB, F_OUT_TYPE, F_OUT_ADDR, F_OUT_SUB,
    F_UNK1, F_UNK2, F_N1_L2, F_N2_L2, F_N3_L2, F_UNK3,
    SHAPE_OPTIONS, SUBTYPE_BY_SHAPE, SUBTYPE_FALLBACK,
    COLOR_OPTIONS, IO_TYPE_OPTIONS, SECURITY_OPTIONS, SETUP_OPTIONS,
    cell_ids, _empty_row, resolve_options,
)

_INT_ADDR_RE  = _re.compile(r'^\d{0,5}$')
_NAME_RE      = _re.compile(r'^[A-Za-z0-9 _\-\.]*$')
_NAME_STRIP   = _re.compile(r'[^A-Za-z0-9 _\-\.]')

# IO type code sets used by _io_rules()
_IO_SIGNAL = frozenset({0, 1})        # --- and SIGNAL
_IO_VAR    = frozenset({0, 2, 3, 4})  # --- and B/I/M variable


def _io_rules(shape, subtype):
    """Return (in_codes, out_codes, has_output) for given shape+subtype.
    Codes match IO_TYPE_OPTIONS: 0=---, 1=Signal, 2=B var, 3=I var, 4=M reg."""
    if shape in (18, 19):        # PRESET COUNTER, COUNTER
        return _IO_VAR, _IO_VAR, (shape == 18)
    if shape == 14:              # SELECTOR SW
        return _IO_SIGNAL, _IO_SIGNAL, True
    if shape in (0, 1, 7):       # CIRCLE, SQUARE 1, SQUARE 2
        has_out = (shape in (1, 7) and subtype != 2)
        return _IO_SIGNAL, _IO_SIGNAL, has_out
    return frozenset({0, 1, 2, 3, 4}), frozenset({0, 1, 2, 3, 4}), True


# Table column → field index mapping (for non-combo text columns)
_TEXT_COL_FIELD = {
    5:  F_N1_L1,
    6:  F_N2_L1,
    7:  F_N3_L1,
    12: F_IN_ADDR,
    14: F_OUT_ADDR,
    15: F_N1_L2,
    16: F_N2_L2,
    17: F_N3_L2,
}
_NAME_COLS = frozenset({5, 6, 7, 15, 16, 17})
_ADDR_COLS = frozenset({12, 14})

# Combo columns → field index
_COMBO_COL_FIELD = {
    1:  F_SETUP,
    2:  F_SHAPE,
    3:  F_SUBTYPE,
    4:  F_COLOR,
    8:  F_TCOLOR,
    9:  F_SECURITY,
    11: F_IN_TYPE,
    13: F_OUT_TYPE,
}

_N_COLS = 18  # table columns

# Stylesheet applied to OUTPUT combo when OUTPUT is not available for the row
_COMBO_HIDDEN_SS = (
    "QComboBox { background: transparent; color: transparent; border: none; }"
    "QComboBox::drop-down { border: none; image: none; width: 0; }"
)

# ── Preview widget ─────────────────────────────────────────────────────────────

# Panel colour codes → on-screen hue, matched to the real YRC1000 teach pendant.
# Code 0 (BLACK) is a real, selectable colour — it must NOT be treated as "unset".
_PREVIEW_COLORS = {
    0: QColor('#202020'),   # BLACK
    1: QColor('#909090'),   # GRAY
    2: QColor('#e02424'),   # RED
    3: QColor('#18c818'),   # GREEN
    4: QColor('#e0c000'),   # YELLOW
    5: QColor('#2858e0'),   # BLUE
    6: QColor('#f0f0f0'),   # WHITE
    7: QColor('#20b8d0'),   # SKY BLUE / CYAN
    8: QColor('#c020a0'),   # MAGENTA
}
# Teach-pendant style: light 3D button face on a light blue-grey panel, dark text.
_CELL_BG      = QColor('#b9bdc6')   # active button face (light grey, like the TP)
_CELL_BG_OFF  = QColor('#cdd2db')   # empty slot (very light, almost flush with panel)
_CELL_BORDER  = QColor('#6f747e')
_TEXT_ON      = QColor('#101010')   # labels are dark on the light button face
_TEXT_OFF     = QColor('#8a8f99')
_LCD_BG       = QColor('#f4f4ec')   # counter window is a light LCD with dark digits
_LCD_FG       = QColor('#101010')


class _IFPanelPreview(QWidget):
    """Draws the teach-pendant style 4×8 IF Panel grid — fills available space."""

    _GAP = 3   # gap between cells
    _OX  = 10  # left/right margin
    _OY  = 10  # top/bottom margin

    def __init__(self, panel, is_dark, parent=None):
        """Initialise the IF-panel preview widget for a panel."""
        super().__init__(parent)
        self._panel   = panel
        self._is_dark = is_dark
        self._ids     = cell_ids()
        self.setMinimumSize(400, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_panel(self, panel):
        """Set the panel to render and repaint."""
        self._panel = panel
        self.update()

    def _cell_dims(self):
        """Return the cell width and height for the current widget size."""
        W = max(self.width(),  400)
        H = max(self.height(), 200)
        cw = (W - 2 * self._OX - 7 * self._GAP) // 8
        ch = (H - 2 * self._OY - 3 * self._GAP) // 4
        return max(cw, 50), max(ch, 40)

    def paintEvent(self, event):
        """Paint the 15-cell IF panel."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        bg = QColor('#3a4250') if self._is_dark else QColor('#c3cdd9')
        painter.fillRect(self.rect(), bg)
        cw, ch = self._cell_dims()
        for idx, cid in enumerate(self._ids):
            row_i = idx // 8
            col_i = idx % 8
            x = self._OX + col_i * (cw + self._GAP)
            y = self._OY + row_i * (ch + self._GAP)
            row = self._panel['cells'].get(cid, _empty_row(cid))
            self._draw_cell(painter, x, y, cw, ch, cid, row)
        painter.end()

    def _draw_cell(self, painter, x, y, w, h, cid, row):
        """Paint a single IF-panel cell (background colour, label, and I/O assignment)."""
        try:
            setup   = int(row[F_SETUP])
            shape   = int(row[F_SHAPE])
            subtype = int(row[F_SUBTYPE])
            color_c = int(row[F_COLOR])
            tcolor_c = int(row[F_TCOLOR])
            n1 = str(row[F_N1_L1])
            n2 = str(row[F_N2_L1])
            n3 = str(row[F_N3_L1])
        except Exception:
            setup = shape = subtype = color_c = tcolor_c = 0
            n1 = n2 = n3 = ''

        # The configured panel colour drives the ring/border/symbol. Code 0 (BLACK)
        # is a valid colour, so always resolve via the table — never fall back to a
        # default just because the code happens to be 0.
        panel_col = _PREVIEW_COLORS.get(color_c, _PREVIEW_COLORS[0])
        text_col  = _PREVIEW_COLORS.get(tcolor_c, _TEXT_ON)
        radius = max(3, w // 14)

        if not setup:
            painter.setBrush(QBrush(_CELL_BG_OFF))
            painter.setPen(QPen(_CELL_BORDER, 1))
            painter.drawRoundedRect(x, y, w, h, radius, radius)
            f = QFont(); f.setPointSize(max(5, h // 9))
            painter.setFont(f)
            painter.setPen(_TEXT_OFF)
            painter.drawText(x + 3, y + 3, w - 6, h // 3, Qt.AlignLeft | Qt.AlignTop, cid)
            return

        # Active cell background
        painter.setBrush(QBrush(_CELL_BG))
        painter.setPen(QPen(_CELL_BORDER, 1))
        painter.drawRoundedRect(x, y, w, h, radius, radius)

        # Top highlight strip
        hi = QColor(255, 255, 255, 28)
        painter.setBrush(QBrush(hi))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(x + 2, y + 1, w - 4, h // 3, radius, radius)

        sym_pad = max(5, w // 10)

        if shape == 0:           # CIRCLE
            cx_  = x + w // 2
            cy_  = y + h // 2
            r_   = min(w, h) // 2 - sym_pad
            ring = panel_col
            painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
            painter.setPen(QPen(ring, max(2, w // 22)))
            painter.drawEllipse(cx_ - r_, cy_ - r_, r_ * 2, r_ * 2)
            # inner fill hint
            inner = QColor(ring)
            inner.setAlpha(40)
            painter.setBrush(QBrush(inner))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(cx_ - r_ + 2, cy_ - r_ + 2, r_ * 2 - 4, r_ * 2 - 4)

        elif shape in (1, 7):    # SQUARE 1 / SQUARE 2
            if subtype == 2:     # indication only — coloured outline
                painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
                painter.setPen(QPen(panel_col, max(2, w // 22)))
                painter.drawRoundedRect(x + sym_pad, y + sym_pad,
                                        w - sym_pad*2, h - sym_pad*2, radius, radius)
            else:                # push / hold — light face with coloured frame
                painter.setBrush(QBrush(_CELL_BG.lighter(108)))
                painter.setPen(QPen(panel_col, max(2, w // 18)))
                painter.drawRoundedRect(x + sym_pad, y + sym_pad,
                                        w - sym_pad*2, h - sym_pad*2, radius, radius)

        elif shape in (18, 19):  # COUNTER / PRESET COUNTER
            bw_ = w - sym_pad * 2
            bh_ = max(10, h // 3)
            bx_ = x + sym_pad
            by_ = y + (h - bh_) // 2
            painter.fillRect(bx_, by_, bw_, bh_, _LCD_BG)
            painter.setPen(QPen(_CELL_BORDER, 1))
            painter.drawRect(bx_, by_, bw_, bh_)
            f_lcd = QFont('Courier'); f_lcd.setPointSize(max(5, bh_ // 2))
            f_lcd.setBold(True)
            painter.setFont(f_lcd)
            painter.setPen(_LCD_FG)
            painter.drawText(bx_, by_, bw_, bh_, Qt.AlignCenter, '8 8 8')

        elif shape == 14:        # SELECTOR SW
            mid_y = y + h // 2
            sw_col = panel_col
            trk_w = max(2, h // 10)
            painter.setPen(QPen(sw_col, trk_w))
            painter.drawLine(x + sym_pad, mid_y, x + w - sym_pad, mid_y)
            knob_r = max(5, h // 7)
            painter.setBrush(QBrush(sw_col))
            painter.setPen(QPen(sw_col.lighter(150), 1))
            painter.drawEllipse(x + sym_pad - knob_r // 2, mid_y - knob_r,
                                knob_r * 2, knob_r * 2)

        # Cell ID — small, top-left, muted dark (readable on the light face)
        f_id = QFont(); f_id.setPointSize(max(5, h // 9))
        painter.setFont(f_id)
        painter.setPen(_TEXT_OFF)
        painter.drawText(x + 3, y + 2, w - 6, h // 4, Qt.AlignLeft | Qt.AlignTop, cid)

        # Name text — center, in the configured TEXT COLOR
        name_parts = [p for p in [n1, n2, n3] if p]
        if name_parts:
            name_text = '\n'.join(name_parts)
            f_nm = QFont(); f_nm.setPointSize(max(6, h // 7))
            f_nm.setBold(True)
            painter.setFont(f_nm)
            painter.setPen(text_col)
            painter.drawText(x + 3, y + h // 4, w - 6, h * 3 // 4,
                             Qt.AlignCenter | Qt.TextWordWrap, name_text)


# ── Main view ─────────────────────────────────────────────────────────────────

class IFPanelView(QWidget):

    def __init__(self, filepath, app_state, on_close_cb):
        """Build the IF-panel editor view for the given file."""
        super().__init__()
        self._filepath     = filepath
        self._app_state    = app_state
        self._on_close     = on_close_cb
        self._panels       = []
        self._tab_info     = {}  # tab_idx → TabInfo dict
        self._built_tabs   = set()
        self._preview_panel_idx = 0
        self._load()
        self._build_ui()
        self._apply_theme()

    # ── Load ──────────────────────────────────────────────────────────────────

    def _load(self):
        """Parse the IFPANEL.DAT file into the editable panel data."""
        try:
            from docs.ifpanel import parse_ifpanel
            self._panels = parse_ifpanel(self._filepath)
        except Exception as exc:
            logger.error("log_error_generic", str(exc))
            from docs.ifpanel import _empty_panel
            self._panels = [_empty_panel(i) for i in range(PANEL_COUNT)]

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Build the view's widgets (tabbed editable panel tables and buttons)."""
        t = TRANSLATIONS[self._app_state.language]
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        # ── Global toolbar
        tb = QHBoxLayout()
        tb.setSpacing(6)
        self._lbl_title = QLabel(t.get("ifpanel_view_title", "IFPanel — YASKAWA YRC1000"))
        self._lbl_title.setStyleSheet("font-weight:bold; font-size:10pt;")
        tb.addWidget(self._lbl_title)
        tb.addStretch()
        self._btn_export = QPushButton(t.get("ifpanel_btn_export", "ESPORTA"))
        self._btn_export.setFixedHeight(26)
        self._btn_export.clicked.connect(self._on_export)
        tb.addWidget(self._btn_export)
        self._btn_close_main = QPushButton(t.get("preview_close", "Chiudi"))
        self._btn_close_main.setFixedHeight(26)
        self._btn_close_main.clicked.connect(self._on_close_main)
        tb.addWidget(self._btn_close_main)
        root.addLayout(tb)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # ── Stacked widget: page 0 = table editor, page 1 = preview
        self._stacked = QStackedWidget()

        # ── Page 0: Tab widget with 15 panels
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(True)
        tab_label = t.get("ifpanel_tab_label", "Panel {}")
        for i in range(PANEL_COUNT):
            placeholder = QWidget()
            pl_lay = QVBoxLayout(placeholder)
            pl_lay.addWidget(QLabel("..."))
            self._tab_widget.addTab(placeholder, tab_label.format(i + 1))
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self._stacked.addWidget(self._tab_widget)

        # ── Page 1: Preview
        preview_page = QWidget()
        pp_lay = QVBoxLayout(preview_page)
        pp_lay.setContentsMargins(4, 4, 4, 4)
        pp_lay.setSpacing(4)

        # Preview toolbar
        ptb = QHBoxLayout()
        self._lbl_preview = QLabel()
        self._lbl_preview.setStyleSheet("font-weight:bold; font-size:10pt;")
        ptb.addWidget(self._lbl_preview)
        ptb.addStretch()
        self._btn_preview_close = QPushButton(t.get("ifpanel_preview_close", "Chiudi Anteprima"))
        self._btn_preview_close.setFixedHeight(26)
        self._btn_preview_close.clicked.connect(self._on_preview_close)
        ptb.addWidget(self._btn_preview_close)
        pp_lay.addLayout(ptb)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine); sep2.setFrameShadow(QFrame.Sunken)
        pp_lay.addWidget(sep2)

        # Preview fills all available space directly (no scroll)
        self._preview_widget = _IFPanelPreview(
            self._panels[0], self._app_state.is_dark_mode)
        pp_lay.addWidget(self._preview_widget, 1)

        self._stacked.addWidget(preview_page)
        root.addWidget(self._stacked, 1)

        # Build first tab immediately
        self._build_tab(0)
        self._tab_widget.setCurrentIndex(0)

    def _on_tab_changed(self, idx):
        """Handle switching between panel tabs."""
        self._build_tab(idx)

    def _build_tab(self, tab_idx):
        """Build the editable table for one panel tab."""
        if tab_idx in self._built_tabs:
            return
        self._built_tabs.add(tab_idx)
        t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
        panel = self._panels[tab_idx]

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        # ── Group name row
        gn_row = QHBoxLayout()
        gn_row.setSpacing(6)
        lbl_l1 = QLabel(t.get("ifpanel_group_l1_lbl", "Nome Gruppo (L1):"))
        gn_row.addWidget(lbl_l1)
        name_l1 = QLineEdit(panel.get('name_l1', ''))
        name_l1.setMaximumWidth(160)
        name_l1.textChanged.connect(
            lambda txt, ti=tab_idx: self._on_group_name(ti, 'name_l1', txt))
        gn_row.addWidget(name_l1)

        lbl_l2 = QLabel(t.get("ifpanel_group_l2_lbl", "Nome Gruppo (L2):"))
        gn_row.addWidget(lbl_l2)
        name_l2 = QLineEdit(panel.get('name_l2', ''))
        name_l2.setMaximumWidth(160)
        name_l2.textChanged.connect(
            lambda txt, ti=tab_idx: self._on_group_name(ti, 'name_l2', txt))
        gn_row.addWidget(name_l2)

        gn_row.addStretch()
        btn_preview = QPushButton(t.get("ifpanel_btn_preview", "Anteprima"))
        btn_preview.setFixedHeight(24)
        btn_preview.clicked.connect(lambda _, ti=tab_idx: self._on_preview(ti))
        gn_row.addWidget(btn_preview)
        lay.addLayout(gn_row)

        # ── Table
        ids = cell_ids()
        tbl = QTableWidget(len(ids), _N_COLS)
        tbl.setHorizontalHeaderLabels(self._col_headers(t))
        tbl.setAlternatingRowColors(True)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.verticalHeader().setVisible(False)
        tbl.horizontalHeader().setStretchLastSection(False)
        tbl.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.AnyKeyPressed)

        combos = {}   # row_idx → {col_idx: QComboBox}

        # Prepare option lists
        setup_opts   = resolve_options(SETUP_OPTIONS,     t)
        color_opts   = resolve_options(COLOR_OPTIONS,     t)
        io_type_opts = resolve_options(IO_TYPE_OPTIONS,   t)
        shape_opts   = resolve_options(SHAPE_OPTIONS,     t)

        for r, cid in enumerate(ids):
            row = panel['cells'].get(cid, _empty_row(cid))

            def _int(fi, _row=row):
                """Read a panel field's text as int (row-bound helper)."""
                try: return int(str(_row[fi]).strip())
                except: return 0

            def _str(fi, _row=row):
                """Read a panel field's text as string (row-bound helper)."""
                return str(_row[fi]) if _row[fi] is not None else ''

            # Auto-set SECURITY = 1 (Editing Mode) — hidden from UI
            row[F_SECURITY] = 1
            # No interlock field exists in the YRC1000 row — force its reserved
            # slot to 0 (the column is hidden) so it can never break the load.
            row[F_INTERLOCK] = 0

            # Col 0: Cell ID (read-only)
            ci = QTableWidgetItem(cid)
            ci.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            ci.setTextAlignment(Qt.AlignCenter)
            tbl.setItem(r, 0, ci)

            # Col 1: Setup
            s_cb = self._make_combo(setup_opts, _int(F_SETUP))
            s_cb.currentIndexChanged.connect(
                lambda _, ri=r, ti=tab_idx, cid_=cid, cb=s_cb:
                    self._combo_changed(ti, ri, cid_, F_SETUP, cb))
            tbl.setCellWidget(r, 1, s_cb)
            self._wire_combo_log(s_cb, tab_idx, cid, 1)

            # Col 2: Shape
            sh_cb = self._make_combo(shape_opts, _int(F_SHAPE))
            cur_shape = _int(F_SHAPE)
            tbl.setCellWidget(r, 2, sh_cb)
            self._wire_combo_log(sh_cb, tab_idx, cid, 2)

            # Col 3: Subtype (depends on shape)
            sub_opts = resolve_options(SUBTYPE_BY_SHAPE.get(cur_shape, SUBTYPE_FALLBACK), t)
            sub_cb = self._make_combo(sub_opts, _int(F_SUBTYPE))
            sub_cb.currentIndexChanged.connect(
                lambda _, ri=r, ti=tab_idx, cid_=cid, cb=sub_cb:
                    self._on_subtype_changed(ti, ri, cid_, cb))
            tbl.setCellWidget(r, 3, sub_cb)
            self._wire_combo_log(sub_cb, tab_idx, cid, 3)

            # Wire shape change → rebuild subtype + IO rules
            sh_cb.currentIndexChanged.connect(
                lambda _, ri=r, ti=tab_idx, cid_=cid, sh=sh_cb, su=sub_cb:
                    self._on_shape_changed(ti, ri, cid_, sh, su))

            # Col 4: Panel color
            pc_cb = self._make_combo(color_opts, _int(F_COLOR))
            pc_cb.currentIndexChanged.connect(
                lambda _, ri=r, ti=tab_idx, cid_=cid, cb=pc_cb:
                    self._combo_changed(ti, ri, cid_, F_COLOR, cb))
            tbl.setCellWidget(r, 4, pc_cb)
            self._wire_combo_log(pc_cb, tab_idx, cid, 4)

            # Col 5-7: Name L1
            for col, fi in ((5, F_N1_L1), (6, F_N2_L1), (7, F_N3_L1)):
                tbl.setItem(r, col, QTableWidgetItem(_str(fi)))

            # Col 8: Text color
            tc_cb = self._make_combo(color_opts, _int(F_TCOLOR))
            tc_cb.currentIndexChanged.connect(
                lambda _, ri=r, ti=tab_idx, cid_=cid, cb=tc_cb:
                    self._combo_changed(ti, ri, cid_, F_TCOLOR, cb))
            tbl.setCellWidget(r, 8, tc_cb)
            self._wire_combo_log(tc_cb, tab_idx, cid, 8)

            # Col 9: Security — hidden, auto-managed (no combo created)
            tbl.setItem(r, 9, QTableWidgetItem(""))

            # Col 10: Interlock — hidden, no real field (reserved, kept at 0)
            tbl.setItem(r, 10, QTableWidgetItem(""))

            # Col 11: Input type
            it_cb = self._make_combo(io_type_opts, _int(F_IN_TYPE))
            it_cb.currentIndexChanged.connect(
                lambda _, ri=r, ti=tab_idx, cid_=cid, cb=it_cb:
                    self._combo_changed(ti, ri, cid_, F_IN_TYPE, cb))
            tbl.setCellWidget(r, 11, it_cb)
            self._wire_combo_log(it_cb, tab_idx, cid, 11)

            # Col 12: Input address (empty when zero)
            in_addr_val = _int(F_IN_ADDR)
            tbl.setItem(r, 12, QTableWidgetItem("" if in_addr_val == 0 else str(in_addr_val)))

            # Col 13: Output type
            ot_cb = self._make_combo(io_type_opts, _int(F_OUT_TYPE))
            ot_cb.currentIndexChanged.connect(
                lambda _, ri=r, ti=tab_idx, cid_=cid, cb=ot_cb:
                    self._combo_changed(ti, ri, cid_, F_OUT_TYPE, cb))
            tbl.setCellWidget(r, 13, ot_cb)
            self._wire_combo_log(ot_cb, tab_idx, cid, 13)

            # Col 14: Output address (empty when zero)
            out_addr_val = _int(F_OUT_ADDR)
            tbl.setItem(r, 14, QTableWidgetItem("" if out_addr_val == 0 else str(out_addr_val)))

            # Col 15-17: Name L2
            for col, fi in ((15, F_N1_L2), (16, F_N2_L2), (17, F_N3_L2)):
                tbl.setItem(r, col, QTableWidgetItem(_str(fi)))

            combos[r] = {
                1: s_cb, 2: sh_cb, 3: sub_cb, 4: pc_cb,
                8: tc_cb, 11: it_cb, 13: ot_cb,
            }

        # Stretch all columns to fill available horizontal space
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        tbl.verticalHeader().setDefaultSectionSize(22)

        tbl.cellClicked.connect(
            lambda r, c, ti=tab_idx: self._on_cell_clicked(ti, r, c))
        tbl.itemChanged.connect(
            lambda item, ti=tab_idx: self._on_item_changed(ti, item, ids))

        lay.addWidget(tbl, 1)

        tbl.setColumnHidden(9, True)    # SECURITY — hidden, auto-set to Editing Mode
        tbl.setColumnHidden(10, True)   # INTERLOCK — hidden, no real field (kept 0)

        self._tab_info[tab_idx] = {
            'name_l1':     name_l1,
            'name_l2':     name_l2,
            'lbl_l1':      lbl_l1,
            'lbl_l2':      lbl_l2,
            'btn_preview': btn_preview,
            'table':       tbl,
            'combos':      combos,
            'ids':         ids,
        }

        # Apply IO filtering rules to every row (hides OUTPUT where not applicable)
        tbl.blockSignals(True)
        for r_idx, cid_r in enumerate(ids):
            self._apply_io_rules_row(tab_idx, r_idx, cid_r)
        tbl.blockSignals(False)

        self._tab_widget.removeTab(tab_idx)
        self._tab_widget.insertTab(tab_idx, container,
                                   TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
                                   .get("ifpanel_tab_label", "Panel {}").format(tab_idx + 1))
        self._tab_widget.setCurrentIndex(tab_idx)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_combo(opts, cur_val):
        """Build a combo box with the given options and current value."""
        cb = QComboBox()
        for code, label in opts:
            cb.addItem(label, code)
        idx = next((i for i, (c, _) in enumerate(opts) if c == cur_val), 0)
        cb.setCurrentIndex(idx)
        return cb

    @staticmethod
    def _col_headers(t=None):
        """Return the localized column headers for the panel table."""
        if t is None:
            t = {}
        return [
            t.get("ifpanel_col_arrange",  "ARRANGE"),
            t.get("ifpanel_col_setup",    "SETUP"),
            t.get("ifpanel_col_shape",    "PANEL TYPE"),
            t.get("ifpanel_col_subtype",  "SUBTYPE"),
            t.get("ifpanel_col_color",    "PANEL COLOR"),
            "Descr 1 (ITA)",
            "Descr 2 (ITA)",
            "Descr 3 (ITA)",
            t.get("ifpanel_col_tcolor",    "TEXT COLOR"),
            t.get("ifpanel_col_security",  "SECURITY"),
            t.get("ifpanel_col_interlock", "INTERLOCK"),
            t.get("ifpanel_col_in_type",   "INPUT"),
            t.get("ifpanel_col_in_addr",   "IN Addr"),
            t.get("ifpanel_col_out_type",  "OUTPUT"),
            t.get("ifpanel_col_out_addr",  "OUT Addr"),
            "Descr 1 (EN)",
            "Descr 2 (EN)",
            "Descr 3 (EN)",
        ]

    # ── Combo click logging ───────────────────────────────────────────────────

    def _wire_combo_log(self, cb, tab_idx, cid, col_idx):
        """Connect a combo box so its changes are logged and applied."""
        cb._log_tab     = tab_idx
        cb._log_cid     = cid
        cb._log_col_idx = col_idx
        cb.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Qt event filter: intercept events for the watched widgets."""
        if event.type() == QEvent.Type.MouseButtonPress:
            tab  = getattr(obj, '_log_tab',     None)
            cid  = getattr(obj, '_log_cid',     None)
            cidx = getattr(obj, '_log_col_idx', None)
            if tab is not None and cid is not None:
                try:
                    t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
                    hdrs = self._col_headers(t)
                    col_name = hdrs[cidx] if cidx is not None and cidx < len(hdrs) else str(cidx)
                    logger.info("log_ifpanel_cell_clicked", tab + 1, cid, col_name)
                except Exception:
                    pass
        return super().eventFilter(obj, event)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_group_name(self, tab_idx, key, text):
        """Handle editing a panel group's name."""
        try:
            self._panels[tab_idx][key] = text
            t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
            logger.info("log_ifpanel_group_changed", tab_idx + 1, key, text)
        except Exception:
            pass

    def _combo_changed(self, tab_idx, row_idx, cid, field_idx, combo):
        """Handle a combo selection change in a panel cell."""
        try:
            val = combo.currentData()
            if val is None:
                return
            self._panels[tab_idx]['cells'][cid][field_idx] = val
            t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
            logger.info("log_ifpanel_cell_changed", tab_idx + 1, cid,
                        _FIELD_LABELS.get(field_idx, str(field_idx)), val)
        except Exception as exc:
            logger.error("log_error_generic", str(exc))

    def _on_shape_changed(self, tab_idx, row_idx, cid, shape_cb, sub_cb):
        """Handle a cell's shape change and refresh its sub-type options."""
        try:
            shape_val = shape_cb.currentData()
            self._panels[tab_idx]['cells'][cid][F_SHAPE] = shape_val
            t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
            opts = resolve_options(SUBTYPE_BY_SHAPE.get(shape_val, SUBTYPE_FALLBACK), t)
            cur_sub = self._panels[tab_idx]['cells'][cid][F_SUBTYPE]
            sub_cb.blockSignals(True)
            sub_cb.clear()
            for code, label in opts:
                sub_cb.addItem(label, code)
            idx = next((i for i, (c, _) in enumerate(opts) if c == cur_sub), 0)
            sub_cb.setCurrentIndex(idx)
            sub_cb.blockSignals(False)
            self._apply_io_rules_row(tab_idx, row_idx, cid)
            logger.info("log_ifpanel_cell_changed", tab_idx + 1, cid, "SHAPE", shape_val)
        except Exception as exc:
            logger.error("log_error_generic", str(exc))

    def _on_subtype_changed(self, tab_idx, row_idx, cid, sub_cb):
        """Handle a cell's sub-type change."""
        try:
            val = sub_cb.currentData()
            if val is None:
                return
            self._panels[tab_idx]['cells'][cid][F_SUBTYPE] = val
            self._apply_io_rules_row(tab_idx, row_idx, cid)
            logger.info("log_ifpanel_cell_changed", tab_idx + 1, cid, "SUBTYPE", val)
        except Exception as exc:
            logger.error("log_error_generic", str(exc))

    def _apply_io_rules_row(self, tab_idx, row_idx, cid):
        """Update INPUT/OUTPUT type combos and Out Addr editability based on shape+subtype."""
        try:
            ti = self._tab_info.get(tab_idx)
            if not ti:
                return
            cb_map = ti['combos'].get(row_idx, {})
            tbl    = ti.get('table')
            if not tbl:
                return

            t    = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS['IT'])
            cell = self._panels[tab_idx]['cells'].get(cid)
            if cell is None:
                return

            try:
                shape   = int(str(cell[F_SHAPE]).strip()   or 0)
                subtype = int(str(cell[F_SUBTYPE]).strip() or 0)
            except (ValueError, TypeError):
                shape = subtype = 0

            in_codes, out_codes, has_output = _io_rules(shape, subtype)
            all_opts = resolve_options(IO_TYPE_OPTIONS, t)

            # Update INPUT type combo
            it_cb = cb_map.get(11)
            if it_cb:
                in_opts = [(c, l) for c, l in all_opts if c in in_codes]
                cur_in  = it_cb.currentData()
                if cur_in not in in_codes:
                    cur_in = next((c for c in in_codes if c != 0), 0)
                    cell[F_IN_TYPE] = cur_in
                it_cb.blockSignals(True)
                it_cb.clear()
                for code, label in in_opts:
                    it_cb.addItem(label, code)
                idx = next((i for i, (c, _) in enumerate(in_opts) if c == cur_in), 0)
                it_cb.setCurrentIndex(idx)
                it_cb.blockSignals(False)

            # Update OUTPUT type combo — visually hide via stylesheet when not available.
            # Never remove/replace the combo widget (Qt ownership issues).
            ot_cb = cb_map.get(13)
            if ot_cb:
                if has_output:
                    out_opts = [(c, l) for c, l in all_opts if c in out_codes]
                    cur_out  = ot_cb.currentData()
                    if cur_out not in out_codes:
                        cur_out = 0
                        cell[F_OUT_TYPE] = 0
                    ot_cb.blockSignals(True)
                    ot_cb.clear()
                    for code, label in out_opts:
                        ot_cb.addItem(label, code)
                    idx = next((i for i, (c, _) in enumerate(out_opts) if c == cur_out), 0)
                    ot_cb.setCurrentIndex(idx)
                    ot_cb.blockSignals(False)
                    ot_cb.setEnabled(True)
                    ot_cb.setStyleSheet("")   # restore inherited theme style
                else:
                    # Visually hide — keep widget in cell to avoid Qt ownership issues
                    ot_cb.blockSignals(True)
                    ot_cb.clear()
                    ot_cb.blockSignals(False)
                    ot_cb.setEnabled(False)
                    ot_cb.setStyleSheet(_COMBO_HIDDEN_SS)
                    cell[F_OUT_TYPE] = 0

            # Update Out Addr cell — clear and lock when OUTPUT not available
            out_item = tbl.item(row_idx, 14)
            if out_item:
                if has_output:
                    out_item.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                else:
                    out_item.setFlags(Qt.ItemIsEnabled)
                    tbl.blockSignals(True)
                    out_item.setText('')
                    tbl.blockSignals(False)
                    cell[F_OUT_ADDR] = 0

        except Exception as exc:
            logger.error('log_error_generic', str(exc))

    def _on_item_changed(self, tab_idx, item, ids):
        """Handle an edit to a table item and write it back to the panel data."""
        if item is None:
            return
        try:
            r   = item.row()
            col = item.column()
            txt = item.text()
            fi  = _TEXT_COL_FIELD.get(col)
            if fi is None:
                return
            if col in _NAME_COLS:
                cleaned = _NAME_STRIP.sub('', txt) if not _NAME_RE.match(txt) else txt
                if not _NAME_RE.match(txt):
                    logger.warning("log_invalid_input", txt)
                    tbl = self._tab_info.get(tab_idx, {}).get('table')
                    if tbl:
                        tbl.blockSignals(True)
                        item.setText(cleaned)
                        tbl.blockSignals(False)
                    txt = cleaned
                if len(txt) > TEXT_MAX_LEN:
                    logger.warning("log_invalid_input",
                                   f"{txt} (max {TEXT_MAX_LEN})")
                    txt = txt[:TEXT_MAX_LEN]
                    tbl = self._tab_info.get(tab_idx, {}).get('table')
                    if tbl:
                        tbl.blockSignals(True)
                        item.setText(txt)
                        tbl.blockSignals(False)
            elif col in _ADDR_COLS:
                # Skip non-editable OUT Addr cells (OUTPUT disabled for this shape)
                if not (item.flags() & Qt.ItemIsEditable):
                    return
                if txt and not _INT_ADDR_RE.match(txt):
                    logger.warning("log_invalid_input", txt)
                    cleaned = _re.sub(r'[^\d]', '', txt)[:5]
                    tbl = self._tab_info.get(tab_idx, {}).get('table')
                    if tbl:
                        tbl.blockSignals(True)
                        item.setText(cleaned)
                        tbl.blockSignals(False)
                    txt = cleaned
                # SIGNAL validation: last digit cannot be 8 or 9. The signal-type
                # combo sits in the column immediately left of the address column
                # (IN type=11 for IN addr=12, OUT type=13 for OUT addr=14).
                if txt and col in _ADDR_COLS:
                    io_cb = (self._tab_info.get(tab_idx, {})
                             .get('combos', {}).get(r, {}).get(col - 1))
                    if io_cb and io_cb.currentData() == 1 and txt[-1] in ('8', '9'):
                        logger.warning("log_invalid_input",
                                       txt + " (SIGNAL: digit 8/9 invalid)")
                        cleaned = txt[:-1]
                        tbl = self._tab_info.get(tab_idx, {}).get('table')
                        if tbl:
                            tbl.blockSignals(True)
                            item.setText(cleaned)
                            tbl.blockSignals(False)
                        txt = cleaned

            cid = ids[r] if r < len(ids) else '?'
            try:
                val = int(txt) if col in _ADDR_COLS and txt else txt
            except ValueError:
                val = 0
            self._panels[tab_idx]['cells'][cid][fi] = val
            logger.info("log_ifpanel_cell_changed", tab_idx + 1, cid,
                        _FIELD_LABELS.get(fi, str(fi)), repr(val))
        except Exception as exc:
            logger.error("log_error_generic", str(exc))

    def _on_cell_clicked(self, tab_idx, row, col):
        """Handle clicking a table cell."""
        try:
            ti = self._tab_info.get(tab_idx)
            if not ti:
                return
            ids = ti['ids']
            cid = ids[row] if row < len(ids) else '?'
            t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
            col_names = self._col_headers(t)
            col_name = col_names[col] if col < len(col_names) else str(col)
            logger.info("log_ifpanel_cell_clicked", tab_idx + 1, cid, col_name)
            # Warn when the user clicks an editable-type cell that is locked
            # (e.g. an OUT Addr cell disabled because OUTPUT is off for this
            # shape). The cell already refuses input; this just tells the user
            # why nothing happens instead of leaving the log silent.
            if col in _TEXT_COL_FIELD:
                tbl = ti.get('table')
                cell = tbl.item(row, col) if tbl else None
                if cell is not None and not (cell.flags() & Qt.ItemIsEditable):
                    logger.warning("log_ifpanel_cell_locked",
                                   tab_idx + 1, cid, col_name)
        except Exception as exc:
            logger.error("log_error_generic", str(exc))

    def _on_preview(self, panel_idx):
        """Open the graphical preview for the selected panel."""
        try:
            self._sync_group_names(panel_idx)
            self._preview_panel_idx = panel_idx
            panel = self._panels[panel_idx]
            self._preview_widget.set_panel(panel)
            t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
            name = panel.get('name_l1', f'Panel {panel_idx + 1}')
            title = t.get("ifpanel_preview_title", "Anteprima — {}").format(name)
            self._lbl_preview.setText(title)
            self._stacked.setCurrentIndex(1)
            logger.info("log_ifpanel_preview_opened", panel_idx + 1)
        except Exception as exc:
            logger.error("log_error_generic", str(exc))

    def _on_preview_close(self):
        """Close the panel preview."""
        self._stacked.setCurrentIndex(0)
        logger.info("log_ifpanel_preview_closed")

    def _on_close_main(self):
        """Close the IF-panel view."""
        logger.info("log_btn_pressed", self._btn_close_main.text())
        self._on_close()

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export(self):
        """Export the edited panels to an IFPANEL.DAT file."""
        import os
        t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS["IT"])
        folder = QFileDialog.getExistingDirectory(
            self, t.get("dialog_export_folder", "Seleziona cartella di destinazione"), "")
        if not folder:
            logger.info("log_cancelled", t.get("menu_ifpanel", "IFPanel"))
            return
        logger.info("log_btn_pressed", self._btn_export.text())
        try:
            self._sync_all_group_names()
            out = os.path.join(folder, 'IFPANEL.DAT')
            from docs.ifpanel import write_ifpanel
            write_ifpanel(out, self._panels)
            logger.info("log_ifpanel_exported", out)
            try:
                from docs.fsutil import reveal_in_explorer
                opened = reveal_in_explorer(out)
                logger.info("log_open_folder", opened)
            except Exception as exc:
                logger.warning("log_error_generic", str(exc))
        except Exception as exc:
            logger.error("log_error_generic", str(exc))
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self, t.get("menu_ifpanel", "IFPanel"),
                    t.get("ifpanel_export_failed", "IFPanel export failed:") + f"\n{exc}")
            except Exception:
                pass

    def _sync_group_names(self, tab_idx):
        """Sync one tab's group-name fields into the panel data."""
        ti = self._tab_info.get(tab_idx)
        if not ti:
            return
        self._panels[tab_idx]['name_l1'] = ti['name_l1'].text()
        self._panels[tab_idx]['name_l2'] = ti['name_l2'].text()

    def _sync_all_group_names(self):
        """Sync every tab's group-name fields into the panel data."""
        for ti_idx in self._built_tabs:
            self._sync_group_names(ti_idx)

    # ── Language update ───────────────────────────────────────────────────────

    def update_language(self, lang):
        """Re-translate the IF-panel view for the new language."""
        try:
            t = TRANSLATIONS.get(lang, TRANSLATIONS["IT"])
            self._lbl_title.setText(t.get("ifpanel_view_title", "IFPanel — YASKAWA YRC1000"))
            self._btn_export.setText(t.get("ifpanel_btn_export", "ESPORTA"))
            self._btn_close_main.setText(t.get("preview_close", "Chiudi"))
            self._btn_preview_close.setText(t.get("ifpanel_preview_close", "Chiudi Anteprima"))
            tab_label = t.get("ifpanel_tab_label", "Panel {}")
            for i in range(self._tab_widget.count()):
                self._tab_widget.setTabText(i, tab_label.format(i + 1))
            self._rebuild_combos_lang(t)
            hdrs = self._col_headers(t)
            for ti in self._tab_info.values():
                tbl = ti.get('table')
                if tbl:
                    tbl.setHorizontalHeaderLabels(hdrs)
                lbl = ti.get('lbl_l1')
                if lbl:
                    lbl.setText(t.get("ifpanel_group_l1_lbl", "Nome Gruppo (L1):"))
                lbl = ti.get('lbl_l2')
                if lbl:
                    lbl.setText(t.get("ifpanel_group_l2_lbl", "Nome Gruppo (L2):"))
                btn = ti.get('btn_preview')
                if btn:
                    btn.setText(t.get("ifpanel_btn_preview", "Anteprima"))
            # Refresh preview title if currently in preview page
            if self._stacked.currentIndex() == 1:
                panel = self._panels[self._preview_panel_idx]
                name  = panel.get('name_l1', f'Panel {self._preview_panel_idx + 1}')
                self._lbl_preview.setText(
                    t.get("ifpanel_preview_title", "Anteprima — {}").format(name))
        except Exception as exc:
            logger.error("log_error_generic", str(exc))

    def _rebuild_combos_lang(self, t):
        """Rebuild the combo-box option labels for the new language."""
        setup_opts   = resolve_options(SETUP_OPTIONS,     t)
        color_opts   = resolve_options(COLOR_OPTIONS,     t)
        io_type_opts = resolve_options(IO_TYPE_OPTIONS,   t)
        shape_opts   = resolve_options(SHAPE_OPTIONS,     t)

        _opts_by_col = {
            1:  setup_opts,
            2:  shape_opts,
            4:  color_opts,
            8:  color_opts,
            11: io_type_opts,
            13: io_type_opts,
        }

        for tab_idx, ti in self._tab_info.items():
            for r, cb_map in ti['combos'].items():
                cid = ti['ids'][r] if r < len(ti['ids']) else None
                cur_shape = (self._panels[tab_idx]['cells'].get(cid, _empty_row(cid))[F_SHAPE]
                             if cid else 0)
                for col, cb in cb_map.items():
                    # IO type combos (11, 13) are rebuilt by _apply_io_rules_row below
                    if col in (11, 13):
                        continue
                    if col == 3:
                        opts = resolve_options(
                            SUBTYPE_BY_SHAPE.get(cur_shape, SUBTYPE_FALLBACK), t)
                    else:
                        opts = _opts_by_col.get(col)
                    if opts is None:
                        continue
                    cur = cb.currentData()
                    cb.blockSignals(True)
                    cb.clear()
                    for code, label in opts:
                        cb.addItem(label, code)
                    idx = next((i for i, (c, _) in enumerate(opts) if c == cur), 0)
                    cb.setCurrentIndex(idx)
                    cb.blockSignals(False)

            # Re-apply IO rules (rebuilds INPUT/OUTPUT combos with correct filtered options)
            tbl = ti.get('table')
            if tbl:
                tbl.blockSignals(True)
                for r_idx, cid_r in enumerate(ti['ids']):
                    self._apply_io_rules_row(tab_idx, r_idx, cid_r)
                tbl.blockSignals(False)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        """Apply the current light/dark theme styling to the view."""
        ff = "'Yu Gothic UI','Meiryo','MS Gothic','Segoe UI',sans-serif"
        if self._app_state.is_dark_mode:
            self.setStyleSheet(f"""
                QWidget          {{ background:#231811; color:white; font-family:{ff}; font-size:8pt; }}
                QTabWidget::pane {{ border:1px solid #5C4938; }}
                QTabBar::tab     {{ background:#3A2D26; color:white;
                                   padding:3px 8px; margin-right:1px; font-size:8pt; }}
                QTabBar::tab:selected {{ background:#D97757; }}
                QTableWidget     {{ background:#231811; color:white;
                                   gridline-color:#5C4938;
                                   alternate-background-color:#3A2D26;
                                   font-size:8pt; }}
                QTableWidget::item:selected, QAbstractItemView::item:selected {{ background:#FF9248; color:black; }}
                QHeaderView::section {{ background:#8A4533; color:white;
                                        border:1px solid #5C4938; padding:2px;
                                        font-size:7pt; font-weight:bold; }}
                QPushButton      {{ background:#3A2D26; color:white;
                                   border:1px solid #5C4938;
                                   padding:4px 12px; border-radius:8px; }}
                QPushButton:hover {{ background:#D97757; }}
                QLabel           {{ color:white; }}
                QLineEdit        {{ background:#3A2D26; color:white;
                                   border:1px solid #5C4938; border-radius:6px;
                                   padding:3px 6px; font-size:8pt; }}
                QLineEdit:focus  {{ border:1px solid #FF9248; }}
                QComboBox        {{ background:#3A2D26; color:white;
                                   border:1px solid #5C4938; border-radius:6px;
                                   padding:3px 22px 3px 8px; min-height:18px; font-size:8pt; }}
                QComboBox:hover  {{ border:1px solid #D97757; background:#46352B; }}
                QComboBox:focus, QComboBox:on {{ border:1px solid #FF9248; }}
                QComboBox::drop-down {{ subcontrol-origin:padding; subcontrol-position:center right;
                                   width:20px; border:none; }}
                QComboBox::down-arrow {{ image:none; width:0; height:0; margin-right:7px;
                                   border-left:4px solid transparent;
                                   border-right:4px solid transparent;
                                   border-top:5px solid #E8A07F; }}
                QComboBox::down-arrow:hover {{ border-top:5px solid #FF9248; }}
                QComboBox QAbstractItemView {{ background:#2B211B; color:white;
                                   border:1px solid #5C4938; border-radius:6px;
                                   outline:0; padding:3px; font-size:8pt;
                                   selection-background-color:#D97757; selection-color:white; }}
                QComboBox QAbstractItemView::item {{ min-height:20px; padding:3px 8px;
                                   border-radius:8px; }}
                QComboBox QAbstractItemView::item:hover {{ background:#46352B; }}
                QFrame[frameShape="4"] {{ color:#5C4938; }}
                QScrollArea      {{ border:none; }}
            """)
        else:
            self.setStyleSheet(f"""
                QWidget          {{ background:#f5f5f5; color:black; font-family:{ff}; font-size:8pt; }}
                QTabWidget::pane {{ border:1px solid #cccccc; }}
                QTabBar::tab     {{ background:#e0e0e0; color:black;
                                   padding:3px 8px; margin-right:1px; font-size:8pt; }}
                QTabBar::tab:selected {{ background:#D97757; color:white; }}
                QTableWidget     {{ background:white; color:black;
                                   gridline-color:#dddddd;
                                   alternate-background-color:#FFF7F1;
                                   font-size:8pt; }}
                QTableWidget::item:selected, QAbstractItemView::item:selected {{ background:#FF9248; color:black; }}
                QHeaderView::section {{ background:#D97757; color:white;
                                        border:1px solid #cccccc;
                                        font-weight:bold; padding:2px; font-size:7pt; }}
                QPushButton      {{ background:white; color:#A85C42;
                                   border:1px solid #aaaaaa;
                                   padding:4px 12px; border-radius:8px; }}
                QPushButton:hover {{ background:#D97757; color:white; }}
                QLabel           {{ color:black; }}
                QLineEdit        {{ background:white; color:black;
                                   border:1px solid #c4c4c4; border-radius:6px;
                                   padding:3px 6px; font-size:8pt; }}
                QLineEdit:focus  {{ border:1px solid #D97757; }}
                QComboBox        {{ background:white; color:black;
                                   border:1px solid #c4c4c4; border-radius:6px;
                                   padding:3px 22px 3px 8px; min-height:18px; font-size:8pt; }}
                QComboBox:hover  {{ border:1px solid #D97757; background:#FFF7F1; }}
                QComboBox:focus, QComboBox:on {{ border:1px solid #D97757; }}
                QComboBox::drop-down {{ subcontrol-origin:padding; subcontrol-position:center right;
                                   width:20px; border:none; }}
                QComboBox::down-arrow {{ image:none; width:0; height:0; margin-right:7px;
                                   border-left:4px solid transparent;
                                   border-right:4px solid transparent;
                                   border-top:5px solid #B0703F; }}
                QComboBox::down-arrow:hover {{ border-top:5px solid #D97757; }}
                QComboBox QAbstractItemView {{ background:white; color:black;
                                   border:1px solid #d8d8d8; border-radius:6px;
                                   outline:0; padding:3px; font-size:8pt;
                                   selection-background-color:#D97757; selection-color:white; }}
                QComboBox QAbstractItemView::item {{ min-height:20px; padding:3px 8px;
                                   border-radius:8px; }}
                QComboBox QAbstractItemView::item:hover {{ background:#FFE8DC; }}
                QFrame[frameShape="4"] {{ color:#cccccc; }}
                QScrollArea      {{ border:none; }}
            """)


# ── Human-readable field labels (for logging) ─────────────────────────────────
_FIELD_LABELS = {
    F_SETUP:     "SETUP",
    F_SHAPE:     "SHAPE",
    F_SUBTYPE:   "SUBTYPE",
    F_COLOR:     "COLOR",
    F_N1_L1:     "N1(L1)",
    F_N2_L1:     "N2(L1)",
    F_N3_L1:     "N3(L1)",
    F_TCOLOR:    "TEXT_COLOR",
    F_SECURITY:  "SECURITY",
    F_INTERLOCK: "INTERLOCK",
    F_IN_TYPE:   "INPUT_TYPE",
    F_IN_ADDR:   "INPUT_ADDR",
    F_OUT_TYPE:  "OUTPUT_TYPE",
    F_OUT_ADDR:  "OUTPUT_ADDR",
    F_N1_L2:     "N1(L2)",
    F_N2_L2:     "N2(L2)",
    F_N3_L2:     "N3(L2)",
}
