"""Shared PDF page header: company logo (left) + name (center) + accent bar."""
import os
import sys
from reportlab.lib.units import mm
from reportlab.lib import colors

HEADER_H_MM   = 17   # total header area height (reserved from top of page)
BAR_H_MM      = 2    # accent bar height
TOP_MARGIN_MM = 22   # recommended topMargin for all PDFs using this header

_ACCENT = colors.HexColor('#D97757')


def _logo_path():
    """Return the path to the bundled logo (PNG preferred, BMP fallback), handling PyInstaller bundling."""
    if hasattr(sys, '_MEIPASS'):
        base = os.path.join(sys._MEIPASS, 'assets')
    else:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    for ext in ('.png', '.bmp'):
        p = os.path.join(base, f'logo-home{ext}')
        if os.path.exists(p):
            return p
    return os.path.join(base, 'logo-home.bmp')


def _get_company():
    """Return the current creator name from the shared app state, with a compiled-in fallback."""
    try:
        import main as _main
        name = getattr(_main.app_state, 'creator_name', None)
        if name and name.strip():
            return name.strip()
    except Exception:
        pass
    return "0THack1A"


def draw_page_header(canvas, doc):
    """Draw the uniform company header at the top of every PDF page."""
    canvas.saveState()
    try:
        W, H = doc.pagesize
        lm   = doc.leftMargin

        hh     = HEADER_H_MM * mm
        bar    = BAR_H_MM * mm
        bar_y  = H - hh          # y coordinate of bar bottom = header area bottom
        area_h = hh - bar        # height of logo+text zone (above the bar)
        area_y = bar_y + bar     # y coordinate of logo+text zone bottom

        # Logo (proportionally scaled inside a 30mm × area_h*0.75 bounding box)
        logo = _logo_path()
        if os.path.exists(logo):
            try:
                img_h = area_h * 0.75
                img_y = area_y + (area_h - img_h) / 2
                canvas.drawImage(
                    logo, lm, img_y,
                    width=30 * mm, height=img_h,
                    preserveAspectRatio=True, mask='auto', anchor='sw',
                )
            except Exception:
                pass

        # Company text — centered in the space to the right of the logo
        logo_end = lm + 30 * mm + 2 * mm
        rm = getattr(doc, 'rightMargin', lm)
        text_x = (logo_end + W - rm) / 2
        font_size = 7 if (W < 500) else 8   # smaller on A5/smaller pages
        canvas.setFont('Helvetica', font_size)
        canvas.setFillColor(colors.HexColor('#333333'))
        canvas.drawCentredString(text_x, area_y + area_h / 2 - 3.5, _get_company())

        # Accent bar (full page width)
        canvas.setFillColor(_ACCENT)
        canvas.rect(0, bar_y, W, bar, fill=1, stroke=0)
    except Exception:
        pass
    canvas.restoreState()
