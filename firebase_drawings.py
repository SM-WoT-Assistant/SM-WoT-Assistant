"""
firebase_drawings.py — публікація / завантаження малюнків через RTDB REST API.
Прибрано Firestore (не працює з API key). Використовує RTDB як решта системи.
Пише в schemes/{drawing_id} — той самий шлях, що читає schemes.html.
"""
import json
import uuid
import time
import threading
import config
import requests
import firebase_identity
import firebase_reporter


def publish_drawing(map_name, map_id, elements_data, title="", comment="", on_done=None):
    """Публікує малюнок у RTDB (schemes/)."""
    if not firebase_reporter._is_configured():
        if on_done:
            on_done(False, "Firebase не налаштовано.")
        return

    identity = firebase_identity.get_identity()
    if not identity:
        if on_done:
            on_done(False, "Не зареєстровано. Зареєструйтесь у програмі.")
        return

    nick = identity.get("nickname", "")
    user_id = identity.get("user_id", "")
    pin_hash = identity.get("pin_hash", "")
    drawing_id = str(uuid.uuid4())

    if isinstance(elements_data, list):
        elements_str = json.dumps(elements_data, ensure_ascii=False)
        element_count = len(elements_data)
    elif isinstance(elements_data, str):
        elements_str = elements_data
        try:
            element_count = len(json.loads(elements_str))
        except Exception:
            element_count = 0
    else:
        elements_str = "[]"
        element_count = 0

    scheme = {
        "drawing_id": drawing_id,
        "map_id": map_id,
        "map_name": map_name,
        "author_nickname": nick,
        "author_id": user_id,
        "pin_hash": pin_hash,
        "title": title[:60] if title else "",
        "comment": comment[:500] if comment else "",
        "elements": elements_str,
        "element_count": element_count,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    def _send():
        try:
            url = firebase_reporter._rtdb_url(f"schemes/{drawing_id}")
            r = requests.put(url, json=scheme, headers=config.HEADERS, timeout=10)
            ok = 200 <= r.status_code < 300
            msg = "Опубліковано!" if ok else f"Помилка: {r.status_code}"
            if on_done:
                on_done(ok, msg)
        except Exception as e:
            if on_done:
                on_done(False, str(e))

    t = threading.Thread(target=_send, daemon=True)
    t.start()


def fetch_drawings(map_name=None, limit=50, on_done=None):
    """Завантажує малюнки з RTDB schemes/."""
    if not firebase_reporter._is_configured():
        if on_done:
            on_done([])
        return

    def _fetch():
        try:
            url = firebase_reporter._rtdb_url("schemes")
            r = requests.get(url, headers=config.HEADERS, timeout=10)
            if r.status_code != 200:
                if on_done:
                    on_done([])
                return

            data = r.json()
            if not data or not isinstance(data, dict):
                if on_done:
                    on_done([])
                return

            results = []
            for key, item in data.items():
                if not item or not isinstance(item, dict):
                    continue
                if not item.get("drawing_id"):
                    continue
                if map_name and item.get("map_name") != map_name and item.get("map_id") != map_name:
                    continue

                try:
                    if isinstance(item.get("elements"), str):
                        item["elements"] = json.loads(item["elements"])
                except Exception:
                    item["elements"] = []

                results.append(item)
                if len(results) >= limit:
                    break

            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            if on_done:
                on_done(results)
        except Exception:
            if on_done:
                on_done([])

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()


def download_drawing(drawing_id, on_done=None):
    """Завантажує один малюнок з RTDB по ID."""
    if not firebase_reporter._is_configured():
        if on_done:
            on_done(None)
        return

    def _fetch():
        try:
            url = firebase_reporter._rtdb_url(f"schemes/{drawing_id}")
            r = requests.get(url, headers=config.HEADERS, timeout=10)
            if r.status_code != 200:
                if on_done:
                    on_done(None)
                return
            item = r.json()
            if not item or not isinstance(item, dict):
                if on_done:
                    on_done(None)
                return
            try:
                if isinstance(item.get("elements"), str):
                    item["elements"] = json.loads(item["elements"])
            except Exception:
                item["elements"] = []
            if on_done:
                on_done(item)
        except Exception:
            if on_done:
                on_done(None)

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
