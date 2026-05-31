"""
Test di sicurezza (OWASP A03 Injection / robustezza) per i generatori PDF/Excel.

Verifica che contenuto ostile proveniente dai file robot e dal nome cartella:
  - NON faccia fallire la generazione del PDF (reportlab markup injection)
  - venga neutralizzato negli export Excel (formula/CSV injection)
"""
import os
import sys
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

R1 = os.path.join(os.path.dirname(HERE), "R1")

from pypdf import PdfReader


# ── Test helper functions ──────────────────────────────────────────────────────

def test_helpers():
    from docs.utils import xml_escape, excel_safe
    assert xml_escape("a<b>&c") == "a&lt;b&gt;&amp;c"
    assert xml_escape(None) == ""
    assert xml_escape(123) == "123"
    # & deve essere escapato per primo
    assert xml_escape("<&>") == "&lt;&amp;&gt;"
    # excel_safe: prefissa solo i trigger di formula, NON il meno (numeri negativi)
    assert excel_safe("=cmd()") == "'=cmd()"
    assert excel_safe("+1+1") == "'+1+1"
    assert excel_safe("@SUM") == "'@SUM"
    assert excel_safe("-5") == "-5"        # numero negativo preservato
    assert excel_safe("normale") == "normale"
    assert excel_safe(42) == 42
    assert excel_safe("") == ""
    print("OK test_helpers")


def _make_malicious_folder():
    """Copia R1 in una cartella col nome contenente '&' e inietta contenuto ostile."""
    base = tempfile.mkdtemp(prefix="sec_")
    # Windows consente '&' nei nomi cartella (non '<>:"/\\|?*')
    folder = os.path.join(base, "R&D_test")
    shutil.copytree(R1, folder)

    # Inietta markup ostile in SYSTEM.SYS (targhetta/panel leggono questo)
    sys_path = os.path.join(folder, "SYSTEM.SYS")
    payload = (
        "/SYSTEM\r\n"
        "//ROBOT NAME: GP<8>L & <link href='evil'>X</link>\r\n"
        "//SYSTEM NO: 1 & 2 < 3 > 0\r\n"
        "//APPLI: <font color='red'>RED</font>\r\n"
        "//REVISION\r\n"
        "BOARD<1> v1.0 & beta\r\n"
        "//CONTROL POWER\r\n"
        "TOTAL : 100:00'00,2025\r\n"
    )
    with open(sys_path, "w", encoding="utf-8", newline="") as f:
        f.write(payload)

    # Inietta una rete con valore ostile
    ipnet_path = os.path.join(folder, "IPNETCFG.DAT")
    with open(ipnet_path, "w", encoding="latin-1", newline="") as f:
        f.write("//IPNETCFG\r\n///HOST\r\n<b>evilhost</b> & co\r\n=cmd|'/c calc'!A1\r\n")

    return base, folder


def test_pdf_robustness():
    base, folder = _make_malicious_folder()
    try:
        out = os.path.join(base, "out.pdf")
        results = {}

        # targhetta
        from docs.targhetta import generate_pdf as targ
        targ(folder, out, lang="IT")
        results["targhetta"] = len(PdfReader(out).pages)

        # panel
        from docs.panel import generate_pdf as panel
        try:
            panel(folder, out, lang="IT")
            results["panel"] = len(PdfReader(out).pages)
        except Exception as e:
            results["panel"] = f"ERR {e}"

        # params (serve ALL.PRM; se assente la funzione ritorna senza PDF -> ok)
        from docs.params import generate_pdf as params
        params(folder, out, lang="IT")

        # ipnet
        from docs.ipnet import load_network_config, generate_ipnet_pdf
        rows = load_network_config(folder)
        ok_ip = generate_ipnet_pdf(rows, out, folder_name=os.path.basename(folder), lang="IT")
        results["ipnet_pdf"] = ok_ip

        # jobs (header con folder_name '&')
        from docs.jobs import generate_pdf as jobs
        jobs(folder, out, lang="IT")
        results["jobs"] = len(PdfReader(out).pages)

        # completa (sommario con label e folder_name ostili)
        from docs.completa import generate_completa
        errs = []
        ok_c = generate_completa(folder, out, attachments=[], lang="IT",
                                 log_fn=lambda k, *a: errs.append((k, a)))
        results["completa_pages"] = len(PdfReader(out).pages)
        crit = [e for e in errs if e[0] == "log_error_generic"]
        results["completa_errors"] = len(crit)

        print("Risultati robustezza PDF:")
        for k, v in results.items():
            print(f"  {k}: {v}")

        assert results["targhetta"] >= 1
        assert isinstance(results["panel"], int) and results["panel"] >= 1
        assert results["ipnet_pdf"] is True
        assert results["jobs"] >= 1
        assert results["completa_pages"] >= 1
        # La generazione completa non deve loggare errori critici nonostante l'input ostile
        assert results["completa_errors"] == 0, f"errori completa: {crit}"
        print("OK test_pdf_robustness")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_excel_formula_injection():
    base, folder = _make_malicious_folder()
    try:
        import openpyxl
        out = os.path.join(base, "ipnet.xlsx")
        from docs.ipnet import load_network_config, generate_ipnet_excel
        rows = load_network_config(folder)
        ok = generate_ipnet_excel(rows, out, folder_name="R&D", lang="IT")
        assert ok, "generate_ipnet_excel fallito"

        wb = openpyxl.load_workbook(out)
        ws = wb.active
        dangerous = []
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                v = cell.value
                if isinstance(v, str) and v[:1] in ("=", "+", "@"):
                    dangerous.append(v)
        print(f"  celle con formula attiva residue: {len(dangerous)}")
        assert not dangerous, f"formula injection non neutralizzata: {dangerous}"
        print("OK test_excel_formula_injection")
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    print("R1:", R1, "esiste:", os.path.isdir(R1))
    test_helpers()
    test_pdf_robustness()
    test_excel_formula_injection()
    print("=== TUTTI I TEST SICUREZZA OK ===")
