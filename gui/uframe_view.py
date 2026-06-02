"""Editable UF#() view: load UFRAME.CND, allow editing Name and BUSER coordinates."""
import os
import re

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QFrame, QAbstractItemView,
                               QStyledItemDelegate, QLineEdit)
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator

from translations import TRANSLATIONS
import logger

_RE_NAME = re.compile(r'^[A-Za-z0-9 ,_\-]*$')
_RE_NUM  = re.compile(r'^-?[0-9]*[.,]?[0-9]*$')


class _NameDelegate(QStyledItemDelegate):
    """Max 16 chars, only [A-Za-z0-9 ,_-]. Logs warning on invalid input."""
    def __init__(self, app_state, parent=None):
        """Initialise the cell delegate with the shared application state."""
        super().__init__(parent)
        self._app_state = app_state

    def createEditor(self, parent, option, index):
        """Create the editor widget for a user-frame value cell."""
        ed = QLineEdit(parent)
        ed.setMaxLength(16)
        rx = QRegularExpression(r'[A-Za-z0-9 ,_\-]*')
        val = QRegularExpressionValidator(rx, ed)
        ed.setValidator(val)
        ed.inputRejected.connect(
            lambda: logger.warning("log_invalid_input", ed.text() or "?"))
        self._prev = index.data() or ""
        return ed

    def setEditorData(self, editor, index):
        """Load the cell's current value into the editor."""
        self._prev = index.data() or ""
        editor.setText(self._prev)

    def setModelData(self, editor, model, index):
        """Validate and write the editor's value back into the model."""
        text = editor.text()
        if len(text) > 16:
            text = text[:16]
            logger.warning("log_invalid_input", text)
        if not _RE_NAME.match(text):
            logger.warning("log_invalid_input", text)
            return
        if text != self._prev:
            uf_num = model.index(index.row(), 0).data() or str(index.row() + 1)
            logger.info("log_uframe_value_changed", uf_num, "Nome", self._prev, text)
        super().setModelData(editor, model, index)


class _NumericDelegate(QStyledItemDelegate):
    """Only digits + optional comma or period (real). Logs warning on invalid."""
    def __init__(self, app_state, col_name="", parent=None):
        """Initialise the name-column delegate."""
        super().__init__(parent)
        self._app_state = app_state
        self._col_name  = col_name

    def createEditor(self, parent, option, index):
        """Create the editor widget for a name cell."""
        ed = QLineEdit(parent)
        rx = QRegularExpression(r'-?[0-9]*[.,]?[0-9]*')
        val = QRegularExpressionValidator(rx, ed)
        ed.setValidator(val)
        ed.inputRejected.connect(
            lambda: logger.warning("log_invalid_input", ed.text() or "?"))
        self._prev = index.data() or ""
        return ed

    def setEditorData(self, editor, index):
        """Load the cell's current value into the editor."""
        self._prev = index.data() or ""
        editor.setText(self._prev)

    def setModelData(self, editor, model, index):
        """Validate and write the editor's value back into the model."""
        text = editor.text().replace(',', '.')
        if not _RE_NUM.match(editor.text()):
            logger.warning("log_invalid_input", editor.text())
            return
        try:
            float(text) if text not in ('', '-', '.') else 0.0
        except ValueError:
            logger.warning("log_invalid_input", editor.text())
            return
        if text != self._prev.replace(',', '.'):
            uf_num = model.index(index.row(), 0).data() or str(index.row() + 1)
            logger.info("log_uframe_value_changed", uf_num, self._col_name, self._prev, text)
        super().setModelData(editor, model, index)


class UFrameView(QWidget):
    """Editable table for UFRAME.CND: UF# | Name | X | Y | Z | Rx | Ry | Rz."""

    def __init__(self, folder, app_state, on_close_cb):
        """Build the user-frame editing view for the given folder."""
        super().__init__()
        self._folder = folder
        self._app_state = app_state
        self._on_close = on_close_cb
        self._frames = []
        self._build_ui()
        self._apply_theme()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Build the view's widgets (editable table, save/close buttons)."""
        t = TRANSLATIONS[self._app_state.language]
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._lbl_title = QLabel(t.get("uframe_view_title", "UF#() — YASKAWA YRC1000"))
        self._lbl_title.setStyleSheet("font-weight: bold; font-size: 10pt;")
        toolbar.addWidget(self._lbl_title)
        toolbar.addStretch()
        self._btn_save = QPushButton(t.get("uframe_btn_export", "Esporta"))
        self._btn_save.setFixedHeight(26)
        self._btn_save.clicked.connect(self._on_save)
        toolbar.addWidget(self._btn_save)
        self._btn_close = QPushButton(t.get("preview_close", "Chiudi"))
        self._btn_close.setFixedHeight(26)
        self._btn_close.clicked.connect(self._on_close)
        toolbar.addWidget(self._btn_close)
        root.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        self._tbl = self._build_table(t)
        root.addWidget(self._tbl, 1)

    def _build_table(self, t):
        """Populate the user-frame table with rows and editing delegates."""
        name_hdr = t.get("tool_col_name", "Nome")
        col_names = ["X [mm]", "Y [mm]", "Z [mm]", "Rx [°]", "Ry [°]", "Rz [°]"]
        coord_keys = ['x', 'y', 'z', 'rx', 'ry', 'rz']
        headers = ["UF#", name_hdr] + col_names

        from docs.uf_tools import parse_uframe_cnd, UFRAME_FILE
        uf_path = os.path.join(self._folder, UFRAME_FILE)
        frames_by_num = {}
        if os.path.isfile(uf_path):
            try:
                all_frames = parse_uframe_cnd(uf_path)
                for f in all_frames:
                    n = f.get('num', 0)
                    if 1 <= n <= 63:
                        frames_by_num[n] = f
            except Exception as exc:
                try:
                    logger.warning("log_error_generic", str(exc))
                except Exception:
                    pass
        self._frames = frames_by_num

        tbl = QTableWidget(63, 8)
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setAlternatingRowColors(True)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setColumnWidth(0, 44)
        tbl.setColumnWidth(1, 160)
        for ci in range(2, 8):
            tbl.setColumnWidth(ci, 90)

        tbl.setItemDelegateForColumn(1, _NameDelegate(self._app_state, tbl))
        for ci, cname in enumerate(col_names, start=2):
            tbl.setItemDelegateForColumn(ci, _NumericDelegate(self._app_state, cname, tbl))

        for ri in range(63):
            num = ri + 1
            fr = frames_by_num.get(num, {})

            item_num = QTableWidgetItem(str(num))
            item_num.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_num.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            tbl.setItem(ri, 0, item_num)

            item_name = QTableWidgetItem(fr.get('name', '') or '')
            item_name.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            tbl.setItem(ri, 1, item_name)

            for ci, key in enumerate(coord_keys, start=2):
                val = fr.get(key, 0.0)
                item = QTableWidgetItem(f"{val:.3f}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tbl.setItem(ri, ci, item)

        return tbl

    # ── Save ──────────────────────────────────────────────────────────────────

    def _on_save(self):
        """Validate the edited frames and export them to a chosen destination."""
        from PySide6.QtWidgets import QFileDialog
        from docs.uf_tools import write_uframe_cnd, UFRAME_FILE
        t = TRANSLATIONS[self._app_state.language]

        # Ask the user where to export. Default to the source folder and keep the
        # exact UFRAME.CND filename so the file can be re-imported on the robot.
        src_path = os.path.join(self._folder, UFRAME_FILE)
        default_path = src_path
        uf_path, _ = QFileDialog.getSaveFileName(
            self, t.get("uframe_btn_export", "Esporta"), default_path,
            "Controller Data (*.CND);;All Files (*)")
        if not uf_path:
            logger.info("log_cancelled", "UF#()")
            return

        frames_by_num = {}
        for ri in range(self._tbl.rowCount()):
            try:
                num_item = self._tbl.item(ri, 0)
                if num_item is None:
                    continue
                num = int(num_item.text())
                name_item = self._tbl.item(ri, 1)
                name = (name_item.text() if name_item else '').strip()
                coords = {}
                for ci, key in enumerate(['x', 'y', 'z', 'rx', 'ry', 'rz'], start=2):
                    item = self._tbl.item(ri, ci)
                    v = float((item.text() or '0').replace(',', '.')) if item else 0.0
                    coords[key] = v
                frames_by_num[num] = {'name': name, **coords}
            except Exception:
                continue
        try:
            ok, err = write_uframe_cnd(uf_path, frames_by_num, src_path=src_path)
            if ok:
                logger.info("log_uframe_saved")
                try:
                    from docs.fsutil import reveal_in_explorer
                    folder = reveal_in_explorer(uf_path)
                    logger.info("log_open_folder", folder)
                except Exception as exc:
                    logger.warning("log_error_generic", str(exc))
            else:
                logger.error("log_uframe_error", err or "unknown error")
                self._show_error(t, err or "unknown error")
        except Exception as exc:
            try:
                logger.error("log_uframe_error", str(exc))
            except Exception:
                pass
            self._show_error(t, str(exc))

    def _show_error(self, t, msg):
        """Surface an export failure to the user, not just the logs."""
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                t.get("uframe_view_title", "UF#()"),
                t.get("uframe_export_failed", "Export failed:") + f"\n{msg}")
        except Exception:
            pass

    # ── Language / theme ──────────────────────────────────────────────────────

    def update_language(self, lang):
        """Re-translate the user-frame view for the new language."""
        try:
            t = TRANSLATIONS.get(lang, TRANSLATIONS["IT"])
            self._lbl_title.setText(t.get("uframe_view_title", "UF#() — YASKAWA YRC1000"))
            self._btn_save.setText(t.get("uframe_btn_export", "Esporta"))
            self._btn_close.setText(t.get("preview_close", "Chiudi"))
            name_hdr = t.get("tool_col_name", "Nome")
            hdrs = ["UF#", name_hdr,
                    "X [mm]", "Y [mm]", "Z [mm]",
                    "Rx [°]", "Ry [°]", "Rz [°]"]
            for ci, hdr in enumerate(hdrs):
                item = self._tbl.horizontalHeaderItem(ci)
                if item:
                    item.setText(hdr)
        except Exception:
            pass

    def _apply_theme(self):
        """Apply the current light/dark theme styling to the view."""
        if self._app_state.is_dark_mode:
            self.setStyleSheet("""
                QWidget { background:#231811; color:white; }
                QTableWidget { background:#231811; color:white;
                               gridline-color:#5C4938;
                               alternate-background-color:#3A2D26; }
                QHeaderView::section { background:#8A4533; color:white;
                                       border:1px solid #5C4938;
                                       font-weight:bold; padding:4px; }
                QTableWidget::item:selected { background:#FF9248; color:black; }
                QPushButton { background:#3A2D26; color:white;
                              border:1px solid #5C4938;
                              padding:2px 10px; border-radius:3px; }
                QPushButton:hover { background:#D97757; }
                QLabel { color:white; }
                QFrame[frameShape="4"] { color:#5C4938; }
            """)
        else:
            self.setStyleSheet("""
                QWidget { background:#f5f5f5; color:black; }
                QTableWidget { background:white; color:black;
                               gridline-color:#dddddd;
                               alternate-background-color:#FFF7F1; }
                QHeaderView::section { background:#D97757; color:white;
                                       border:1px solid #cccccc;
                                       font-weight:bold; padding:4px; }
                QTableWidget::item:selected { background:#FF9248; color:black; }
                QPushButton { background:white; color:#A85C42;
                              border:1px solid #aaaaaa;
                              padding:2px 10px; border-radius:3px; }
                QPushButton:hover { background:#D97757; color:white; }
                QLabel { color:black; }
                QFrame[frameShape="4"] { color:#cccccc; }
            """)
