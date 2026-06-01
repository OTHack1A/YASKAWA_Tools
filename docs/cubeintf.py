"""
Parser + PDF generator for YASKAWA interference cubes (CUBEINTF.CND).

The YRC1000/DX200 controller stores up to 64 cubic interference areas in
CUBEINTF.CND.  Each cube is defined by a diagonal pair of corner points
(MAX / MIN) expressed in a reference coordinate system (BASE / ROBOT / USER),
together with the control group it belongs to and — when the coordinate system
is USER — the user-frame number.  Only the first few cubes are normally used;
the rest are stored as all-zero blocks and must be ignored.

File structure of one cube block::

    //CUBEINTF 1
    ///NAME KENTAI
    3,1,1                                  <- check method, control group, coord
    500000,1000000,2500000,0,0,0,0,0       <- MAX point  (X,Y,Z in 0.001 mm)
    -1000000,-1000000,-1000000,0,0,0,0,0   <- MIN point  (X,Y,Z in 0.001 mm)
    1                                      <- user-frame number
    0,0,0,0,0,0,0,0                        <- reserved
    0,0,0,0,0,0,0,0                        <- reserved

Linear coordinates are stored in micrometres (0.001 mm) — the same convention
used by the other YASKAWA position files — and are converted to millimetres for
display.

Every public function is defensive: it never raises, returning [] / False on
any error so the caller (preview or "Completa") can keep working and simply
note the problem in the log.
"""

import os

CUBEINTF_FILE = "CUBEINTF.CND"
MAX_CUBES = 64

# Reference coordinate system codes (YASKAWA). Kept as invariant technical
# terms (like the codes used by the IF-Panel section).
_COORD_LABELS = {0: "BASE", 1: "ROBOT", 2: "USER"}


def _nums(line):
    """Parse a comma-separated line into a list of numbers (int where possible)."""
    out = []
    for tok in line.split(","):
        tok = tok.strip()
        if tok == "":
            continue
        try:
            out.append(int(tok))
        except ValueError:
            try:
                out.append(float(tok))
            except ValueError:
                out.append(0)
    return out


def parse_cubeintf(folder_path):
    """Parse CUBEINTF.CND into a list of raw cube blocks.

    Returns a list of dicts ``{"num": int, "name": str, "data": [[num,...], ...]}``.
    Robust: returns [] if the file is missing or unreadable.
    """
    path = os.path.join(folder_path, CUBEINTF_FILE)
    cubes = []
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return cubes

    cur = None
    for raw in lines:
        line = raw.rstrip("\r\n").strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("//CUBEINTF"):
            if cur is not None:
                cubes.append(cur)
            num = len(cubes) + 1
            try:
                num = int(line.split()[-1])
            except (ValueError, IndexError):
                pass
            cur = {"num": num, "name": "", "data": []}
        elif line.startswith("///"):
            if cur is not None:
                tag = line[3:].strip()
                parts = tag.split(None, 1)
                if parts and parts[0].upper() == "NAME":
                    cur["name"] = parts[1].strip() if len(parts) > 1 else ""
        elif line.startswith("//"):
            # other comment / unknown header — ignore
            continue
        else:
            if cur is not None:
                cur["data"].append(_nums(line))
    if cur is not None:
        cubes.append(cur)
    return cubes


def _scale_xyz(vals):
    """First three values, micrometre (0.001 mm) → mm. Tolerates short rows."""
    xyz = (list(vals) + [0, 0, 0])[:3]
    out = []
    for v in xyz:
        try:
            out.append(float(v) / 1000.0)
        except (TypeError, ValueError):
            out.append(0.0)
    return tuple(out)


def build_cubes(folder_path):
    """Return the list of ACTIVE interference cubes (any non-zero value).

    A cube is considered "used" if any number in its data block is non-zero,
    even if it has no name.  All-zero blocks are skipped.  Robust: never raises.
    """
    try:
        raw = parse_cubeintf(folder_path)
    except Exception:
        return []

    result = []
    for c in raw:
        try:
            data = c.get("data", [])
            # Active iff at least one numeric value differs from zero.
            active = any(any(v != 0 for v in row) for row in data)
            if not active:
                continue
            line_a = data[0] if len(data) > 0 else []
            max_pt = data[1] if len(data) > 1 else []
            min_pt = data[2] if len(data) > 2 else []
            uf_row = data[3] if len(data) > 3 else []

            method = line_a[0] if len(line_a) > 0 else 0
            group  = line_a[1] if len(line_a) > 1 else 0
            coord  = line_a[2] if len(line_a) > 2 else 0
            uf     = uf_row[0] if len(uf_row) > 0 else 0

            result.append({
                "num":    c.get("num", 0),
                "name":   c.get("name", "") or "",
                "method": method,
                "group":  group,
                "coord":  coord,
                "uf":     uf,
                "max":    _scale_xyz(max_pt),
                "min":    _scale_xyz(min_pt),
            })
        except Exception:
            # Skip any malformed cube without aborting the whole parse.
            continue

    # Only the first 64 areas exist on the controller.
    result = [r for r in result if 1 <= r["num"] <= MAX_CUBES]
    result.sort(key=lambda r: r["num"])
    return result


def _fmt_mm(v):
    try:
        return f"{float(v):.3f}"
    except (TypeError, ValueError):
        return "0.000"


def _coord_label(coord):
    # Some controllers set the high bit of this field as an internal flag,
    # while the low bits carry the BASE/ROBOT/USER selector. Mask it so the
    # label stays clean (e.g. 129 → 1 → ROBOT). Unknown values fall back to raw.
    try:
        c = int(coord) & 0x7F
    except (TypeError, ValueError):
        return str(coord)
    return _COORD_LABELS.get(c, str(int(coord)))


def _group_label(group):
    try:
        g = int(group)
    except (TypeError, ValueError):
        return str(group)
    return f"R{g}" if g >= 1 else "—"


def generate_pdf(folder_path, output_path, lang="IT", page_offset=0, log_fn=None):
    """Generate the interference-cubes PDF. Returns True on success, False otherwise.

    Always produces a valid PDF (a "no active cubes" page when none are found)
    so the preview never breaks. Never raises — failures are logged via log_fn.
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
        cubes = build_cubes(folder_path)

        ACCENT  = colors.HexColor("#D97757")
        WHITE = colors.white
        CGRID = colors.HexColor("#cccccc")
        LGRAY = colors.HexColor("#f5f5f5")
        GRAY  = colors.HexColor("#888888")

        f_reg  = pdf_font(lang, bold=False)
        f_bold = pdf_font(lang, bold=True)
        W = A4[0] - 40 * mm
        folder_name = os.path.basename(os.path.normpath(folder_path))

        s_head = ParagraphStyle("ch", fontName=f_bold, fontSize=15, textColor=WHITE,
                                alignment=TA_CENTER, leading=20)
        s_th   = ParagraphStyle("cth", fontName=f_bold, fontSize=8, textColor=WHITE,
                                alignment=TA_CENTER, leading=10)
        s_td   = ParagraphStyle("ctd", fontName=f_reg, fontSize=8, textColor=colors.black,
                                leading=10)
        s_tdc  = ParagraphStyle("ctdc", fontName=f_reg, fontSize=8, textColor=colors.black,
                                alignment=TA_CENTER, leading=10)
        s_num  = ParagraphStyle("ctn", fontName="Courier", fontSize=8,
                                textColor=colors.black, leading=10, alignment=TA_CENTER)
        s_miss = ParagraphStyle("cms", fontName=f_reg, fontSize=10, textColor=GRAY,
                                alignment=TA_CENTER, leading=14)

        title    = tr.get("cubeintf_title", "CUBI DI INTERFERENZA")
        c_num    = tr.get("cubeintf_col_num",   "N°")
        c_name   = tr.get("cubeintf_col_name",  "Nome")
        c_group  = tr.get("cubeintf_col_group", "Gruppo")
        c_coord  = tr.get("cubeintf_col_coord", "Coordinate")
        c_uf     = tr.get("cubeintf_col_uf",    "UF#")
        c_max    = tr.get("cubeintf_col_max",   "Punto MAX (X/Y/Z mm)")
        c_min    = tr.get("cubeintf_col_min",   "Punto MIN (X/Y/Z mm)")
        no_data  = tr.get("cubeintf_no_data",   "Nessun cubo di interferenza attivo.")

        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=22 * mm, bottomMargin=18 * mm,
        )

        # Header bar (same look as Targhetta / Panel / Parametri)
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

        story = [hdr, Spacer(1, 5 * mm)]

        if not cubes:
            story.append(Spacer(1, 20 * mm))
            story.append(Paragraph(xml_escape(no_data), s_miss))
        else:
            col_w = [12 * mm, 30 * mm, 18 * mm, 22 * mm, 14 * mm,
                     (W - 96 * mm) / 2.0, (W - 96 * mm) / 2.0]
            rows = [[
                Paragraph(c_num,   s_th), Paragraph(c_name,  s_th),
                Paragraph(c_group, s_th), Paragraph(c_coord, s_th),
                Paragraph(c_uf,    s_th), Paragraph(c_max,   s_th),
                Paragraph(c_min,   s_th),
            ]]
            for cube in cubes:
                mx, my, mz = cube["max"]
                nx, ny, nz = cube["min"]
                max_cell = (f"{_fmt_mm(mx)}<br/>{_fmt_mm(my)}<br/>{_fmt_mm(mz)}")
                min_cell = (f"{_fmt_mm(nx)}<br/>{_fmt_mm(ny)}<br/>{_fmt_mm(nz)}")
                uf_disp = str(cube["uf"])
                rows.append([
                    Paragraph(str(cube["num"]), s_num),
                    Paragraph(xml_escape(cube["name"]) or "—", s_td),
                    Paragraph(xml_escape(_group_label(cube["group"])), s_tdc),
                    Paragraph(xml_escape(_coord_label(cube["coord"])), s_tdc),
                    Paragraph(xml_escape(uf_disp), s_tdc),
                    Paragraph(max_cell, s_num),
                    Paragraph(min_cell, s_num),
                ])

            tbl = Table(rows, colWidths=col_w, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND",     (0, 0), (-1, 0), ACCENT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGRAY]),
                ("GRID",           (0, 0), (-1, -1), 0.3, CGRID),
                ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",     (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
                ("LEFTPADDING",    (0, 0), (-1, -1), 4),
                ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
            ]))
            story.append(tbl)

        # Footer section label — right-aligned and uppercase, consistent with
        # every other section (JOBs, User Group, Targhetta, ...).
        section_label = tr.get("menu_cubeintf", "Cubo interferenza").upper()

        def _draw(canvas, doc_):
            draw_page_header(canvas, doc_)
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#555555"))
            W_pg = doc_.pagesize[0]
            canvas.drawCentredString(W_pg / 2.0, 12 * mm, str(doc_.page + page_offset))
            canvas.drawRightString(W_pg - 20 * mm, 12 * mm, section_label)
            canvas.restoreState()

        doc.build(story, onFirstPage=_draw, onLaterPages=_draw)
        _log("log_cubeintf_generated", len(cubes))
        return True
    except Exception as exc:
        _log("log_error_generic", str(exc))
        return False
