import os
import sys
import re

PANEL_FILE = "PANELBOX.LOG"

_MESI = {
    "01": "gennaio",  "02": "febbraio", "03": "marzo",
    "04": "aprile",   "05": "maggio",   "06": "giugno",
    "07": "luglio",   "08": "agosto",   "09": "settembre",
    "10": "ottobre",  "11": "novembre", "12": "dicembre",
}

# YYYY/MM/DD HH:MM,HHHH:MM'SS  (ore accumulate)
_RE_DH = re.compile(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}:\d{2}),(\d+):(\d+)'(\d+)")
# YYYY/MM/DD HH:MM:SS  (timestamp semplice)
_RE_DT = re.compile(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}:\d{2}:\d{2})")


def _sub_dh(m):
    y, mo, d, hm, hh, mm, ss = m.groups()
    return (f"{int(d)} {_MESI.get(mo, mo)} {y} ore {hm}"
            f" - totale {int(hh)} ore {int(mm)} min {int(ss)} sec")


def _sub_dt(m):
    y, mo, d, t = m.groups()
    return f"{int(d)} {_MESI.get(mo, mo)} {y} {t}"


def _convert_dates(text):
    """Converte entrambi i formati data presenti nel file."""
    text = _RE_DH.sub(_sub_dh, text)
    text = _RE_DT.sub(_sub_dt, text)
    return text


def _xml_escape(text):
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _logo_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, "logo-home.bmp")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "logo-home.bmp")


# ── Parsing ───────────────────────────────────────────────────────────────────

def _read_lines(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return [line.rstrip() for line in f]


def _parse_header(lines):
    """
    Legge le sezioni //KEY: VALUE fino alla riga //CONTROLLER SETTING.
    Restituisce (dict_sezioni, indice_inizio_body).
    """
    sections = {}
    cur_key = None
    cur_lines = []
    body_start = len(lines)

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") and "CONTROLLER SETTING" in stripped:
            body_start = idx
            break

        if not stripped:
            continue
        if stripped.startswith("/SYSTEM"):
            continue
        if stripped.startswith("//DATE"):
            continue

        if stripped.startswith("//"):
            if cur_key is not None:
                sections[cur_key] = cur_lines[:]
            content = stripped[2:]
            if ":" in content:
                i = content.index(":")
                cur_key = " ".join(content[:i].split())
                val = content[i + 1:].strip()
                cur_lines = [val] if val else []
            else:
                cur_key = " ".join(content.split())
                cur_lines = []
        else:
            if cur_key is not None and stripped:
                cur_lines.append(stripped)

    if cur_key is not None:
        sections[cur_key] = cur_lines[:]

    return sections, body_start


def _parse_body(lines, body_start):
    """
    Divide il corpo del file in sezioni delimitate da ====.
    Restituisce lista di (titolo, [righe_contenuto]).
    """
    sections = []
    cur_title = None
    cur_lines = []
    title_set = False

    for line in lines[body_start:]:
        if line.startswith("===="):
            # flush sezione corrente
            if cur_title is not None or any(l.strip() for l in cur_lines):
                sections.append((cur_title or "", cur_lines[:]))
            cur_title = None
            cur_lines = []
            title_set = False
        else:
            if not title_set:
                candidate = line.strip().lstrip("/").strip()
                if candidate:
                    cur_title = candidate
                    title_set = True
                # righe vuote prima del titolo: ignorate
            else:
                cur_lines.append(line)

    # flush ultima sezione
    if cur_title is not None or any(l.strip() for l in cur_lines):
        sections.append((cur_title or "", cur_lines[:]))

    return sections


# ── Generazione PDF ───────────────────────────────────────────────────────────

def generate_pdf(folder_path, output_path, lang="IT", page_offset=0):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, HRFlowable)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from translations import TRANSLATIONS
    from docs.utils import make_footer, pdf_font
    tr = TRANSLATIONS.get(lang, TRANSLATIONS["IT"])

    filepath = os.path.join(folder_path, PANEL_FILE)
    raw_lines = _read_lines(filepath)
    header_data, body_start = _parse_header(raw_lines)
    body_sections = _parse_body(raw_lines, body_start)
    folder_name = os.path.basename(os.path.normpath(folder_path))

    # ── Palette ───────────────────────────────────────────────────────────────
    ACCENT  = colors.HexColor("#D97757")
    LGRAY = colors.HexColor("#f5f5f5")
    MGRAY = colors.HexColor("#d8d8d8")
    CGRID = colors.HexColor("#cccccc")
    WHITE = colors.white

    W = A4[0] - 40 * mm   # larghezza utile (margini 20mm)
    f_reg  = pdf_font(lang, bold=False)
    f_bold = pdf_font(lang, bold=True)

    # ── Footer: numero pagina centrato + nome file a destra ───────────────────
    _footer = make_footer(os.path.splitext(PANEL_FILE)[0], page_offset)

    # ── Documento ─────────────────────────────────────────────────────────────
    from docs.pdf_header import draw_page_header
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=22 * mm,
    )

    # ── Stili ─────────────────────────────────────────────────────────────────
    def ps(name, font=None, size=9, color=colors.black,
           align=TA_LEFT, **kw):
        fn = font if font is not None else f_reg
        return ParagraphStyle(name, fontName=fn, fontSize=size,
                              textColor=color, alignment=align,
                              leading=size * 1.4, **kw)

    s_head = ps("hd", f_bold, 15, colors.black, TA_CENTER)
    s_sec  = ps("sc", f_bold,  9, ACCENT,  spaceBefore=6, spaceAfter=2)
    s_bsec = ps("bs", f_bold,  9, ACCENT,  spaceBefore=8, spaceAfter=2)
    s_lbl  = ps("lb", f_bold,  8, colors.black)
    s_val  = ps("vl", f_reg,   8, colors.black)
    s_mono = ps("mo", "Courier", 7, colors.black, spaceAfter=0)

    # ── Tabella generica 2 colonne ────────────────────────────────────────────
    def make_table(rows, c1=45 * mm):
        t = Table(rows, colWidths=[c1, W - c1])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LGRAY),
            ("BACKGROUND",    (0, 0), (0, -1),  MGRAY),
            ("GRID",          (0, 0), (-1, -1), 0.3, CGRID),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ]))
        return t

    elems = []

    # ── Document title (below the per-page company header) ───────────────────
    hdr = Table(
        [[Paragraph(f"PANEL<br/><font size='10'>{_xml_escape(folder_name)}</font>", s_head)]],
        colWidths=[W],
    )
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), ACCENT),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    elems += [hdr, Spacer(1, 5 * mm)]

    # ── Informazioni sistema ──────────────────────────────────────────────────
    elems.append(Paragraph(tr.get("targ_section_info", "INFORMAZIONI SISTEMA"), s_sec))
    sys_rows = []
    robot_lines = header_data.get("ROBOT NAME", [])
    if robot_lines:
        sys_rows.append([Paragraph(tr.get("targ_lbl_robot", "Robot"), s_lbl),
                         Paragraph(_xml_escape(" ".join(" ".join(robot_lines).split())), s_val)])
    for lookup, label in [
        ("SYSTEM NO", tr.get("targ_lbl_sistema", "Sistema")),
        ("PARAM NO",  tr.get("targ_lbl_params",  "Parametri")),
        ("APPLI",     tr.get("targ_lbl_appli",   "Applicazione")),
        ("LANGUAGE",  tr.get("targ_lbl_lang",    "Lingua SW")),
    ]:
        val = " ".join(header_data.get(lookup, ["—"])).strip() or "—"
        sys_rows.append([Paragraph(label, s_lbl), Paragraph(_xml_escape(val), s_val)])
    elems += [make_table(sys_rows, 40 * mm), Spacer(1, 4 * mm)]

    # ── Revisioni software ────────────────────────────────────────────────────
    revs = [r for r in header_data.get("REVISION", []) if r]
    if revs:
        elems.append(Paragraph("REVISIONI SOFTWARE", s_sec))
        rev_rows = []
        for entry in revs:
            parts = entry.split(None, 1)
            rev_rows.append([Paragraph(_xml_escape(parts[0] if parts else entry), s_lbl),
                             Paragraph(_xml_escape(parts[1] if len(parts) > 1 else ""), s_val)])
        elems += [make_table(rev_rows, 28 * mm), Spacer(1, 4 * mm)]

    # ── Ore operative ─────────────────────────────────────────────────────────
    time_map = [
        ("CONTROL POWER",  "Potenza Controllo"),
        ("SERVO POWER",    "Potenza Servo"),
        ("PLAYBACK TIME",  "Tempo Playback"),
        ("MOVING TIME",    "Tempo Movimento"),
        ("OPERATING TIME", "Tempo Operativo"),
        ("ENERGY TIME",    "Tempo Energia"),
    ]
    time_rows = []
    for key, label in time_map:
        for entry in header_data.get(key, []):
            m = _RE_DH.search(entry)
            if m:
                y, mo, d, hm, hh, mm_, ss = m.groups()
                date_str  = f"{int(d)} {_MESI.get(mo, mo)} {y} ore {hm}"
                hours_str = f"totale {int(hh)} ore {int(mm_)} min {int(ss)} sec"
                before    = entry[:m.start()].strip().rstrip(":").strip()
                subtype   = before if before else "TOTAL"
                row_label = label if subtype.upper() == "TOTAL" else f"{label} ({subtype})"
                val_str   = f"{date_str} - {hours_str}"
            else:
                row_label = label
                val_str   = entry
            time_rows.append([Paragraph(_xml_escape(row_label), s_lbl),
                              Paragraph(_xml_escape(val_str), s_val)])
    if time_rows:
        elems.append(Paragraph("ORE OPERATIVE", s_sec))
        elems += [make_table(time_rows, 55 * mm), Spacer(1, 5 * mm)]

    # ── Separatore tra header e corpo ─────────────────────────────────────────
    elems.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT))
    elems.append(Spacer(1, 3 * mm))

    # ── Sezioni corpo (CONTROLLER SETTING) ───────────────────────────────────
    for title, content_lines in body_sections:
        # sezioni completamente vuote: salta
        if not title and not any(l.strip() for l in content_lines):
            continue

        if title:
            elems.append(Paragraph(_xml_escape(title), s_bsec))

        for line in content_lines:
            stripped = line.strip()
            if not stripped:
                elems.append(Spacer(1, 1 * mm))
            elif stripped.startswith("----"):
                elems.append(HRFlowable(width="100%", thickness=0.3,
                                        color=CGRID, spaceAfter=1))
            else:
                converted = _convert_dates(line)
                safe = _xml_escape(converted)
                elems.append(Paragraph(safe, s_mono))

    def _page_fn(canvas, doc):
        draw_page_header(canvas, doc)
        _footer(canvas, doc)

    doc.build(elems, onFirstPage=_page_fn, onLaterPages=_page_fn)
