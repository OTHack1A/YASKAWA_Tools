import os
import json
import time
from datetime import datetime, timedelta

# We'll use argon2 for verification
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
except ImportError:
    pass

# This is the actual hash for the application password
HASHED_PASSWORD = "$argon2id$v=19$m=65536,t=3,p=4$XMYMlSmfuYIDDafY+x4XdA$9JgU8+PyzMXCPue+awTDZg5ErrK5/TJO/jaaoWtnnjE"

# ── Persistent lockout state ──────────────────────────────────────────────────
#
# Without persistence the per-process attempt counter is reset by simply
# closing and relaunching the application, allowing an attacker to brute-force
# without bound.  The state file lives under %APPDATA%\YaskawaTools, a
# directory whose default ACLs restrict access to the current Windows user.

_MAX_ATTEMPTS  = 3
_LOCKOUT_MIN   = 5         # minutes of lockout after _MAX_ATTEMPTS failures
_MIN_VERIFY_MS = 500       # constant-time floor for each verify() call

try:
    from secure_paths import app_data_dir
    _STATE_FILE = os.path.join(app_data_dir(), "auth_state.json")
except Exception:
    _STATE_FILE = "auth_state.json"


def _load_state():
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "attempts":      int(data.get("attempts", 0) or 0),
            "lockout_until": data.get("lockout_until") or None,
        }
    except Exception:
        return {"attempts": 0, "lockout_until": None}


def _save_state(state):
    try:
        tmp = _STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, _STATE_FILE)
    except Exception:
        pass


def lockout_remaining_seconds():
    """Return seconds left in active lockout window, or 0 if not locked out."""
    state = _load_state()
    lu = state.get("lockout_until")
    if not lu:
        return 0
    try:
        until = datetime.fromisoformat(lu)
    except Exception:
        return 0
    delta = (until - datetime.now()).total_seconds()
    return max(0, int(delta))


def record_failure():
    """Increment failure counter; arm a lockout window when threshold reached."""
    state = _load_state()
    state["attempts"] = (state.get("attempts", 0) or 0) + 1
    if state["attempts"] >= _MAX_ATTEMPTS:
        state["lockout_until"] = (
            datetime.now() + timedelta(minutes=_LOCKOUT_MIN)
        ).isoformat()
        state["attempts"] = 0
    _save_state(state)


def record_success():
    """Clear persisted attempts and any active lockout."""
    _save_state({"attempts": 0, "lockout_until": None})


def get_hasher():
    return PasswordHasher()


def verify_password(password):
    """Verify the supplied password against the stored Argon2id hash.

    Implements a constant-time floor: every call sleeps until at least
    ``_MIN_VERIFY_MS`` milliseconds have elapsed, neutralising timing
    side-channels that could distinguish "wrong password" from "no
    password configured" or "hash invalid".
    """
    start = time.monotonic()
    result = False
    try:
        if HASHED_PASSWORD and HASHED_PASSWORD != "None":
            ph = get_hasher()
            try:
                result = ph.verify(HASHED_PASSWORD, password)
            except Exception:
                # Any failure (VerifyMismatchError or other) → denied access.
                result = False
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        if elapsed_ms < _MIN_VERIFY_MS:
            time.sleep((_MIN_VERIFY_MS - elapsed_ms) / 1000)
    return result
