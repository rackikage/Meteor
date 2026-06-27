"""Persistent user settings + chat history."""
import json
import os

DATA_DIR = os.path.expanduser("~/.local/share/meteor-ldrago")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

DEFAULTS = {
    "dark": True,
    "ollama_url": "http://127.0.0.1:11434",
    "model": "llama3.2",
    "refresh_ms": 1500,
    "ai_enabled": True,
}


def _load(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            pass
    return default


def _save(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    json.dump(data, open(path, "w"), indent=2)


def load_settings() -> dict:
    s = _load(SETTINGS_FILE, dict(DEFAULTS))
    for k, v in DEFAULTS.items():
        s.setdefault(k, v)
    return s


def save_settings(s: dict) -> None:
    _save(SETTINGS_FILE, s)


def load_history() -> list:
    return _load(HISTORY_FILE, [{
        "role": "assistant",
        "content": "Meteor L·Drago online. System meters live on the left. Ask me anything.",
    }])


def save_history(h: list) -> None:
    _save(HISTORY_FILE, h[-200:])
