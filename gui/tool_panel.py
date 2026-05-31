import os
import json
import re

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QLineEdit, QHeaderView, QFrame, QAbstractItemView,
                               QFileDialog)
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator

from translations import TRANSLATIONS
import logger

# ── Persistence ───────────────────────────────────────────────────────────────

_STATE_FILE = os.path.join(
    os.getenv("APPDATA", os.path.expanduser("~")),
    "YaskawaTools", "tool_panel.json"
)

TOOL_COUNT = 64

# ── Name edit (col 1) ─────────────────────────────────────────────────────────

_RE_TOOL_NAME = re.compile(r'^[A-Za-z0-9 ,_\-]*$')

class _NameEdit(QLineEdit):
    """Name column editor: logs changes on focus-out, warns on invalid chars."""

    _VALID_NAME_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ,_-")

    def __init__(self, app_state, tool_row, on_name_changed=None, parent=None):
        super().__init__(parent)
        self._app_state        = app_state
        self._tool_row         = tool_row
        self._on_name_changed  = on_name_changed
        self._prev_val         = ""
        self.setMaxLength(32)
        self.setFrame(False)
        if on_name_changed is not None:
            self.textChanged.connect(lambda txt: on_name_changed(bool(txt.strip())))

    def keyPressEvent(self, event):
        char = event.text()
        if char and char.isprintable() and char not in self._VALID_NAME_CHARS:
            try:
                logger.warning("log_invalid_input", char)
            except Exception:
                pass
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        self._prev_val = self.text()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        cur = self.text()
        if cur != self._prev_val:
            try:
                logger.info("log_tool_value_changed",
                            self._tool_row, "Nome", self._prev_val, cur)
            except Exception:
                pass
            self._prev_val = cur
        super().focusOutEvent(event)


# ── Numeric input ─────────────────────────────────────────────────────────────

class _NumericEdit(QLineEdit):
    """Numeric-only QLineEdit: accepts digits, minus and dot; converts comma→dot."""

    _VALID_CHARS = set("0123456789.-")
    _VALIDATOR   = QRegularExpressionValidator(
        QRegularExpression(r"^-?\d*\.?\d*$")
    )

    def __init__(self, app_state, tool_row=0, field_name="", parent=None):
        super().__init__(parent)
        self._app_state  = app_state
        self._tool_row   = tool_row
        self._field_name = field_name
        self._prev_val   = ""
        self.setValidator(self._VALIDATOR)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setPlaceholderText("0.000")

    def keyPressEvent(self, event):
        char = event.text()
        if char == ',':
            # Italian numpad decimal separator: silently convert to dot
            self.insert('.')
            return
        # Drop invalid printable chars; let control sequences (Ctrl+C/V/Z…) through
        if char and char.isprintable() and char not in self._VALID_CHARS:
            try:
                logger.warning("log_invalid_input", char)
            except Exception:
                pass
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        self._prev_val = self.text()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        cur = self.text()
        if cur != self._prev_val:
            try:
                logger.info("log_tool_value_changed",
                            self._tool_row, self._field_name, self._prev_val, cur)
            except Exception:
                pass
            self._prev_val = cur
        super().focusOutEvent(event)

    def float_value(self):
        try:
            return float(self.text()) if self.text().strip("-. ") else 0.0
        except ValueError:
            return 0.0


# ── Tool panel widget ─────────────────────────────────────────────────────────

class ToolPanel(QWidget):
    """Tabular editor for YASKAWA YRC1000 tool TCP coordinates (all 64 tools)."""

    # (column header literal, width px, default text, short field name for logging)
    _NUMERIC_COLS = [
        ("X [mm]",       85, "0.000",  "X"),
        ("Y [mm]",       85, "0.000",  "Y"),
        ("Z [mm]",       85, "0.000",  "Z"),
        ("Rx [°]",       85, "0.0000", "Rx"),
        ("Ry [°]",       85, "0.0000", "Ry"),
        ("Rz [°]",       85, "0.0000", "Rz"),
        ("Xg [mm]",      85, "0.000",  "Xg"),
        ("Yg [mm]",      85, "0.000",  "Yg"),
        ("Zg [mm]",      85, "0.000",  "Zg"),
        ("W [kg]",       75, "0.000",  "W"),
        ("Ixx [kg·m²]", 95, "0.000",  "Ixx"),
        ("Iyy [kg·m²]", 95, "0.000",  "Iyy"),
        ("Izz [kg·m²]", 95, "0.000",  "Izz"),
    ]

    # JSON field names matching _rows widget order (nome, x, y, z, rx, ry, rz, xg, yg, zg, w, ixx, iyy, izz)
    _FIELDS   = ("name", "x", "y", "z", "rx", "ry", "rz",
                 "xg", "yg", "zg", "w", "ixx", "iyy", "izz")
    _DEFAULTS = ("", "0.000", "0.000", "0.000", "0.0000", "0.0000", "0.0000",
                 "0.000", "0.000", "0.000", "0.000", "0.000", "0.000", "0.000")

    # Tool 0 reference display values (always hardcoded in export)
    _TOOL0_DISPLAY = ("STANDARD TOOL", "0.000", "0.000", "0.000",
                      "0.0000", "0.0000", "0.0000",
                      "80.000", "0.000", "200.000",
                      "5.000", "0.010", "0.010", "0.010")

    def __init__(self, app_state, on_close_cb, parent=None):
        super().__init__(parent)
        self._app_state = app_state
        self._on_close  = on_close_cb
        self._rows      = []   # (name_edit, x,y,z,rx,ry,rz,xg,yg,zg,w,ixx,iyy,izz) per tool
        self._build_ui()
        self._load_state()
        self._apply_theme()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        t = TRANSLATIONS[self._app_state.language]
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._title_lbl = QLabel(t.get("tool_panel_title", "Tool"))
        self._title_lbl.setStyleSheet("font-weight: bold; font-size: 10pt;")
        toolbar.addWidget(self._title_lbl)
        toolbar.addStretch()

        self._btn_export = QPushButton(t.get("tool_btn_export", "Esporta"))
        self._btn_export.setFixedHeight(26)
        self._btn_export.clicked.connect(self._do_export)
        toolbar.addWidget(self._btn_export)

        self._btn_close = QPushButton(t.get("preview_close", "Chiudi"))
        self._btn_close.setFixedHeight(26)
        self._btn_close.clicked.connect(self._handle_close)
        toolbar.addWidget(self._btn_close)

        root.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # Table
        col0_hdr = t.get("tool_col_tool", "Tool")
        col1_hdr = t.get("tool_col_name", "Nome")
        headers  = [col0_hdr, col1_hdr] + [c[0] for c in self._NUMERIC_COLS]

        self._table = QTableWidget(TOOL_COUNT, len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._table.setColumnWidth(0, 45)   # Tool#
        self._table.setColumnWidth(1, 120)  # Nome
        for ci, (_, w, _d, _f) in enumerate(self._NUMERIC_COLS, start=2):
            self._table.setColumnWidth(ci, w)

        for row in range(TOOL_COUNT):
            # Col 0 – tool number (read-only label)
            num_item = QTableWidgetItem(str(row))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFlags(Qt.ItemIsEnabled)
            self._table.setItem(row, 0, num_item)

            # Col 1 – name
            if row == 0:
                # Tool 0: no enable/disable callback — locked separately
                name_edit = _NameEdit(self._app_state, tool_row=row, on_name_changed=None)
            else:
                name_edit = _NameEdit(self._app_state, tool_row=row,
                                      on_name_changed=None)  # callback wired after edits list is ready

            self._table.setCellWidget(row, 1, name_edit)

            # Cols 2-14 – numeric fields
            edits = []
            for ci, (_, _w, default, fname) in enumerate(self._NUMERIC_COLS, start=2):
                ed = _NumericEdit(self._app_state, tool_row=row, field_name=fname)
                ed.setFrame(False)
                ed.setText(default)
                self._table.setCellWidget(row, ci, ed)
                edits.append(ed)

            self._table.setRowHeight(row, 26)
            self._rows.append((name_edit, *edits))

            # Wire name → enable/disable numeric fields for editable rows
            if row > 0:
                captured = edits          # new list each iteration — safe to capture
                name_edit.textChanged.connect(
                    lambda txt, eds=captured: self._on_name_changed(txt, eds)
                )
                # Initially disabled — enabled only when name is set
                for ed in edits:
                    ed.setEnabled(False)

        # Pre-fill and lock Tool 0
        for widget, val in zip(self._rows[0], self._TOOL0_DISPLAY):
            widget.setText(val)
        self._lock_row(0)

        root.addWidget(self._table, 1)

    def _lock_row(self, row):
        for widget in self._rows[row]:
            widget.setEnabled(False)

    def _on_name_changed(self, text, edits):
        enabled = bool(text.strip())
        for ed in edits:
            ed.setEnabled(enabled)

    # ── State persistence ─────────────────────────────────────────────────────

    def _load_state(self):
        try:
            if not os.path.isfile(_STATE_FILE):
                return
            with open(_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            tools = data.get("tools", [])
            for i, row_widgets in enumerate(self._rows):
                if i == 0 or i >= len(tools):
                    continue  # Tool 0 always uses hardcoded display values
                td = tools[i]
                for widget, field, default in zip(row_widgets, self._FIELDS, self._DEFAULTS):
                    widget.setText(str(td.get(field, default)))
            logger.info("log_tool_loaded")
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
            tools = []
            for row_widgets in self._rows:
                td = {}
                for widget, field in zip(row_widgets, self._FIELDS):
                    td[field] = widget.text()
                tools.append(td)
            with open(_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"tools": tools}, f, indent=2, ensure_ascii=False)
            logger.info("log_tool_saved")
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))

    def _handle_close(self):
        self.save_state()
        self._on_close()

    # ── Export ────────────────────────────────────────────────────────────────

    def _do_export(self):
        t = TRANSLATIONS[self._app_state.language]
        folder = QFileDialog.getExistingDirectory(
            self,
            t.get("dialog_export_folder", "Seleziona cartella di destinazione"),
        )
        if not folder:
            return
        out_path = os.path.join(folder, "TOOL.CND")
        try:
            self._write_tool_cnd(out_path)
            logger.info("log_tool_exported", out_path)
            os.startfile(folder)   # open Explorer at the output folder
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))

    @staticmethod
    def _fv(ed, spec):
        try:
            v = float(ed.text()) if ed.text().strip("-. ") else 0.0
        except (ValueError, AttributeError):
            v = 0.0
        return format(v, spec)

    def _write_tool_cnd(self, path):
        """Write TOOL.CND from current table values (CRLF, latin-1)."""
        with open(path, "w", encoding="latin-1", newline="\r\n") as f:
            for i, row_widgets in enumerate(self._rows):
                (name_e, x_e, y_e, z_e, rx_e, ry_e, rz_e,
                 xg_e, yg_e, zg_e, w_e, ixx_e, iyy_e, izz_e) = row_widgets

                if i == 0:
                    name = "STANDARD TOOL"
                    tcp  = "0.000,0.000,0.000,0.0000,0.0000,0.0000"
                    grav = "80.000,0.000,200.000"
                    wt   = "5.000"
                    iner = "0.010,0.010,0.010"
                else:
                    f3 = ".3f"
                    f4 = ".4f"
                    name = name_e.text().strip()
                    tcp  = (f"{self._fv(x_e,f3)},{self._fv(y_e,f3)},{self._fv(z_e,f3)},"
                            f"{self._fv(rx_e,f4)},{self._fv(ry_e,f4)},{self._fv(rz_e,f4)}")
                    grav = f"{self._fv(xg_e,f3)},{self._fv(yg_e,f3)},{self._fv(zg_e,f3)}"
                    wt   = self._fv(w_e, f3)
                    iner = f"{self._fv(ixx_e,f3)},{self._fv(iyy_e,f3)},{self._fv(izz_e,f3)}"

                flag = "0.000,0,2" if i < 3 else "0.000,0,1"

                f.write(f"//TOOL {i}\n")
                f.write(f"///NAME {name}\n")
                f.write(f"{tcp}\n")
                f.write(f"{grav}\n")
                f.write(f"{wt}\n")
                f.write(f"{iner}\n")
                f.write(f"{flag}\n")

    # ── Language update ───────────────────────────────────────────────────────

    def update_language(self, lang):
        t = TRANSLATIONS[lang]
        self._title_lbl.setText(t.get("tool_panel_title", "Tool"))
        self._btn_export.setText(t.get("tool_btn_export", "Esporta"))
        self._btn_close.setText(t.get("preview_close", "Chiudi"))
        col0 = t.get("tool_col_tool", "Tool")
        col1 = t.get("tool_col_name", "Nome")
        headers = [col0, col1] + [c[0] for c in self._NUMERIC_COLS]
        for ci, hdr in enumerate(headers):
            item = self._table.horizontalHeaderItem(ci)
            if item is not None:
                item.setText(hdr)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        if self._app_state.is_dark_mode:
            self.setStyleSheet("""
                QWidget          { background:#231811; color:white; }
                QTableWidget     { background:#231811; color:white;
                                   gridline-color:#5C4938;
                                   alternate-background-color:#3A2D26; }
                QHeaderView::section { background:#8A4533; color:white;
                                       border:1px solid #5C4938;
                                       font-weight:bold; padding:2px; }
                QLineEdit        { background:#231811; color:white;
                                   selection-background-color:#FF9248; }
                QLineEdit:disabled { background:#111820; color:#556070; }
                QPushButton      { background:#3A2D26; color:white;
                                   border:1px solid #5C4938;
                                   padding:2px 10px; border-radius:3px; }
                QPushButton:hover { background:#D97757; }
                QLabel           { color:white; }
                QFrame[frameShape="4"] { color:#5C4938; }
            """)
        else:
            self.setStyleSheet("""
                QWidget          { background:#f5f5f5; color:black; }
                QTableWidget     { background:white; color:black;
                                   gridline-color:#dddddd;
                                   alternate-background-color:#f0f4ff; }
                QHeaderView::section { background:#D97757; color:white;
                                       border:1px solid #cccccc;
                                       font-weight:bold; padding:2px; }
                QLineEdit        { background:white; color:black;
                                   selection-background-color:#FF9248; }
                QLineEdit:disabled { background:#d8d8d8; color:#888888; }
                QPushButton      { background:white; color:#A85C42;
                                   border:1px solid #aaaaaa;
                                   padding:2px 10px; border-radius:3px; }
                QPushButton:hover { background:#D97757; color:white; }
                QLabel           { color:black; }
                QFrame[frameShape="4"] { color:#cccccc; }
            """)
