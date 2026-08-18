#!/usr/bin/env python3
"""SM WoT Assistant Admin — encrypted credential vault (Windows DPAPI).

Stores credentials for external accounts (YouTube, Reddit, Ko-fi) encrypted
with the current Windows user's DPAPI key (CryptProtectData/CryptUnprotectData
from crypt32.dll — zero extra dependencies, values are bound to the user
account and cannot be decrypted on another machine/user).

File: %APPDATA%/SM WoT Assistant/admin_vault.json
Format: {"service": {"field": "<base64 of DPAPI blob>"}}

Values are decrypted only on demand (never stored/logged in plain text).
"""
import os
import json
import base64
import ctypes
from ctypes import wintypes

VAULT_PATH = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "admin_vault.json")

_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data)
    return _DATA_BLOB(len(data),
                      ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))


def _protect(data: bytes) -> bytes:
    """Encrypt bytes with DPAPI (user scope, no UI)."""
    if not data:
        raise ValueError("empty data")
    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(_DATA_BLOB)]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    out = _DATA_BLOB()
    ok = _crypt32.CryptProtectData(
        ctypes.byref(_blob(data)), None, None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
    if not ok:
        raise RuntimeError("CryptProtectData failed: %d" % ctypes.get_last_error())
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _unprotect(data: bytes) -> bytes:
    """Decrypt bytes with DPAPI (user scope)."""
    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.POINTER(wintypes.LPCWSTR),
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(_DATA_BLOB)]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    out = _DATA_BLOB()
    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(_blob(data)), None, None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
    if not ok:
        raise RuntimeError("CryptUnprotectData failed: %d" % ctypes.get_last_error())
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _load() -> dict:
    try:
        with open(VAULT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save(data: dict):
    try:
        os.makedirs(os.path.dirname(VAULT_PATH), exist_ok=True)
        tmp = VAULT_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, VAULT_PATH)
    except Exception:
        pass


def vault_set(service: str, field: str, value: str):
    """Encrypt and store a value for service.field."""
    if not service or not field or not value:
        return
    data = _load()
    data.setdefault(service, {})[field] = base64.b64encode(_protect(value.encode("utf-8"))).decode("ascii")
    _save(data)


def vault_get(service: str, field: str):
    """Return the decrypted value or None (missing / corrupt / wrong user)."""
    data = _load()
    blob = (data.get(service) or {}).get(field)
    if not blob:
        return None
    try:
        raw = base64.b64decode(blob)
        return _unprotect(raw).decode("utf-8")
    except Exception:
        return None


def vault_has(service: str, field: str) -> bool:
    data = _load()
    return bool((data.get(service) or {}).get(field))


def vault_fields(service: str) -> list:
    data = _load()
    return list((data.get(service) or {}).keys())


def vault_delete_field(service: str, field: str):
    data = _load()
    entry = data.get(service)
    if entry and field in entry:
        del entry[field]
        if not entry:
            data.pop(service, None)
        _save(data)


def vault_delete(service: str):
    data = _load()
    if service in data:
        del data[service]
        _save(data)


if __name__ == "__main__":
    # smoke test: set/get round-trip
    import sys
    vault_set("_test", "k", "secret-123")
    v = vault_get("_test", "k")
    print("round-trip:", "OK" if v == "secret-123" else f"FAIL got {v!r}")
    vault_delete("_test")
    print("deleted:", "OK" if not vault_has("_test", "k") else "FAIL")
