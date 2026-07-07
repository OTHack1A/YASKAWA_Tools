from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QFrame, QAbstractItemView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from translations import TRANSLATIONS
from docs.help_data import get_params, get_known_params
import logger


class HelpView(QWidget):
    """Read-only tabular view of embedded YASKAWA parameter reference data.

    view_type:
        "params"  — YASKAWA.md data  (2 columns: parameter, description)
        "known"   — YASKAWA2.md data (3 columns: parameter, value, description)
    """

    _MONO = QFont("Courier New", 9)

    def __init__(self, app_state, view_type, on_close_cb, parent=None):
        """Build the help view for the given parameter-guide type."""
        super().__init__(parent)
        self._app_state  = app_state
        self._view_type  = view_type   # "params" | "known"
        self._on_close   = on_close_cb
        self._build_ui()
        self._apply_theme()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Build the help view's widgets (search box, table, close button)."""
        t = TRANSLATIONS[self._app_state.language]
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        if self._view_type == "params":
            title_key = "help_title_params"
            default_title = "Parametri — YASKAWA YRC1000"
            headers_keys = ["help_col_param", "help_col_desc"]
            headers_default = ["Parametro", "Descrizione"]
            self._col_widths = [140, None]
        else:
            title_key = "help_title_known"
            default_title = "Param. Noti — YASKAWA YRC1000"
            headers_keys = ["help_col_param", "help_col_value", "help_col_desc"]
            headers_default = ["Parametro", "Valore", "Descrizione"]
            self._col_widths = [120, 90, None]

        self._title_lbl = QLabel(t.get(title_key, default_title))
        self._title_lbl.setStyleSheet("font-weight: bold; font-size: 10pt;")
        toolbar.addWidget(self._title_lbl)
        toolbar.addStretch()

        self._btn_close = QPushButton(t.get("preview_close", "Chiudi"))
        self._btn_close.setFixedHeight(26)
        self._btn_close.clicked.connect(self._handle_close)
        toolbar.addWidget(self._btn_close)

        root.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        headers = [t.get(k, d) for k, d in zip(headers_keys, headers_default)]
        num_cols = len(headers)

        self._table = QTableWidget(0, num_cols)
        self._table.setHorizontalHeaderLabels(headers)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)

        for ci, w in enumerate(self._col_widths[:-1]):
            if w is not None:
                self._table.setColumnWidth(ci, w)

        root.addWidget(self._table, 1)

        self._populate_table(self._app_state.language)

    def _populate_table(self, lang):
        """Fill the help table with the parameter entries for the given language."""
        if self._view_type == "params":
            data = get_params(lang)
        else:
            data = get_known_params(lang)

        self._table.setRowCount(len(data))
        for ri, row_data in enumerate(data):
            for ci, cell_text in enumerate(row_data):
                item = QTableWidgetItem(str(cell_text))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if ci == 0:
                    item.setFont(self._MONO)
                self._table.setItem(ri, ci, item)

    def showEvent(self, event):
        """On show, populate the table for the current language."""
        super().showEvent(event)
        try:
            self._table.resizeRowsToContents()
        except Exception:
            pass

    # ── Close ─────────────────────────────────────────────────────────────────

    def _handle_close(self):
        """Invoke the close callback to dismiss the help view."""
        self._on_close()

    # ── Language update ───────────────────────────────────────────────────────

    def update_language(self, lang):
        """Re-translate the help view and repopulate it for the new language."""
        try:
            t = TRANSLATIONS[lang]
            if self._view_type == "params":
                self._title_lbl.setText(t.get("help_title_params", "Parametri — YASKAWA YRC1000"))
                headers = [
                    t.get("help_col_param", "Parametro"),
                    t.get("help_col_desc",  "Descrizione"),
                ]
            else:
                self._title_lbl.setText(t.get("help_title_known", "Param. Noti — YASKAWA YRC1000"))
                headers = [
                    t.get("help_col_param", "Parametro"),
                    t.get("help_col_value", "Valore"),
                    t.get("help_col_desc",  "Descrizione"),
                ]
            self._btn_close.setText(t.get("preview_close", "Chiudi"))
            for ci, hdr in enumerate(headers):
                item = self._table.horizontalHeaderItem(ci)
                if item is not None:
                    item.setText(hdr)
            self._populate_table(lang)
            try:
                self._table.resizeRowsToContents()
            except Exception:
                pass
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        """Apply the current light/dark theme styling to the help view."""
        if self._app_state.is_dark_mode:
            self.setStyleSheet("""
                QWidget          { background:#231811; color:white; }
                QTableWidget     { background:#231811; color:white;
                                   gridline-color:#5C4938;
                                   alternate-background-color:#3A2D26; }
                QHeaderView::section { background:#8A4533; color:white;
                                       border:1px solid #5C4938;
                                       font-weight:bold; padding:4px; }
                QTableWidget::item:selected { background:#FF9248; color:black; }
                QPushButton      { background:#3A2D26; color:white;
                                   border:1px solid #5C4938;
                                   padding:4px 12px; border-radius:8px; }
                QPushButton:hover { background:#D97757; }
                QLabel           { color:white; }
                QFrame[frameShape="4"] { color:#5C4938; }
            """)
        else:
            self.setStyleSheet("""
                QWidget          { background:#f5f5f5; color:black; }
                QTableWidget     { background:white; color:black;
                                   gridline-color:#dddddd;
                                   alternate-background-color:#f0f4f0; }
                QHeaderView::section { background:#D97757; color:white;
                                       border:1px solid #cccccc;
                                       font-weight:bold; padding:4px; }
                QTableWidget::item:selected { background:#FF9248; color:black; }
                QPushButton      { background:white; color:#A85C42;
                                   border:1px solid #aaaaaa;
                                   padding:4px 12px; border-radius:8px; }
                QPushButton:hover { background:#D97757; color:white; }
                QLabel           { color:black; }
                QFrame[frameShape="4"] { color:#cccccc; }
            """)
