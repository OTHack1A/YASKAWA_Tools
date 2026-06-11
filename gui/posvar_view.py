"""Editable table view for YASKAWA position variables (Genera → Solo punti).

Shows every P slot of VAR.DAT in one ordered, editable table. Edits are written
back through :mod:`docs.posvar`, which preserves every untouched line
byte-for-byte so the exported file always reloads on the robot.
"""

import os
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QComboBox,
    QStyledItemDelegate, QLineEdit, QCheckBox, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression

from translations import TRANSLATIONS
import logger
import secure_paths
from docs.posvar import (
    parse_var_dat, write_var_dat, write_varname_dat, generate_posvar_pdf,
    axis_labels, format_value, CONFIG_LEN, NAME_MAX_LEN,
    VAR_FILE, VARNAME_FILE,
)

# ── Column indices ──────────────────────────────────────────────────────────
C_P, C_NAME, C_TYPE, C_FR, C_TOOL, C_CONFIG = 0, 1, 2, 3, 4, 5
C_V0 = 6                       # first axis value column
N_VALUES = 8                   # value columns V1..V8
N_COLS = C_V0 + N_VALUES       # 14
_VAL_COLS = range(C_V0, C_V0 + N_VALUES)
_E1_COL, _E2_COL = C_V0 + 6, C_V0 + 7   # external axes (locked on 6-axis robots)

_TYPE_CHOICES = ['PULSE', 'RECTAN', 'UNUSED']
_VALUE_RE  = re.compile(r'^[+\-]?\d*([.,]\d*)?$')
_INT_RE    = re.compile(r'^\d{1,3}$')
_CONFIG_RE = re.compile(r'^[01]{%d}$' % CONFIG_LEN)


class _TypeDelegate(QStyledItemDelegate):
    """Combo-box editor for the Tipo column (PULSE / RECTAN / UNUSED)."""

    def __init__(self, view, parent=None):
        """Store the owning view so edits route back to its handler."""
        super().__init__(parent)
        self._view = view

    def createEditor(self, parent, option, index):
        """Create the Tipo combo editor."""
        cb = QComboBox(parent)
        cb.addItems(_TYPE_CHOICES)
        return cb

    def setEditorData(self, editor, index):
        """Initialise the combo with the cell's current type."""
        cur = index.data() or 'UNUSED'
        i = editor.findText(cur)
        editor.setCurrentIndex(i if i >= 0 else _TYPE_CHOICES.index('UNUSED'))

    def setModelData(self, editor, model, index):
        """Apply the chosen type via the view (handles activation + relabel)."""
        self._view._on_type_chosen(index.row(), editor.currentText())


class PosVarView(QWidget):
    """In-window editor for the ///P section of VAR.DAT."""

    def __init__(self, folder, app_state, on_close_cb):
        """Build the position-variable editor for the VAR.DAT in ``folder``."""
        super().__init__()
        self._folder    = folder
        self._app_state = app_state
        self._on_close  = on_close_cb
        self._data      = None
        self._points    = []
        self._building  = True
        self._has_ext   = False     # True if robot has external axes (E1/E2 editable)
        self._load()
        self._build_ui()
        self._apply_theme()
        self._building = False

    # ── Load ────────────────────────────────────────────────────────────────

    def _load(self):
        """Parse VAR.DAT (and VARNAME names) for the working folder."""
        self._data = parse_var_dat(self._folder)
        self._points = self._data['points']
        self._has_ext = (self._data.get('pfnum', 6) or 6) > 6
        logger.info('log_posvar_loaded', len(self._points),
                    sum(1 for p in self._points if p['used']))

    # ── UI ────────────────────────────────────────────────────────────────────

    def _t(self):
        """Return the current translation dict."""
        return TRANSLATIONS.get(self._app_state.language, TRANSLATIONS['IT'])

    def _build_ui(self):
        """Build the toolbar, filter row and the editable table."""
        t = self._t()
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(6)
        self._lbl_title = QLabel(t.get('posvar_title', 'Variabili di posizione (P) — VAR.DAT'))
        self._lbl_title.setStyleSheet('font-weight:bold; font-size:10pt;')
        tb.addWidget(self._lbl_title)
        tb.addStretch()
        self._btn_export = QPushButton(t.get('posvar_btn_export', 'Esporta'))
        self._btn_export.setFixedHeight(26)
        self._btn_export.clicked.connect(self._on_export)
        tb.addWidget(self._btn_export)
        self._btn_pdf = QPushButton(t.get('btn_generate_pdf', 'Genera PDF'))
        self._btn_pdf.setFixedHeight(26)
        self._btn_pdf.clicked.connect(self._on_generate_pdf)
        tb.addWidget(self._btn_pdf)
        self._btn_close = QPushButton(t.get('preview_close', 'Chiudi'))
        self._btn_close.setFixedHeight(26)
        self._btn_close.clicked.connect(self._on_close_clicked)
        tb.addWidget(self._btn_close)
        root.addLayout(tb)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # Filter row
        fr = QHBoxLayout()
        fr.setSpacing(6)
        self._lbl_search = QLabel(t.get('posvar_search', 'Cerca (P o nome):'))
        fr.addWidget(self._lbl_search)
        self._search = QLineEdit()
        self._search.setFixedWidth(200)
        self._search.setPlaceholderText('P048, HOME, …')
        self._search.textChanged.connect(self._apply_filter)
        fr.addWidget(self._search)
        self._chk_used = QCheckBox(t.get('posvar_only_defined', 'Solo punti definiti'))
        # Default OFF: show every P slot (defined and UNUSED) so the user can see
        # the whole table and turn any free slot into a new point.
        self._chk_used.setChecked(False)
        self._chk_used.stateChanged.connect(self._apply_filter)
        fr.addWidget(self._chk_used)
        fr.addStretch()
        self._lbl_count = QLabel('')
        self._lbl_count.setStyleSheet('color:gray; font-size:8pt;')
        fr.addWidget(self._lbl_count)
        root.addLayout(fr)

        # Table
        self._tbl = QTableWidget(len(self._points), N_COLS)
        self._tbl.setHorizontalHeaderLabels(self._headers(t))
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.AnyKeyPressed)
        self._tbl.setItemDelegateForColumn(C_TYPE, _TypeDelegate(self, self._tbl))
        self._tbl.verticalHeader().setDefaultSectionSize(20)

        self._tbl.blockSignals(True)
        for r in range(len(self._points)):
            self._render_row(r)
        self._tbl.blockSignals(False)

        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        self._tbl.setColumnWidth(C_P, 56)
        self._tbl.setColumnWidth(C_NAME, 150)
        self._tbl.setColumnWidth(C_TYPE, 90)
        self._tbl.setColumnWidth(C_FR, 48)
        self._tbl.setColumnWidth(C_TOOL, 48)
        self._tbl.setColumnWidth(C_CONFIG, 200)
        for c in _VAL_COLS:
            self._tbl.setColumnWidth(c, 78)

        self._tbl.itemChanged.connect(self._on_item_changed)
        self._tbl.cellDoubleClicked.connect(self._on_cell_double_clicked)
        root.addWidget(self._tbl, 1)

        self._apply_filter()

    def _headers(self, t):
        """Return the 14 localized column headers."""
        ax = ['S / X', 'L / Y', 'U / Z', 'R / Rx', 'B / Ry', 'T / Rz', 'E1', 'E2']
        return [
            t.get('posvar_col_p', 'P'),
            t.get('posvar_col_name', 'Nome'),
            t.get('posvar_col_type', 'Tipo'),
            t.get('posvar_col_fr', 'Fr#'),
            t.get('posvar_col_tool', 'Tool'),
            t.get('posvar_col_config', 'Config (RCONF 24bit)'),
        ] + ax

    # ── Row rendering & locking ───────────────────────────────────────────────

    def _mk_item(self, text, editable, center=False):
        """Create a table item with the right edit flags and alignment."""
        it = QTableWidgetItem('' if text is None else str(text))
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if editable:
            flags |= Qt.ItemIsEditable
        it.setFlags(flags)
        if center:
            it.setTextAlignment(Qt.AlignCenter)
        return it

    def _render_row(self, r):
        """(Re)populate every cell of row ``r`` from the point model."""
        p = self._points[r]
        used = p.get('used', False)
        is_raw = (p.get('type') == 'RAW')
        editable = used and not is_raw

        # P id (read-only); name editable on defined slots (stored in VARNAME.DAT)
        self._tbl.setItem(r, C_P, self._mk_item('P%03d' % p['index'], False, center=True))
        self._tbl.setItem(r, C_NAME, self._mk_item(p.get('name', ''), editable))

        # Type — editable via delegate unless RAW
        type_disp = p.get('type', 'UNUSED')
        self._tbl.setItem(r, C_TYPE, self._mk_item(type_disp, not is_raw, center=True))

        is_rectan = (p.get('type') == 'RECTAN')
        # Frame number (only meaningful/editable for RECTAN)
        fr_val = p.get('h2', 0) if used else ''
        self._tbl.setItem(r, C_FR,
                          self._mk_item(fr_val, editable and is_rectan, center=True))
        # Tool
        tool_val = p.get('tool', 0) if used else ''
        self._tbl.setItem(r, C_TOOL, self._mk_item(tool_val, editable, center=True))
        # Config
        cfg = p.get('config', '') if used else ''
        self._tbl.setItem(r, C_CONFIG, self._mk_item(cfg, editable))

        # Values
        ax = axis_labels(p)
        vals = list(p.get('values', []))
        vals = (vals + [''] * N_VALUES)[:N_VALUES]
        for i, c in enumerate(_VAL_COLS):
            is_ext = c in (_E1_COL, _E2_COL)
            cell_edit = editable and (self._has_ext or not is_ext)
            it = self._mk_item(vals[i] if used else '', cell_edit, center=False)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if used and i < len(ax):
                it.setToolTip(ax[i])
            self._tbl.setItem(r, c, it)

    # ── Filtering ─────────────────────────────────────────────────────────────

    def _apply_filter(self, *_):
        """Show/hide rows per the search text and 'only defined' toggle.

        Number search is a *prefix* match on the un-padded point number, so
        ``p10`` (or ``10``) matches P10, P100..P109, P1000..P1099 and so on —
        every point whose decimal index starts with the typed digits.  A
        non-numeric query is matched as a substring of the point name.
        """
        try:
            q = (self._search.text() or '').strip().lower()
        except Exception:
            q = ''
        # Extract the digit prefix from queries like "p10", "P10" or "10".
        m = re.match(r'^p?0*(\d+)$', q) if q else None
        num_prefix = m.group(1) if m else None
        only_used = self._chk_used.isChecked()
        shown = 0
        for r, p in enumerate(self._points):
            ok = True
            if only_used and not p.get('used'):
                ok = False
            if ok and q:
                if num_prefix is not None:
                    ok = str(p['index']).startswith(num_prefix)
                else:
                    ok = q in (p.get('name', '') or '').lower()
            self._tbl.setRowHidden(r, not ok)
            if ok:
                shown += 1
        total_used = sum(1 for p in self._points if p.get('used'))
        self._lbl_count.setText(
            self._t().get('posvar_count', '{} mostrati · {} definiti · {} slot')
            .format(shown, total_used, len(self._points)))

    # ── Edit handlers ─────────────────────────────────────────────────────────

    def _set_cell_text(self, r, c, text):
        """Set a cell's text without re-triggering itemChanged."""
        self._tbl.blockSignals(True)
        it = self._tbl.item(r, c)
        if it is not None:
            it.setText('' if text is None else str(text))
        self._tbl.blockSignals(False)

    def _on_item_changed(self, item):
        """Validate and apply an edit to Fr#/Tool/Config/value cells."""
        if self._building or item is None:
            return
        r, c = item.row(), item.column()
        if r >= len(self._points):
            return
        p = self._points[r]
        try:
            if c == C_NAME:
                self._commit_name(p, r, c, item)
            elif c == C_TOOL:
                self._commit_int(p, r, c, 'tool', item, lo=0, hi=63)
            elif c == C_FR:
                self._commit_int(p, r, c, 'h2', item, lo=0, hi=63)
            elif c == C_CONFIG:
                self._commit_config(p, r, c, item)
            elif c in _VAL_COLS:
                self._commit_value(p, r, c, item)
        except Exception as exc:
            logger.error('log_error_generic', str(exc))

    def _commit_name(self, p, r, c, item):
        """Commit a point-name edit (goes to VARNAME.DAT, not VAR.DAT).

        Pendant rules: max ``NAME_MAX_LEN`` chars, latin-1 encodable, no
        control characters.  Commas are rejected because the VARNAME line
        format is comma-separated.  An empty text clears the name.
        """
        txt = item.text().strip()
        ok = (len(txt) <= NAME_MAX_LEN and ',' not in txt
              and not any(ord(ch) < 32 for ch in txt))
        if ok:
            try:
                txt.encode('latin-1')
            except UnicodeEncodeError:
                ok = False
        if not ok:
            logger.warning('log_invalid_input', txt or '—')
            self._set_cell_text(r, c, p.get('name', ''))
            return
        old = p.get('name', '')
        if txt == old:
            return
        p['name'] = txt
        # Names live in VARNAME.DAT: a separate dirty flag so a rename never
        # forces the point's VAR.DAT line to be rewritten.
        p['name_dirty'] = True
        self._set_cell_text(r, c, txt)
        logger.info('log_posvar_edit', 'P%03d' % p['index'],
                    self._tbl.horizontalHeaderItem(c).text(),
                    old or '—', txt or '—')

    def _commit_int(self, p, r, c, key, item, lo, hi):
        """Commit an integer cell (Tool / Fr#) with range validation + logging."""
        txt = item.text().strip()
        if not _INT_RE.match(txt) or not (lo <= int(txt) <= hi):
            logger.warning('log_invalid_input', txt or '—')
            self._set_cell_text(r, c, p.get(key, 0))
            return
        old = p.get(key, 0)
        new = int(txt)
        if new == old:
            return
        p[key] = new
        p['dirty'] = True
        logger.info('log_posvar_edit', 'P%03d' % p['index'],
                    self._tbl.horizontalHeaderItem(c).text(), old, new)

    def _commit_config(self, p, r, c, item):
        """Commit the 24-bit config (RCONF) cell with strict validation."""
        txt = item.text().strip()
        if not _CONFIG_RE.match(txt):
            logger.warning('log_posvar_bad_config', txt or '—')
            self._set_cell_text(r, c, p.get('config', '0' * CONFIG_LEN))
            return
        old = p.get('config', '')
        if txt == old:
            return
        p['config'] = txt
        p['dirty'] = True
        logger.info('log_posvar_edit', 'P%03d' % p['index'], 'Config', old, txt)

    def _commit_value(self, p, r, c, item):
        """Commit an axis value cell with numeric validation + canonical format."""
        idx = c - C_V0
        txt = item.text().strip()
        if txt and not _VALUE_RE.match(txt):
            logger.warning('log_invalid_input', txt)
            old_disp = p['values'][idx] if idx < len(p['values']) else ''
            self._set_cell_text(r, c, old_disp)
            return
        # Ensure values list is long enough
        while len(p['values']) <= idx:
            p['values'].append('0')
        old = p['values'][idx]
        new = format_value(p.get('type'), idx, txt)
        if new == old:
            if item.text() != new:
                self._set_cell_text(r, c, new)
            return
        p['values'][idx] = new
        p['dirty'] = True
        self._set_cell_text(r, c, new)
        ax = axis_labels(p)
        col_name = ax[idx] if idx < len(ax) else 'V%d' % (idx + 1)
        logger.info('log_posvar_edit', 'P%03d' % p['index'], col_name, old, new)

    def _on_type_chosen(self, r, new_type):
        """Apply a Tipo change from the combo delegate (activate / clear / switch)."""
        if self._building or r >= len(self._points):
            return
        p = self._points[r]
        old_type = p.get('type', 'UNUSED')
        if new_type == old_type:
            return
        if new_type == 'UNUSED':
            p['used'] = False
            p['type'] = 'UNUSED'
            p['values'] = []
            p['dirty'] = True
            logger.info('log_posvar_type', 'P%03d' % p['index'], old_type, 'UNUSED')
        else:
            # PULSE or RECTAN — (re)initialise the slot.
            was_used = p.get('used')
            p['type'] = new_type
            p['used'] = True
            if not was_used:
                p['h0'] = 0
                p['h1'] = 1 if new_type == 'RECTAN' else 0
                p['h2'] = 0
                p['h4'] = 0
                p['tool'] = p.get('tool', 0) or 0
                p['config'] = '0' * CONFIG_LEN
                p['values'] = [format_value(new_type, i, '0') for i in range(N_VALUES)]
                logger.info('log_posvar_type', 'P%03d' % p['index'], old_type, new_type)
            else:
                # Switching PULSE<->RECTAN: values are not convertible → reset.
                p['h1'] = 1 if new_type == 'RECTAN' else 0
                p['values'] = [format_value(new_type, i, '0') for i in range(N_VALUES)]
                logger.warning('log_posvar_type_switch',
                               'P%03d' % p['index'], old_type, new_type)
        p['dirty'] = True
        self._tbl.blockSignals(True)
        self._render_row(r)
        self._tbl.blockSignals(False)
        self._apply_filter()

    def _on_cell_double_clicked(self, r, c):
        """Warn in the log when the user tries to edit a locked cell."""
        if r >= len(self._points):
            return
        it = self._tbl.item(r, c)
        if it is None or (it.flags() & Qt.ItemIsEditable):
            return
        # Non-editable cell that the user attempted to edit.
        if c == C_P:
            return  # silently read-only (point id)
        p = self._points[r]
        col_name = self._tbl.horizontalHeaderItem(c).text()
        if c in (_E1_COL, _E2_COL) and not self._has_ext:
            logger.warning('log_posvar_locked_ext', 'P%03d' % p['index'], col_name)
        elif not p.get('used'):
            logger.warning('log_posvar_locked_unused', 'P%03d' % p['index'], col_name)
        else:
            logger.warning('log_posvar_locked', 'P%03d' % p['index'], col_name)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_close_clicked(self):
        """Handle the Close button."""
        logger.info('log_btn_pressed', self._btn_close.text())
        self._on_close()

    def _on_export(self):
        """Export the edited VAR.DAT to a chosen folder (preserving all else).

        The source file is reloaded and rewritten losslessly: every line outside
        the edited points is kept byte-for-byte, so only the ///P point lines the
        user actually changed are touched.  Result and errors go to the log only
        (no blocking pop-up), and the run never raises out of this handler.
        """
        t = self._t()
        logger.info('log_btn_pressed', self._btn_export.text())
        try:
            folder = QFileDialog.getExistingDirectory(
                self, t.get('dialog_export_folder', 'Seleziona cartella di destinazione'),
                self._folder)
        except Exception as exc:
            logger.error('log_error_generic', str(exc))
            return
        if not folder:
            logger.info('log_cancelled', t.get('menu_solo_punti', 'Solo punti'))
            return
        out = os.path.join(folder, VAR_FILE)
        try:
            n = write_var_dat(self._data, out, log_fn=logger.info)
            logger.info('log_posvar_exported', out, n)
            # Names live in VARNAME.DAT — export it too when any name changed.
            if any(p.get('name_dirty') for p in self._points):
                out_names = os.path.join(folder, VARNAME_FILE)
                wn = write_varname_dat(self._data, out_names, log_fn=logger.info)
                logger.info('log_posvar_names_exported', out_names, wn)
            try:
                from docs.fsutil import reveal_in_explorer
                reveal_in_explorer(out)
            except Exception as exc:
                logger.warning('log_error_generic', str(exc))
        except Exception as exc:
            # Never surface a dialog or crash — the log is the single channel.
            logger.error('log_posvar_export_fail', str(exc))

    def _on_generate_pdf(self):
        """Generate a PDF of the current (in-table) point values."""
        t = self._t()
        logger.info('log_btn_pressed', self._btn_pdf.text())
        folder_name = os.path.basename(os.path.normpath(self._folder))
        default_name = f'Punti_{folder_name}.pdf'
        tmp = secure_paths.temp_path(default_name)
        headers = {
            'point': t.get('posvar_col_p', 'P'),
            'name':  t.get('posvar_col_name', 'Nome'),
            'type':  t.get('posvar_col_type', 'Tipo'),
            'tool':  t.get('posvar_col_tool', 'Tool'),
        }
        only_used = self._chk_used.isChecked()
        try:
            ok = generate_posvar_pdf(
                self._points, tmp,
                file_label=f'{VAR_FILE} — {folder_name}',
                headers=headers, lang=self._app_state.language,
                log_fn=logger.info, used_only=only_used)
        except Exception as exc:
            logger.error('log_error_generic', str(exc))
            return
        if not ok:
            QMessageBox.warning(
                self, t.get('menu_solo_punti', 'Solo punti'),
                t.get('posvar_pdf_empty', 'Nessun punto da inserire nel PDF.'))
            return
        sp, _ = QFileDialog.getSaveFileName(
            self, t.get('dialog_save_pdf', 'Salva PDF'),
            os.path.join(os.path.expanduser('~'), 'Desktop', default_name),
            'PDF Files (*.pdf)')
        if not sp:
            logger.info('log_cancelled', f"{t.get('menu_solo_punti', 'Solo punti')} — PDF")
            return
        try:
            import shutil
            shutil.copy2(tmp, sp)
            logger.info('log_pdf_saved', sp)
            try:
                from docs.fsutil import reveal_in_explorer
                reveal_in_explorer(sp)
            except Exception:
                pass
        except Exception as exc:
            logger.error('log_error_generic', str(exc))

    # ── Language ──────────────────────────────────────────────────────────────

    def update_language(self, lang):
        """Re-translate the view for a new language."""
        try:
            t = TRANSLATIONS.get(lang, TRANSLATIONS['IT'])
            self._lbl_title.setText(t.get('posvar_title',
                                          'Variabili di posizione (P) — VAR.DAT'))
            self._btn_export.setText(t.get('posvar_btn_export', 'Esporta'))
            self._btn_pdf.setText(t.get('btn_generate_pdf', 'Genera PDF'))
            self._btn_close.setText(t.get('preview_close', 'Chiudi'))
            self._lbl_search.setText(t.get('posvar_search', 'Cerca (P o nome):'))
            self._chk_used.setText(t.get('posvar_only_defined', 'Solo punti definiti'))
            self._tbl.setHorizontalHeaderLabels(self._headers(t))
            self._apply_filter()
        except Exception as exc:
            logger.error('log_error_generic', str(exc))

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        """Apply the current light/dark theme styling to the view."""
        if self._app_state.is_dark_mode:
            self.setStyleSheet("""
                QWidget          { background:#231811; color:white; font-size:8pt; }
                QTableWidget     { background:#231811; color:white;
                                   gridline-color:#5C4938;
                                   alternate-background-color:#3A2D26; font-size:8pt; }
                QTableWidget::item:selected, QAbstractItemView::item:selected {
                                   background:#FF9248; color:black; }
                QHeaderView::section { background:#8A4533; color:white;
                                       border:1px solid #5C4938; padding:2px;
                                       font-size:7pt; font-weight:bold; }
                QPushButton      { background:#3A2D26; color:white;
                                   border:1px solid #5C4938;
                                   padding:2px 10px; border-radius:3px; }
                QPushButton:hover { background:#D97757; }
                QLabel           { color:white; }
                QCheckBox        { color:white; }
                QLineEdit        { background:#3A2D26; color:white;
                                   border:1px solid #5C4938; border-radius:4px;
                                   padding:3px 6px; }
                QLineEdit:focus  { border:1px solid #FF9248; }
                QComboBox        { background:#3A2D26; color:white;
                                   border:1px solid #5C4938; border-radius:4px;
                                   padding:2px 6px; }
                QFrame[frameShape="4"] { color:#5C4938; }
            """)
        else:
            self.setStyleSheet("""
                QWidget          { background:#f5f5f5; color:black; font-size:8pt; }
                QTableWidget     { background:white; color:black;
                                   gridline-color:#dddddd;
                                   alternate-background-color:#FFF7F1; font-size:8pt; }
                QTableWidget::item:selected, QAbstractItemView::item:selected {
                                   background:#FF9248; color:black; }
                QHeaderView::section { background:#D97757; color:white;
                                       border:1px solid #cccccc;
                                       font-weight:bold; padding:2px; font-size:7pt; }
                QPushButton      { background:white; color:#A85C42;
                                   border:1px solid #aaaaaa;
                                   padding:2px 10px; border-radius:3px; }
                QPushButton:hover { background:#D97757; color:white; }
                QLabel           { color:black; }
                QCheckBox        { color:black; }
                QLineEdit        { background:white; color:black;
                                   border:1px solid #c4c4c4; border-radius:4px;
                                   padding:3px 6px; }
                QLineEdit:focus  { border:1px solid #D97757; }
                QComboBox        { background:white; color:black;
                                   border:1px solid #c4c4c4; border-radius:4px;
                                   padding:2px 6px; }
                QFrame[frameShape="4"] { color:#cccccc; }
            """)
