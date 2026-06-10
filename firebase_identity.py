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
import config

_IDENTITY_FILE = os.path.join(config.USER_DATA_DIR, "identity.json")


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


def register(nickname, pin):
    data = _load()
    if data.get("user_id"):
        return False, "Вже зареєстровано. Використовуйте зміну PIN."

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

    data["user_id"] = str(uuid.uuid4())
    data["nickname"] = nickname
    data["pin_text"] = pin
    data["pin_hash"] = hash_pin(pin)
    data["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    data["synced_to_firestore"] = False

    _save(data)
    return True, data["user_id"]


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
