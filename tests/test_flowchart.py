"""Test del layout flowchart: archi ortogonali, niente merge che attraversa le box,
e verifica delle nuove chiavi di log tradotte."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
R1 = os.path.join(os.path.dirname(HERE), "R1")

from docs.flowchart import build_flowcharts, generate_pdf, Shape


def _seg_crosses_box(x, y0, y1, box, margin=2.0):
    """True se il segmento verticale x=cost da y0..y1 attraversa il corpo della box."""
    lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
    bx0, bx1 = box.cx - box.w/2 + margin, box.cx + box.w/2 - margin
    by0, by1 = box.cy - box.h/2 + margin, box.cy + box.h/2 - margin
    return (bx0 < x < bx1) and (lo < by1 and hi > by0)


def test_no_merge_through_box():
    fcs = build_flowcharts(R1)
    assert fcs, "nessun flowchart costruito da R1"
    boxes_kinds = {'io', 'proc', 'call', 'call_plain', 'move', 'alarm', 'label', 'jump'}
    crossings = 0
    for fc in fcs:
        boxes = [s for s in fc.shapes if s.kind in boxes_kinds]
        for e in fc.edges:
            if e.via_x is None:
                continue
            # Il segmento verticale dell'arco di merge è a x = via_x, da y1 a y2.
            for b in boxes:
                if _seg_crosses_box(e.via_x, e.y1, e.y2, b):
                    crossings += 1
    print(f"  flowchart={len(fcs)}, attraversamenti merge→box: {crossings}")
    assert crossings == 0, f"archi di merge che attraversano box: {crossings}"
    print("OK test_no_merge_through_box")


def test_all_edges_orthogonal_render():
    """Genera i PDF di tutti i flowchart senza errori (robustezza)."""
    fcs = build_flowcharts(R1)
    out = os.path.join(tempfile.mkdtemp(prefix="fc_"), "fc.pdf")
    ok = generate_pdf(fcs, out, lang="IT")
    assert os.path.isfile(out), "PDF flowchart non generato"
    from pypdf import PdfReader
    n = len(PdfReader(out).pages)
    print(f"  PDF flowchart generato, pagine={n}")
    assert n >= 1
    print("OK test_all_edges_orthogonal_render")


def test_via_x_present():
    """I chart con IF/ELSEIF devono avere archi di merge instradati via lane."""
    fcs = build_flowcharts(R1)
    fc = next((f for f in fcs if f.name == "RANGE"), None)
    assert fc is not None
    via = [e for e in fc.edges if e.via_x is not None]
    print(f"  RANGE: archi merge con via_x = {len(via)}")
    assert via, "nessun arco di merge instradato via lane in RANGE"
    print("OK test_via_x_present")


def test_new_log_keys():
    from translations import TRANSLATIONS
    keys = ["log_translate_attachment", "log_backup_no_data", "log_backup_no_pdf_data"]
    for lang in ("IT", "EN", "FR", "DE", "ES", "UA", "JA"):
        for k in keys:
            assert TRANSLATIONS.get(lang, {}).get(k), f"{k} mancante in {lang}"
    # placeholder corretti
    t = TRANSLATIONS["IT"]["log_translate_attachment"]
    assert "{0}" in t and "{1}" in t and "{2}" in t
    print("OK test_new_log_keys")


if __name__ == "__main__":
    test_new_log_keys()
    test_no_merge_through_box()
    test_via_x_present()
    test_all_edges_orthogonal_render()
    print("=== TUTTI I TEST FLOWCHART OK ===")
