import os
import time
import datetime
import getpass
from translations import TRANSLATIONS
from PySide6.QtCore import QObject, Signal

class LoggerSignals(QObject):
    log_emitted = Signal(str)

signals = LoggerSignals()

# Place the log file under %APPDATA%\YaskawaTools so it lives in a
# per-user, ACL-restricted directory.  Falling back to CWD on failure
# keeps the previous behaviour as a safety net.
try:
    from secure_paths import app_data_dir
    LOG_FILE = os.path.join(app_data_dir(), "YASKAWAToolsLog.log")
except Exception:
    LOG_FILE = "YASKAWAToolsLog.log"
CURRENT_LANG = "EN" # Default

# ── Circular (size-capped) log ────────────────────────────────────────────────
# The log must never grow without bound.  Once it exceeds MAX_LOG_BYTES the
# oldest records are dropped (FIFO) so the file stays under the cap: we keep the
# most recent ~_LOG_TRIM_TARGET bytes and discard everything older.  Trimming to
# a target below the cap leaves headroom so it does not run on every single
# write (only when the cap is actually crossed).
MAX_LOG_BYTES    = 10 * 1024 * 1024      # 10 MB hard cap
_LOG_TRIM_TARGET = 8 * 1024 * 1024       # keep the newest ~8 MB after trimming


def _trim_log_if_needed():
    """Drop the oldest log records when the file exceeds MAX_LOG_BYTES.

    Robust: any failure is swallowed — logging must never crash the app.
    """
    try:
        if os.path.getsize(LOG_FILE) <= MAX_LOG_BYTES:
            return
        with open(LOG_FILE, "rb") as f:
            data = f.read()
        if len(data) > _LOG_TRIM_TARGET:
            data = data[-_LOG_TRIM_TARGET:]
            # Align to a line boundary so the first kept record is complete.
            nl = data.find(b"\n")
            if nl != -1:
                data = data[nl + 1:]
        tmp = LOG_FILE + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, LOG_FILE)
    except Exception:
        pass

# ── Timing infrastructure ─────────────────────────────────────────────────────
# Every log entry now carries a ``[NN.NNNs]`` suffix.  Two complementary
# mechanisms feed that number:
#
# 1. Delta-since-last-log (``_LAST_LOG_T``): zero-cost, always available.
#    For a typical flow ``info("log_btn_pressed") → ... → info("log_pdf_generated")``
#    the second entry's delta IS the action duration.
#
# 2. Explicit ``duration_s`` kwarg or the ``timed(...)`` context manager:
#    used when the caller wants to time a specific block (preferred for
#    PDF previews / Excel exports) regardless of what was logged before.

_LAST_LOG_T = None

def set_log_language(lang_code):
    global CURRENT_LANG
    if lang_code in TRANSLATIONS:
        CURRENT_LANG = lang_code


def _format_duration(seconds: float) -> str:
    """Format a duration as ``[N.NNNs]`` (seconds with millisecond resolution)."""
    if seconds is None or seconds < 0:
        seconds = 0.0
    return f"[{seconds:.3f}s]"


def _write_log(level, msg_key, *args, duration_s=None):
    global _LAST_LOG_T
    now_t = time.monotonic()

    # Resolve duration: explicit > delta-since-last-log > 0.000
    if duration_s is None:
        if _LAST_LOG_T is None:
            elapsed = 0.0
        else:
            elapsed = max(0.0, now_t - _LAST_LOG_T)
    else:
        try:
            elapsed = max(0.0, float(duration_s))
        except Exception:
            elapsed = 0.0
    _LAST_LOG_T = now_t

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = getpass.getuser()

    # Get translated message
    lang_dict = TRANSLATIONS.get(CURRENT_LANG, TRANSLATIONS["IT"])
    msg_template = lang_dict.get(msg_key, msg_key)

    if args:
        try:
            msg = msg_template.format(*args)
        except Exception:
            msg = msg_template + " " + str(args)
    else:
        msg = msg_template

    duration_str = _format_duration(elapsed)
    log_entry = f"{now} | {user} | [{level}] | {msg} {duration_str}\n"

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        _trim_log_if_needed()
        signals.log_emitted.emit(log_entry)
    except Exception:
        pass  # The application must be robust and not crash


def info(msg_key, *args, duration_s=None):
    _write_log("INFO", msg_key, *args, duration_s=duration_s)


def warning(msg_key, *args, duration_s=None):
    _write_log("WARNING", msg_key, *args, duration_s=duration_s)


def error(msg_key, *args, duration_s=None):
    _write_log("ERROR", msg_key, *args, duration_s=duration_s)


class timed:
    """Context manager that times a block and logs duration on exit.

    Usage::

        with logger.timed("log_pdf_generated", out_path):
            generate_pdf(...)

    The log entry is written after the ``with`` block finishes, with the
    elapsed wall-clock time appended as ``[N.NNNs]``.  ``exc`` is swallowed
    in the __exit__ contract — the caller decides whether to re-raise.
    """
    __slots__ = ("level", "key", "args", "_t0")

    def __init__(self, key, *args, level="INFO"):
        self.level = level
        self.key   = key
        self.args  = args
        self._t0   = None

    def __enter__(self):
        self._t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.monotonic() - (self._t0 or time.monotonic())
        try:
            _write_log(self.level, self.key, *self.args, duration_s=elapsed)
        except Exception:
            pass
        return False
