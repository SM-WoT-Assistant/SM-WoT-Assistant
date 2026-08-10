"""
admin_auth.py — автентифікація адмін-тулінгу для запису в RTDB.

Отримує Firebase ID-токен через Identity Toolkit REST (accounts:signInWithPassword)
з локального admin_creds.json у %APPDATA%/SM WoT Assistant/ (gitignored).
Використовується тільки адмін-кодом: build.py, admin_build_generator.py, admin_app.py.
Клієнтський застосунок НЕ використовує цей модуль — він працює з відкритими
клієнтськими нодами RTDB без автентифікації.

admin_creds.json (формат):
    {"email": "smwotassistant@gmail.com", "password": "..."}
"""
import json
import os
import threading
import time

import requests

import config
from firebase_reporter import FIREBASE_API_KEY

_CREDS_FILE = os.path.join(config.USER_DATA_DIR, "admin_creds.json")

_ID_TOKEN = None
_REFRESH_TOKEN = None
_EXPIRES_AT = 0.0
_LOCK = threading.Lock()
_WARNED = False


def has_credentials():
    """True, якщо admin_creds.json існує і містить email+password."""
    email, password = _load_creds()
    return bool(email and password)


def _load_creds():
    try:
        with open(_CREDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        email = str(data.get("email", "")).strip()
        password = str(data.get("password", ""))
        if email and password:
            return email, password
    except Exception:
        pass
    return None, None


def _sign_in():
    """signInWithPassword → (id_token, refresh_token) або (None, None)."""
    email, password = _load_creds()
    if not email:
        return None, None
    url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    params = {"key": FIREBASE_API_KEY}
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r = requests.post(url, params=params, json=payload, timeout=10)
    if r.status_code != 200:
        return None, None
    data = r.json()
    return data.get("idToken"), data.get("refreshToken")


def _apply_token(token, refresh_token, expires_in):
    global _ID_TOKEN, _REFRESH_TOKEN, _EXPIRES_AT
    _ID_TOKEN = token
    _REFRESH_TOKEN = refresh_token
    try:
        _EXPIRES_AT = time.time() + int(float(expires_in)) - 120
    except Exception:
        _EXPIRES_AT = time.time() + 3480


def _refresh():
    """Оновлення ID-токена по refreshToken."""
    if not _REFRESH_TOKEN:
        return None
    url = "https://securetoken.googleapis.com/v1/token"
    params = {"key": FIREBASE_API_KEY}
    payload = {"grant_type": "refresh_token", "refresh_token": _REFRESH_TOKEN}
    r = requests.post(url, params=params, json=payload, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    token = data.get("id_token")
    if not token:
        return None
    _apply_token(token, data.get("refresh_token") or _REFRESH_TOKEN,
                 data.get("expires_in", 3600))
    return token


def get_id_token():
    """Повертає актуальний ID-токен або None (креденціали відсутні/невалідні)."""
    global _WARNED
    with _LOCK:
        if _ID_TOKEN and time.time() < _EXPIRES_AT:
            return _ID_TOKEN
        token = _refresh()
        if not token:
            token, refresh_token = _sign_in()
            if token:
                _apply_token(token, refresh_token, 3600)
        if not token and not _WARNED:
            _WARNED = True
            print("[ADMIN_AUTH] Не вдалося отримати ID-токен для запису в RTDB. "
                  "Перевір admin_creds.json у %APPDATA%/SM WoT Assistant/ "
                  '({"email": "...", "password": "..."}).')
        return token


def _rtdb_url_with_token(path):
    """URL для запису в RTDB з ID-токеном (повертає None, якщо токена немає).

    Зрізає наявний ?auth=... (API-ключ), бо RTDB використовує ПЕРШИЙ
    auth-параметр — ключ невалідний і блокує записи (401).
    """
    token = get_id_token()
    if not token:
        return None
    base, _, qs = path.partition("?")
    if qs:
        kept = [p for p in qs.split("&") if not p.startswith("auth=")]
        if kept:
            return f"{base}?{'&'.join(kept)}&auth={token}"
    return f"{base}?auth={token}"
