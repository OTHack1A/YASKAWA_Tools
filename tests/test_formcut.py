"""Test del modulo FormCut (FORMCUT.CND) e integrazione in Completa."""
import os
import sys
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
R1 = os.path.join(os.path.dirname(HERE), "R1")

from pypdf import PdfReader

# 2 form cut attivi + 1 tutto-zero (da ignorare)
SAMPLE = """//FORMCUT 1
0,150.000,0.000
0.000,0.000,10.000
0.50,0.00,1.00
0.00,0.00,0.00
0.250,0,0,0,5.0,45.0,0.0
//FORMCUT 2
1,80.000,40.000
0.000,0.000,5.000
1.00,0.00,2.00
0.00,0.00,0.00
0.000,1,0,0,2.0,30.0,1.0
//FORMCUT 3
0,0.000,0.000
0.000,0.000,0.000
0.00,0.00,0.00
0.00,0.00,0.00
0.000,0,0,0,0.0,0.0,0.0
"""


# Un job che USA i form cut 1 e 2 (FCF#)
JOB = """/JOB
//NAME TAGLIO
NOP
MOVL V=138.0
FORMAPR FCF#(1)
CALL JOB:LASERON
FORMCUT FCF#(1)
FORMCUT FCF#(2)
CALL JOB:LASEROFF
END
"""


def _make_folder(with_job=True):
    base = tempfile.mkdtemp(prefix="fc_")
    with open(os.path.join(base, "FORMCUT.CND"), "w", encoding="latin-1", newline="\r\n") as f:
        f.write(SAMPLE)
    if with_job:
        with open(os.path.join(base, "TAGLIO.JBI"), "w", encoding="latin-1", newline="\r\n") as f:
            f.write(JOB)
    return base


def test_translations_all_langs():
    from translations import TRANSLATIONS
    keys = ["menu_formcut", "completa_section_formcut", "formcut_title",
            "formcut_desc", "formcut_caption", "formcut_no_data",
            "log_formcut_opened", "log_formcut_generated", "log_formcut_no_file",
            "formcut_lbl_num", "formcut_lbl_figure", "formcut_lbl_dim",
            "formcut_lbl_speed", "formcut_lbl_angle", "formcut_lbl_dir",
            "formcut_shape_0", "formcut_shape_1", "formcut_shape_2",
            "formcut_shape_3", "formcut_shape_4",
            "formcut_example_caption", "formcut_example_note", "formcut_example_code",
            "formcut_lbl_used", "formcut_dir_note"]
    for lang in ("IT", "EN", "FR", "DE", "ES", "UA", "JA"):
        for k in keys:
            assert TRANSLATIONS.get(lang, {}).get(k), f"{k} mancante in {lang}"
    print("OK test_translations_all_langs")


def test_tooltip_all_langs():
    import tooltips
    for lang in ("IT", "EN", "FR", "DE", "ES", "UA", "JA"):
        assert tooltips.get("action_formcut", lang), f"tooltip mancante per {lang}"
    print("OK test_tooltip_all_langs")


def test_parser_usage():
    """Solo i form cut USATI nei JBI vengono restituiti, con 'used_in'."""
    from docs.formcut import build_formcuts, find_formcut_usage
    base = _make_folder()
    try:
        usage = find_formcut_usage(base)
        assert usage.get(1) == ["TAGLIO"] and usage.get(2) == ["TAGLIO"], usage
        fcs = build_formcuts(base)
        print(f"[parser] form cut usati: {len(fcs)} -> {[b['num'] for b in fcs]}")
        assert len(fcs) == 2, f"attesi 2 usati, trovati {len(fcs)}"
        assert fcs[0]["num"] == 1 and fcs[1]["num"] == 2
        assert fcs[0]["used_in"] == ["TAGLIO"]
        assert fcs[0]["lines"][0] == ["0", "150.000", "0.000"]
        print("OK test_parser_usage")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_not_used():
    """FORMCUT.CND presente ma nessun JBI lo usa → nessun form cut elencato."""
    from docs.formcut import build_formcuts, generate_pdf
    base = _make_folder(with_job=False)   # niente JBI
    try:
        assert build_formcuts(base) == [], "non dovrebbe esserci alcun form cut usato"
        out = os.path.join(base, "out.pdf")
        assert generate_pdf(base, out, lang="IT") and os.path.isfile(out)
        txt = " ".join((PdfReader(out).pages[0].extract_text() or "").split())
        assert "Nessun Form Cut" in txt, "manca il messaggio 'nessun form cut'"
        print("OK test_not_used")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_no_file():
    from docs.formcut import build_formcuts, generate_pdf
    base = tempfile.mkdtemp(prefix="fc_empty_")
    try:
        assert build_formcuts(base) == []
        out = os.path.join(base, "out.pdf")
        assert generate_pdf(base, out, lang="IT") and os.path.isfile(out)
        assert len(PdfReader(out).pages) >= 1
        print("OK test_no_file")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_pdf_all_langs():
    from docs.formcut import generate_pdf
    base = _make_folder()
    try:
        for lang in ("IT", "EN", "FR", "DE", "ES", "UA", "JA"):
            out = os.path.join(base, f"out_{lang}.pdf")
            assert generate_pdf(base, out, lang=lang) and os.path.isfile(out), lang
            txt = "".join((p.extract_text() or "") for p in PdfReader(out).pages)
            norm = " ".join(txt.split())
            assert "FCF#" in norm, f"esempio FCF# assente in {lang}"
            assert "CW" in norm and "CCW" in norm, f"direzioni assenti in {lang}"
        print("OK test_pdf_all_langs (7 lingue)")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_table_and_example():
    """Tabella con intestazioni di campo + blocco esempio; niente disclaimer."""
    from docs.formcut import generate_pdf
    base = _make_folder()
    try:
        out = os.path.join(base, "labels.pdf")
        assert generate_pdf(base, out, lang="IT")
        txt = "".join((p.extract_text() or "") for p in PdfReader(out).pages)
        norm = " ".join(txt.split())
        # Intestazioni tabella + valori interpretati
        for needle in ("Figura", "Velocità", "Angolo", "Direzione",
                       "Cerchio", "Rettangolo", "CW", "CCW", "45.0"):
            assert needle in norm, f"'{needle}' assente nel PDF FormCut"
        assert "80.000" in norm and "40.000" in norm, "dimensioni rettangolo assenti"
        # Blocco esempio d'uso (istruzioni reali)
        for needle in ("FORMAPR", "FORMCUT", "FCF#"):
            assert needle in norm, f"esempio: '{needle}' assente"
        # Colonna "Usato in" + nome del job che usa i form cut
        assert "Usato in" in norm, "colonna 'Usato in' assente"
        assert "TAGLIO" in norm, "job che usa i form cut assente"
        # Nota CW/CCW
        assert "orario" in norm and "antiorario" in norm, "nota direzione assente"
        # Il disclaimer rimosso non deve più comparire
        assert "non è pubblicato" not in norm, "disclaimer ancora presente"
        print("OK test_table_and_example")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_footer_left_uppercase():
    """Il nome sezione nel footer deve essere a SINISTRA e MAIUSCOLO (stile Targhetta)."""
    from docs.formcut import generate_pdf
    base = _make_folder()
    try:
        out = os.path.join(base, "footer.pdf")
        assert generate_pdf(base, out, lang="IT")
        page = PdfReader(out).pages[0]
        page_w = float(page.mediabox.width)
        hits = []
        def _visit(text, cm, tm, font_dict, font_size):
            try:
                if text and text.strip():
                    hits.append((text, float(tm[4]), float(tm[5])))
            except Exception:
                pass
        try:
            page.extract_text(visitor_text=_visit)
        except TypeError:
            txt = page.extract_text() or ""
            assert "FORMCUT" in txt
            print("OK test_footer_left_uppercase (solo verifica testo)")
            return
        # Il footer è il frammento ESATTO "FORMCUT" (la descrizione contiene
        # "FORMCUT.CND" e le card "FORMCUT 1/2" → escluse dal match esatto).
        foot = [(t, x, y) for (t, x, y) in hits if t.strip() == "FORMCUT"]
        assert foot, f"footer esatto 'FORMCUT' non trovato. Frammenti: {[h[0] for h in hits][:10]}"
        t, x, y = foot[0]
        print(f"  footer='{t.strip()}' x={x:.0f} center={page_w/2:.0f}")
        assert x < page_w / 2.0, f"footer non a sinistra (x={x:.0f})"
        assert t.strip() == t.strip().upper(), "footer non maiuscolo"
        print("OK test_footer_left_uppercase")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_completa_integration():
    from docs.completa import generate_completa
    base = tempfile.mkdtemp(prefix="fc_completa_")
    folder = os.path.join(base, "R1")
    shutil.copytree(R1, folder)
    # forza un FORMCUT.CND noto + un job che lo usa (altrimenti la sezione è vuota)
    with open(os.path.join(folder, "FORMCUT.CND"), "w", encoding="latin-1", newline="\r\n") as f:
        f.write(SAMPLE)
    with open(os.path.join(folder, "TAGLIO.JBI"), "w", encoding="latin-1", newline="\r\n") as f:
        f.write(JOB)
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

        fc_page = next((i for i in range(n) if "TAGLIO SAGOME" in txt(i)), None)
        toc_has = any("FormCut" in txt(i) for i in range(1, 6))

        idx = next((i for i in range(n) if "INDICE" in txt(i)), 1)
        n_toc = 0; j = idx
        while j < n and ("Sezione" in txt(j) or j == idx):
            n_toc += 1; j += 1
        link_ok = False
        for p in range(idx, idx + n_toc):
            ann = reader.pages[p].get("/Annots")
            if not ann: continue
            for a in ann:
                o = a.get_object()
                if o.get("/Subtype") == "/Link":
                    d = o.get("/Dest")
                    try:
                        if d is not None and int(d[0]) == fc_page:
                            link_ok = True
                    except Exception:
                        pass

        print(f"[completa] pagine={n}, errori={len(errs)}, pagina formcut={fc_page}, "
              f"TOC ha voce={toc_has}, link_ok={link_ok}")
        for e in errs: print("  ERR", e)
        assert len(errs) == 0, f"errori: {errs}"
        assert fc_page is not None, "sezione FormCut assente"
        assert toc_has, "voce FormCut assente nel sommario"
        assert link_ok, "link sommario non punta alla sezione FormCut"
        print("OK test_completa_integration")
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    test_translations_all_langs()
    test_tooltip_all_langs()
    test_parser_usage()
    test_not_used()
    test_no_file()
    test_pdf_all_langs()
    test_table_and_example()
    test_footer_left_uppercase()
    test_completa_integration()
    print("=== TUTTI I TEST FORMCUT OK ===")
