"""UI Translator — translates app-specific UI text to any language using Google Translate.
Protects keyboard shortcuts, symbols and numbers from translation."""

import os
import json
import re
import time
import traceback
import config

_cache = {}
_gt = None  # cached GoogleTranslator class

def _get_translator():
    global _gt
    if _gt is not None:
        return _gt
    try:
        from deep_translator import GoogleTranslator
        _gt = GoogleTranslator
        print("[SERVICE] deep_translator loaded OK")
        return _gt
    except ModuleNotFoundError:
        print("[SERVICE] deep_translator not available — UI will remain in English")
        return None

_KNOWN_KEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20", "F21", "F22", "F23", "F24",
    "Ctrl", "Alt", "Shift", "LMB", "RMB", "Enter", "Esc", "Tab", "Del",
    "Up", "Down", "Left", "Right", "Home", "End", "PgUp", "PgDn", "Space", "Backspace",
    "E", "Z", "X", "C", "V",
    "LT", "MT", "HT", "TD", "SPG",
]
_KEY_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(k) for k in sorted(_KNOWN_KEYS, key=len, reverse=True)) + r')\b'
)
_SYM_RE = re.compile(r'(?:->|=>|<-|<=|\{[^}]+\}|[|/\\\u2190\u2191\u2192\u2193\u2194+\-:\[\]()<>])')

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
    if not _get_translator():
        return text
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

_BATCH_SEP = "\n|||__BATCH_SEP__|||\n"
_MAX_CHUNK_CHARS = 4500

def translate_batch(en_dict, target_lang, progress_cb=None):
    """Translate a dict of key->EN_value in batch requests to Google Translate.
    Joins multiple texts with separator to send fewer HTTP requests.
    Returns dict of key->translated_value, caches results."""
    gt = _get_translator()
    if not gt:
        return {}
    if not target_lang or target_lang == "en" or target_lang == "en_US":
        return dict(en_dict)
    cache = _load_cache(target_lang)
    result = {}
    untranslated = []
    for key, en_val in en_dict.items():
        if en_val in cache:
            result[key] = cache[en_val]
        else:
            untranslated.append((key, en_val))
    if not untranslated:
        return result
    texts = [v for _, v in untranslated]
    shielded_list = []
    ph_list = []
    for text in texts:
        s, ph = _shield(text)
        shielded_list.append(s)
        ph_list.append(ph)
    chunks = []
    cur_keys = []
    cur_phs = []
    cur_size = 0
    for i, s in enumerate(shielded_list):
        item_size = len(s) + len(_BATCH_SEP)
        if cur_size + item_size > _MAX_CHUNK_CHARS and cur_keys:
            chunks.append((cur_keys, cur_phs, cur_size))
            cur_keys = []
            cur_phs = []
            cur_size = 0
        cur_keys.append(i)
        cur_phs.append(ph_list[i])
        cur_size += item_size
    if cur_keys:
        chunks.append((cur_keys, cur_phs, cur_size))
    total_items = len(untranslated)
    done = 0
    try:
        t = gt(source="en", target=target_lang)
        for ci, (chunk_keys, chunk_phs, _) in enumerate(chunks):
            if ci > 0:
                time.sleep(0.5)
            chunk_texts = [shielded_list[i] for i in chunk_keys]
            joined = _BATCH_SEP.join(chunk_texts)
            raw = t.translate(joined)
            if raw:
                parts = raw.split(_BATCH_SEP)
                for pi, orig_idx in enumerate(chunk_keys):
                    trans = parts[pi] if pi < len(parts) else None
                    key, en_val = untranslated[orig_idx]
                    if trans:
                        trans = _unshield(trans, chunk_phs[pi] if pi < len(chunk_phs) else ph_list[orig_idx])
                        if trans and trans != en_val:
                            cache[en_val] = trans
                            result[key] = trans
                            done += 1
                            continue
                    result[key] = en_val
                    done += 1
            else:
                for orig_idx in chunk_keys:
                    key, en_val = untranslated[orig_idx]
                    result[key] = en_val
                    done += 1
            if progress_cb:
                pct = min(99, int(done * 100 / total_items))
                progress_cb(pct, f"Translating ({done}/{total_items})...")
        _save_cache(target_lang, cache)
    except Exception as e:
        print(f"[SERVICE] translate_batch ERROR for {target_lang}: {e}")
        traceback.print_exc()
        return {}

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
