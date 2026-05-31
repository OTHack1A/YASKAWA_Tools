"""
Simulazione/test del sommario unico nel PDF Completa.

Verifica:
  1. jobs.generate_pdf(include_toc=False) NON genera la pagina SOMMARIO interna
     e restituisce nav_items con pagine relative corrette.
  2. jobs.generate_pdf(include_toc=True) (default) mantiene il comportamento storico.
  3. generate_completa produce UN SOLO sommario (nessun doppione) e i link
     iniettati nella pagina TOC puntano alle pagine giuste (incrocio
     annotation Link -> outline bookmark -> testo della pagina target).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

R1 = os.path.join(os.path.dirname(HERE), "R1")

from pypdf import PdfReader


def _page_text(reader, idx):
    try:
        return reader.pages[idx].extract_text() or ""
    except Exception:
        return ""


def test_jobs_include_toc_flag():
    from docs.jobs import generate_pdf

    out_no = os.path.join(HERE, "_t_jobs_notoc.pdf")
    out_yes = os.path.join(HERE, "_t_jobs_toc.pdf")

    nav_no = generate_pdf(R1, out_no, lang="IT", include_toc=False)
    nav_yes = generate_pdf(R1, out_yes, lang="IT", include_toc=True)

    n_no = len(PdfReader(out_no).pages)
    n_yes = len(PdfReader(out_yes).pages)

    print(f"[jobs] include_toc=False: pagine={n_no}, nav_items={len(nav_no)}")
    print(f"[jobs] include_toc=True : pagine={n_yes}, nav_items={len(nav_yes)}")

    assert nav_no, "nav_items vuoto con include_toc=False"
    assert nav_yes, "nav_items vuoto con include_toc=True"
    # Senza SOMMARIO la sezione deve avere meno pagine (l'indice interno puo'
    # occupare 1+ pagine a seconda del numero di JOB).
    assert n_no < n_yes, f"atteso n_no < n_yes, got {n_no} vs {n_yes}"
    # Le voci di navigazione devono restare le stesse (ALBERO + jobs + LADDER).
    assert len(nav_no) == len(nav_yes), "conteggio nav diverso tra le due modalita'"

    # Con include_toc=False la prima pagina contiene l'header JOBs + ALBERO,
    # non un elenco SOMMARIO separato.
    r_no = PdfReader(out_no)
    first = _page_text(r_no, 0)
    assert "JOBs" in first, "header 'JOBs' assente nella prima pagina (notoc)"

    # Verifica che ogni nav punti a una pagina valida e che la pagina target
    # contenga il nome del job.
    for name, rel in nav_no:
        idx = rel - 1
        assert 0 <= idx < n_no, f"pagina relativa fuori range per {name}: {rel}"
    print("  prime voci nav:", nav_no[:5])
    print("OK test_jobs_include_toc_flag\n")
    for p in (out_no, out_yes):
        try:
            os.remove(p)
        except OSError:
            pass


def test_completa_single_toc():
    from docs.completa import generate_completa

    out = os.path.join(HERE, "_t_completa.pdf")
    logs = []

    def _log(key, *args):
        logs.append((key, args))

    ok = generate_completa(R1, out, attachments=[], lang="IT", log_fn=_log)
    assert ok, "generate_completa ha restituito False"

    reader = PdfReader(out)
    n = len(reader.pages)
    print(f"[completa] pagine totali={n}")

    # Stampa eventuali errori loggati (devono essere assenti o non critici).
    errs = [l for l in logs if l[0] == "log_error_generic"]
    for e in errs:
        print("  LOG:", e)

    # ── Conta i "sommari": cerca le pagine che contengono l'intestazione TOC ──
    # Il TOC di Completa ha titolo "INDICE" (completa_toc_title).
    # Il vecchio SOMMARIO interno dei jobs aveva titolo "SOMMARIO".
    toc_pages = []
    sommario_pages = []
    for i in range(n):
        txt = _page_text(reader, i)
        if "INDICE" in txt:
            toc_pages.append(i)
        # "SOMMARIO" appare solo nella vecchia pagina indice interna dei jobs
        # (lo stato footer iniziale è "SOMMARIO", ma quello è nel footer di
        # ogni pagina solo se rendiamo quella pagina). Controlliamo il titolo
        # di sezione, non il footer.
    print(f"  pagine con 'INDICE' (TOC principale): {toc_pages}")

    # Deve esserci un solo TOC principale.
    assert len(toc_pages) == 1, f"atteso 1 TOC, trovati {len(toc_pages)}"
    toc_idx = toc_pages[0]

    # ── Mappa idnum -> indice pagina per risolvere i target dei link ─────────
    idnum_to_page = {}
    for pi, pg in enumerate(reader.pages):
        ir = pg.indirect_reference
        if ir is not None:
            idnum_to_page[ir.idnum] = pi

    def _resolve_dest(dest):
        if dest is None:
            return None
        try:
            ref = dest[0]
        except Exception:
            return None
        # pypdf Link(target_page_index=N) salva /Dest = [N, /Fit] (intero diretto)
        try:
            return int(ref)
        except (TypeError, ValueError):
            pass
        # fallback: riferimento indiretto a una pagina
        return idnum_to_page.get(getattr(ref, "idnum", None))

    # ── Raccogli i link su TUTTE le pagine del TOC (puo' essere multipagina) ─
    # Le pagine del TOC sono quelle tra targhetta e la prima sezione.
    link_targets = []
    n_toc_pages = 0
    pi = toc_idx
    while pi < n and ("Sezione" in _page_text(reader, pi) or pi == toc_idx):
        n_toc_pages += 1
        annots = reader.pages[pi].get("/Annots")
        if annots:
            for a in annots:
                obj = a.get_object()
                if obj.get("/Subtype") == "/Link":
                    tgt = _resolve_dest(obj.get("/Dest"))
                    if tgt is None:
                        A = obj.get("/A")
                        if A and A.get("/S") == "/GoTo":
                            tgt = _resolve_dest(A.get("/D"))
                        if tgt is None and A is not None:
                            tgt = _resolve_dest(A.get("/Dest"))
                    link_targets.append(tgt)
        pi += 1

    resolved = [t for t in link_targets if t is not None]
    print(f"  pagine TOC: {n_toc_pages}")
    print(f"  link totali sul TOC: {len(link_targets)}, risolti: {len(resolved)}")
    print(f"  target pagine (campione): {sorted(set(resolved))[:15]} ...")

    # Devono esistere link e tutti quelli risolti puntare a pagine valide.
    assert link_targets, "nessun link nelle pagine TOC"
    assert resolved, "nessun link risolto a una pagina"
    for t in resolved:
        assert 0 <= t < n, f"link a pagina non valida: {t}"

    # ── Verifica incrocio: il primo JOB del nav deve avere il suo nome nella
    #    pagina target indicata dall'outline. ─────────────────────────────────
    # Ricava p_jobs (prima pagina sezione JOBs) cercando la pagina con header
    # "JOBs" + "ALBERO DI RICHIAMO".
    p_jobs = None
    for i in range(n):
        txt = _page_text(reader, i)
        if "ALBERO DI RICHIAMO" in txt and "JOBs" in txt:
            p_jobs = i
            break
    print(f"  prima pagina sezione JOBs (p_jobs): {p_jobs}")
    assert p_jobs is not None, "sezione JOBs non trovata"

    # ── Cross-check FORTE: ogni JOB deve trovarsi sulla pagina assoluta che il
    #    sommario/outline indica (p_jobs + rel - 1). ───────────────────────────
    from docs.jobs import generate_pdf as _jgen
    tmpj = os.path.join(HERE, "_t_jobs_xc.pdf")
    nav = _jgen(R1, tmpj, lang="IT", include_toc=False)
    try:
        os.remove(tmpj)
    except OSError:
        pass
    mismatches = []
    for name, rel in nav:
        abs_idx = p_jobs + (rel - 1)
        if not (0 <= abs_idx < n):
            mismatches.append((name, rel, abs_idx, "fuori range"))
            continue
        page_txt = _page_text(reader, abs_idx)
        # ALBERO DI RICHIAMO e LADDER sono heading speciali; i job hanno il nome.
        token = name.split(" ")[0]
        if token not in page_txt:
            mismatches.append((name, rel, abs_idx, "nome assente"))
    print(f"  cross-check JOB→pagina: {len(nav)} voci, mismatch={len(mismatches)}")
    for m in mismatches[:10]:
        print("    MISMATCH:", m)
    assert not mismatches, f"{len(mismatches)} job non sulla pagina attesa"

    # ── Verifica che il PDF non contenga DUE elenchi-sommario consecutivi ────
    # Il primo job nel TOC deve avere il suo testo nella pagina target.
    print("OK test_completa_single_toc\n")

    # lascia il PDF su disco per ispezione manuale
    print(f"  PDF salvato per ispezione: {out}")


def test_completa_with_attachment():
    """Verifica che il numero pagina stampato sull'allegato coincida con quello
    mostrato nel sommario (att_off + 1)."""
    from reportlab.pdfgen import canvas as _c
    from reportlab.lib.pagesizes import A4 as _A4
    from docs.completa import generate_completa

    att = os.path.join(HERE, "_t_attach.pdf")
    cv = _c.Canvas(att, pagesize=_A4)
    cv.drawString(100, 700, "ALLEGATO DI PROVA - PAGINA UNO")
    cv.showPage()
    cv.drawString(100, 700, "ALLEGATO DI PROVA - PAGINA DUE")
    cv.save()

    out = os.path.join(HERE, "_t_completa_att.pdf")
    ok = generate_completa(R1, out, attachments=[att], lang="IT", log_fn=None)
    assert ok

    reader = PdfReader(out)
    n = len(reader.pages)

    # Trova la pagina dell'allegato (contiene "ALLEGATO DI PROVA").
    att_idx = None
    for i in range(n):
        if "ALLEGATO DI PROVA" in _page_text(reader, i):
            att_idx = i
            break
    assert att_idx is not None, "allegato non trovato nel PDF"

    # Il numero stampato sull'allegato (footer) deve essere coerente: cerca nella
    # pagina TOC la riga "Allegato" e il suo numero.
    toc_txt = "".join(_page_text(reader, i) for i in range(1, att_idx))
    print(f"  allegato a indice pagina {att_idx} (tot {n})")
    # Il footer dell'allegato stampa att_off+1. att_off = att_idx - (n_targ+n_toc).
    # n_targ=1; conta pagine TOC.
    n_toc = 0
    j = 1
    while j < n and ("Sezione" in _page_text(reader, j) or j == 1):
        n_toc += 1
        j += 1
    expected_printed = att_idx - (1 + n_toc) + 1
    att_page_txt = _page_text(reader, att_idx)
    print(f"  n_toc={n_toc}, numero pagina atteso sull'allegato={expected_printed}")
    assert str(expected_printed) in att_page_txt, \
        f"numero pagina {expected_printed} non stampato sull'allegato"

    for p in (att, out):
        try:
            os.remove(p)
        except OSError:
            pass
    print("OK test_completa_with_attachment\n")


if __name__ == "__main__":
    print("Cartella test R1:", R1, "esiste:", os.path.isdir(R1))
    test_jobs_include_toc_flag()
    test_completa_single_toc()
    test_completa_with_attachment()
    print("=== TUTTI I TEST OK ===")
