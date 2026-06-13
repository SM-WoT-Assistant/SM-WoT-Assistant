"""UI Translator — translates app-specific UI text to any language using Google Translate.
Protects keyboard shortcuts, symbols and numbers from translation."""

import os
import json
import re
import config

_cache = {}

_KNOWN_KEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20", "F21", "F22", "F23", "F24",
    "Ctrl", "Alt", "Shift", "LMB", "RMB", "Enter", "Esc", "Tab", "Del", "Delete",
    "Up", "Down", "Left", "Right", "Home", "End", "PgUp", "PgDn", "Space", "Backspace",
    "E", "Z", "X", "C", "V",
]
_KEY_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(k) for k in sorted(_KNOWN_KEYS, key=len, reverse=True)) + r')\b'
)
_SYM_RE = re.compile(r'[|/\\\u2190\u2191\u2192\u2193\u2194+\-:\[\](){}<>]')

def _shield(text):
    """Replace keyboard shortcuts and symbols with placeholders for safe translation."""
    placeholders = {}
    idx = [0]

    def _store(m):
        key = f"__PH{idx[0]}__"
        placeholders[key] = m.group(0)
        idx[0] += 1
        return key

    text = _KEY_RE.sub(_store, text)
    text = _SYM_RE.sub(_store, text)
    return text, placeholders

def _unshield(text, placeholders):
    """Restore placeholders after translation."""
    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text

def _cache_path(lang):
    return os.path.join(config.USER_DATA_DIR, "localization", lang, "ui_cache.json")

def translate(text, target_lang):
    if not target_lang or target_lang == "en" or target_lang == "en_US":
        return text
    cache = _load_cache(target_lang)
    if text in cache:
        return cache[text]
    try:
        shielded, ph = _shield(text)
        from deep_translator import GoogleTranslator
        t = GoogleTranslator(source="en", target=target_lang)
        result = t.translate(shielded)
        if result:
            result = _unshield(result, ph)
            if result and result != text:
                cache[text] = result
                _save_cache(target_lang, cache)
                return result
    except Exception:
        pass
    return text

def translate_dict(en_dict, target_lang):
    result = {}
    for key, value in en_dict.items():
        result[key] = translate(value, target_lang)
    return result

def _load_cache(lang):
    global _cache
    if lang not in _cache:
        _cache[lang] = {}
        path = _cache_path(lang)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    _cache[lang] = json.load(f)
            except Exception:
                pass
    return _cache[lang]

def _save_cache(lang, data):
    global _cache
    _cache[lang] = data
    try:
        path = _cache_path(lang)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass
