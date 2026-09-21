"""UI Translator — translates app-specific UI text to any language using Google Translate.
Protects keyboard shortcuts, symbols and numbers from translation."""

import os
import json
import re
import time
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

_MAX_CHUNK_CHARS = 4500
_NUMBERED_RE = re.compile(r"^\d+\.\s*(.+)$")

def _build_numbered(texts):
    """Build a numbered list from texts: '1. text1\\n2. text2'."""
    return "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))

def _parse_numbered(raw, expected_count):
    """Parse numbered list from Google response. Returns list of translated strings.
    Returns None if parsing fails (count mismatch, empty parts)."""
    if not raw:
        return None
    parts = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        m = _NUMBERED_RE.match(line)
        if m:
            parts.append(m.group(1).strip())
    if len(parts) != expected_count:
        return None
    if any(not p for p in parts):
        return None
    return parts

def _validate_parts(parts, original_texts):
    """Validate that translations are not shuffled (no duplicates with originals)."""
    if not parts:
        return False
    seen = set()
    for p in parts:
        if p in seen:
            return False
        seen.add(p)
    return True

def _translate_one_by_one(t, chunk_texts, chunk_keys, ph_list, untranslated, cache):
    """Translate texts one by one — slow but 100% reliable fallback."""
    result = {}
    for pi, orig_idx in enumerate(chunk_keys):
        key, en_val = untranslated[orig_idx]
        try:
            single = t.translate(chunk_texts[pi])
        except Exception:
            continue
        if single:
            trans = _unshield(single, ph_list[orig_idx])
            if trans and trans != en_val and not _looks_like_english(trans, en_val):
                cache[en_val] = trans
                result[key] = trans
            else:
                result[key] = en_val
    return result

def _looks_like_english(trans, original):
    """Reject translations that look identical to English source (Google passthrough)."""
    if not trans or not original:
        return False
    t = trans.strip().lower()
    o = original.strip().lower()
    return t == o

def _translate_chunk(t, chunk_texts, chunk_keys, chunk_phs, ph_list, untranslated, cache):
    """Translate a single chunk via GoogleTranslator using numbered format.
    Returns translated dict. On failure, falls back to one-by-one."""
    result = {}
    numbered = _build_numbered(chunk_texts)
    try:
        raw = t.translate(numbered)
    except Exception as e:
        if type(e).__name__ == "TranslationNotFound":
            print(f"[SERVICE] chunk identity-rejected — retrying one-by-one")
            return _translate_one_by_one(t, chunk_texts, chunk_keys, ph_list, untranslated, cache)
        print(f"[SERVICE] chunk failed ({type(e).__name__}) — retrying one-by-one")
        return _translate_one_by_one(t, chunk_texts, chunk_keys, ph_list, untranslated, cache)
    parts = _parse_numbered(raw, len(chunk_texts))
    if not parts or not _validate_parts(parts, chunk_texts):
        print(f"[SERVICE] chunk parse failed — retrying one-by-one")
        return _translate_one_by_one(t, chunk_texts, chunk_keys, ph_list, untranslated, cache)
    for pi, orig_idx in enumerate(chunk_keys):
        trans = _unshield(parts[pi], chunk_phs[pi] if pi < len(chunk_phs) else ph_list[orig_idx])
        key, en_val = untranslated[orig_idx]
        if trans and trans != en_val:
            cache[en_val] = trans
            result[key] = trans
        else:
            result[key] = en_val
    return result

def _translate_chunk_gtx(chunk_texts, chunk_keys, chunk_phs, ph_list, untranslated, cache, target_lang="uk"):
    """Fallback: translate via translate.googleapis.com (gtx client) using numbered format."""
    import requests as _req
    result = {}
    numbered = _build_numbered(chunk_texts)
    try:
        r = _req.get("https://translate.googleapis.com/translate_a/single",
                      params={"client": "gtx", "sl": "en", "tl": target_lang, "dt": "t", "q": numbered},
                      headers={"User-Agent": "Mozilla/5.0"},
                      timeout=10)
        data = r.json()
        if data and data[0]:
            raw_text = "".join(seg[0] for seg in data[0] if seg[0])
            parts = _parse_numbered(raw_text, len(chunk_texts))
            if parts:
                for pi, orig_idx in enumerate(chunk_keys):
                    trans = _unshield(parts[pi].strip(), ph_list[orig_idx])
                    key, en_val = untranslated[orig_idx]
                    if trans and trans != en_val:
                        cache[en_val] = trans
                        result[key] = trans
                    else:
                        result[key] = en_val
            else:
                print(f"[SERVICE] gtx parse failed — retrying one-by-one")
                return _translate_one_by_one_gtx(chunk_texts, chunk_keys, ph_list, untranslated, cache, target_lang)
    except Exception as e:
        print(f"[SERVICE] gtx fallback failed ({type(e).__name__})")
    return result

def _translate_one_by_one_gtx(chunk_texts, chunk_keys, ph_list, untranslated, cache, target_lang="uk"):
    """GTX one-by-one fallback."""
    import requests as _req
    result = {}
    for pi, orig_idx in enumerate(chunk_keys):
        key, en_val = untranslated[orig_idx]
        try:
            r = _req.get("https://translate.googleapis.com/translate_a/single",
                          params={"client": "gtx", "sl": "en", "tl": target_lang, "dt": "t", "q": chunk_texts[pi]},
                          headers={"User-Agent": "Mozilla/5.0"},
                          timeout=10)
            data = r.json()
            if data and data[0] and data[0][0]:
                trans = _unshield(data[0][0][0].strip(), ph_list[orig_idx])
                if trans and trans != en_val and not _looks_like_english(trans, en_val):
                    cache[en_val] = trans
                    result[key] = trans
                else:
                    result[key] = en_val
        except Exception:
            continue
    return result

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
        item_size = len(s) + 10
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
    except Exception as e:
        print(f"[SERVICE] translator init ERROR for {target_lang}: {e}")
        return {}
    gtx_failed = False
    for ci, (chunk_keys, chunk_phs, _) in enumerate(chunks):
        if ci > 0:
            time.sleep(0.5)
        chunk_texts = [shielded_list[i] for i in chunk_keys]
        chunk_result = _translate_chunk(
            t, chunk_texts, chunk_keys, chunk_phs,
            ph_list, untranslated, cache
        )
        has_real = any(
            chunk_result.get(untranslated[ci][0], "") != untranslated[ci][1]
            for ci in chunk_keys
            if untranslated[ci][0] in chunk_result
        )
        if not has_real and not gtx_failed:
            print(f"[SERVICE] deep_translator returned no real translations — trying gtx fallback")
            chunk_result = _translate_chunk_gtx(
                chunk_texts, chunk_keys, chunk_phs,
                ph_list, untranslated, cache
            )
            if not chunk_result:
                gtx_failed = True
        result.update(chunk_result)
        done += len(chunk_keys)
        if progress_cb:
            pct = min(99, int(done * 100 / total_items))
            progress_cb(pct, f"Translating ({done}/{total_items})...")
    _save_cache(target_lang, cache)

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
