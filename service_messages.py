"""
service_messages.py — черга внутрішніх службових подій.
Користувач НІКОЛИ не бачить ці повідомлення.
Вони накопичуються локально і будуть відправлені на сервер (у майбутньому).
Після відправки маркуються delivered=true.
"""

import os
import json
import time
import uuid

_SERVICE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_messages.json")


def _load():
    if os.path.exists(_SERVICE_FILE):
        try:
            with open(_SERVICE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save(messages):
    try:
        with open(_SERVICE_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def log_event(category, message, level="info"):
    """Додає службову подію в чергу (невидимо для користувача)."""
    messages = _load()
    messages.append({
        "id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "category": category,
        "message": message,
        "level": level,
        "delivered": False,
    })
    _save(messages)
    print(f"[SERVICE] [{level.upper()}] {category}: {message}")


def get_pending():
    """Повертає всі undelivered події для відправки на сервер."""
    return [m for m in _load() if not m.get("delivered")]


def mark_delivered(message_ids):
    """Позначає події як доставлені (після успішної відправки на сервер)."""
    messages = _load()
    for m in messages:
        if m.get("id") in message_ids:
            m["delivered"] = True
    _save(messages)
