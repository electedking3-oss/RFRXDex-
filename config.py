import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_config: dict | None = None


def _load() -> dict:
    global _config
    if _config is not None:
        return _config
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _config = json.load(f)
    return _config


def reload():
    global _config
    _config = None
    return _load()


# ── Accessors ─────────────────────────────────────────────────────────────────

def prefix() -> str:
    return _load()["bot"]["prefix"]

def status() -> str:
    return _load()["bot"]["status"]

def owner_ids() -> list[int]:
    return [int(x) for x in _load()["bot"]["owner_ids"]]

def spawn_interval() -> tuple[int, int]:
    s = _load()["spawn"]
    return s["interval_min"], s["interval_max"]

def starting_coins() -> int:
    return _load()["economy"]["starting_coins"]

def admin_roles() -> list[str]:
    return _load()["admin_roles"]
