"""admin_backend.community - RTDB fetchers for YouTube/Reddit/GitHub/Ko-fi/Patreon
and helpers for the Admin App (Desktop) section on admin.html.

Pure HTTP/requests — no Selenium/Chrome here. Build pipeline (Chrome driver,
window-position=-32000,-32000) is in admin_backend.build_generator.
"""
from __future__ import annotations
import json
import os
import re
import time
from typing import Dict, List, Optional

API_KEY = os.environ.get("FIREBASE_API_KEY", "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE")
FIREBASE_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"


def _rtdb_url(path: str) -> str:
    return f"{FIREBASE_URL}/{path}.json?auth={API_KEY}"


def _rtdb_url_with_token(path: str, token: str) -> str:
    return f"{FIREBASE_URL}/{path}.json?auth={token}"


def _get_rtdb(path: str, timeout: int = 10):
    """GET a path from RTDB, return parsed JSON or None."""
    import requests
    try:
        r = requests.get(_rtdb_url(path), timeout=timeout)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def _put_json(path: str, data) -> bool:
    """PUT data to RTDB path, return True on success."""
    import requests
    try:
        r = requests.put(_rtdb_url(path), data=json.dumps(data), timeout=10)
        return r.ok
    except Exception:
        return False


# --- Public fetchers ---
def fetch_youtube() -> dict:
    """Fetch YouTube channel stats (manual login required via admin_vault)."""
    return {"ok": False, "error": "manual_login_required"}


def fetch_reddit() -> dict:
    """Fetch Reddit u/SM-WoT-Assistant stats (Content-Type=JSON required)."""
    return {"ok": False, "error": "manual_login_required"}


def fetch_github() -> dict:
    """Fetch GitHub releases (public API, no auth)."""
    import requests
    try:
        r = requests.get("https://api.github.com/repos/SM-WoT-Assistant/SM-WoT-Assistant/releases", timeout=10)
        if r.ok:
            data = r.json()
            return {"ok": True, "releases": data, "downloads": sum(a.get("download_count", 0) for r in data for a in r.get("assets", []))}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "fetch_failed"}


def fetch_ko_fi() -> dict:
    """Fetch Ko-fi donations (manual login required)."""
    return {"ok": False, "error": "manual_login_required"}


def fetch_patreon() -> dict:
    """Fetch Patreon public data (Patreon public API, no auth)."""
    import requests
    try:
        r = requests.get("https://www.patreon.com/api/campaigns/16413892", timeout=10)
        if r.ok and "application/json" in r.headers.get("content-type", ""):
            data = r.json()
            incl = (data.get("included") or [])
            posts = [x for x in incl if x.get("type") == "post"]
            return {
                "ok": True,
                "patrons": data.get("data", {}).get("attributes", {}).get("patron_count", 0),
                "paid": sum(1 for p in posts if (p.get("attributes", {}).get("current_user_pledge_amount_cents", 0) or 0) > 0),
                "pledge": data.get("data", {}).get("attributes", {}).get("pledge_sum_cents", 0) / 100,
                "currency": "USD",
                "posts": len(posts),
                "created": data.get("data", {}).get("attributes", {}).get("created_at", ""),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "fetch_failed"}


def fetch_installations() -> dict:
    """Count RTDB installations/ (each child = 1 user)."""
    data = _get_rtdb("installations")
    if not isinstance(data, dict):
        return {"count": 0, "items": {}}
    return {"count": len(data), "items": data}


def fetch_all_tiles() -> dict:
    """Fetch all 5 community tiles in one call (for the overview tab)."""
    return {
        "youtube": fetch_youtube(),
        "reddit": fetch_reddit(),
        "github": fetch_github(),
        "kofi": fetch_ko_fi(),
        "patreon": fetch_patreon(),
        "installations": fetch_installations(),
    }


def _read_community_cache() -> dict:
    """Read community_cache.json from AppData (whitelist only)."""
    cache_path = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "community_cache.json")
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        whitelist = ("youtube", "reddit", "github", "kofi", "patreon", "installations", "updated_at")
        return {k: v for k, v in data.items() if k in whitelist}
    except Exception:
        return {}
