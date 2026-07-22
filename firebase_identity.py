"""
firebase_identity.py — локальна система ідентичності (нікнейм + PIN).
Без паролів, без email. user_id = uuid4.
Firestore-ready: методи для синхронізації з хмарою (users/{user_id}).
"""
import os
import json
import uuid
import hashlib
import time
import requests
import config

_IDENTITY_FILE = os.path.join(config.USER_DATA_DIR, "identity.json")

_FIREBASE_API_KEY = "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"
_RTDB_BASE = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"

def _rtdb_url(path):
    if "?" in path:
        base_path, qs = path.split("?", 1)
        return f"{_RTDB_BASE}/{base_path}.json?{qs}&auth={_FIREBASE_API_KEY}"
    return f"{_RTDB_BASE}/{path}.json?auth={_FIREBASE_API_KEY}"

def _rtdb_put(path, data):
    try:
        r = requests.put(_rtdb_url(path), json=data, timeout=8)
        return 200 <= r.status_code < 300
    except Exception:
        return False

def _rtdb_get(path):
    try:
        r = requests.get(_rtdb_url(path), timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _rtdb_patch(path, data):
    try:
        r = requests.patch(_rtdb_url(path), json=data, timeout=8)
        return 200 <= r.status_code < 300
    except Exception:
        return False


def _load():
    if os.path.exists(_IDENTITY_FILE):
        try:
            with open(_IDENTITY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data):
    try:
        os.makedirs(os.path.dirname(_IDENTITY_FILE), exist_ok=True)
        with open(_IDENTITY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def hash_pin(pin):
    return hashlib.sha256(f"wot_assistant_pin_salt_{pin}".encode()).hexdigest()


def get_identity():
    data = _load()
    if data.get("user_id"):
        return data
    return None


def is_registered():
    return get_identity() is not None


def check_nickname_available(nickname):
    """Перевіряє чи нікнейм вільний в RTDB."""
    nickname = nickname.strip().lower()
    if len(nickname) < 2:
        return True
    data = _rtdb_get(f'users?orderBy="nickname_lower"&equalTo="{nickname}"')
    if not data:
        return True
    for v in data.values():
        if isinstance(v, dict) and v.get("nickname_lower") == nickname:
            return False
    return True


def register(nickname, pin):
    if not nickname or not pin:
        return False, "Нікнейм та PIN обов'язкові."

    nickname = nickname.strip()
    pin = pin.strip()

    if len(nickname) < 2:
        return False, "Нікнейм має бути не менше 2 символів."
    if len(nickname) > 20:
        return False, "Нікнейм має бути не більше 20 символів."
    if not pin.isdigit() or len(pin) != 4:
        return False, "PIN має бути рівно 4 цифри."

    if not check_nickname_available(nickname):
        return False, "Цей нікнейм вже зайнятий."

    data = _load()
    if data.get("user_id"):
        return False, "Вже зареєстровано. Використовуйте зміну PIN."

    data["user_id"] = str(uuid.uuid4())
    data["nickname"] = nickname
    data["pin_text"] = pin
    data["pin_hash"] = hash_pin(pin)
    data["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    _save(data)
    _rtdb_put(f"users/{data['user_id']}", {
        "nickname": nickname,
        "nickname_lower": nickname.lower(),
        "pin_hash": data["pin_hash"],
        "created_at": data["created_at"],
    })
    return True, data["user_id"]


def login(nickname, pin):
    try:
        nickname = nickname.strip()
        pin = pin.strip()
        if not nickname or not pin:
            return False, "Nickname and PIN are required."
        if not pin.isdigit() or len(pin) != 4:
            return False, "PIN must be 4 digits."

        data = _rtdb_get(f'users?orderBy="nickname_lower"&equalTo="{nickname.lower()}"')
        if not data:
            return False, "User not found. Check your nickname."

        entries = [v for v in data.values() if isinstance(v, dict)]
        if not entries:
            return False, "User not found."

        entry = entries[0]
        if entry.get("pin_hash") != hash_pin(pin):
            return False, "Wrong PIN."

        local = {
            "user_id": list(data.keys())[0],
            "nickname": entry["nickname"],
            "pin_text": pin,
            "pin_hash": entry["pin_hash"],
            "created_at": entry.get("created_at", ""),
            "connected": True,
        }
        _save(local)
        return True, entry["nickname"]
    except Exception as e:
        return False, str(e)


def is_connected():
    data = _load()
    return data.get("connected", False)


def connect():
    """Локальна верифікація: перевіряє збережені дані без RTDB."""
    data = _load()
    nick = data.get("nickname", "")
    pin = data.get("pin_text", "")
    hash_ = data.get("pin_hash", "")
    if not nick or not pin or not hash_:
        return False, "Немає збережених облікових даних."
    if hash_pin(pin) != hash_:
        return False, "Дані пошкоджено."
    data["connected"] = True
    _save(data)
    uid = data.get("user_id")
    if uid:
        _rtdb_patch(f"users/{uid}", {"connected": True})
    return True, nick


def disconnect():
    """Відключення: встановлює connected=False без видалення даних."""
    data = _load()
    if data.get("user_id"):
        data["connected"] = False
        _save(data)
        _rtdb_patch(f"users/{data['user_id']}", {"connected": False})


def verify_pin(pin):
    data = get_identity()
    if not data:
        return False
    return data.get("pin_hash") == hash_pin(pin)


def change_pin(old_pin, new_pin):
    data = _load()
    if not data.get("user_id"):
        return False, "Не зареєстровано."

    if data.get("pin_hash") != hash_pin(old_pin):
        return False, "Невірний поточний PIN."

    if not new_pin.isdigit() or len(new_pin) != 4:
        return False, "Новий PIN має бути рівно 4 цифри."

    data["pin_text"] = new_pin
    data["pin_hash"] = hash_pin(new_pin)
    _save(data)
    return True, "PIN змінено."


def change_nickname(new_nickname, pin):
    data = _load()
    if not data.get("user_id"):
        return False, "Не зареєстровано."

    if data.get("pin_hash") != hash_pin(pin):
        return False, "Невірний PIN."

    new_nickname = new_nickname.strip()
    if len(new_nickname) < 2 or len(new_nickname) > 20:
        return False, "Нікнейм має бути 2-20 символів."

    old_nickname = data.get("nickname")
    data["nickname"] = new_nickname
    data["synced_to_firestore"] = False
    _save(data)
    return True, old_nickname


def get_user_id():
    data = get_identity()
    return data.get("user_id") if data else None


def get_nickname():
    data = get_identity()
    return data.get("nickname", "") if data else ""


def get_pin_text():
    data = get_identity()
    return data.get("pin_text", "") if data else ""


def get_auth_display():
    nick = get_nickname()
    return f" {nick}" if nick else ""


def mark_synced():
    data = _load()
    data["synced_to_firestore"] = True
    _save(data)


def needs_sync():
    data = _load()
    return data.get("user_id") and not data.get("synced_to_firestore", False)


def get_identity_for_firestore():
    data = _load()
    if not data.get("user_id"):
        return None
    return {
        "nickname": data["nickname"],
        "nickname_lower": data["nickname"].lower(),
        "pin_hash": data["pin_hash"],
        "created_at": data["created_at"],
    }
