"""User Group view: PDF preview with editable table mode for USRGRPIN/USRGRPOT."""
import os
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QAbstractItemView, QStyledItemDelegate, QLineEdit,
    QComboBox, QTabWidget, QStackedWidget, QFileDialog,
)
from PySide6.QtCore import Qt

from translations import TRANSLATIONS
import logger

_RE_NAME = re.compile(r'^[A-Za-z0-9 _\-]*$')
_RE_GPIN = re.compile(r'^1\d{0,3}$')


# ── Name delegate ──────────────────────────────────────────────────────────────

class _NameLineEdit(QLineEdit):
    """QLineEdit that blocks chars beyond 16 and invalid chars, logging each."""
    _MAX = 16
    _CH_RE = re.compile(r'[A-Za-z0-9 _\-]')

    def keyPressEvent(self, event):
        """Handle key presses in the cell editor."""
        ch = event.text()
        if ch and ord(ch[0]) >= 32:
            sel = self.selectedText()
            free = self._MAX - len(self.text()) + len(sel)
            if free <= 0:
                logger.warning("log_invalid_input", ch)
                return
            if not self._CH_RE.match(ch):
                logger.warning("log_invalid_input", ch)
                return
        super().keyPressEvent(event)


class _NameDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        """Create the cell editor widget."""
        ed = _NameLineEdit(parent)
        self._prev = index.data() or ""
        return ed

    def setEditorData(self, editor, index):
        """Load the cell's value into the editor."""
        self._prev = index.data() or ""
        editor.setText(self._prev)

    def setModelData(self, editor, model, index):
        """Validate and write the editor's value back into the model."""
        text = editor.text()
        if not _RE_NAME.match(text):
            logger.warning("log_invalid_input", text)
            return
        if len(text) > _NameLineEdit._MAX:
            logger.warning("log_invalid_input", text[_NameLineEdit._MAX:])
            text = text[:_NameLineEdit._MAX]
        model.setData(index, text)


# ── GPIN delegate ──────────────────────────────────────────────────────────────

class _GpinLineEdit(QLineEdit):
    """QLineEdit accepting only values ^2\\d{0,3}$, logs blocked chars."""

    def keyPressEvent(self, event):
        """Handle key presses in the cell editor."""
        ch = event.text()
        if ch and ord(ch[0]) >= 32:
            if not ch.isdigit():
                logger.warning("log_invalid_input", ch)
                return
            sel = self.selectedText()
            cursor = self.cursorPosition()
            cur = self.text()
            if sel:
                tentative = cur[:self.selectionStart()] + ch + cur[self.selectionStart() + len(sel):]
            else:
                tentative = cur[:cursor] + ch + cur[cursor:]
            if len(tentative) > 4:
                logger.warning("log_invalid_input", ch)
                return
            if not tentative.startswith('1'):
                logger.warning("log_invalid_input", ch)
                return
        super().keyPressEvent(event)


class _GpinDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        """Create the cell editor widget."""
        ed = _GpinLineEdit(parent)
        self._prev = index.data() or ""
        return ed

    def setEditorData(self, editor, index):
        """Load the cell's value into the editor."""
        self._prev = index.data() or ""
        editor.setText(self._prev)

    def setModelData(self, editor, model, index):
        """Validate and write the editor's value back into the model."""
        text = editor.text().strip()
        if text and not _RE_GPIN.match(text):
            logger.warning("log_invalid_input", text)
            return
        model.setData(index, text)


# ── Bits delegate (ComboBox 8 / 16) ──────────────────────────────────────────

class _BitsDelegate(QStyledItemDelegate):
    _OPTIONS = ["8", "16"]

    def createEditor(self, parent, option, index):
        """Create the cell editor widget."""
        cb = QComboBox(parent)
        cb.addItems(self._OPTIONS)
        return cb

    def setEditorData(self, editor, index):
        """Load the cell's value into the editor."""
        val = str(index.data() or "16")
        idx = editor.findText(val)
        editor.setCurrentIndex(idx if idx >= 0 else 1)

    def setModelData(self, editor, model, index):
        """Validate and write the editor's value back into the model."""
        model.setData(index, editor.currentText())


# ── SWAP delegate ──────────────────────────────────────────────────────────────

class _SwapLineEdit(QLineEdit):
    """Accepts only '0' or '1'."""

    def keyPressEvent(self, event):
        """Handle key presses in the cell editor."""
        ch = event.text()
        if ch and ord(ch[0]) >= 32:
            if ch not in ('0', '1'):
                logger.warning("log_invalid_input", ch)
                return
            if len(self.selectedText()) == 0 and len(self.text()) >= 1:
                self.setText(ch)
                return
        super().keyPressEvent(event)


class _SwapDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        """Create the cell editor widget."""
        ed = _SwapLineEdit(parent)
        ed.setMaxLength(1)
        return ed

    def setEditorData(self, editor, index):
        """Load the cell's value into the editor."""
        editor.setText(str(index.data() or "0"))

    def setModelData(self, editor, model, index):
        """Validate and write the editor's value back into the model."""
        text = editor.text().strip()
        if text not in ('0', '1', ''):
            logger.warning("log_invalid_input", text)
            return
        model.setData(index, text if text else "0")


# ── Main view ──────────────────────────────────────────────────────────────────

class UsrGrpView(QWidget):
    """User Group view: PDF preview that switches to editable tables on 'Modifica'."""

    def __init__(self, folder, gpin_groups, gpot_groups, tmp_pdf,
                 app_state, on_close_cb,
                 progress_begin_fn=None, progress_end_fn=None):
        """Build the user-group view for the given folder."""
        super().__init__()
        self._folder         = folder
        self._gpin_groups    = [dict(g) for g in gpin_groups]
        self._gpot_groups    = [dict(g) for g in gpot_groups]
        self._tmp_pdf        = tmp_pdf
        self._app_state      = app_state
        self._on_close       = on_close_cb
        self._prog_begin     = progress_begin_fn or (lambda: None)
        self._prog_end       = progress_end_fn   or (lambda: None)
        self._edit_mode      = False
        self._pdf_doc        = None
        self._pdf_view       = None
        self._gpin_tbl       = None
        self._gpot_tbl       = None
        self._tab_widget     = None
        self._build_ui()
        self._apply_theme()

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Build the view's widgets (preview and edit pages, buttons)."""
        t = TRANSLATIONS[self._app_state.language]
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(6)

        self._lbl_title = QLabel(
            t.get("usrgrp_view_title", "User Group — YASKAWA YRC1000"))
        self._lbl_title.setStyleSheet("font-weight: bold; font-size: 10pt;")
        tb.addWidget(self._lbl_title)
        tb.addStretch()

        self._btn_export_pdf = QPushButton(t.get("btn_export_pdf", "Esporta PDF"))
        self._btn_export_pdf.setFixedHeight(26)
        self._btn_export_pdf.clicked.connect(self._on_export_pdf)
        tb.addWidget(self._btn_export_pdf)

        self._btn_export_excel = QPushButton(t.get("btn_export_excel", "Esporta Excel"))
        self._btn_export_excel.setFixedHeight(26)
        self._btn_export_excel.clicked.connect(self._on_export_excel)
        tb.addWidget(self._btn_export_excel)

        self._btn_modifica = QPushButton(t.get("btn_modifica", "Modifica"))
        self._btn_modifica.setFixedHeight(26)
        self._btn_modifica.clicked.connect(self._on_modifica)
        tb.addWidget(self._btn_modifica)

        self._btn_back = QPushButton(t.get("btn_back", "Indietro"))
        self._btn_back.setFixedHeight(26)
        self._btn_back.clicked.connect(self._on_back)
        self._btn_back.setVisible(False)
        tb.addWidget(self._btn_back)

        self._btn_export_groups = QPushButton(
            t.get("btn_export_groups", "Esporta Gruppi"))
        self._btn_export_groups.setFixedHeight(26)
        self._btn_export_groups.clicked.connect(self._on_export_groups)
        self._btn_export_groups.setVisible(False)
        tb.addWidget(self._btn_export_groups)

        self._btn_close = QPushButton(t.get("preview_close", "Chiudi"))
        self._btn_close.setFixedHeight(26)
        self._btn_close.clicked.connect(self._on_close)
        tb.addWidget(self._btn_close)

        root.addLayout(tb)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # Stacked: page 0 = PDF preview, page 1 = editable tabs
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_pdf_page())
        self._stack.addWidget(self._build_edit_page(t))
        self._stack.setCurrentIndex(0)
        root.addWidget(self._stack, 1)

    def _build_pdf_page(self):
        """Build the PDF-preview page."""
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        try:
            from PySide6.QtPdfWidgets import QPdfView
            from PySide6.QtPdf import QPdfDocument
            doc = QPdfDocument(self)
            doc.load(self._tmp_pdf)
            self._pdf_doc = doc
            view = QPdfView(container)
            view.setDocument(doc)
            view.setPageMode(QPdfView.PageMode.MultiPage)
            view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self._pdf_view = view
            lay.addWidget(view)
        except Exception as exc:
            lay.addWidget(QLabel(str(exc)))
        return container

    def _build_edit_page(self, t):
        """Build the editable groups page."""
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(True)

        self._gpin_tbl = self._make_table(self._gpin_groups, has_swap=False, t=t)
        self._gpot_tbl = self._make_table(self._gpot_groups, has_swap=False, t=t)

        self._tab_widget.addTab(
            self._gpin_tbl, t.get("usrgrp_tab_gpin", "Ingressi (USRGRPIN)"))
        self._tab_widget.addTab(
            self._gpot_tbl, t.get("usrgrp_tab_gpot", "Uscite (USRGRPOT)"))

        return self._tab_widget

    def _make_table(self, groups, has_swap, t):
        """Build the editable user-group table."""
        headers = [
            t.get("usrgrp_col_num",  "#"),
            t.get("usrgrp_col_name", "Name"),
            t.get("usrgrp_col_gpin", "GPIN"),
            t.get("usrgrp_col_bits", "Bit"),
        ]
        if has_swap:
            headers.append(t.get("usrgrp_col_swap", "SWAP"))

        n_rows = len(groups)
        n_cols = len(headers)
        tbl = QTableWidget(n_rows, n_cols)
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setAlternatingRowColors(True)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.setColumnWidth(0, 40)
        tbl.setColumnWidth(2, 72)
        tbl.setColumnWidth(3, 52)
        if has_swap:
            tbl.setColumnWidth(4, 56)
        tbl.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.AnyKeyPressed)

        tbl.setItemDelegateForColumn(1, _NameDelegate(tbl))
        tbl.setItemDelegateForColumn(2, _GpinDelegate(tbl))
        tbl.setItemDelegateForColumn(3, _BitsDelegate(tbl))
        if has_swap:
            tbl.setItemDelegateForColumn(4, _SwapDelegate(tbl))

        for ri, g in enumerate(groups):
            item_num = QTableWidgetItem(str(g['num']))
            item_num.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_num.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            tbl.setItem(ri, 0, item_num)

            item_name = QTableWidgetItem(g.get('name', ''))
            tbl.setItem(ri, 1, item_name)

            gpin_val = g.get('gpin', 0)
            item_gpin = QTableWidgetItem(str(gpin_val) if gpin_val else "")
            item_gpin.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            tbl.setItem(ri, 2, item_gpin)

            item_bits = QTableWidgetItem(str(g.get('bits', 0)))
            item_bits.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            tbl.setItem(ri, 3, item_bits)

            if has_swap:
                item_swap = QTableWidgetItem(str(g.get('val3', 0)))
                item_swap.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                tbl.setItem(ri, 4, item_swap)

        return tbl

    # ── Toolbar actions ───────────────────────────────────────────────────────

    def _on_modifica(self):
        """Switch to the edit page."""
        self._edit_mode = True
        self._stack.setCurrentIndex(1)
        self._btn_modifica.setVisible(False)
        self._btn_export_pdf.setVisible(False)
        self._btn_export_excel.setVisible(False)
        self._btn_back.setVisible(True)
        self._btn_export_groups.setVisible(True)

    def _on_back(self):
        """Return to the preview page."""
        self._edit_mode = False
        self._stack.setCurrentIndex(0)
        self._btn_back.setVisible(False)
        self._btn_export_groups.setVisible(False)
        self._btn_modifica.setVisible(True)
        self._btn_export_pdf.setVisible(True)
        self._btn_export_excel.setVisible(True)

    def _on_export_pdf(self):
        """Export the user-group PDF to a chosen path."""
        import shutil
        t = TRANSLATIONS[self._app_state.language]
        folder_name = os.path.basename(os.path.normpath(self._folder))
        default_name = f"UserGroup_{folder_name}.pdf"
        sp, _ = QFileDialog.getSaveFileName(
            self, t.get("dialog_save_pdf", "Salva PDF"),
            os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "PDF Files (*.pdf)")
        if not sp:
            logger.info("log_cancelled", "User Group - salva PDF")
            return
        try:
            shutil.copy2(self._tmp_pdf, sp)
            logger.info("log_usrgrp_pdf_saved", sp)
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))

    def _on_export_excel(self):
        """Export the user-group data to an Excel file."""
        t = TRANSLATIONS[self._app_state.language]
        folder_name = os.path.basename(os.path.normpath(self._folder))
        default_name = f"UserGroup_{folder_name}.xlsx"
        sp, _ = QFileDialog.getSaveFileName(
            self, t.get("dialog_save_excel", "Salva Excel"),
            os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "Excel Files (*.xlsx)")
        if not sp:
            logger.info("log_cancelled", "User Group - salva Excel")
            return
        self._prog_begin()
        try:
            from docs.usrgrp import generate_excel
            generate_excel(self._gpin_groups, self._gpot_groups,
                           sp, lang=self._app_state.language)
            logger.info("log_usrgrp_excel_saved", sp)
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))
        finally:
            self._prog_end()

    def _on_export_groups(self):
        """Export the edited groups to the controller files."""
        t = TRANSLATIONS[self._app_state.language]
        out_folder = QFileDialog.getExistingDirectory(
            self, t.get("dialog_export_folder", "Seleziona cartella di destinazione"),
            "", QFileDialog.Option.ShowDirsOnly)
        if not out_folder:
            logger.info("log_cancelled", "User Group - esporta gruppi")
            return
        self._prog_begin()
        try:
            gpin_data = self._collect_table(self._gpin_tbl, has_swap=False,
                                            orig=self._gpin_groups)
            gpot_data = self._collect_table(self._gpot_tbl, has_swap=False,
                                            orig=self._gpot_groups)
            from docs.usrgrp import write_gpin, write_gpot
            write_gpin(gpin_data, os.path.join(out_folder, "USRGRPIN.DAT"))
            write_gpot(gpot_data, os.path.join(out_folder, "USRGRPOT.DAT"))
            logger.info("log_usrgrp_exported", out_folder)
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))
        finally:
            self._prog_end()

    def _collect_table(self, tbl, has_swap, orig):
        """Read current table state into a list of group dicts."""
        result = []
        n_orig = len(orig)
        for ri in range(tbl.rowCount()):
            try:
                num_item = tbl.item(ri, 0)
                num = int(num_item.text()) if num_item else ri + 1

                name_item = tbl.item(ri, 1)
                name = (name_item.text() if name_item else '').strip()

                gpin_item = tbl.item(ri, 2)
                gpin_txt = (gpin_item.text() if gpin_item else '').strip()
                gpin = int(gpin_txt) if gpin_txt.isdigit() else 0

                bits_item = tbl.item(ri, 3)
                bits_txt = (bits_item.text() if bits_item else '').strip()
                bits = int(bits_txt) if bits_txt.isdigit() else 0

                val3 = 0
                if has_swap:
                    swap_item = tbl.item(ri, 4)
                    swap_txt = (swap_item.text() if swap_item else '').strip()
                    val3 = int(swap_txt) if swap_txt in ('0', '1') else 0

                result.append({'num': num, 'name': name,
                               'gpin': gpin, 'bits': bits, 'val3': val3})
            except Exception:
                result.append(dict(orig[ri]) if ri < n_orig else
                              {'num': ri + 1, 'name': '', 'gpin': 0, 'bits': 0, 'val3': 0})
        return result

    # ── Language / theme ──────────────────────────────────────────────────────

    def update_language(self, lang):
        """Re-translate the view for the new language."""
        try:
            t = TRANSLATIONS.get(lang, TRANSLATIONS["IT"])
            self._lbl_title.setText(
                t.get("usrgrp_view_title", "User Group — YASKAWA YRC1000"))
            self._btn_export_pdf.setText(t.get("btn_export_pdf", "Esporta PDF"))
            self._btn_export_excel.setText(t.get("btn_export_excel", "Esporta Excel"))
            self._btn_modifica.setText(t.get("btn_modifica", "Modifica"))
            self._btn_back.setText(t.get("btn_back", "Indietro"))
            self._btn_export_groups.setText(
                t.get("btn_export_groups", "Esporta Gruppi"))
            self._btn_close.setText(t.get("preview_close", "Chiudi"))
            if self._tab_widget is not None:
                self._tab_widget.setTabText(
                    0, t.get("usrgrp_tab_gpin", "Ingressi (USRGRPIN)"))
                self._tab_widget.setTabText(
                    1, t.get("usrgrp_tab_gpot", "Uscite (USRGRPOT)"))
            self._update_headers(self._gpin_tbl, t, has_swap=False)
            self._update_headers(self._gpot_tbl, t, has_swap=False)
            if not self._edit_mode:
                self._regen_pdf(lang)
        except Exception:
            pass

    def _regen_pdf(self, lang):
        """Regenerate the preview PDF for the given language."""
        try:
            from docs.usrgrp import generate_pdf
            generate_pdf(self._gpin_groups, self._gpot_groups,
                         self._tmp_pdf, lang=lang)
            if self._pdf_doc is not None:
                self._pdf_doc.close()
                self._pdf_doc.load(self._tmp_pdf)
        except Exception as exc:
            logger.warning("log_error_generic", str(exc))

    def _update_headers(self, tbl, t, has_swap):
        """Update the table headers for the current language."""
        if tbl is None:
            return
        hdrs = [
            t.get("usrgrp_col_num",  "#"),
            t.get("usrgrp_col_name", "Name"),
            t.get("usrgrp_col_gpin", "GPIN"),
            t.get("usrgrp_col_bits", "Bit"),
        ]
        if has_swap:
            hdrs.append(t.get("usrgrp_col_swap", "SWAP"))
        for ci, hdr in enumerate(hdrs):
            item = tbl.horizontalHeaderItem(ci)
            if item:
                item.setText(hdr)

    def _apply_theme(self):
        """Apply the current light/dark theme styling to the view."""
        if self._app_state.is_dark_mode:
            self.setStyleSheet("""
                QWidget { background:#231811; color:white; }
                QTabWidget::pane { border:1px solid #5C4938; }
                QTabBar::tab { background:#3A2D26; color:white;
                               padding:5px 12px; margin-right:2px; border-top-left-radius:6px; border-top-right-radius:6px; }
                QTabBar::tab:selected { background:#D97757; }
                QTableWidget { background:#231811; color:white;
                               gridline-color:#5C4938;
                               alternate-background-color:#3A2D26; }
                QHeaderView::section { background:#8A4533; color:white;
                                       border:1px solid #5C4938;
                                       font-weight:bold; padding:2px; }
                QTableWidget::item:selected { background:#FF9248; color:black; }
                QPushButton { background:#3A2D26; color:white;
                              border:1px solid #5C4938;
                              padding:4px 12px; border-radius:8px; }
                QPushButton:hover { background:#D97757; }
                QLabel { color:white; }
                QFrame[frameShape="4"] { color:#5C4938; }
            """)
        else:
            self.setStyleSheet("""
                QWidget { background:#f5f5f5; color:black; }
                QTabWidget::pane { border:1px solid #cccccc; }
                QTabBar::tab { background:#e0e0e0; color:black;
                               padding:5px 12px; margin-right:2px; border-top-left-radius:6px; border-top-right-radius:6px; }
                QTabBar::tab:selected { background:#D97757; color:white; }
                QTableWidget { background:white; color:black;
                               gridline-color:#dddddd;
                               alternate-background-color:#FFF7F1; }
                QHeaderView::section { background:#D97757; color:white;
                                       border:1px solid #cccccc;
                                       font-weight:bold; padding:2px; }
                QTableWidget::item:selected { background:#FF9248; color:black; }
                QPushButton { background:white; color:#A85C42;
                              border:1px solid #aaaaaa;
                              padding:4px 12px; border-radius:8px; }
                QPushButton:hover { background:#D97757; color:white; }
                QLabel { color:black; }
                QFrame[frameShape="4"] { color:#cccccc; }
            """)
