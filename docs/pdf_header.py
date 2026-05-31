"""Shared PDF page header: company logo (left) + name (center) + blue bar."""
import os
import sys
from reportlab.lib.units import mm
from reportlab.lib import colors

HEADER_H_MM   = 17   # total header area height (reserved from top of page)
BAR_H_MM      = 2    # blue dividing bar height
TOP_MARGIN_MM = 22   # recommended topMargin for all PDFs using this header

_BLUE    = colors.HexColor('#D97757')
_COMPANY = "0THack1A"


def _logo_path():
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for ext in ('.png', '.bmp'):
        p = os.path.join(base, f'logo-home{ext}')
        if os.path.exists(p):
            return p
    return os.path.join(base, 'logo-home.bmp')


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
        canvas.drawCentredString(text_x, area_y + area_h / 2 - 3.5, _COMPANY)

        # Blue dividing bar (full page width)
        canvas.setFillColor(_BLUE)
        canvas.rect(0, bar_y, W, bar, fill=1, stroke=0)
    except Exception:
        pass
    canvas.restoreState()
