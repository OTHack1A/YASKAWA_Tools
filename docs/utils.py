from reportlab.lib import colors
from reportlab.lib.units import mm


def xml_escape(text):
    """Escape untrusted text for safe use inside a ReportLab ``Paragraph``.

    ReportLab interprets a small XML/HTML dialect inside ``Paragraph`` (``<font>``,
    ``<br/>``, ``<link>`` ...).  Raw ``&``, ``<`` or ``>`` coming from robot
    configuration files or from a folder name (Windows allows ``&`` in folder
    names, e.g. ``R&D``) would otherwise either raise during ``doc.build`` —
    aborting the whole PDF — or inject unintended markup into the document.

    Always returns a ``str``; ``None`` becomes ``""`` and non-string values are
    coerced.  Order matters: ``&`` must be escaped first.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


# Characters that make a spreadsheet cell be interpreted as a formula by
# Excel / LibreOffice when the file is opened (CSV/formula injection — the
# value could run a command or exfiltrate data).  A leading "-" is deliberately
# NOT included: robot parameter values are frequently negative numbers and
# quoting them would corrupt legitimate data; lone numbers are not executed.
_EXCEL_FORMULA_TRIGGERS = ("=", "+", "@", "\t", "\r")


def excel_safe(value):
    """Neutralise spreadsheet formula injection for a single cell value.

    If ``value`` is a string that begins with a formula trigger, prefix it with
    a single quote so the spreadsheet shows it as literal text instead of
    evaluating it.  Numbers and other types are returned unchanged.
    """
    if isinstance(value, str) and value[:1] in _EXCEL_FORMULA_TRIGGERS:
        return "'" + value
    return value


_GRAY  = colors.HexColor("#aaaaaa")
_FONT  = "Helvetica"
_SIZE  = 8
_Y_MM  = 10

_CJK_REGISTERED = False
_CYR_REGISTERED = False

_JA_FONT      = "YuGothic"
_JA_FONT_BOLD = "YuGothic-Bold"

def register_cjk_font():
    """Register Yu Gothic TTF (Windows 10+); fallback MS Gothic; fallback CID."""
    global _CJK_REGISTERED, _JA_FONT, _JA_FONT_BOLD
    if _CJK_REGISTERED:
        return True
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase import pdfmetrics
        pdfmetrics.registerFont(
            TTFont("YuGothic",      r"C:\Windows\Fonts\YuGothR.ttc", subfontIndex=0))
        pdfmetrics.registerFont(
            TTFont("YuGothic-Bold", r"C:\Windows\Fonts\YuGothB.ttc", subfontIndex=0))
        _JA_FONT      = "YuGothic"
        _JA_FONT_BOLD = "YuGothic-Bold"
        _CJK_REGISTERED = True
        return True
    except Exception:
        pass
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase import pdfmetrics
        pdfmetrics.registerFont(
            TTFont("MSGothic", r"C:\Windows\Fonts\msgothic.ttc", subfontIndex=0))
        _JA_FONT      = "MSGothic"
        _JA_FONT_BOLD = "MSGothic"
        _CJK_REGISTERED = True
        return True
    except Exception:
        pass
    try:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase import pdfmetrics
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        _JA_FONT      = "HeiseiKakuGo-W5"
        _JA_FONT_BOLD = "HeiseiKakuGo-W5"
        _CJK_REGISTERED = True
        return True
    except Exception:
        return False

def register_cyrillic_font():
    """Register Arial TTF (supports Cyrillic) from Windows Fonts once."""
    global _CYR_REGISTERED
    if _CYR_REGISTERED:
        return True
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase import pdfmetrics
        pdfmetrics.registerFont(TTFont("ArialUA", r"C:\Windows\Fonts\arial.ttf"))
        pdfmetrics.registerFont(TTFont("ArialUA-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
        _CYR_REGISTERED = True
        return True
    except Exception:
        return False

def pdf_font(lang, bold=False):
    """Return the appropriate ReportLab font name for the given language."""
    if lang == "JA" and register_cjk_font():
        return _JA_FONT_BOLD if bold else _JA_FONT
    if lang == "UA" and register_cyrillic_font():
        return "ArialUA-Bold" if bold else "ArialUA"
    return "Helvetica-Bold" if bold else "Helvetica"


def make_footer(source_name, page_offset=0):
    """
    Ritorna un callable (canvas, doc) per ReportLab.
    Numero pagina centrato, nome sorgente (senza estensione) a destra.
    page_offset: aggiunto al numero di pagina interno (per numerazione globale).
    """
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(_FONT, _SIZE)
        canvas.setFillColor(_GRAY)
        w      = doc.pagesize[0]
        margin = 20 * mm
        canvas.drawCentredString(w / 2.0,    _Y_MM * mm, str(doc.page + page_offset))
        canvas.drawRightString(w - margin,   _Y_MM * mm, source_name)
        canvas.restoreState()
    return _footer
