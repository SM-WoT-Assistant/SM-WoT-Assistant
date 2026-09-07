"""admin_backend.prompts - load, save, merge (local + RTDB), and validation.

Extracted from admin_app.py (load_prompts, save_prompt) and
admin_build_generator.py (load_prompts_merged, _is_build_complete).
"""
from __future__ import annotations
import json
import os
import sys
from typing import Dict, Optional, Tuple

API_KEY = os.environ.get("FIREBASE_API_KEY", "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE")
FIREBASE_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"
PROMPTS_FILE = "prompts_cache.json"


def _data_dir():
    base = os.environ.get("APPDATA", ".")
    return os.path.join(base, "SM WoT Assistant")


def _rtdb_url(path: str) -> str:
    return f"{FIREBASE_URL}/{path}.json?auth={API_KEY}"


def load_prompts() -> Dict[str, str]:
    """Load local prompts_cache.json (fallback only)."""
    path = os.path.join(_data_dir(), PROMPTS_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_prompts_merged(timeout: int = 10) -> Dict[str, str]:
    """Load prompts from local + RTDB (RTDB overrides local)."""
    import requests
    local = load_prompts()
    try:
        r = requests.get(_rtdb_url("prompts/tanks"), timeout=timeout)
        if r.ok:
            remote = r.json() or {}
            # RTDB override local
            merged = dict(local)
            merged.update(remote)
            return merged
    except Exception:
        pass
    return local


def save_prompt(tag: str, prompt_text: str) -> bool:
    """Save prompt to local + RTDB."""
    import requests
    local = load_prompts()
    local[tag] = prompt_text
    try:
        os.makedirs(_data_dir(), exist_ok=True)
        with open(os.path.join(_data_dir(), PROMPTS_FILE), "w", encoding="utf-8") as f:
            json.dump(local, f, ensure_ascii=False, indent=2)
    except Exception:
        return False
    try:
        r = requests.put(_rtdb_url(f"prompts/tanks/{tag}"), data=json.dumps(prompt_text), timeout=10)
        return r.ok
    except Exception:
        return False


def is_build_complete(build_data: dict) -> bool:
    """Check if a build has equipment_1 and consumables_1 non-empty."""
    if not isinstance(build_data, dict):
        return False
    eq1 = build_data.get("equipment_1") or {}
    cons1 = build_data.get("consumables_1") or {}
    if not (isinstance(eq1, dict) and eq1) and not (isinstance(cons1, dict) and cons1):
        return False
    return True
