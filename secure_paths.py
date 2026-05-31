"""Centralised filesystem helpers for security-sensitive paths.

All paths returned by this module live under directories whose access is
restricted to the current Windows user (per default ACLs on %APPDATA% and
%LOCALAPPDATA%\\Temp).  This avoids two classes of issue:

* TOCTOU / symlink attacks on shared temp directories — temp files now live
  inside a per-process subdirectory whose name is not predictable.
* Log / state files written into the current working directory, which may
  be a folder the user does not control (USB drive, shared share, ...).
"""

import os
import tempfile

_APP_NAME = "YaskawaTools"
_RUN_TMPDIR = None  # cached per-process isolated temp dir


def app_data_dir() -> str:
    """Return ``%APPDATA%\\YaskawaTools`` on Windows, ``~/.YaskawaTools`` elsewhere.

    The directory is created on first call.  A failure to create falls back
    to the user's home directory so the caller always gets a writable path.
    """
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, _APP_NAME)
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except Exception:
        return os.path.expanduser("~")


def run_temp_dir() -> str:
    """Return an isolated temp directory unique to this process.

    The directory name carries a cryptographically random suffix
    (``tempfile.mkdtemp``), so paths inside it cannot be guessed or
    pre-created by another process — eliminating TOCTOU/symlink races
    on the well-known ``%TEMP%/fixed_name.pdf`` pattern.
    """
    global _RUN_TMPDIR
    if _RUN_TMPDIR is None or not os.path.isdir(_RUN_TMPDIR):
        try:
            _RUN_TMPDIR = tempfile.mkdtemp(prefix=f"{_APP_NAME}_")
        except Exception:
            _RUN_TMPDIR = tempfile.gettempdir()
    return _RUN_TMPDIR


def temp_path(name: str) -> str:
    """Build a path inside the isolated per-run temp directory."""
    return os.path.join(run_temp_dir(), name)
