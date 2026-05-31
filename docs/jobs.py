import os
import re
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                Paragraph, Spacer, PageBreak,
                                HRFlowable, Table, TableStyle, Image)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.flowables import Flowable
from docs.pdf_header import draw_page_header as _draw_header

MAIN_JBI   = "MAIN.JBI"
CIOPRG_LST = "CIOPRG.LST"

# Regex used by _sort_files (MAIN.JBI direct calls only)
_RE_CALL = re.compile(r'CALL\s+JOB:([A-Za-z0-9_]+)')

# Regex used by the tree builder (CALL + PSTART, all files)
_RE_CALLS_PARSE = re.compile(r'\b(CALL|PSTART)\s+JOB:([A-Za-z0-9_]+)', re.IGNORECASE)

_MAX_TREE_DEPTH = 25
_state = {"job": "SOMMARIO"}

# ── JBI (Inform) syntax colours ───────────────────────────────────────────────
_C_COMMENT = "#008800"
_C_MOTION  = "#0044bb"
_C_CALL    = "#cc0000"
_C_LABEL   = "#cc6600"
_C_WAIT    = "#007788"
_C_SET     = "#886600"
_C_IO      = "#990077"
_C_PULSE   = "#6633aa"
_C_DEFAULT = "#111111"
_C_LINENUM = "#aaaaaa"

# ── CIOP / Ladder syntax colours ──────────────────────────────────────────────
_LC_STR    = "#0044bb"
_LC_OUT    = "#cc0000"
_LC_PLS    = "#6633aa"
_LC_TMR    = "#cc6600"
_LC_AND    = "#007788"
_LC_OR     = "#228833"
_LC_CNT    = "#886600"
_LC_DIFU   = "#990077"
_LC_HEADER = "#888888"

_RE_MOTION = re.compile(
    r'^(MOVJ|MOVC|MOVL|MOVS|MOVCX|MOVCR|MOVCY)\b', re.IGNORECASE
)
_RE_LABEL_TOK = re.compile(r'\*L\d+')


# ── Per-line colour selectors ─────────────────────────────────────────────────

def _line_color(stripped):
    if not stripped:
        return _C_DEFAULT
    if stripped.startswith("'"):
        return _C_COMMENT
    u = stripped.upper()
    if u.startswith("SETALARM"):
        return _C_CALL
    if _RE_MOTION.match(stripped):
        return _C_MOTION
    if u.startswith("CALL"):
        return _C_CALL
    if u.startswith("WAIT"):
        return _C_WAIT
    if u.startswith("PULSE"):
        return _C_PULSE
    if u.startswith("SET"):
        return _C_SET
    if u.startswith("DOUT") or u.startswith("DIN"):
        return _C_IO
    if _RE_LABEL_TOK.search(stripped):
        return _C_LABEL
    return _C_DEFAULT


def _line_color_ladder(stripped):
    if not stripped:
        return _C_DEFAULT
    u = stripped.upper()
    if u.startswith("/") or u.startswith("PART"):
        return _LC_HEADER
    if u.startswith("STR"):
        return _LC_STR
    if u.startswith("OUT"):
        return _LC_OUT
    if u.startswith("PLS"):
        return _LC_PLS
    if u.startswith("TMR"):
        return _LC_TMR
    if u.startswith("AND"):
        return _LC_AND
    if u.startswith("OR"):
        return _LC_OR
    if u.startswith("CNT"):
        return _LC_CNT
    if u.startswith("DIFU") or u.startswith("DIFD"):
        return _LC_DIFU
    return _C_DEFAULT


def _xml_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tabs_to_spaces(text, tab_size=4):
    return text.expandtabs(tab_size)


def _make_line_para(raw_line, linenum, max_digits, style, color_fn=_line_color):
    text = _tabs_to_spaces(raw_line.rstrip("\n\r"))
    lstripped = text.lstrip(" ")
    n_indent = len(text) - len(lstripped)
    color = color_fn(lstripped)
    num_str = str(linenum).rjust(max_digits)
    escaped = _xml_escape(lstripped)
    nbsp_indent = "&nbsp;" * n_indent
    if lstripped:
        markup = (
            f'<font color="{_C_LINENUM}">{_xml_escape(num_str)}  </font>'
            f'<font color="{color}">{nbsp_indent}{escaped}</font>'
        )
    else:
        markup = f'<font color="{_C_LINENUM}">{_xml_escape(num_str)}</font>&nbsp;'
    return Paragraph(markup, style)


# ── Call tree builder ─────────────────────────────────────────────────────────

def _parse_all_calls(filepath):
    """Return ordered list of (call_type_upper, job_name_upper) from a JBI file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return []
    seen, result = set(), []
    for m in _RE_CALLS_PARSE.finditer(content):
        ct   = m.group(1).upper()
        name = m.group(2).upper()
        if (ct, name) not in seen:
            seen.add((ct, name))
            result.append((ct, name))
    return result


def _build_node(job_name, name_map, folder, ancestors, depth):
    """Recursively build one call-tree node. Detects cycles via ancestors set."""
    node = {
        "name":      job_name,
        "call_type": "CALL",
        "children":  [],
        "missing":   job_name not in name_map,
        "recursive": job_name in ancestors,
        "too_deep":  False,
    }
    if node["missing"] or node["recursive"]:
        return node
    if depth >= _MAX_TREE_DEPTH:
        node["too_deep"] = True
        return node

    fpath = os.path.join(folder, name_map[job_name])
    new_ancestors = ancestors | {job_name}
    for call_type, child_name in _parse_all_calls(fpath):
        child = _build_node(child_name, name_map, folder, new_ancestors, depth + 1)
        child["call_type"] = call_type
        node["children"].append(child)
    return node


def _build_call_tree(folder, name_map):
    """
    Build the full call tree.
    Root priority: PNS001 → MAIN → first file alphabetically.
    """
    root_name = None
    for candidate in ("PNS001", "MAIN"):
        if candidate in name_map:
            root_name = candidate
            break
    if root_name is None and name_map:
        root_name = sorted(name_map)[0]
    if root_name is None:
        return None
    root = _build_node(root_name, name_map, folder, set(), 0)
    root["call_type"] = "ROOT"
    return root


def _collect_reachable(node, seen=None):
    """Return set of all job names reachable in the tree (handles cycles)."""
    if seen is None:
        seen = set()
    name = node["name"]
    if name in seen:
        return seen
    seen.add(name)
    for child in node.get("children", []):
        _collect_reachable(child, seen)
    return seen


def _tree_lines(node, prefix="", is_last=True, is_root=True):
    """
    Yield (prefix_str, connector_str, name, call_type, flags_dict) for each
    node in the tree, depth-first, using ASCII tree connectors.
    """
    flags = {
        "missing":   node.get("missing",   False),
        "recursive": node.get("recursive", False),
        "too_deep":  node.get("too_deep",  False),
    }
    if is_root:
        yield ("", "", node["name"], "ROOT", flags)
    else:
        connector = "\\-- " if is_last else "+-- "
        yield (prefix, connector, node["name"], node.get("call_type", "CALL"), flags)

    if not any(flags.values()):
        child_prefix = prefix + ("    " if is_last else "|   ")
        children = node["children"]
        for i, child in enumerate(children):
            yield from _tree_lines(child, child_prefix, i == len(children) - 1,
                                   is_root=False)


def _render_tree_to_story(tree_root, story, s_code, s_miss, tr=None):
    """Append tree-line Paragraphs to story."""
    if tr is None:
        tr = {}
    if tree_root is None:
        story.append(Paragraph(tr.get("jobs_no_jbi", "[Nessun file JBI trovato]"), s_miss))
        return

    for prefix, connector, name, call_type, flags in _tree_lines(tree_root):
        if flags.get("missing"):
            name_color = "#cc0000"
        elif flags.get("recursive"):
            name_color = "#cc6600"
        elif flags.get("too_deep"):
            name_color = "#888888"
        else:
            name_color = "#0044bb"

        parts = []
        if flags.get("missing"):
            parts.append(tr.get("jobs_missing", "[non trovato]"))
        elif flags.get("recursive"):
            parts.append(tr.get("jobs_recursive", "[→ ricorsivo]"))
        elif flags.get("too_deep"):
            parts.append("[...]")
        if call_type == "PSTART":
            parts.append("(PSTART)")
        annotation = "  " + "  ".join(parts) if parts else ""

        esc_pre  = _xml_escape(prefix).replace(" ", "&nbsp;")
        esc_con  = _xml_escape(connector).replace(" ", "&nbsp;")
        esc_name = _xml_escape(name)
        esc_ann  = _xml_escape(annotation)

        can_link = not flags.get("missing") and not flags.get("recursive") and not flags.get("too_deep")
        if can_link:
            name_part = f'<link href="#job_{name}"><font color="{name_color}"><b>{esc_name}</b></font></link>'
        else:
            name_part = f'<font color="{name_color}"><b>{esc_name}</b></font>'

        markup = (
            f'<font color="#888888">{esc_pre}{esc_con}</font>'
            f'{name_part}'
            f'<font color="#888888">{esc_ann}</font>'
        )
        story.append(Paragraph(markup, s_code))


# ── Dynamic footer tracker ────────────────────────────────────────────────────

class _SetJob(Flowable):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.width = 0
        self.height = 0

    def draw(self):
        _state["job"] = self.name


# ── Bookmarkable heading ──────────────────────────────────────────────────────

class _Heading(Paragraph):
    def __init__(self, text, key, style, heading_text=None):
        super().__init__(text, style)
        self.key = key
        self.heading_text = heading_text if heading_text is not None else text

    def drawOn(self, canvas, x, y, _sW=0):
        canvas.bookmarkPage(self.key)
        super().drawOn(canvas, x, y, _sW)


# ── Custom doc template (onPageEnd for footer — fires AFTER flowables drawn) ─

class _JobsDocTemplate(BaseDocTemplate):
    def __init__(self, output_path, footer_fn, **kw):
        super().__init__(output_path, **kw)
        W, H = A4
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            W - self.leftMargin - self.rightMargin,
            H - self.topMargin - self.bottomMargin,
            id="normal", leftPadding=0, rightPadding=0,
            topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates([
            PageTemplate(id="main", frames=[frame],
                         onPage=_draw_header, onPageEnd=footer_fn)
        ])

    def beforeDocument(self):
        # Fires at the start of every multiBuild pass — reset the per-pass
        # heading registry so the final list reflects only the last pass.
        self._toc_entries = []

    def afterFlowable(self, flowable):
        if isinstance(flowable, _Heading):
            self.notify("TOCEntry", (0, flowable.heading_text, self.page, flowable.key))
            # Collect headings independently of the TableOfContents flowable so
            # navigation entries are available even when the internal SOMMARIO
            # page is suppressed (include_toc=False, used by Completa).
            try:
                self._toc_entries.append((flowable.heading_text, self.page, flowable.key))
            except AttributeError:
                self._toc_entries = [(flowable.heading_text, self.page, flowable.key)]
            # bookmarkPage is called in _Heading.drawOn for correct top-of-heading placement


# ── Helpers ───────────────────────────────────────────────────────────────────

def _logo_path():
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "logo-home.bmp")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "logo-home.bmp")


def _parse_call_order(folder):
    """Direct CALL order from MAIN.JBI only (used for file sort order)."""
    main_path = os.path.join(folder, MAIN_JBI)
    if not os.path.isfile(main_path):
        return []
    with open(main_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    seen, order = set(), []
    for m in _RE_CALL.finditer(content):
        name = m.group(1).upper()
        if name not in seen:
            seen.add(name)
            order.append(name)
    return order


def _sort_files(folder, name_map, lbl_always_called="sempre richiamato", lbl_not_called="non richiamato"):
    """
    Returns list of (base_name_upper, filepath, status_or_None).
    Order: MAIN → direct CALL order from MAIN.JBI → remaining (alphabetical).
    Status is provisional; generate_pdf will correct it based on tree reachability.
    """
    call_order = _parse_call_order(folder)
    result, placed = [], set()

    if "MAIN" in name_map:
        result.append(("MAIN", os.path.join(folder, name_map["MAIN"]), None))
        placed.add("MAIN")

    for name in call_order:
        if name in placed or name not in name_map:
            continue
        result.append((name, os.path.join(folder, name_map[name]), None))
        placed.add(name)

    for name in sorted(n for n in name_map if n not in placed):
        status = lbl_always_called if name.startswith("SYS") else lbl_not_called
        result.append((name, os.path.join(folder, name_map[name]), status))

    return result


def _make_footer(page_offset=0):
    GRAY = colors.HexColor("#aaaaaa")

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GRAY)
        W = doc.pagesize[0]
        canvas.drawCentredString(W / 2.0, 10 * mm, str(doc.page + page_offset))
        canvas.drawRightString(W - 20 * mm, 10 * mm, _state["job"])
        canvas.restoreState()

    return _footer


# ── PDF generation ────────────────────────────────────────────────────────────

def generate_pdf(folder_path, output_path, log_fn=None, lang="IT", page_offset=0,
                 include_toc=True):
    from translations import TRANSLATIONS
    from docs.utils import pdf_font
    tr = TRANSLATIONS.get(lang, TRANSLATIONS["IT"])

    BLUE  = colors.HexColor("#D97757")
    CGRID = colors.HexColor("#cccccc")
    WHITE = colors.white
    GRAY  = colors.HexColor("#888888")

    W = A4[0] - 40 * mm
    folder_name = os.path.basename(os.path.normpath(folder_path))
    f_reg  = pdf_font(lang, bold=False)
    f_bold = pdf_font(lang, bold=True)

    def ps(name, font=None, size=9, color=colors.black, align=TA_LEFT, **kw):
        fn = font if font is not None else f_reg
        return ParagraphStyle(name, fontName=fn, fontSize=size, textColor=color,
                              alignment=align, leading=size * 1.4, **kw)

    s_head = ps("hd", f_bold, 15, colors.black, TA_CENTER)
    s_sec  = ps("sc", f_bold,  9, BLUE,  spaceBefore=4, spaceAfter=2)
    s_job  = ps("jb", f_bold, 10, BLUE,  spaceBefore=4, spaceAfter=1)
    s_miss = ps("ms", f_reg,   8, GRAY)
    s_code = ParagraphStyle("cd", fontName="Courier", fontSize=7,
                            leading=8.5, spaceBefore=0, spaceAfter=0,
                            leftIndent=0, rightIndent=0)

    # ── Build name map ────────────────────────────────────────────────────────
    try:
        all_jbi = [f for f in os.listdir(folder_path) if f.upper().endswith(".JBI")]
    except OSError:
        all_jbi = []
    name_map = {os.path.splitext(f)[0].upper(): f for f in all_jbi}

    # ── Build call tree and collect reachable jobs ────────────────────────────
    try:
        tree_root = _build_call_tree(folder_path, name_map)
        reachable = _collect_reachable(tree_root) if tree_root else set()
    except Exception:
        tree_root = None
        reachable = set()

    lbl_always_called = tr.get("jobs_always_called", "sempre richiamato")
    lbl_not_called    = tr.get("jobs_not_called",    "non richiamato")

    # ── Sort files for display order ──────────────────────────────────────────
    entries = _sort_files(folder_path, name_map, lbl_always_called, lbl_not_called)

    # Correct "not called" for jobs that ARE reachable through the tree
    entries = [
        (n, p, None if (s == lbl_not_called and n in reachable) else s)
        for n, p, s in entries
    ]

    def make_header():
        hdr = Table(
            [[Paragraph(f"JOBs<br/><font size='10'>{_xml_escape(folder_name)}</font>", s_head)]],
            colWidths=[W],
        )
        hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BLUE),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ]))
        return hdr

    # ── TOC ───────────────────────────────────────────────────────────────────
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc0", fontName=f_reg, fontSize=9,
                       leading=14, leftIndent=0, textColor=BLUE)
    ]

    # ── Document ──────────────────────────────────────────────────────────────
    _state["job"] = "SOMMARIO"
    footer_fn = _make_footer(page_offset)
    doc = _JobsDocTemplate(
        output_path, footer_fn,
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=22 * mm,
    )

    lbl_sommario = tr.get("jobs_sommario", "SOMMARIO")
    lbl_albero   = tr.get("jobs_albero",   "ALBERO DI RICHIAMO")

    story = []

    if include_toc:
        # First flowable resets state at the start of every multiBuild pass
        story.append(_SetJob(lbl_sommario))

        # ── SOMMARIO page ─────────────────────────────────────────────────────
        story.append(make_header())
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(lbl_sommario, s_sec))
        story.append(Spacer(1, 2 * mm))
        story.append(toc)
        story.append(PageBreak())

        # ── CALL TREE page ────────────────────────────────────────────────────
        story.append(_SetJob(lbl_albero))
    else:
        # Used by Completa: suppress the internal SOMMARIO page so the document
        # has a single, unified table of contents. The "JOBs" header sits atop
        # the ALBERO page instead of occupying a dedicated page.
        story.append(_SetJob(lbl_albero))
        story.append(make_header())
        story.append(Spacer(1, 5 * mm))

    story.append(_Heading(lbl_albero, "job_ALBERO", s_job,
                           heading_text=lbl_albero))
    story.append(HRFlowable(width="100%", thickness=0.5, color=CGRID, spaceAfter=3))
    story.append(Spacer(1, 2 * mm))
    _render_tree_to_story(tree_root, story, s_code, s_miss, tr=tr)
    story.append(PageBreak())

    # ── JBI sections ─────────────────────────────────────────────────────────
    for base_name, fpath, status in entries:
        key = f"job_{base_name}"
        story.append(_SetJob(base_name))

        if status:
            display   = f"{base_name} <font color='#888888' size='8'>— {status}</font>"
            toc_label = f"{base_name} — {status}"
        else:
            display   = base_name
            toc_label = base_name

        story.append(_Heading(display, key, s_job, heading_text=toc_label))
        story.append(HRFlowable(width="100%", thickness=0.5, color=CGRID, spaceAfter=2))

        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            if log_fn:
                log_fn("log_file_read", base_name, len(lines))
            max_digits = len(str(len(lines)))
            for i, line in enumerate(lines):
                story.append(_make_line_para(line, i + 1, max_digits, s_code,
                                             color_fn=_line_color))
        else:
            msg = tr.get("jobs_file_not_found", "[File non trovato: {}]").format(base_name + ".JBI")
            story.append(Paragraph(msg, s_miss))

        story.append(PageBreak())

    # ── CIOPRG.LST — Ladder / Concurrent I/O ─────────────────────────────────
    cio_path  = os.path.join(folder_path, CIOPRG_LST)
    cio_key   = "job_CIOPRG"
    cio_label = "LADDER Concurrent I/O"

    story.append(_SetJob("CIOPRG"))
    story.append(_Heading(cio_label, cio_key, s_job, heading_text=cio_label))
    story.append(HRFlowable(width="100%", thickness=0.5, color=CGRID, spaceAfter=2))

    if os.path.isfile(cio_path):
        with open(cio_path, "r", encoding="utf-8", errors="replace") as f:
            cio_lines = f.readlines()
        if log_fn:
            log_fn("log_file_read", "CIOPRG.LST", len(cio_lines))
        max_digits = len(str(len(cio_lines)))
        for i, line in enumerate(cio_lines):
            story.append(_make_line_para(line, i + 1, max_digits, s_code,
                                         color_fn=_line_color_ladder))
    else:
        if log_fn:
            log_fn("log_file_not_found", "CIOPRG.LST")
        story.append(Paragraph(tr.get("jobs_cioprg_not_found", "[File CIOPRG.LST non trovato]"), s_miss))

    doc.multiBuild(story)

    # ── Return navigation items (name → page) for GUI sidebar / Completa TOC ──
    # Collected in afterFlowable (doc._toc_entries) so they are available whether
    # or not the internal SOMMARIO page was rendered.
    nav_items = []
    try:
        for text, page_num, key in getattr(doc, "_toc_entries", []):
            nav_items.append((text, page_num))
    except Exception:
        nav_items = []
    return nav_items
