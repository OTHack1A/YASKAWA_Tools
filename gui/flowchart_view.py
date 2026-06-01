"""FlowchartView — panel shown when the user clicks Documentation › Flowchart."""
import os
import tempfile

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QFrame, QFileDialog, QSplitter,
                                QListWidget, QListWidgetItem, QProgressBar)
from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal
from PySide6.QtGui import QPixmap

from translations import TRANSLATIONS
import logger


class _Worker(QThread):
    """Background thread: parses JBI files and generates PDF."""
    done      = pyqtSignal(str, list)   # (pdf_path, fcs)
    error     = pyqtSignal(str)

    def __init__(self, folder: str, lang: str, pdf_path: str):
        """Initialise the flowchart-generation worker with folder, language, and output path."""
        super().__init__()
        self._folder   = folder
        self._lang     = lang
        self._pdf_path = pdf_path

    def run(self):
        """Worker thread body: build the flowcharts and PDF, emitting the result or an error."""
        try:
            from docs.flowchart import build_flowcharts, generate_pdf
            t = TRANSLATIONS.get(self._lang, TRANSLATIONS['IT'])
            fcs = build_flowcharts(self._folder)
            if not fcs:
                self.error.emit('no_jbi')
                return
            generate_pdf(
                fcs, self._pdf_path, self._lang,
                title=t.get('flowchart_pdf_title', 'Flowchart JBI'),
                toc_title=t.get('flowchart_toc_title', 'Sommario'),
            )
            self.done.emit(self._pdf_path, fcs)
        except Exception as exc:
            self.error.emit(str(exc))


class FlowchartView(QWidget):
    """Main content panel for the Flowchart feature."""

    def __init__(self, folder: str, app_state, on_close_cb):
        """Build the flowchart view for the given backup folder."""
        super().__init__()
        self._folder     = folder
        self._app_state  = app_state
        self._on_close   = on_close_cb
        self._fcs        = []
        self._pdf_path   = None
        self._pdf_doc    = None
        self._pdf_view   = None
        self._worker     = None
        self._tmp_dir    = tempfile.mkdtemp(prefix='fc_')
        self._build_ui()
        self._apply_theme()
        self._start_generation()

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Build the view's widgets (PDF preview, navigation list, export buttons)."""
        t  = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS['IT'])
        ly = QVBoxLayout(self)
        ly.setContentsMargins(8, 6, 8, 6)
        ly.setSpacing(4)

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(6)
        self._lbl_title = QLabel(t.get('flowchart_view_title', 'Flowchart'))
        self._lbl_title.setStyleSheet('font-weight:bold; font-size:10pt;')
        tb.addWidget(self._lbl_title)
        tb.addStretch()

        self._btn_export_pdf = QPushButton(t.get('flowchart_btn_export_pdf', 'Esporta PDF'))
        self._btn_export_pdf.setFixedHeight(26)
        self._btn_export_pdf.setEnabled(False)
        self._btn_export_pdf.clicked.connect(self._on_export_pdf)
        tb.addWidget(self._btn_export_pdf)

        self._btn_export_drawio = QPushButton(t.get('flowchart_btn_export_drawio', 'Esporta draw.io'))
        self._btn_export_drawio.setFixedHeight(26)
        self._btn_export_drawio.setEnabled(False)
        self._btn_export_drawio.clicked.connect(self._on_export_drawio)
        tb.addWidget(self._btn_export_drawio)

        self._btn_close = QPushButton(t.get('preview_close', 'Chiudi'))
        self._btn_close.setFixedHeight(26)
        self._btn_close.clicked.connect(self._on_close)
        tb.addWidget(self._btn_close)

        ly.addLayout(tb)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        ly.addWidget(sep)

        # Status / progress
        self._lbl_status = QLabel(t.get('flowchart_generating', 'Generazione in corso…'))
        self._lbl_status.setAlignment(Qt.AlignCenter)
        ly.addWidget(self._lbl_status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.setFixedHeight(8)
        ly.addWidget(self._progress)

        # Content area (splitter: TOC list + PDF viewer)
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setVisible(False)

        self._nav_list = QListWidget()
        self._nav_list.setMaximumWidth(200)
        self._nav_list.setMinimumWidth(120)
        self._nav_list.itemClicked.connect(self._on_nav_clicked)
        self._splitter.addWidget(self._nav_list)

        self._viewer_container = QWidget()
        self._viewer_layout    = QVBoxLayout(self._viewer_container)
        self._viewer_layout.setContentsMargins(0, 0, 0, 0)
        self._splitter.addWidget(self._viewer_container)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        ly.addWidget(self._splitter, 1)

    # ── Generation ─────────────────────────────────────────────────────────────

    def _start_generation(self):
        """Start the background flowchart generation."""
        pdf_path = os.path.join(self._tmp_dir, 'flowchart.pdf')
        self._worker = _Worker(self._folder, self._app_state.language, pdf_path)
        self._worker.done.connect(self._on_generation_done)
        self._worker.error.connect(self._on_generation_error)
        self._worker.start()

    def _on_generation_done(self, pdf_path: str, fcs: list):
        """On success, load the PDF preview and populate the navigation list."""
        t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS['IT'])
        self._fcs      = fcs
        self._pdf_path = pdf_path
        self._progress.setVisible(False)
        self._lbl_status.setVisible(False)

        logger.info('log_flowchart_generated', len(fcs))

        # Populate nav list
        self._nav_list.clear()
        # TOC is page 1, charts start at page 2
        toc_item = QListWidgetItem(t.get('flowchart_toc_title', 'Sommario'))
        toc_item.setData(Qt.UserRole, 0)
        self._nav_list.addItem(toc_item)
        for i, fc in enumerate(fcs):
            item = QListWidgetItem(fc.name)
            item.setData(Qt.UserRole, i + 1)   # 0-based page index
            self._nav_list.addItem(item)

        # Load PDF viewer
        self._load_pdf(pdf_path)
        self._splitter.setVisible(True)
        self._btn_export_pdf.setEnabled(True)
        self._btn_export_drawio.setEnabled(True)

    def _on_generation_error(self, msg: str):
        """On failure, show the error message."""
        t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS['IT'])
        self._progress.setVisible(False)
        if msg == 'no_jbi':
            self._lbl_status.setText(t.get('flowchart_no_jbi', 'Nessun file JBI trovato.'))
            logger.warning('log_flowchart_error', 'Nessun JBI')
        else:
            self._lbl_status.setText(t.get('log_flowchart_error', 'Errore: {}').format(msg))
            logger.error('log_flowchart_error', msg)

    def _load_pdf(self, pdf_path: str):
        # Remove previous viewer widget if any
        """Render the generated PDF into the preview area."""
        while self._viewer_layout.count():
            item = self._viewer_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()

        try:
            from PySide6.QtPdfWidgets import QPdfView
            from PySide6.QtPdf import QPdfDocument
            doc = QPdfDocument(self)
            doc.load(pdf_path)
            if doc.pageCount() <= 0:
                raise RuntimeError('empty')
            self._pdf_doc = doc
            view = QPdfView(self)
            view.setDocument(doc)
            try:
                view.setPageMode(QPdfView.PageMode.MultiPage)
            except AttributeError:
                pass
            self._pdf_view = view
            self._viewer_layout.addWidget(view)
        except Exception:
            lbl = QLabel('PDF generato — impossibile visualizzare anteprima.\n'
                         'Usare "Esporta PDF" per salvare e aprire esternamente.')
            lbl.setAlignment(Qt.AlignCenter)
            self._viewer_layout.addWidget(lbl)

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _on_nav_clicked(self, item: QListWidgetItem):
        """Scroll the preview to the flowchart selected in the navigation list."""
        page_idx = item.data(Qt.UserRole)
        if self._pdf_view is None or self._pdf_doc is None:
            return
        try:
            from PySide6.QtPdf import QPdfDocument
            from PySide6.QtCore import QPointF
            nav = self._pdf_view.pageNavigator()
            if nav is not None:
                nav.jump(page_idx, QPointF(0, 0))
        except Exception:
            pass

    # ── Export ─────────────────────────────────────────────────────────────────

    def _on_export_pdf(self):
        """Export the generated flowchart PDF to a user-chosen path."""
        t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS['IT'])
        dest, _ = QFileDialog.getSaveFileName(
            self, t.get('flowchart_btn_export_pdf', 'Esporta PDF'),
            os.path.join(os.path.expanduser('~'), 'flowchart.pdf'),
            'PDF (*.pdf)')
        if not dest:
            return
        try:
            import shutil
            shutil.copy2(self._pdf_path, dest)
            logger.info('log_flowchart_exported_pdf', dest)
        except Exception as exc:
            logger.error('log_flowchart_error', str(exc))

    def _on_export_drawio(self):
        """Export the flowcharts as a draw.io XML file to a user-chosen path."""
        t = TRANSLATIONS.get(self._app_state.language, TRANSLATIONS['IT'])
        dest, _ = QFileDialog.getSaveFileName(
            self, t.get('flowchart_btn_export_drawio', 'Esporta draw.io'),
            os.path.join(os.path.expanduser('~'), 'flowchart.drawio'),
            'draw.io (*.drawio *.xml)')
        if not dest:
            return
        try:
            from docs.flowchart import generate_drawio
            generate_drawio(self._fcs, dest)
            logger.info('log_flowchart_exported_drawio', dest)
        except Exception as exc:
            logger.error('log_flowchart_error', str(exc))

    # ── Language / Theme ───────────────────────────────────────────────────────

    def update_language(self, lang: str):
        """Re-translate the flowchart view for the new language."""
        t = TRANSLATIONS.get(lang, TRANSLATIONS['IT'])
        self._lbl_title.setText(t.get('flowchart_view_title', 'Flowchart'))
        self._btn_export_pdf.setText(t.get('flowchart_btn_export_pdf', 'Esporta PDF'))
        self._btn_export_drawio.setText(t.get('flowchart_btn_export_drawio', 'Esporta draw.io'))
        self._btn_close.setText(t.get('preview_close', 'Chiudi'))
        # Re-generate the inline PDF preview in the newly selected language.
        # Robustness: any failure is swallowed and reported to the log only;
        # the UI keeps the previously rendered PDF.
        try:
            if self._fcs and self._pdf_path:
                from docs.flowchart import generate_pdf
                generate_pdf(
                    self._fcs, self._pdf_path, lang,
                    title=t.get('flowchart_pdf_title', 'Flowchart JBI'),
                    toc_title=t.get('flowchart_toc_title', 'Sommario'),
                )
                self._load_pdf(self._pdf_path)
        except Exception as exc:
            try:
                logger.warning('log_error_generic', f'Flowchart regen: {exc}')
            except Exception:
                pass

    def _apply_theme(self):
        """Apply the current light/dark theme styling to the view."""
        dark = getattr(self._app_state, 'dark_mode', False)
        bg   = '#2b2b2b' if dark else '#ffffff'
        fg   = '#dddddd' if dark else '#1a1a1a'
        self.setStyleSheet(f'background:{bg}; color:{fg};')
