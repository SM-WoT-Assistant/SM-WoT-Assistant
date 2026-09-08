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


_REDDIT_USER = "SM-WoT-Assistant"
_REDDIT_OAUTH_URL = "https://www.reddit.com/api/v1/access_token"
_REDDIT_API_BASE = "https://oauth.reddit.com"


def _vault_get(service: str, field: str):
    """Retrieve a decrypted credential from admin_vault."""
    try:
        import admin_vault
        return admin_vault.vault_get(service, field)
    except Exception:
        return None


# --- Public fetchers ---
def fetch_youtube() -> dict:
    """Fetch YouTube channel stats via Data API v3 (public API key from vault)."""
    api_key = _vault_get("youtube", "api_key")
    if not api_key:
        return {"ok": False, "error": "no_api_key"}
    import requests
    try:
        url = (
            "https://www.googleapis.com/youtube/v3/channels"
            "?part=statistics&forHandle=SMWoTAssistant&key=" + api_key
        )
        r = requests.get(url, timeout=10)
        if r.ok:
            data = r.json()
            items = data.get("items", [])
            if items:
                stats = items[0].get("statistics", {})
                return {
                    "ok": True,
                    "views": int(stats.get("viewCount", 0)),
                    "subscribers": int(stats.get("subscriberCount", 0)),
                    "videos": int(stats.get("videoCount", 0)),
                }
            return {"ok": False, "error": "channel_not_found"}
        return {"ok": False, "error": f"http_{r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}


def fetch_reddit() -> dict:
    """Fetch Reddit u/SM-WoT-Assistant posts via OAuth2 Script flow.

    Uses bot account credentials from admin_vault (reddit/client_id,
    reddit/client_secret, reddit/username, reddit/password).
    Returns post count + recent posts list.
    """
    client_id = _vault_get("reddit", "client_id")
    client_secret = _vault_get("reddit", "client_secret")
    username = _vault_get("reddit", "username")
    password = _vault_get("reddit", "password")
    if not all([client_id, client_secret, username, password]):
        return {"ok": False, "error": "no_vault_credentials"}
    import requests
    from requests.auth import HTTPBasicAuth
    try:
        token_resp = requests.post(
            _REDDIT_OAUTH_URL,
            data={"grant_type": "password", "username": username, "password": password},
            auth=HTTPBasicAuth(str(client_id), str(client_secret)),
            headers={"User-Agent": "SMWoTAssistant/1.0 (admin bot)"},
            timeout=10,
        )
        if not token_resp.ok:
            return {"ok": False, "error": f"token_http_{token_resp.status_code}"}
        access_token = token_resp.json().get("access_token")
        if not access_token:
            return {"ok": False, "error": "no_access_token"}
        posts_resp = requests.get(
            f"{_REDDIT_API_BASE}/user/{_REDDIT_USER}/submitted",
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "SMWoTAssistant/1.0 (admin bot)",
            },
            params={"limit": 25, "raw_json": 1},
            timeout=10,
        )
        if not posts_resp.ok:
            return {"ok": False, "error": f"posts_http_{posts_resp.status_code}"}
        children = posts_resp.json().get("data", {}).get("children", [])
        posts = []
        for ch in children:
            d = ch.get("data", {})
            posts.append({
                "title": d.get("title", ""),
                "date": time.strftime("%Y-%m-%d", time.localtime(d.get("created_utc", 0))),
                "score": d.get("score", 0),
                "comments": d.get("num_comments", 0),
                "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                "subreddit": d.get("subreddit", ""),
            })
        return {"ok": True, "posts": posts, "count": len(posts)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}


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
    """Fetch all community tiles in parallel with hard 5s timeout (for dashboard)."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    platforms = {
        "youtube": fetch_youtube,
        "reddit": fetch_reddit,
        "github": fetch_github,
        "kofi": fetch_ko_fi,
        "patreon": fetch_patreon,
        "installations": fetch_installations,
    }
    result = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {name: ex.submit(fn) for name, fn in platforms.items()}
        for name, fut in futures.items():
            try:
                result[name] = fut.result(timeout=5)
            except FuturesTimeout:
                result[name] = {"ok": False, "error": "timeout"}
            except Exception as e:
                result[name] = {"ok": False, "error": str(e) or "error"}
    return result


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
