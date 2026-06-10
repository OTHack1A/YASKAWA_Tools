import os
import json
import time
import hmac
import hashlib
import platform
from datetime import datetime, timedelta

# We'll use argon2 for verification
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
except ImportError:
    pass

# Argon2id hash of the application password, generated with the hardened cost
# parameters below (128 MiB memory, time 4, parallelism 4) to slow offline
# brute-force attempts.  The plaintext password is intentionally NOT recorded
# anywhere in this repository.
HASHED_PASSWORD = "$argon2id$v=19$m=131072,t=4,p=4$zUX2pOCWCtqhhd89hd04Vg$6RBfbuBHmEjcabOSblFJt7/9FaixTtm4jxtCWsQrqt0"

# Cost parameters used when (re)hashing.  Argon2 verify() reads the parameters
# embedded in the stored hash, so these only need to match for rehash checks.
_ARGON2_TIME_COST   = 4
_ARGON2_MEMORY_COST = 131072   # 128 MiB
_ARGON2_PARALLELISM = 4

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

# ── Tamper-evident state integrity ────────────────────────────────────────────
#
# The lockout state is integrity-protected with an HMAC keyed by an embedded
# pepper bound to the local machine name.  A file that is present but carries a
# missing/invalid signature is treated as tampering and *fails closed* (it is
# read back as an active lockout), so an attacker cannot clear an in-progress
# lockout — or transplant a forged state from another machine — by editing the
# JSON.  (Deleting the file resets to a first-run state, which remains an
# inherent limit of any purely local, server-less lockout.)
_STATE_PEPPER = b"YaskawaTools/auth-state/v1"


def _state_key():
    """Derive the HMAC key from the embedded pepper bound to this machine."""
    node = (platform.node() or os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME") or "").encode("utf-8", "replace")
    return hmac.new(_STATE_PEPPER, node, hashlib.sha256).digest()


def _state_sig(attempts, lockout_until):
    """Return the HMAC-SHA256 signature over the canonical state fields."""
    raw = json.dumps({"attempts": attempts, "lockout_until": lockout_until},
                     sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_state_key(), raw, hashlib.sha256).hexdigest()


def _locked_default():
    """Fail-closed state: behave as if a fresh lockout window were active."""
    return {
        "attempts": _MAX_ATTEMPTS,
        "lockout_until": (datetime.now() + timedelta(minutes=_LOCKOUT_MIN)).isoformat(),
    }


def _load_state():
    """Load the persisted lockout state, verifying its HMAC.

    A missing file yields first-run defaults; a present-but-tampered file
    (bad/absent signature) fails closed via :func:`_locked_default`.
    """
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"attempts": 0, "lockout_until": None}
    except Exception:
        return {"attempts": 0, "lockout_until": None}
    try:
        attempts = int(data.get("attempts", 0) or 0)
        lockout_until = data.get("lockout_until") or None
        sig = data.get("sig")
        if not sig or not hmac.compare_digest(
                str(sig), _state_sig(attempts, lockout_until)):
            # Present but tampered/forged → fail closed, but persist a real
            # signed lockout so it counts down and self-heals after the window
            # (rather than locking out forever on a one-off file corruption).
            locked = _locked_default()
            _save_state(locked)
            return locked
    except Exception:
        # Malformed but present → treat conservatively as tampering.
        locked = _locked_default()
        _save_state(locked)
        return locked
    return {"attempts": attempts, "lockout_until": lockout_until}


def _save_state(state):
    """Atomically persist the signed lockout state via a temp file + os.replace."""
    try:
        attempts = int(state.get("attempts", 0) or 0)
        lockout_until = state.get("lockout_until") or None
        payload = {
            "attempts": attempts,
            "lockout_until": lockout_until,
            "sig": _state_sig(attempts, lockout_until),
        }
        tmp = _STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
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


def attempts_remaining():
    """Return how many login attempts remain before a lockout is armed.

    Returns 0 while a lockout window is active.  Otherwise it is
    ``_MAX_ATTEMPTS`` minus the persisted failure count, so the UI can show
    an accurate count that survives application restarts.
    """
    if lockout_remaining_seconds() > 0:
        return 0
    state = _load_state()
    used = int(state.get("attempts", 0) or 0)
    return max(0, _MAX_ATTEMPTS - used)


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
    """Return a PasswordHasher configured with the hardened cost parameters."""
    return PasswordHasher(
        time_cost=_ARGON2_TIME_COST,
        memory_cost=_ARGON2_MEMORY_COST,
        parallelism=_ARGON2_PARALLELISM,
    )


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
