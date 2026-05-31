"""Verifica del log circolare (size-capped) in logger.py."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import logger


def test_circular_log():
    d = tempfile.mkdtemp(prefix="log_")
    try:
        # Riduci il cap per un test rapido (50 KB cap, target 35 KB)
        logger.LOG_FILE = os.path.join(d, "test.log")
        logger.MAX_LOG_BYTES = 50 * 1024
        logger._LOG_TRIM_TARGET = 35 * 1024

        N = 8000
        for i in range(N):
            logger.info("log_error_generic", f"riga {i} " + ("x" * 40))

        size = os.path.getsize(logger.LOG_FILE)
        print(f"  righe scritte={N}, dimensione finale={size} bytes "
              f"(cap={logger.MAX_LOG_BYTES})")

        # Mai oltre il cap (tolleranza di una riga scritta prima del trim)
        assert size <= logger.MAX_LOG_BYTES + 1024, f"superato il cap: {size}"

        with open(logger.LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        # I record più recenti restano, i più vecchi sono usciti (FIFO/circolare)
        assert f"riga {N-1} " in content, "manca il record più recente"
        assert "riga 0 " not in content, "il record più vecchio non è stato eliminato"
        # La prima riga conservata deve essere completa (nessun frammento)
        first = content.splitlines()[0]
        assert first.startswith("20") or "|" in first, f"prima riga troncata: {first[:40]!r}"
        print("OK test_circular_log")
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    test_circular_log()
    print("=== TEST LOG CIRCOLARE OK ===")
