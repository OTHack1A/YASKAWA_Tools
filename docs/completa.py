"""
Generates the complete documentation PDF by merging all sections:
Targhetta → TOC → Panel → JOBs → Parametri → UF#()/Tools → Allegati → Logo page
"""

import os
import sys
import shutil
import tempfile

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, Image)


def _logo_path():
    """Return the path to the bundled logo, handling PyInstaller bundling."""
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for ext in (".png", ".bmp"):
        p = os.path.join(base, "logo-home" + ext)
        if os.path.exists(p):
            return p
    return os.path.join(base, "logo-home.png")


def _count_pages(pdf_path):
    """Return the page count of a PDF, or 0 on error."""
    try:
        from pypdf import PdfReader
        with open(pdf_path, "rb") as f:
            return len(PdfReader(f).pages)
    except Exception:
        return 0


class _TrackingParagraph(Paragraph):
    """Paragraph subclass that records its absolute page Y when drawn.

    drawOn(canvas, x, y) receives LOCAL y (relative to the table's CTM origin).
    We compose with the current transformation matrix to get the absolute page Y.
    """
    def __init__(self, text, style, registry, key):
        """Initialise a Paragraph that records its absolute page position in the link registry."""
        super().__init__(text, style)
        self._registry = registry
        self._key = key

    def drawOn(self, canvas, x, y, _sW=0):
        """Draw the paragraph and store its absolute page Y in the link registry."""
        m = canvas._currentMatrix  # (a, b, c, d, e, f)
        # absolute page Y = b*x + d*y + f  (standard 2-D affine transform)
        abs_y = m[1] * x + m[3] * y + m[5]
        # Record the 0-based page index within the (possibly multi-page) TOC so
        # the link annotation is later stamped on the correct page.
        try:
            page0 = canvas.getPageNumber() - 1
        except Exception:
            page0 = 0
        self._registry[self._key] = (page0, abs_y)
        super().drawOn(canvas, x, y, _sW)


def _generate_toc_pdf(output_path, sections, folder_name, lang, t, link_registry=None):
    """
    Generate a single-page TOC PDF.
    sections: list of (dest_key, label, content_page_number)
    """
    from docs.utils import pdf_font, xml_escape
    from docs.pdf_header import draw_page_header

    f_reg  = pdf_font(lang, bold=False)
    f_bold = pdf_font(lang, bold=True)
    ACCENT   = colors.HexColor("#D97757")
    WHITE  = colors.white
    CGRID  = colors.HexColor("#cccccc")
    LGRAY  = colors.HexColor("#f5f5f5")

    W = A4[0] - 40 * mm

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=22 * mm,
    )

    s_head = ParagraphStyle("th", fontName=f_bold, fontSize=15, textColor=colors.black,
                             alignment=TA_CENTER, leading=20)
    s_th   = ParagraphStyle("tth", fontName=f_bold, fontSize=9, textColor=colors.black)
    s_td   = ParagraphStyle("ttd", fontName=f_reg, fontSize=10, textColor=ACCENT, leading=14)
    s_pg   = ParagraphStyle("tpg", fontName=f_bold, fontSize=10, textColor=ACCENT, leading=14,
                             alignment=TA_CENTER)

    toc_title   = t.get("completa_toc_title",   "INDICE")
    col_section = t.get("completa_toc_section", "Sezione")
    col_page    = t.get("completa_toc_page",    "Pagina")

    hdr = Table(
        [[Paragraph(f"{xml_escape(toc_title)}<br/><font size='10'>{xml_escape(folder_name)}</font>", s_head)]],
        colWidths=[W],
    )
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), ACCENT),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    _reg = link_registry if link_registry is not None else {}

    # TOC table rows: section name | page number
    rows = [[Paragraph(col_section, s_th), Paragraph(col_page, s_th)]]
    for key, label, page_num in sections:
        rows.append([
            _TrackingParagraph(xml_escape(label), s_td, _reg, key),
            Paragraph(str(page_num), s_pg),
        ])

    toc_tbl = Table(rows, colWidths=[W - 28 * mm, 28 * mm], repeatRows=1)
    toc_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), ACCENT),
        ("TEXTCOLOR",     (0, 0), (-1,  0), colors.black),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LGRAY]),
        ("GRID",          (0, 0), (-1, -1), 0.3, CGRID),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))

    story = [hdr, Spacer(1, 8 * mm), toc_tbl]
    doc.build(story, onFirstPage=draw_page_header, onLaterPages=draw_page_header)


def _generate_logo_page(output_path):
    """Generate a blank final page with the company logo centered."""
    from docs.pdf_header import draw_page_header

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=22 * mm,
    )

    logo = _logo_path()
    story = [Spacer(1, 60 * mm)]
    if os.path.isfile(logo):
        try:
            img = Image(logo, width=100 * mm, height=100 * mm, kind='proportional')
            img.hAlign = 'CENTER'
            story.append(img)
        except Exception:
            pass

    doc.build(story, onFirstPage=draw_page_header, onLaterPages=draw_page_header)


def _merge_pdfs(pdf_paths, output_path):
    """Merge PDF files into output_path using pypdf."""
    from pypdf import PdfWriter, PdfReader

    writer = PdfWriter()
    for path in pdf_paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as f:
                writer.append(PdfReader(f))
        except Exception:
            pass

    with open(output_path, "wb") as f:
        writer.write(f)


def _add_named_destinations(merged_path, output_path, dest_map):
    """
    Re-open the merged PDF and add named destinations so that <a href="#key">
    links in the TOC navigate to the correct pages.
    dest_map: {name: page_index_0based}
    """
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(merged_path)
        writer = PdfWriter()
        writer.append(reader)
        for name, page_idx in dest_map.items():
            if page_idx is not None and 0 <= page_idx < len(reader.pages):
                try:
                    writer.add_named_destination(name, page_idx)
                except Exception:
                    pass
        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception:
        shutil.copy2(merged_path, output_path)
        return False


def _generate_header_overlay(output_path):
    """Generate a single-page A4 PDF containing only the company header (for overlaying on attachments)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as pdf_canvas
    from docs.pdf_header import draw_page_header

    class _Doc:
        pagesize = A4
        leftMargin = 20 * mm
        rightMargin = 20 * mm

    c = pdf_canvas.Canvas(output_path, pagesize=A4)
    draw_page_header(c, _Doc())
    c.save()


_LANG_CODE_MAP = {
    "IT": "it", "EN": "en", "FR": "fr",
    "ES": "es", "DE": "de", "UK": "uk", "JA": "ja",
}


def _create_translated_attachment_pdf(input_path, output_path,
                                      start_page_num, section_label,
                                      target_lang_code, lang="IT"):
    """
    Extract text from a PDF, detect its language, and if different from
    target_lang_code, translate it via Google Translate (deep-translator)
    and write a new clean PDF with company header + translated text + page numbers.

    Returns True  → translation done, output_path written.
    Returns False → no translation needed (same language or no text).
    Raises        → translation failed (caller falls back to normal pipeline).
    """
    import io as _io
    from langdetect import detect, LangDetectException
    from deep_translator import GoogleTranslator
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.units import mm as _mm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from docs.pdf_header import draw_page_header, HEADER_H_MM
    from docs.utils import pdf_font

    reader = PdfReader(input_path)

    # Build a sample for language detection (first ~3 pages, up to 3000 chars)
    sample = ""
    for pg in reader.pages[:3]:
        sample += (pg.extract_text() or "") + "\n"
        if len(sample) >= 3000:
            break

    if not sample.strip():
        return False  # No selectable text → nothing to translate

    try:
        src_lang = detect(sample[:2000])
    except LangDetectException:
        return False

    if src_lang == target_lang_code:
        return False  # Already the correct language

    # Transparency: the attachment text is about to be sent to Google Translate.
    # Log a warning so the operator sees this in the Registro panel before any
    # outbound data leaves the machine.
    try:
        import logger as _logger
        _logger.warning(
            "log_translate_attachment",
            os.path.basename(input_path), src_lang, target_lang_code,
        )
    except Exception:
        pass

    translator  = GoogleTranslator(source=src_lang, target=target_lang_code)
    header_h_pt = HEADER_H_MM * _mm
    footer_h_pt = 18 * _mm
    font_name   = pdf_font(lang)   # HeiseiKakuGo-W5 for JA, ArialUA for UK, Helvetica otherwise
    font_size   = 9
    line_h      = 13  # leading

    first_page = reader.pages[0]
    W = float(first_page.mediabox.width)
    H = float(first_page.mediabox.height)

    class _Doc:
        pagesize  = (W, H)
        leftMargin  = 20 * _mm
        rightMargin = 20 * _mm

    left     = 20 * _mm
    right    = W - 20 * _mm
    text_w   = right - left
    top_y    = H - header_h_pt - 4 * _mm
    bottom_y = footer_h_pt + 4 * _mm

    buf = _io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(W, H))

    for page_idx, page in enumerate(reader.pages):
        raw = page.extract_text() or ""

        # Translate in 4 000-char chunks (Google free limit)
        translated_parts = []
        for j in range(0, len(raw), 4000):
            chunk = raw[j:j + 4000].strip()
            if chunk:
                try:
                    translated_parts.append(translator.translate(chunk) or chunk)
                except Exception:
                    translated_parts.append(chunk)
        translated = "\n".join(translated_parts) if translated_parts else ""

        # Company header
        draw_page_header(c, _Doc())

        # Translated text
        c.setFont(font_name, font_size)
        c.setFillColor(colors.black)
        y = top_y
        for paragraph in translated.split("\n"):
            words = paragraph.split()
            if not words:
                y -= line_h // 2
                continue
            line_buf = ""
            for word in words:
                test = (line_buf + " " + word).strip()
                if stringWidth(test, font_name, font_size) <= text_w:
                    line_buf = test
                else:
                    if line_buf and y > bottom_y:
                        c.drawString(left, y, line_buf)
                    y -= line_h
                    line_buf = word
            if line_buf and y > bottom_y:
                c.drawString(left, y, line_buf)
            y -= line_h + 2  # extra paragraph gap

        # Footer: page number + section label
        pg_num = start_page_num + page_idx
        c.setFont(font_name, 7)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawRightString(right, 12 * _mm, str(pg_num))
        if section_label:
            c.drawString(left, 12 * _mm, section_label)

        if page_idx < len(reader.pages) - 1:
            c.showPage()

    c.save()
    buf.seek(0)
    with open(output_path, "wb") as f:
        f.write(buf.read())
    return True


def _overlay_header_on_pdf(input_path, output_path, header_overlay_path):
    """Stamp the company header on every page of a PDF, scaling content to fit below it."""
    try:
        from pypdf import PdfReader, PdfWriter
        try:
            from pypdf import Transformation
        except ImportError:
            from pypdf.transformations import Transformation
        from docs.pdf_header import HEADER_H_MM
        from reportlab.lib.units import mm as _mm

        header_h_pt = HEADER_H_MM * _mm   # 17 mm → ~48 pt
        footer_h_pt = 18 * _mm            # matches white rect in _stamp_page_numbers_on_pdf

        reader = PdfReader(input_path)
        hdr_reader = PdfReader(header_overlay_path)
        hdr_page = hdr_reader.pages[0]
        writer = PdfWriter()
        for page in reader.pages:
            try:
                h = float(page.mediabox.height)
                avail_h = h - header_h_pt - footer_h_pt
                scale = avail_h / h if h > 0 else 1.0
                # ctm = (a, b, c, d, e, f): uniform scale + translate up by footer_h_pt
                page.add_transformation(
                    Transformation(ctm=(scale, 0, 0, scale, 0, footer_h_pt))
                )
            except Exception:
                pass
            try:
                page.merge_page(hdr_page)
            except Exception:
                pass
            writer.add_page(page)
        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception:
        shutil.copy2(input_path, output_path)
        return False


def _stamp_page_numbers_on_pdf(input_path, output_path, start_page_num, section_label=""):
    """Stamp sequential page numbers on a PDF; covers existing numbers with a white rect."""
    import io as _io
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.units import mm as _mm

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page_idx, page in enumerate(reader.pages):
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)

            buf = _io.BytesIO()
            c = pdf_canvas.Canvas(buf, pagesize=(w, h))
            # White rect covers bottom 18 mm to erase any pre-existing page numbers
            c.setFillColor(colors.white)
            c.rect(0, 0, w, 18 * _mm, fill=1, stroke=0)
            # Page number — same style as other sections (gray, 7 pt, right-aligned)
            pg_num = start_page_num + page_idx
            c.setFont("Helvetica", 7)
            c.setFillColor(colors.HexColor("#555555"))
            c.drawRightString(w - 20 * _mm, 12 * _mm, str(pg_num))
            if section_label:
                c.drawString(20 * _mm, 12 * _mm, section_label)
            c.save()
            buf.seek(0)

            overlay_reader = PdfReader(buf)
            page.merge_page(overlay_reader.pages[0])
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception:
        shutil.copy2(input_path, output_path)
        return False


def _add_outline_items(pdf_path, output_path, outline_items):
    """
    Add PDF outline (bookmark sidebar) items to a PDF for easy navigation.
    outline_items: list of (title, page_index_0based)
    """
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        writer.append(reader)
        for title, page_idx in outline_items:
            if 0 <= page_idx < len(reader.pages):
                try:
                    writer.add_outline_item(title, page_idx)
                except Exception:
                    pass
        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception:
        shutil.copy2(pdf_path, output_path)
        return False


def _inject_toc_page_links(merged_path, output_path, toc_start_page_idx, entries):
    """
    Post-merge: stamp /Link annotations on the TOC page(s) at exact Y coordinates.
    entries: [(toc_page0, y_in_pdf_pts, target_page_0based), ...]
      - toc_page0: 0-based page index WITHIN the TOC (0 for a single-page TOC)
    Each link is stamped on merged page (toc_start_page_idx + toc_page0), so a
    multi-page TOC links correctly. Y comes from _TrackingParagraph.drawOn.
    """
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import Link
        from pypdf.generic import RectangleObject

        reader = PdfReader(merged_path)
        writer = PdfWriter()
        writer.append(reader)

        n_pages = len(reader.pages)
        lm = 20 * 2.8346  # 20 mm → pt
        row_h = 26  # 6 topPadding + 14 leading + 6 bottomPadding

        for toc_page0, y, target_page in entries:
            abs_toc_idx = toc_start_page_idx + toc_page0
            if not (0 <= abs_toc_idx < n_pages):
                continue
            if not (0 <= target_page < n_pages):
                continue
            page_w = float(reader.pages[abs_toc_idx].mediabox.width)
            rm = page_w - lm
            rect = RectangleObject([lm, y - 6, rm, y + row_h - 6])
            writer.add_annotation(page_number=abs_toc_idx,
                                  annotation=Link(rect=rect, target_page_index=target_page))

        with open(output_path, 'wb') as f:
            writer.write(f)
        return True
    except Exception:
        shutil.copy2(merged_path, output_path)
        return False


def generate_completa(folder_path, output_path, attachments=None,
                      lang="IT", log_fn=None, progress_fn=None):
    """
    Generate the complete documentation PDF.
    Merges: Targhetta, Panel, JOBs, Parametri, UF#()/Tools, Allegati, Logo page.
    Returns True on success.
    """
    from translations import TRANSLATIONS
    t = TRANSLATIONS.get(lang, TRANSLATIONS["IT"])

    if attachments is None:
        attachments = []

    def _log(key, *args):
        """Forward a log message to the caller's log callback, ignoring any error."""
        if log_fn:
            try:
                log_fn(key, *args)
            except Exception:
                pass

    def _progress(value):
        """Report an integer progress value (0-100) to the optional progress callback."""
        if progress_fn:
            try:
                progress_fn(int(value))
            except Exception:
                pass

    folder_name = os.path.basename(os.path.normpath(folder_path))

    with tempfile.TemporaryDirectory() as tmp_dir:

        tmp_targ         = os.path.join(tmp_dir, "targhetta.pdf")
        tmp_panel        = os.path.join(tmp_dir, "panel.pdf")
        tmp_usrgrp       = os.path.join(tmp_dir, "usrgrp.pdf")
        tmp_jobs         = os.path.join(tmp_dir, "jobs.pdf")
        tmp_params       = os.path.join(tmp_dir, "params.pdf")
        tmp_uf           = os.path.join(tmp_dir, "uf_tools.pdf")
        tmp_fc           = os.path.join(tmp_dir, "flowchart.pdf")
        tmp_cube         = os.path.join(tmp_dir, "cubeintf.pdf")
        tmp_formcut      = os.path.join(tmp_dir, "formcut.pdf")
        tmp_toc          = os.path.join(tmp_dir, "toc.pdf")
        tmp_logo         = os.path.join(tmp_dir, "logo.pdf")
        tmp_merged       = os.path.join(tmp_dir, "merged.pdf")
        tmp_dest         = os.path.join(tmp_dir, "with_dests.pdf")
        tmp_hdr_overlay  = os.path.join(tmp_dir, "header_overlay.pdf")

        _progress(0)

        # ── Pass 1: generate each section to count pages ──────────────────────

        def _try_gen(label, fn):
            """Run a section generator, logging and swallowing any failure; return True on success."""
            try:
                fn()
                return True
            except Exception as e:
                _log("log_error_generic", f"{label}: {e}")
                return False

        has_targ = _try_gen("Targhetta", lambda: __import__(
            "docs.targhetta", fromlist=["generate_pdf"]
        ).generate_pdf(folder_path, tmp_targ, lang=lang))
        _progress(10)

        has_panel = _try_gen("Panel", lambda: __import__(
            "docs.panel", fromlist=["generate_pdf"]
        ).generate_pdf(folder_path, tmp_panel, lang=lang))
        _progress(18)

        # JOBs: generate WITHOUT the internal SOMMARIO page (include_toc=False).
        # The individual JOB entries are exploded directly into the main Completa
        # TOC instead, giving a single unified summary with correct hyperlinks.
        _jobs_nav: list = []   # list of (name, page_within_jobs_pdf 1-based)

        def _jobs_gen(poff: int = 0):
            """Generate the JOBs section (without its own TOC) and capture its per-job navigation list."""
            nav = __import__(
                "docs.jobs", fromlist=["generate_pdf"]
            ).generate_pdf(folder_path, tmp_jobs, log_fn=log_fn, lang=lang,
                           page_offset=poff, include_toc=False)
            _jobs_nav.clear()
            if nav:
                _jobs_nav.extend(nav)

        has_jobs = _try_gen("JOBs", _jobs_gen)
        _progress(28)

        has_params = _try_gen("Parametri", lambda: __import__(
            "docs.params", fromlist=["generate_pdf"]
        ).generate_pdf(folder_path, tmp_params, log_fn=log_fn, lang=lang))
        _progress(36)

        has_uf = _try_gen("UF/Tools", lambda: __import__(
            "docs.uf_tools", fromlist=["generate_pdf"]
        ).generate_pdf(folder_path, tmp_uf, lang=lang, log_fn=log_fn))
        _progress(43)

        def _gen_usrgrp():
            """Generate the user-group section into a temp PDF."""
            from docs.usrgrp import parse_gpin, parse_gpot, generate_pdf as _gug
            _gug(parse_gpin(folder_path), parse_gpot(folder_path),
                 tmp_usrgrp, lang=lang)

        has_usrgrp = _try_gen("UserGroup", _gen_usrgrp)
        _progress(50)

        # ── Flowchart section (pass 1) ─────────────────────────────────────────
        # Build JBI flowcharts once; reuse the result for both passes.
        _fcs_store: list = []

        def _fc_gen(poff: int = 0):
            """Build the JBI flowcharts (once) and render the flowchart section into a temp PDF."""
            from docs.flowchart import build_flowcharts, generate_pdf as _fc_pdf
            if not _fcs_store:
                _fcs_store.extend(build_flowcharts(folder_path))
            if not _fcs_store:
                raise ValueError(t.get('flowchart_no_jbi', 'Nessun file JBI trovato'))
            # include_toc=False: avoids a duplicate summary — flowchart entries
            # are added directly into the main Completa TOC instead.
            _fc_pdf(
                _fcs_store, tmp_fc, lang=lang,
                title=t.get('menu_flowchart', 'Flowchart'),
                toc_title=t.get('flowchart_toc_title', 'Sommario'),
                page_offset=poff,
                include_toc=False,
            )
            _log('log_completa_fc_added', len(_fcs_store))

        has_fc = _try_gen("Flowchart", _fc_gen)
        _progress(57)

        # ── Interference cubes section (pass 1) ────────────────────────────────
        # Included only when CUBEINTF.CND defines at least one active cube.
        _cube_store: list = []

        if not _cube_store:
            try:
                from docs.cubeintf import build_cubes as _bc
                _cube_store.extend(_bc(folder_path) or [])
            except Exception as _e:
                _log("log_error_generic", f"CubeIntf parse: {_e}")

        def _cube_gen(poff: int = 0):
            """Generate the interference-cubes section into a temp PDF."""
            from docs.cubeintf import generate_pdf as _ci_pdf
            _ci_pdf(folder_path, tmp_cube, lang=lang, page_offset=poff, log_fn=log_fn)

        has_cube = bool(_cube_store) and _try_gen("CubeIntf", lambda: _cube_gen(0))
        _progress(60)

        # ── Form Cutting section (pass 1) ──────────────────────────────────────
        # Included only when FORMCUT.CND defines at least one active Form Cut.
        _formcut_store: list = []

        if not _formcut_store:
            try:
                from docs.formcut import build_formcuts as _bfc
                _formcut_store.extend(_bfc(folder_path) or [])
            except Exception as _e:
                _log("log_error_generic", f"FormCut parse: {_e}")

        def _formcut_gen(poff: int = 0):
            """Generate the form-cutting section into a temp PDF."""
            from docs.formcut import generate_pdf as _fc_pdf2
            _fc_pdf2(folder_path, tmp_formcut, lang=lang, page_offset=poff, log_fn=log_fn)

        has_formcut = bool(_formcut_store) and _try_gen("FormCut", lambda: _formcut_gen(0))
        _progress(62)

        # ── Count pages ───────────────────────────────────────────────────────

        n_targ   = _count_pages(tmp_targ)   if has_targ   else 0
        n_panel  = _count_pages(tmp_panel)  if has_panel  else 0
        n_usrgrp = _count_pages(tmp_usrgrp) if has_usrgrp else 0
        n_jobs   = _count_pages(tmp_jobs)   if has_jobs   else 0
        n_params = _count_pages(tmp_params) if has_params else 0
        n_uf     = _count_pages(tmp_uf)     if has_uf     else 0
        n_fc     = _count_pages(tmp_fc)     if has_fc     else 0
        n_cube   = _count_pages(tmp_cube)   if has_cube   else 0
        n_formcut = _count_pages(tmp_formcut) if has_formcut else 0

        # Content page offsets (panel starts at content page 1):
        panel_off   = 0
        usrgrp_off  = panel_off   + n_panel
        jobs_off    = usrgrp_off  + n_usrgrp
        params_off  = jobs_off    + n_jobs
        uf_off      = params_off  + n_params
        fc_off      = uf_off      + n_uf          # ← flowchart comes after UF/Tools
        cube_off    = fc_off      + n_fc          # ← interference cubes after flowchart
        formcut_off = cube_off    + n_cube        # ← form cuts after the cubes
        att_off     = formcut_off + n_formcut     # ← attachments last

        # ── Pass 2: regenerate sections with correct page offsets ─────────────

        if has_panel and n_panel > 0 and panel_off > 0:
            _try_gen("Panel offset", lambda: __import__(
                "docs.panel", fromlist=["generate_pdf"]
            ).generate_pdf(folder_path, tmp_panel, lang=lang, page_offset=panel_off))

        if has_jobs and n_jobs > 0 and jobs_off > 0:
            _try_gen("JOBs offset", lambda: _jobs_gen(jobs_off))

        if has_params and n_params > 0 and params_off > 0:
            _try_gen("Parametri offset", lambda: __import__(
                "docs.params", fromlist=["generate_pdf"]
            ).generate_pdf(folder_path, tmp_params, log_fn=log_fn, lang=lang,
                           page_offset=params_off))

        if has_uf and n_uf > 0 and uf_off > 0:
            _try_gen("UF/Tools offset", lambda: __import__(
                "docs.uf_tools", fromlist=["generate_pdf"]
            ).generate_pdf(folder_path, tmp_uf, lang=lang, log_fn=log_fn,
                           page_offset=uf_off))

        if has_usrgrp and n_usrgrp > 0 and usrgrp_off > 0:
            def _regen_usrgrp():
                """Regenerate the user-group section with the correct page offset."""
                from docs.usrgrp import parse_gpin, parse_gpot, generate_pdf as _gug
                _gug(parse_gpin(folder_path), parse_gpot(folder_path),
                     tmp_usrgrp, lang=lang, page_offset=usrgrp_off)
            _try_gen("UserGroup offset", _regen_usrgrp)

        # Flowchart pass 2: apply correct page offset now that fc_off is known.
        if has_fc and n_fc > 0 and fc_off > 0:
            _try_gen("Flowchart offset", lambda: _fc_gen(fc_off))

        # Interference cubes pass 2: apply correct page offset.
        if has_cube and n_cube > 0 and cube_off > 0:
            _try_gen("CubeIntf offset", lambda: _cube_gen(cube_off))

        # Form cuts pass 2: apply correct page offset.
        if has_formcut and n_formcut > 0 and formcut_off > 0:
            _try_gen("FormCut offset", lambda: _formcut_gen(formcut_off))

        _progress(65)

        # ── Per-attachment page counts ────────────────────────────────────────

        att_page_counts = [
            _count_pages(a) if os.path.isfile(a) else 0
            for a in attachments
        ]

        # ── Build TOC section list ────────────────────────────────────────────

        toc_sections = []
        if n_panel > 0:
            toc_sections.append(("completa_panel",
                                  t.get("completa_section_panel",  "Panel"),
                                  panel_off + 1))
        if n_usrgrp > 0:
            toc_sections.append(("completa_usrgrp",
                                  t.get("completa_section_usrgrp", "User Group"),
                                  usrgrp_off + 1))
        if n_jobs > 0:
            if _jobs_nav:
                # Explode the JOBs section into one TOC entry per JOB (plus the
                # call-tree and ladder headings) — replaces both the old single
                # "JOBs" row and the now-suppressed internal SOMMARIO page.
                for _ji, (_jname, _jrel) in enumerate(_jobs_nav):
                    toc_sections.append((
                        f"completa_job_{_ji}",
                        _jname,
                        jobs_off + _jrel,
                    ))
            else:
                # Fallback: navigation list unavailable → keep a single entry.
                toc_sections.append(("completa_jobs",
                                      t.get("completa_section_jobs",   "JOBs"),
                                      jobs_off + 1))
        if n_params > 0:
            toc_sections.append(("completa_params",
                                  t.get("completa_section_params", "Parametri"),
                                  params_off + 1))
        if n_uf > 0:
            toc_sections.append(("completa_tools",
                                  t.get("completa_section_tools",  "UF#() / Tools"),
                                  uf_off + 1))
        if n_fc > 0 and _fcs_store:
            # One TOC entry per JBI flowchart — replaces the old single
            # "Flowchart" entry and the now-suppressed internal TOC.
            for _i, _fc_item in enumerate(_fcs_store):
                toc_sections.append((
                    f"completa_fc_{_i}",
                    _fc_item.name,
                    fc_off + _i + 1,
                ))
        if n_cube > 0:
            # Interference cubes: single linkable entry, after the flowcharts.
            toc_sections.append(("completa_cubeintf",
                                  t.get("completa_section_cubeintf", "Cubo interferenza"),
                                  cube_off + 1))
        if n_formcut > 0:
            # Form cuts: single linkable entry — the last main section before
            # any attachments.
            toc_sections.append(("completa_formcut",
                                  t.get("completa_section_formcut", "FormCut"),
                                  formcut_off + 1))
        if attachments:
            cur_att_off = att_off
            for i, att in enumerate(attachments):
                n_att_i = att_page_counts[i]
                if n_att_i > 0:
                    att_name = os.path.splitext(os.path.basename(att))[0]
                    toc_sections.append((
                        f"completa_allegato_{i}",
                        f"{t.get('completa_allegato_prefix', 'Allegato')} - {att_name}",
                        cur_att_off + 1,
                    ))
                    cur_att_off += n_att_i

        # ── Generate TOC and logo pages ───────────────────────────────────────

        toc_link_registry = {}  # key → (toc_page0, y_in_pdf_pts) (set by _TrackingParagraph)
        has_toc = _try_gen("TOC", lambda: _generate_toc_pdf(
            tmp_toc, toc_sections, folder_name, lang, t, toc_link_registry))

        # The TOC may span multiple pages (e.g. many JOBs/flowcharts) — count the
        # real number of pages so all downstream offsets stay correct.
        n_toc = _count_pages(tmp_toc) if (has_toc and os.path.isfile(tmp_toc)) else 0

        has_logo = _try_gen("Logo", lambda: _generate_logo_page(tmp_logo))
        _progress(72)

        # ── Generate header overlay for attachments ───────────────────────────

        has_hdr_overlay = (len(attachments) > 0 and
                           _try_gen("Header overlay", lambda: _generate_header_overlay(tmp_hdr_overlay)))

        # ── Merge all sections ────────────────────────────────────────────────

        merge_list = []
        if has_targ  and os.path.isfile(tmp_targ):   merge_list.append(tmp_targ)
        if has_toc   and os.path.isfile(tmp_toc):    merge_list.append(tmp_toc)
        if has_panel  and os.path.isfile(tmp_panel):   merge_list.append(tmp_panel)
        if has_usrgrp and os.path.isfile(tmp_usrgrp): merge_list.append(tmp_usrgrp)
        if has_jobs   and os.path.isfile(tmp_jobs):   merge_list.append(tmp_jobs)
        if has_params and os.path.isfile(tmp_params): merge_list.append(tmp_params)
        if has_uf    and os.path.isfile(tmp_uf):     merge_list.append(tmp_uf)
        if has_fc    and os.path.isfile(tmp_fc):     merge_list.append(tmp_fc)
        if has_cube  and os.path.isfile(tmp_cube):   merge_list.append(tmp_cube)
        if has_formcut and os.path.isfile(tmp_formcut): merge_list.append(tmp_formcut)
        # First attachment page number — content-relative, exactly like every
        # other section (Panel = 1). att_off already counts all content pages
        # before the attachments (panel..flowchart), so the printed number here
        # matches what the TOC shows for the attachment (att_off + 1).
        att_abs_start = att_off + 1
        cur_att_pg = att_abs_start
        target_lang_code = _LANG_CODE_MAP.get(lang, "it")

        for i, att in enumerate(attachments):
            if os.path.isfile(att):
                att_lbl = f"{t.get('completa_allegato_prefix', 'Allegato')} - {os.path.splitext(os.path.basename(att))[0]}"
                att_final = None

                # Try automatic translation (requires internet + deep-translator)
                att_trans = os.path.join(tmp_dir, f"att_{i}_trans.pdf")
                try:
                    translated = _create_translated_attachment_pdf(
                        att, att_trans, cur_att_pg, att_lbl, target_lang_code, lang)
                    if translated and os.path.isfile(att_trans):
                        att_final = att_trans
                except Exception:
                    pass  # Fall back to normal pipeline

                if att_final is None:
                    # No translation needed or failed — normal header + page-number pipeline
                    att_in = att
                    if has_hdr_overlay and os.path.isfile(tmp_hdr_overlay):
                        att_hdr = os.path.join(tmp_dir, f"att_{i}_hdr.pdf")
                        _try_gen(f"Att overlay {i}",
                                 lambda a=att_in, o=att_hdr:
                                 _overlay_header_on_pdf(a, o, tmp_hdr_overlay))
                        if os.path.isfile(att_hdr):
                            att_in = att_hdr
                    att_pg = os.path.join(tmp_dir, f"att_{i}.pdf")
                    _try_gen(f"Att pages {i}",
                             lambda a=att_in, o=att_pg, pg=cur_att_pg, lbl=att_lbl:
                             _stamp_page_numbers_on_pdf(a, o, pg, lbl))
                    att_final = att_pg if os.path.isfile(att_pg) else att_in

                merge_list.append(att_final)
            cur_att_pg += att_page_counts[i]
        if has_logo  and os.path.isfile(tmp_logo):   merge_list.append(tmp_logo)

        _try_gen("Merge", lambda: _merge_pdfs(merge_list, tmp_merged))
        _progress(88)

        # ── Compute absolute page positions for outline ───────────────────────

        p_panel  = n_targ + n_toc
        p_usrgrp = p_panel  + n_panel
        p_jobs   = p_usrgrp + n_usrgrp
        p_params = p_jobs   + n_jobs
        p_uf     = p_params + n_params
        p_fc      = p_uf     + n_uf
        p_cube    = p_fc     + n_fc
        p_formcut = p_cube   + n_cube
        p_att     = p_formcut + n_formcut

        # ── Add PDF outline (bookmark sidebar) for navigation ─────────────────

        src = tmp_merged

        outline = []
        if n_targ > 0:
            outline.append((t.get("completa_section_targhetta", "Targhetta"), 0))
        if n_toc > 0:
            outline.append((t.get("completa_toc_title", "INDICE"), n_targ))
        if n_panel > 0:
            outline.append((t.get("completa_section_panel",  "Panel"),         p_panel))
        if n_usrgrp > 0:
            outline.append((t.get("completa_section_usrgrp", "User Group"),    p_usrgrp))
        if n_jobs > 0:
            outline.append((t.get("completa_section_jobs",   "JOBs"),          p_jobs))
            if _jobs_nav:
                # One indented bookmark per JOB under the "JOBs" group header.
                for _jname, _jrel in _jobs_nav:
                    _jidx = p_jobs + (_jrel - 1)
                    if 0 <= _jidx:
                        outline.append((f"  {_jname}", _jidx))
        if n_params > 0:
            outline.append((t.get("completa_section_params", "Parametri"),     p_params))
        if n_uf > 0:
            outline.append((t.get("completa_section_tools",  "UF#() / Tools"), p_uf))
        if n_fc > 0 and _fcs_store:
            # Group header + one entry per JBI flowchart
            outline.append((t.get("completa_section_flowchart", "Flowchart"), p_fc))
            for _i, _fc_item in enumerate(_fcs_store):
                outline.append((f"  {_fc_item.name}", p_fc + _i))
        if n_cube > 0:
            outline.append((t.get("completa_section_cubeintf", "Cubo interferenza"), p_cube))
        if n_formcut > 0:
            outline.append((t.get("completa_section_formcut", "FormCut"), p_formcut))
        if attachments:
            cur_p_att = p_att
            for i, att in enumerate(attachments):
                n_att_i = att_page_counts[i]
                if n_att_i > 0:
                    att_name = os.path.splitext(os.path.basename(att))[0]
                    outline.append((f"{t.get('completa_allegato_prefix', 'Allegato')} - {att_name}", cur_p_att))
                    cur_p_att += n_att_i

        tmp_out = os.path.join(tmp_dir, "output.pdf")
        _try_gen("Outline", lambda: _add_outline_items(src, tmp_out, outline))
        after_outline = tmp_out if os.path.isfile(tmp_out) else src

        # ── Inject clickable links into the TOC page ──────────────────────────

        if has_toc and toc_link_registry:
            p_abs = {}
            if n_panel  > 0: p_abs["completa_panel"]     = p_panel
            if n_usrgrp > 0: p_abs["completa_usrgrp"]    = p_usrgrp
            if n_jobs > 0:
                if _jobs_nav:
                    for _ji, (_jname, _jrel) in enumerate(_jobs_nav):
                        p_abs[f"completa_job_{_ji}"] = p_jobs + (_jrel - 1)
                else:
                    p_abs["completa_jobs"] = p_jobs
            if n_params > 0: p_abs["completa_params"]     = p_params
            if n_uf     > 0: p_abs["completa_tools"]      = p_uf
            if n_fc > 0 and _fcs_store:
                for _i in range(len(_fcs_store)):
                    p_abs[f"completa_fc_{_i}"] = p_fc + _i
            if n_cube > 0: p_abs["completa_cubeintf"] = p_cube
            if n_formcut > 0: p_abs["completa_formcut"] = p_formcut
            _cur = p_att
            for _i, _att in enumerate(attachments):
                _ni = att_page_counts[_i]
                if _ni > 0:
                    p_abs[f"completa_allegato_{_i}"] = _cur
                    _cur += _ni

            # entries: (toc_page0, y, target_page_0based) — supports multi-page TOC
            link_entries = []
            for key in toc_link_registry:
                if key in p_abs:
                    val = toc_link_registry[key]
                    try:
                        toc_page0, y = val
                    except (TypeError, ValueError):
                        toc_page0, y = 0, val   # backward-compat: y-only
                    link_entries.append((toc_page0, y, p_abs[key]))

            if link_entries:
                tmp_linked = os.path.join(tmp_dir, "linked.pdf")
                _try_gen("TOC links",
                         lambda: _inject_toc_page_links(
                             after_outline, tmp_linked, n_targ, link_entries))
                final_src = tmp_linked if os.path.isfile(tmp_linked) else after_outline
            else:
                final_src = after_outline
        else:
            final_src = after_outline

        _progress(95)
        shutil.copy2(final_src, output_path)
        _progress(100)

    return True
