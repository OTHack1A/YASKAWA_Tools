"""Test del modulo Cubo interferenza (CUBEINTF.CND) e integrazione in Completa."""
import os
import sys
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
R1 = os.path.join(os.path.dirname(HERE), "R1")

from pypdf import PdfReader

# CUBEINTF.CND di prova: cubo 1 (con nome), cubo 2 (senza nome, attivo),
# cubo 3 (tutti zero → da ignorare), cubo 4 (tutti zero, senza nome → ignorare).
SAMPLE = """//CUBEINTF 1
///NAME KENTAI
3,1,1
500000,1000000,2500000,0,0,0,0,0
-1000000,-1000000,-1000000,0,0,0,0,0
1
0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0
//CUBEINTF 2
///NAME
0,2,2
1200000,800000,300000,0,0,0,0,0
-500000,-200000,0,0,0,0,0,0
3
0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0
//CUBEINTF 3
///NAME
0,0,0
0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0
0
0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0
//CUBEINTF 4
///NAME
0,0,0
0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0
0
0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0
"""


def _make_folder():
    base = tempfile.mkdtemp(prefix="cube_")
    with open(os.path.join(base, "CUBEINTF.CND"), "w", encoding="latin-1", newline="\r\n") as f:
        f.write(SAMPLE)
    return base


def test_parser():
    from docs.cubeintf import build_cubes
    base = _make_folder()
    try:
        cubes = build_cubes(base)
        print(f"[parser] cubi attivi: {len(cubes)}")
        for c in cubes:
            print("  ", c["num"], repr(c["name"]), "coord=", c["coord"],
                  "group=", c["group"], "uf=", c["uf"], "max=", c["max"], "min=", c["min"])
        assert len(cubes) == 2, f"attesi 2 cubi attivi, trovati {len(cubes)}"
        c1 = cubes[0]
        assert c1["num"] == 1 and c1["name"] == "KENTAI"
        # 500000 micron -> 500.0 mm
        assert abs(c1["max"][0] - 500.0) < 1e-6, c1["max"]
        assert abs(c1["min"][0] + 1000.0) < 1e-6, c1["min"]
        # cubo 2: attivo anche senza nome
        c2 = cubes[1]
        assert c2["num"] == 2 and c2["name"] == ""
        print("OK test_parser")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_no_file():
    from docs.cubeintf import build_cubes, generate_pdf
    base = tempfile.mkdtemp(prefix="cube_empty_")
    try:
        assert build_cubes(base) == []
        out = os.path.join(base, "out.pdf")
        ok = generate_pdf(base, out, lang="IT")
        assert ok and os.path.isfile(out), "PDF 'no cubi' non generato"
        assert len(PdfReader(out).pages) >= 1
        print("OK test_no_file (PDF 'nessun cubo' generato senza errori)")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_pdf_all_langs():
    from docs.cubeintf import generate_pdf
    base = _make_folder()
    try:
        for lang in ("IT", "EN", "FR", "DE", "ES", "UA", "JA"):
            out = os.path.join(base, f"out_{lang}.pdf")
            ok = generate_pdf(base, out, lang=lang)
            assert ok and os.path.isfile(out), f"PDF non generato per {lang}"
            txt = PdfReader(out).pages[0].extract_text() or ""
            # KENTAI deve comparire in tutte le lingue (nome cubo invariante)
            assert "KENTAI" in txt, f"KENTAI assente nel PDF {lang}"
        print("OK test_pdf_all_langs (7 lingue)")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_footer_right_uppercase():
    """Il nome sezione nel footer deve essere MAIUSCOLO e allineato a destra."""
    from docs.cubeintf import generate_pdf
    base = _make_folder()
    try:
        out = os.path.join(base, "footer.pdf")
        assert generate_pdf(base, out, lang="IT")
        reader = PdfReader(out)
        page = reader.pages[0]
        page_w = float(page.mediabox.width)

        # Raccogli le posizioni X dei frammenti di testo via visitor.
        hits = []  # (text, x)
        def _visit(text, cm, tm, font_dict, font_size):
            try:
                if text and text.strip():
                    hits.append((text, float(tm[4])))
            except Exception:
                pass
        try:
            page.extract_text(visitor_text=_visit)
        except TypeError:
            # versioni pypdf senza visitor_text → fallback solo sul testo
            txt = page.extract_text() or ""
            assert "CUBO INTERFERENZA" in txt, "label footer maiuscola assente"
            assert "Cubo interferenza" not in txt, "label footer non maiuscola"
            print("OK test_footer_right_uppercase (solo verifica testo)")
            return

        full = "".join(h[0] for h in hits)
        assert "CUBO INTERFERENZA" in full or all(
            tok in full for tok in ("CUBO", "INTERFERENZA")), "label footer maiuscola assente"

        # Trova la X del frammento che contiene 'INTERFERENZA' (il footer).
        xs = [x for (txt, x) in hits if "INTERFERENZA" in txt.upper()]
        assert xs, "frammento footer 'INTERFERENZA' non trovato con posizione"
        x_label = max(xs)
        print(f"  page_w={page_w:.0f}, x_label={x_label:.0f}, center={page_w/2:.0f}")
        assert x_label > page_w / 2.0, \
            f"label footer non a destra (x={x_label:.0f}, center={page_w/2:.0f})"
        print("OK test_footer_right_uppercase")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_completa_integration():
    from docs.completa import generate_completa
    base = tempfile.mkdtemp(prefix="cube_completa_")
    folder = os.path.join(base, "R1")
    shutil.copytree(R1, folder)
    with open(os.path.join(folder, "CUBEINTF.CND"), "w", encoding="latin-1", newline="\r\n") as f:
        f.write(SAMPLE)
    try:
        out = os.path.join(base, "completa.pdf")
        errs = []
        ok = generate_completa(folder, out, attachments=[], lang="IT",
                               log_fn=lambda k, *a: errs.append((k, a)) if k == "log_error_generic" else None)
        assert ok
        reader = PdfReader(out)
        n = len(reader.pages)

        def txt(i):
            try: return reader.pages[i].extract_text() or ""
            except Exception: return ""

        # Trova la pagina della sezione cubi (header "CUBI DI INTERFERENZA")
        cube_page = None
        for i in range(n):
            if "CUBI DI INTERFERENZA" in txt(i):
                cube_page = i
                break
        # Trova la riga "Cubo interferenza" nel sommario (indice)
        toc_has_entry = any("Cubo interferenza" in txt(i) for i in range(1, 5))

        # Verifica link sul TOC che punta alla pagina cubi
        idx = next((i for i in range(n) if "INDICE" in txt(i)), 1)
        n_toc = 0
        j = idx
        while j < n and ("Sezione" in txt(j) or j == idx):
            n_toc += 1; j += 1
        cube_link_ok = False
        for p in range(idx, idx + n_toc):
            ann = reader.pages[p].get("/Annots")
            if not ann: continue
            for a in ann:
                o = a.get_object()
                if o.get("/Subtype") == "/Link":
                    d = o.get("/Dest")
                    try:
                        if d is not None and int(d[0]) == cube_page:
                            cube_link_ok = True
                    except Exception:
                        pass

        print(f"[completa] pagine={n}, errori={len(errs)}, "
              f"pagina cubi={cube_page}, TOC ha voce={toc_has_entry}, link_ok={cube_link_ok}")
        for e in errs: print("  ERR", e)
        assert len(errs) == 0, f"errori critici: {errs}"
        assert cube_page is not None, "sezione cubi assente nel PDF completo"
        assert toc_has_entry, "voce 'Cubo interferenza' assente nel sommario"
        assert cube_link_ok, "link del sommario non punta alla sezione cubi"
        print("OK test_completa_integration")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_tooltip_all_langs():
    """Il tooltip della voce di menu deve esistere in tutte le lingue."""
    import tooltips
    for lang in ("IT", "EN", "FR", "DE", "ES", "UA", "JA"):
        tip = tooltips.get("action_cubeintf", lang)
        assert tip, f"tooltip action_cubeintf mancante per {lang}"
    print("OK test_tooltip_all_langs")


def test_translations_all_langs():
    """Tutte le chiavi della sezione devono esistere in tutte le lingue."""
    from translations import TRANSLATIONS
    keys = ["menu_cubeintf", "completa_section_cubeintf", "cubeintf_title",
            "cubeintf_col_num", "cubeintf_col_name", "cubeintf_col_group",
            "cubeintf_col_coord", "cubeintf_col_uf", "cubeintf_col_max",
            "cubeintf_col_min", "cubeintf_no_data", "log_cubeintf_opened",
            "log_cubeintf_generated", "log_cubeintf_no_file"]
    for lang in ("IT", "EN", "FR", "DE", "ES", "UA", "JA"):
        for k in keys:
            assert TRANSLATIONS.get(lang, {}).get(k), f"{k} mancante in {lang}"
    print("OK test_translations_all_langs")


if __name__ == "__main__":
    test_translations_all_langs()
    test_tooltip_all_langs()
    test_parser()
    test_no_file()
    test_pdf_all_langs()
    test_footer_right_uppercase()
    test_completa_integration()
    print("=== TUTTI I TEST CUBEINTF OK ===")
