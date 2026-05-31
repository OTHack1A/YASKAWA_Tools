import sys
sys.path.insert(0, ".")

print("=== Testing imports ===")
try:
    from docs.utils import pdf_font, register_cjk_font
    ok = register_cjk_font()
    print("CJK font registered:", ok)
    print("JA font:", pdf_font("JA"))
    print("IT font:", pdf_font("IT"))
except Exception as e:
    print("FAIL utils:", e)

try:
    from docs.params import export_excel, parse_all_prm
    print("params OK")
except Exception as e:
    print("FAIL params:", e)

try:
    from docs.jobs import generate_pdf
    print("jobs OK")
except Exception as e:
    print("FAIL jobs:", e)

try:
    from docs.panel import generate_pdf
    print("panel OK")
except Exception as e:
    print("FAIL panel:", e)

try:
    from docs.logdata import generate_logdata_pdf, parse_logdata
    print("logdata OK")
except Exception as e:
    print("FAIL logdata:", e)

try:
    from translations import TRANSLATIONS
    ja = TRANSLATIONS.get("JA", {})
    print("JA keys:", len(ja))
    for k in ["menu_ga500_params","menu_help_params","menu_help_known","menu_logdata","menu_completa"]:
        print(f"  {k}: {ja.get(k, 'MISSING')}")
except Exception as e:
    print("FAIL translations:", e)

import ast
for fname in ["gui/main_window.py", "gui/uframe_view.py"]:
    with open(fname,"r",encoding="utf-8") as f:
        src = f.read()
    ast.parse(src)
    print(f"Syntax OK: {fname}")

with open("gui/main_window.py","r",encoding="utf-8") as f:
    src = f.read()
checks = ["nomi_mode", "_NomeColumnDelegate", "save_edits", "regen_fn",
          "on_pdf_saved", "_regen", "_excel", "on_pdf_saved", "HeiseiKakuGo"]
for c in checks:
    print(f"  {c}: {'YES' if c in src else 'MISSING'}")

print("=== Done ===")
