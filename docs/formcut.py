"""
Parser + PDF generator for YASKAWA Form Cutting condition files (FORMCUT.CND).

The "Form Cutting" function automatically generates the path needed to cut a
geometric shape (circle, rectangle, ellipse, pentagon, 2-D hexagon) starting
from a single taught point; it is recalled in a job through the FORMAPR /
FORMCUT instructions (cutting applications: laser, plasma, oxy-fuel, ...).
Each FORMCUT.CND block stores the cut condition: shape and dimensions, rotation
angle, cutting speed, cut-in (approach/return) length and angle, overlap,
dwell times and rotation direction (CW/CCW). Up to 200 files can be registered.

Example of one block::

    //FORMCUT 1
    0,150.000,0.000
    0.000,0.000,10.000
    0.50,0.00,1.00
    0.00,0.00,0.00
    0.250,0,0,0,5.0,45.0,0.0

The exact byte-by-byte field layout of the .CND is not published by YASKAWA,
so the parameter lines are shown faithfully (grouped as stored) rather than
guessing a wrong label for every single value. Only blocks that carry at least
one non-zero value are shown (the controller keeps many empty reserved blocks).

Every public function is defensive: it never raises, returning [] / False on
any error so the caller (preview or "Completa") keeps working and the problem
is only noted in the log.
"""

import os
import re

FORMCUT_FILE = "FORMCUT.CND"
MAX_FORMCUTS = 200

# FCF#(n) reference used by the FORMAPR / FORMCUT instructions inside jobs.
_RE_FCF = re.compile(r"FCF#\(\s*(\d+)\s*\)", re.IGNORECASE)


def parse_formcut(folder_path):
    """Parse FORMCUT.CND into raw blocks.

    Returns a list of dicts ``{"num": int, "lines": [[token, ...], ...]}`` where
    each token is the original numeric string (formatting preserved). Robust:
    returns [] if the file is missing or unreadable.
    """
    path = os.path.join(folder_path, FORMCUT_FILE)
    blocks = []
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return blocks

    cur = None
    for raw in lines:
        line = raw.rstrip("\r\n").strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("//FORMCUT"):
            if cur is not None:
                blocks.append(cur)
            num = len(blocks) + 1
            try:
                num = int(line.split()[-1])
            except (ValueError, IndexError):
                pass
            cur = {"num": num, "lines": []}
        elif line.startswith("///"):
            # optional sub-tag (e.g. ///NAME) — kept generic, ignored if unknown
            continue
        elif line.startswith("//"):
            continue
        else:
            if cur is not None:
                toks = [t.strip() for t in line.split(",") if t.strip() != ""]
                if toks:
                    cur["lines"].append(toks)
    if cur is not None:
        blocks.append(cur)
    return blocks


def _is_active(block):
    """A block is 'used' if any of its numeric tokens differs from zero."""
    for ln in block.get("lines", []):
        for tok in ln:
            try:
                if float(tok) != 0.0:
                    return True
            except (TypeError, ValueError):
                # a non-numeric token (e.g. a name) also counts as content
                if tok:
                    return True
    return False


def find_formcut_usage(folder_path):
    """Scan every .JBI job for FORMAPR/FORMCUT instructions and map which Form
    Cut file numbers (FCF#(n)) are actually used, and in which jobs.

    Returns ``{formcut_num: [job_name, ...]}`` (job names sorted). Robust:
    never raises, returns {} on any error.
    """
    usage = {}
    try:
        files = [f for f in os.listdir(folder_path) if f.upper().endswith(".JBI")]
    except OSError:
        return {}
    for fn in files:
        job = os.path.splitext(fn)[0]
        try:
            with open(os.path.join(folder_path, fn), "r",
                      encoding="latin-1", errors="replace") as f:
                for line in f:
                    u = line.upper()
                    if "FORMCUT" in u or "FORMAPR" in u:
                        for m in _RE_FCF.finditer(line):
                            try:
                                n = int(m.group(1))
                            except ValueError:
                                continue
                            usage.setdefault(n, set()).add(job)
        except OSError:
            continue
    return {k: sorted(v) for k, v in usage.items()}


def build_formcuts(folder_path):
    """Return the Form Cut blocks that are actually USED by a job.

    A Form Cut is included only if a FORMAPR/FORMCUT FCF#(n) instruction in some
    .JBI references it; each block carries ``used_in`` (list of job names). If no
    job uses any Form Cut, the list is empty. Robust: never raises.
    """
    try:
        raw = parse_formcut(folder_path)
    except Exception:
        raw = []
    by_num = {}
    for b in raw:
        try:
            n = b.get("num", 0)
            if 1 <= n <= MAX_FORMCUTS:
                by_num[n] = b
        except Exception:
            continue

    try:
        usage = find_formcut_usage(folder_path)
    except Exception:
        usage = {}

    out = []
    for n in sorted(usage):
        block = dict(by_num.get(n, {"num": n, "lines": []}))
        block["used_in"] = usage.get(n, [])
        out.append(block)
    return out


def generate_pdf(folder_path, output_path, lang="IT", page_offset=0, log_fn=None):
    """Generate the Form Cut PDF. Returns True on success, False otherwise.

    Always produces a valid PDF (a "no form cut" page when none are found) so
    the preview never breaks. Never raises — failures are logged via log_fn.
    """
    def _log(key, *args):
        if log_fn:
            try:
                log_fn(key, *args)
            except Exception:
                pass

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer)
        from docs.pdf_header import draw_page_header
        from docs.utils import pdf_font, xml_escape
        from translations import TRANSLATIONS
    except Exception as exc:
        _log("log_error_generic", str(exc))
        return False

    try:
        tr = TRANSLATIONS.get(lang, TRANSLATIONS.get("IT", {}))
        formcuts = build_formcuts(folder_path)

        ACCENT  = colors.HexColor("#D97757")
        WHITE = colors.white
        CGRID = colors.HexColor("#cccccc")
        LGRAY = colors.HexColor("#f5f5f5")
        GRAY  = colors.HexColor("#888888")

        f_reg  = pdf_font(lang, bold=False)
        f_bold = pdf_font(lang, bold=True)
        W = A4[0] - 40 * mm
        folder_name = os.path.basename(os.path.normpath(folder_path))

        s_head = ParagraphStyle("fh", fontName=f_bold, fontSize=15, textColor=WHITE,
                                alignment=TA_CENTER, leading=20)
        s_desc = ParagraphStyle("fd", fontName=f_reg, fontSize=9, textColor=colors.black,
                                leading=13)
        s_card = ParagraphStyle("fc", fontName=f_reg, fontSize=8,
                                textColor=colors.black, leading=11)
        s_miss = ParagraphStyle("fm", fontName=f_reg, fontSize=10, textColor=GRAY,
                                alignment=TA_CENTER, leading=14)

        title   = tr.get("formcut_title", "TAGLIO SAGOME (FORM CUT)")
        desc    = tr.get("formcut_desc",
                         "La funzione Form Cut genera il percorso di taglio di una sagoma.")
        caption = tr.get("formcut_caption", "Parametri condizione (FORMCUT.CND)")
        no_data = tr.get("formcut_no_data", "Nessun Form Cut attivo.")
        ex_cap  = tr.get("formcut_example_caption", "Esempio d'uso")
        ex_note = tr.get("formcut_example_note", "")
        ex_code = tr.get("formcut_example_code", "")

        # Column headers / shape names (interpreted from YASKAWA Form Cut docs).
        L_NUM   = tr.get("formcut_lbl_num",    "N°")
        L_FIG   = tr.get("formcut_lbl_figure", "Figura")
        L_DIM   = tr.get("formcut_lbl_dim",    "Dim.")
        L_SPD   = tr.get("formcut_lbl_speed",  "Velocità")
        L_ANG   = tr.get("formcut_lbl_angle",  "Angolo")
        L_DIR   = tr.get("formcut_lbl_dir",    "Direzione")
        L_USED  = tr.get("formcut_lbl_used",   "Usato in")
        dir_note = tr.get("formcut_dir_note",
                          "Direzione: CW = orario, CCW = antiorario.")
        SHAPES  = {i: tr.get(f"formcut_shape_{i}", str(i)) for i in range(5)}

        def _tok(lines, li, ti):
            try:
                return lines[li][ti]
            except (IndexError, TypeError):
                return None

        def _num(tok):
            try:
                return float(tok)
            except (TypeError, ValueError):
                return None

        s_note = ParagraphStyle("fn2", fontName=f_reg, fontSize=7.5,
                                textColor=GRAY, leading=10)
        s_code = ParagraphStyle("fco", fontName="Courier", fontSize=7.5,
                                textColor=colors.black, leading=10)
        s_th   = ParagraphStyle("fth", fontName=f_bold, fontSize=8, textColor=WHITE,
                                alignment=TA_CENTER, leading=10)
        s_tdc  = ParagraphStyle("ftdc", fontName=f_reg, fontSize=8, textColor=colors.black,
                                alignment=TA_CENTER, leading=10)
        s_td   = ParagraphStyle("ftd", fontName=f_reg, fontSize=7.5, textColor=colors.black,
                                alignment=TA_LEFT, leading=9.5)

        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=22 * mm, bottomMargin=18 * mm,
        )

        hdr = Table(
            [[Paragraph(f"{xml_escape(title)}<br/>"
                        f"<font size='10'>{xml_escape(folder_name)}</font>", s_head)]],
            colWidths=[W],
        )
        hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), ACCENT),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))

        story = [hdr, Spacer(1, 4 * mm),
                 Paragraph(xml_escape(desc), s_desc),
                 Spacer(1, 3 * mm)]

        # ── Usage example (instead of the old grey legend) ─────────────────────
        if ex_code:
            story.append(Paragraph(f"<b>{xml_escape(ex_cap)}</b>", s_desc))
            story.append(Spacer(1, 1.5 * mm))
            code_md = "<br/>".join(
                xml_escape(line).replace(" ", "&nbsp;")
                for line in ex_code.split("\n"))
            ex_tbl = Table([[Paragraph(code_md, s_code)]], colWidths=[W])
            ex_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), LGRAY),
                ("BOX",           (0, 0), (-1, -1), 0.3, CGRID),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ]))
            story.append(ex_tbl)
            if ex_note:
                story.append(Spacer(1, 1.5 * mm))
                story.append(Paragraph(f"<i>{xml_escape(ex_note)}</i>", s_note))
            story.append(Spacer(1, 4 * mm))

        if not formcuts:
            story.append(Spacer(1, 12 * mm))
            story.append(Paragraph(xml_escape(no_data), s_miss))
        else:
            # ── Single table: one row per Form Cut, named columns ──────────────
            # Confirmed fields (YASKAWA Form Cut docs + forum): figure, dimension,
            # cutting speed, rotation angle, rotation direction (last line, 2nd
            # value: 0=CW, 1=CCW).
            story.append(Paragraph(f"<b>{xml_escape(caption)}</b>", s_desc))
            if dir_note:
                story.append(Paragraph(f"<i>{xml_escape(dir_note)}</i>", s_note))
            story.append(Spacer(1, 2 * mm))

            dim_hdr = f"{L_DIM} (mm)"
            header = [Paragraph(xml_escape(L_NUM), s_th),
                      Paragraph(xml_escape(L_FIG), s_th),
                      Paragraph(xml_escape(dim_hdr), s_th),
                      Paragraph(xml_escape(L_SPD), s_th),
                      Paragraph(xml_escape(L_ANG), s_th),
                      Paragraph(xml_escape(L_DIR), s_th),
                      Paragraph(xml_escape(L_USED), s_th)]
            data = [header]
            for b in formcuts:
                lines = b.get("lines", [])

                fig_n = _num(_tok(lines, 0, 0))
                shape = SHAPES.get(int(fig_n), str(int(fig_n))) if fig_n is not None else "—"

                dim1 = _tok(lines, 0, 1)
                dim2 = _tok(lines, 0, 2)
                d2n  = _num(dim2)
                if dim1 is None:
                    dim_s = "—"
                elif d2n not in (None, 0.0):
                    dim_s = f"{dim1} × {dim2}"
                else:
                    dim_s = f"{dim1}"

                spd   = _tok(lines, 1, 2)
                spd_s = f"{spd}" if spd is not None else "—"

                ang   = _tok(lines, 4, 5)
                ang_s = f"{ang}°" if ang is not None else "—"

                dir_n = _num(_tok(lines, 4, 1))
                dir_s = "CW" if dir_n == 0 else ("CCW" if dir_n == 1
                                                 else ("—" if dir_n is None else str(int(dir_n))))

                used = ", ".join(b.get("used_in", [])) or "—"

                data.append([
                    Paragraph(str(b.get("num", "")), s_tdc),
                    Paragraph(xml_escape(shape), s_tdc),
                    Paragraph(xml_escape(dim_s), s_tdc),
                    Paragraph(xml_escape(spd_s), s_tdc),
                    Paragraph(xml_escape(ang_s), s_tdc),
                    Paragraph(xml_escape(dir_s), s_tdc),
                    Paragraph(xml_escape(used), s_td),
                ])

            col_w = [10 * mm, 24 * mm, 30 * mm, 22 * mm, 20 * mm, 22 * mm, W - 128 * mm]
            tbl = Table(data, colWidths=col_w, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND",     (0, 0), (-1, 0), ACCENT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGRAY]),
                ("GRID",           (0, 0), (-1, -1), 0.3, CGRID),
                ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",     (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
            ]))
            story.append(tbl)

        # Footer: section name on the LEFT (uppercase) + page number on the RIGHT,
        # exactly like the Targhetta / Panel sections.
        section_label = tr.get("menu_formcut", "FormCut").upper()

        def _draw(canvas, doc_):
            draw_page_header(canvas, doc_)
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#555555"))
            W_pg = doc_.pagesize[0]
            canvas.drawString(20 * mm, 12 * mm, section_label)
            canvas.drawRightString(W_pg - 20 * mm, 12 * mm, str(doc_.page + page_offset))
            canvas.restoreState()

        doc.build(story, onFirstPage=_draw, onLaterPages=_draw)
        _log("log_formcut_generated", len(formcuts))
        return True
    except Exception as exc:
        _log("log_error_generic", str(exc))
        return False
