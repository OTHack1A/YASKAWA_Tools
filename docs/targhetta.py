import os

SYSTEM_FILE = "SYSTEM.SYS"


def parse_system_sys(filepath):
    """
    Parses SYSTEM.SYS and returns dict { normalized_key: [value_lines] }.
    Skips /SYSTEM header and //DATE lines.
    Section keys have internal whitespace normalized (single space).
    """
    sections = {}
    cur_key = None
    cur_lines = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip()
            if not line:
                continue
            if line.startswith("/SYSTEM"):
                continue
            if line.startswith("//DATE"):
                continue
            if line.startswith("//"):
                # flush previous section
                if cur_key is not None:
                    sections[cur_key] = cur_lines[:]
                content = line[2:]
                if ":" in content:
                    i = content.index(":")
                    cur_key = " ".join(content[:i].split())
                    val = content[i + 1:].strip()
                    cur_lines = [val] if val else []
                else:
                    cur_key = " ".join(content.split())
                    cur_lines = []
            else:
                if cur_key is not None:
                    stripped = line.strip()
                    if stripped:
                        cur_lines.append(stripped)

    # flush last section
    if cur_key is not None:
        sections[cur_key] = cur_lines[:]

    return sections


def generate_pdf(folder_path, output_path, lang="IT"):
    """
    Reads SYSTEM.SYS from folder_path, generates a PDF nameplate at output_path.
    Raises on critical errors; caller is responsible for logging.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from translations import TRANSLATIONS
    from docs.utils import pdf_font, xml_escape
    tr = TRANSLATIONS.get(lang, TRANSLATIONS.get("IT", {}))
    f_reg  = pdf_font(lang, bold=False)
    f_bold = pdf_font(lang, bold=True)

    def _fmt_time(raw):
        fmt = tr.get("targ_fmt_time", "{0} h {1} min {2} s")
        try:
            h, rest = raw.split(":", 1)
            m, s    = rest.split("'", 1)
            return fmt.format(int(h), int(m), int(s))
        except Exception:
            return raw

    sys_filepath = os.path.join(folder_path, SYSTEM_FILE)
    data = parse_system_sys(sys_filepath)
    folder_name = os.path.basename(os.path.normpath(folder_path))

    # ── Palette ───────────────────────────────────────────────────────────────
    ACCENT   = colors.HexColor("#D97757")
    DARK   = colors.HexColor("#1a1a2e")
    LGRAY  = colors.HexColor("#f5f5f5")
    MGRAY  = colors.HexColor("#d8d8d8")
    CGRID  = colors.HexColor("#cccccc")
    WHITE  = colors.white

    # ── Document ──────────────────────────────────────────────────────────────
    from docs.pdf_header import draw_page_header
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=22 * mm,
    )
    W = A4[0] - 40 * mm   # usable width

    # ── Style factory ─────────────────────────────────────────────────────────
    def ps(name, font=None, size=8, color=colors.black,
           align=TA_LEFT, **kw):
        fn = font if font is not None else f_reg
        return ParagraphStyle(name, fontName=fn, fontSize=size,
                              textColor=color, alignment=align,
                              leading=size * 1.35, **kw)

    s_head  = ps("hd", f_bold, 15, colors.black, TA_CENTER)
    s_sec   = ps("sc", f_bold,  9, ACCENT,  spaceBefore=4, spaceAfter=1)
    s_lbl   = ps("lb", f_bold,  8, colors.black)
    s_val   = ps("vl", f_reg,   8, colors.black)

    # ── Generic 2-column table builder ───────────────────────────────────────
    def make_table(rows, c1=38 * mm):
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
        [[Paragraph(f"TARGHETTA<br/><font size='10'>{xml_escape(folder_name)}</font>", s_head)]],
        colWidths=[W],
    )
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), ACCENT),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    elems += [hdr, Spacer(1, 4 * mm)]

    # ── System info (robot name incluso) ────────────────────────────────────
    elems.append(Paragraph(tr.get("targ_section_info", "INFORMAZIONI SISTEMA"), s_sec))
    sys_rows = []

    robot_lines = data.get("ROBOT NAME", [])
    if robot_lines:
        robot_val = " ".join(" ".join(robot_lines).split())
        sys_rows.append([Paragraph(tr.get("targ_lbl_robot", "Robot"), s_lbl),
                         Paragraph(xml_escape(robot_val), s_val)])

    for lookup, label in [
        ("SYSTEM NO",  tr.get("targ_lbl_sistema", "Sistema")),
        ("PARAM NO",   tr.get("targ_lbl_params",  "Parametri")),
        ("APPLI",      tr.get("targ_lbl_appli",   "Applicazione")),
        ("LANGUAGE",   tr.get("targ_lbl_lang",    "Lingua SW")),
    ]:
        val = " ".join(data.get(lookup, ["—"])).strip() or "—"
        sys_rows.append([Paragraph(label, s_lbl), Paragraph(xml_escape(val), s_val)])
    elems += [make_table(sys_rows), Spacer(1, 3 * mm)]

    # ── Revisions ─────────────────────────────────────────────────────────────
    revs = [r for r in data.get("REVISION", []) if r]
    if revs:
        elems.append(Paragraph(tr.get("targ_section_revs", "REVISIONI SOFTWARE"), s_sec))
        rev_rows = []
        for entry in revs:
            parts = entry.split(None, 1)
            board   = parts[0] if parts else entry
            version = parts[1] if len(parts) > 1 else ""
            rev_rows.append([Paragraph(xml_escape(board), s_lbl),
                             Paragraph(xml_escape(version), s_val)])
        elems += [make_table(rev_rows, 26 * mm), Spacer(1, 3 * mm)]

    # ── Power / time stats ────────────────────────────────────────────────────
    time_map = [
        ("CONTROL POWER",  tr.get("targ_lbl_ctrl_power",  "Potenza Controllo")),
        ("SERVO POWER",    tr.get("targ_lbl_servo_power", "Potenza Servo")),
        ("PLAYBACK TIME",  tr.get("targ_lbl_playback",    "Tempo Playback")),
        ("MOVING TIME",    tr.get("targ_lbl_moving",      "Tempo Movimento")),
        ("OPERATING TIME", tr.get("targ_lbl_operating",   "Tempo Operativo")),
        ("ENERGY TIME",    tr.get("targ_lbl_energy",      "Tempo Energia")),
    ]
    time_rows = []
    for key, label in time_map:
        for entry in data.get(key, []):
            comma = entry.find(",")
            if comma >= 0:
                left    = entry[:comma]
                raw_hrs = entry[comma + 1:].strip()
                colon   = left.find(":")
                subtype = left[:colon].strip() if colon >= 0 else "TOTAL"
                row_label = label if subtype.upper() == "TOTAL" else f"{label} ({subtype})"
                hours = _fmt_time(raw_hrs)
            else:
                row_label, hours = label, entry
            if hours:
                time_rows.append([Paragraph(xml_escape(row_label), s_lbl),
                                  Paragraph(xml_escape(hours), s_val)])

    if time_rows:
        elems.append(Paragraph(tr.get("targ_section_hours", "ORE OPERATIVE"), s_sec))
        elems.append(make_table(time_rows, 50 * mm))

    section_label = tr.get("targ_section_label", "TARGHETTA")

    def _draw_page(canvas, doc):
        draw_page_header(canvas, doc)
        canvas.saveState()
        W_pg, H_pg = doc.pagesize
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.HexColor('#555555'))
        pg = canvas.getPageNumber()
        canvas.drawRightString(W_pg - 20 * mm, 12 * mm, f"{pg}")
        canvas.drawString(20 * mm, 12 * mm, section_label)
        canvas.restoreState()

    doc.build(elems, onFirstPage=_draw_page, onLaterPages=_draw_page)
