import json
import os

DEFAULT_CREATOR = "0THack1A"

def _path():
    from secure_paths import app_data_dir
    return os.path.join(app_data_dir(), "config.json")

def load_creator_name():
    """Return the persisted creator name, or the default if absent or invalid."""
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("creator_name", "").strip()
        if name:
            return name
    except Exception:
        pass
    return DEFAULT_CREATOR

def save_creator_name(name):
    """Atomically persist the creator name to the config file."""
    try:
        p = _path()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["creator_name"] = name.strip()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        pass
