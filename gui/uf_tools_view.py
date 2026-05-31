import os

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QFrame, QAbstractItemView, QTabWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from translations import TRANSLATIONS
from docs.uf_tools import parse_tool_cnd, parse_uframe_cnd, _is_nonzero, TOOL_FILE, UFRAME_FILE
import logger


class UfToolsView(QWidget):
    """Preview panel: configured tools + all user frames, tabs in content area."""

    _MONO = QFont("Courier New", 9)

    def __init__(self, app_state, folder_path, on_close_cb, on_generate_cb,
                 on_excel_cb=None, parent=None):
        super().__init__(parent)
        self._app_state   = app_state
        self._folder      = folder_path
        self._on_close    = on_close_cb
        self._on_generate = on_generate_cb
        self._on_excel    = on_excel_cb

        self._cfg_tools  = []
        self._all_frames = []
        self._load_data()
        self._build_ui()
        self._apply_theme()

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_data(self):
        tool_path = os.path.join(self._folder, TOOL_FILE)
        uf_path   = os.path.join(self._folder, UFRAME_FILE)

        all_tools = []
        if os.path.isfile(tool_path):
            try:
                all_tools = parse_tool_cnd(tool_path)
            except Exception as exc:
                logger.warning("log_error_generic", str(exc))
        else:
            logger.warning("log_file_not_found", TOOL_FILE)

        if os.path.isfile(uf_path):
            try:
                self._all_frames = parse_uframe_cnd(uf_path)
            except Exception as exc:
                logger.warning("log_error_generic", str(exc))
        else:
            logger.warning("log_file_not_found", UFRAME_FILE)

        self._cfg_tools = [t for t in all_tools if _is_nonzero(t)]

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        t    = TRANSLATIONS[self._app_state.language]
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._title_lbl = QLabel(
            t.get("uf_tools_view_title", "UF#()/Tools — YASKAWA YRC1000"))
        self._title_lbl.setStyleSheet("font-weight: bold; font-size: 10pt;")
        toolbar.addWidget(self._title_lbl)
        toolbar.addStretch()

        self._btn_pdf = QPushButton(t.get("btn_generate_pdf", "Genera PDF"))
        self._btn_pdf.setFixedHeight(26)
        self._btn_pdf.clicked.connect(self._handle_generate)
        toolbar.addWidget(self._btn_pdf)

        if self._on_excel is not None:
            self._btn_excel = QPushButton(t.get("btn_export_excel", "Esporta Excel"))
            self._btn_excel.setFixedHeight(26)
            self._btn_excel.clicked.connect(self._handle_excel)
            toolbar.addWidget(self._btn_excel)

        self._btn_close = QPushButton(t.get("preview_close", "Chiudi"))
        self._btn_close.setFixedHeight(26)
        self._btn_close.clicked.connect(self._handle_close)
        toolbar.addWidget(self._btn_close)

        root.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._tbl_tools = self._make_tools_table(t)
        self._tab_tools_widget = self._wrap_table(self._tbl_tools)
        self._tabs.addTab(self._tab_tools_widget,
                          t.get("uf_tools_tab_tools", "Tool"))

        self._tbl_uf = self._make_uf_table()
        self._tab_uf_widget = self._wrap_table(self._tbl_uf)
        self._tabs.addTab(self._tab_uf_widget,
                          t.get("uf_tools_tab_uf", "User Frame"))

        # track current tab name for change logging
        self._current_tab_name = self._tabs.tabText(0)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        root.addWidget(self._tabs, 1)

    @staticmethod
    def _wrap_table(tbl):
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(2, 4, 2, 2)
        lay.setSpacing(0)
        lay.addWidget(tbl, 1)
        return w

    def _make_tools_table(self, t):
        name_hdr = t.get("tool_col_name", "Nome")
        headers  = ["#", name_hdr,
                    "X [mm]", "Y [mm]", "Z [mm]",
                    "Rx [°]", "Ry [°]", "Rz [°]"]
        tbl = self._base_table(len(self._cfg_tools), headers)
        tbl.setColumnWidth(0, 36)
        tbl.setColumnWidth(1, 150)
        for ci in range(2, 8):
            tbl.setColumnWidth(ci, 82)

        for ri, tool in enumerate(self._cfg_tools):
            row = [str(tool['num']), tool['name'] or '—',
                   f"{tool['x']:.3f}", f"{tool['y']:.3f}", f"{tool['z']:.3f}",
                   f"{tool['rx']:.4f}", f"{tool['ry']:.4f}", f"{tool['rz']:.4f}"]
            for ci, v in enumerate(row):
                item = self._make_item(v, ci, is_tools=True)
                tbl.setItem(ri, ci, item)

        return tbl

    def _make_uf_table(self):
        t = TRANSLATIONS[self._app_state.language]
        name_hdr = t.get("tool_col_name", "Nome")
        headers = ["UF#", name_hdr,
                   "X [mm]", "Y [mm]", "Z [mm]",
                   "Rx [°]", "Ry [°]", "Rz [°]"]
        tbl = self._base_table(len(self._all_frames), headers)
        tbl.setColumnWidth(0, 40)
        tbl.setColumnWidth(1, 140)
        for ci in range(2, 8):
            tbl.setColumnWidth(ci, 82)

        for ri, fr in enumerate(self._all_frames):
            row = [str(fr['num']),
                   fr.get('name', '') or '—',
                   f"{fr['x']:.3f}", f"{fr['y']:.3f}", f"{fr['z']:.3f}",
                   f"{fr['rx']:.4f}", f"{fr['ry']:.4f}", f"{fr['rz']:.4f}"]
            for ci, v in enumerate(row):
                # col 0 = UF#, col 1 = Name, col 2+ = numeric
                item = self._make_item(v, ci, is_tools=(ci == 1))
                tbl.setItem(ri, ci, item)

        return tbl

    @staticmethod
    def _base_table(rows, headers):
        tbl = QTableWidget(rows, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.setAlternatingRowColors(True)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        tbl.horizontalHeader().setStretchLastSection(True)
        return tbl

    def _make_item(self, text, col_index, is_tools):
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        if col_index == 0:
            item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        elif col_index == 1 and is_tools:
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setFont(self._MONO)
        else:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item.setFont(self._MONO)
        return item

    # ── Button / tab handlers ─────────────────────────────────────────────────

    def _handle_generate(self):
        try:
            t = TRANSLATIONS[self._app_state.language]
            logger.info("log_btn_pressed", t.get("btn_generate_pdf", "Genera PDF"))
        except Exception:
            pass
        try:
            self._on_generate()
        except Exception as exc:
            try:
                logger.warning("log_error_generic", str(exc))
            except Exception:
                pass

    def _handle_excel(self):
        try:
            t = TRANSLATIONS[self._app_state.language]
            logger.info("log_btn_pressed", t.get("btn_export_excel", "Esporta Excel"))
        except Exception:
            pass
        try:
            self._on_excel()
        except Exception as exc:
            try:
                logger.warning("log_error_generic", str(exc))
            except Exception:
                pass

    def _handle_close(self):
        try:
            t = TRANSLATIONS[self._app_state.language]
            logger.info("log_btn_pressed", t.get("preview_close", "Chiudi"))
        except Exception:
            pass
        try:
            self._on_close()
        except Exception as exc:
            try:
                logger.warning("log_error_generic", str(exc))
            except Exception:
                pass

    def _on_tab_changed(self, index):
        try:
            new_name = self._tabs.tabText(index)
            logger.info("log_tab_changed", self._current_tab_name, new_name)
            self._current_tab_name = new_name
        except Exception:
            pass

    # ── Language update ───────────────────────────────────────────────────────

    def update_language(self, lang):
        try:
            t = TRANSLATIONS[lang]
            self._title_lbl.setText(
                t.get("uf_tools_view_title", "UF#()/Tools — YASKAWA YRC1000"))
            self._btn_pdf.setText(t.get("btn_generate_pdf", "Genera PDF"))
            if self._on_excel is not None and hasattr(self, '_btn_excel'):
                self._btn_excel.setText(t.get("btn_export_excel", "Esporta Excel"))
            self._btn_close.setText(t.get("preview_close", "Chiudi"))
            self._tabs.setTabText(0, t.get("uf_tools_tab_tools", "Tool"))
            self._tabs.setTabText(1, t.get("uf_tools_tab_uf", "User Frame"))

            name_hdr = t.get("tool_col_name", "Nome")
            tool_hdrs = ["#", name_hdr,
                         "X [mm]", "Y [mm]", "Z [mm]",
                         "Rx [°]", "Ry [°]", "Rz [°]"]
            for ci, hdr in enumerate(tool_hdrs):
                item = self._tbl_tools.horizontalHeaderItem(ci)
                if item:
                    item.setText(hdr)
            uf_hdrs = ["UF#", name_hdr,
                       "X [mm]", "Y [mm]", "Z [mm]",
                       "Rx [°]", "Ry [°]", "Rz [°]"]
            for ci, hdr in enumerate(uf_hdrs):
                item = self._tbl_uf.horizontalHeaderItem(ci)
                if item:
                    item.setText(hdr)
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        if self._app_state.is_dark_mode:
            self.setStyleSheet("""
                QWidget          { background:#231811; color:white; }
                QTabWidget::pane { border:1px solid #5C4938; }
                QTabBar::tab     { background:#3A2D26; color:white;
                                   padding:4px 12px; margin-right:1px; }
                QTabBar::tab:selected { background:#D97757; }
                QTableWidget     { background:#231811; color:white;
                                   gridline-color:#5C4938;
                                   alternate-background-color:#3A2D26; }
                QHeaderView::section { background:#8A4533; color:white;
                                       border:1px solid #5C4938;
                                       font-weight:bold; padding:4px; }
                QTableWidget::item:selected { background:#FF9248; color:black; }
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
                QTabWidget::pane { border:1px solid #cccccc; }
                QTabBar::tab     { background:#e0e0e0; color:black;
                                   padding:4px 12px; margin-right:1px; }
                QTabBar::tab:selected { background:#D97757; color:white; }
                QTableWidget     { background:white; color:black;
                                   gridline-color:#dddddd;
                                   alternate-background-color:#f0f4ff; }
                QHeaderView::section { background:#D97757; color:white;
                                       border:1px solid #cccccc;
                                       font-weight:bold; padding:4px; }
                QTableWidget::item:selected { background:#FF9248; color:black; }
                QPushButton      { background:white; color:#A85C42;
                                   border:1px solid #aaaaaa;
                                   padding:2px 10px; border-radius:3px; }
                QPushButton:hover { background:#D97757; color:white; }
                QLabel           { color:black; }
                QFrame[frameShape="4"] { color:#cccccc; }
            """)
