"""Admin data service — reads from local files, RTDB, and WG API.

Replaces admin_app.py's inline data loading with a clean module-level API.
All data sources are the same as the old admin_app — no new data paths.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config

APPDATA_DIR = Path(os.environ.get("APPDATA", "")) / "SM WoT Assistant"
MANIFEST_FILE = APPDATA_DIR / ".tank_extract_manifest.json"


def load_tank_db() -> Dict[str, dict]:
    """Load tank_db.json with bad-tag filtering."""
    try:
        from admin_build_generator import _is_bad_tag
    except ImportError:
        _is_bad_tag = lambda tag: False
    try:
        path = Path(config.BASE_DIR) / "tank_db.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return {tag: v for tag, v in data.items() if not _is_bad_tag(tag)}
    except Exception:
        return {}


def load_prompts() -> Dict[str, str]:
    """Load prompts_cache.json."""
    try:
        path = Path(config.BASE_DIR) / "prompts_cache.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {}


def load_prompts_merged() -> Dict[str, str]:
    """Merge local prompts with RTDB prompts/tanks/."""
    local = load_prompts()
    try:
        import firebase_reporter as fr
        url = fr._rtdb_url("prompts/tanks")
        import requests
        resp = requests.get(url, timeout=10)
        if resp.ok and resp.json():
            local.update(resp.json())
    except Exception:
        pass
    return local


def read_admin_version() -> str:
    """Read admin_version.txt."""
    try:
        candidates = [
            Path(config.BASE_DIR) / "admin_version.txt",
            APPDATA_DIR / "admin_version.txt",
        ]
        for p in candidates:
            if p.exists():
                return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "-"


def count_raw_tanks() -> int:
    """Count all tanks in tank_db.json (before bad-tag filtering).

    Prefers USER_DATA_DIR (updated by extraction pipeline) over BASE_DIR
    (bundled at build time, may be stale).
    """
    for d in (config.USER_DATA_DIR, config.BASE_DIR):
        path = Path(d) / "tank_db.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return len(data)
            except Exception:
                pass
    return 0


_WG_VEHICLES_URL = "https://api.worldoftanks.eu/wot/encyclopedia/vehicles/"
_WG_APP_ID = "0cc3f254142cf2e40511006d6cd18761"


def fetch_wg_tank_tags() -> set:
    """Fetch all tank tags from WG API (paginated, tags-only for speed).

    WG API uses numeric IDs as dict keys; the actual tag is in the 'tag' field.
    """
    import requests
    tags = set()
    try:
        page = 1
        while True:
            r = requests.get(_WG_VEHICLES_URL, params={
                "application_id": _WG_APP_ID, "language": "en",
                "limit": 100, "page": page, "fields": "tag"
            }, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            if data.get("status") != "ok":
                break
            items = data.get("data", {})
            if not items:
                break
            for _id, info in items.items():
                t = info.get("tag")
                if t:
                    tags.add(t)
            meta = data.get("meta", {})
            if page >= meta.get("page_total", 1):
                break
            page += 1
    except Exception:
        pass
    return tags


def cross_validate_wg() -> Dict[str, Any]:
    """Compare local tank_db with WG API. Returns summary dict."""
    local = load_tank_db()
    wg_tags = fetch_wg_tank_tags()
    if not wg_tags:
        return {"status": "wg_fetch_failed", "local_count": len(local), "wg_count": 0}
    local_tags = set(local.keys())
    new_in_wg = sorted(wg_tags - local_tags)
    missing_from_wg = sorted(local_tags - wg_tags)
    return {
        "status": "ok",
        "local_count": len(local),
        "wg_count": len(wg_tags),
        "new_in_wg": new_in_wg,
        "missing_from_wg": missing_from_wg,
    }


def check_wot_path(wot_path: str) -> Tuple[bool, Optional[str]]:
    """Check if WoT version.xml exists. Returns (exists, version_str)."""
    if not wot_path:
        return False, None
    vxml = Path(wot_path) / "version.xml"
    if not vxml.exists():
        return False, None
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(vxml))
        ver = tree.getroot().findtext("version", "")
        return True, ver
    except Exception:
        return True, None


def get_queue(tank_db: dict, prompts: dict, wot_path: str = "", manifest_path: str = "") -> List[str]:
    """Detect changed tanks via manifest fingerprinting."""
    if not wot_path:
        return []
    try:
        from admin_build_generator import detect_changed_tanks
        return detect_changed_tanks(wot_path, manifest_path or str(MANIFEST_FILE))
    except Exception:
        return []


def check_mismatch(tank_db: dict, prompts: dict) -> Tuple[List[str], List[str]]:
    """Return (prompts_only, tanks_only) lists."""
    try:
        from admin_build_generator import check_prompt_tank_mismatch
        return check_prompt_tank_mismatch(tank_db, prompts)
    except Exception:
        return [], []


def count_builds() -> int:
    """Count builds in RTDB builds/tanks."""
    try:
        import firebase_reporter as fr
        url = fr._rtdb_url("builds/tanks")
        import requests
        resp = requests.get(url, timeout=10)
        if resp.ok:
            data = resp.json()
            return len(data.keys()) if isinstance(data, dict) else 0
    except Exception:
        pass
    return 0


def get_build_tags() -> set:
    """Return set of tank tags that have builds in RTDB."""
    try:
        import firebase_reporter as fr
        url = fr._rtdb_url("builds/tanks")
        import requests
        resp = requests.get(url, timeout=10)
        if resp.ok:
            data = resp.json()
            if isinstance(data, dict):
                return set(data.keys())
    except Exception:
        pass
    return set()


def count_prompts() -> int:
    """Count prompts in RTDB prompts/tanks."""
    try:
        import firebase_reporter as fr
        url = fr._rtdb_url("prompts/tanks")
        import requests
        resp = requests.get(url, timeout=10)
        if resp.ok:
            data = resp.json()
            return len(data.keys()) if isinstance(data, dict) else 0
    except Exception:
        pass
    return 0


def get_pending_status(path: str = "builds") -> dict:
    """Read pending_updates/{path} from RTDB. Returns {status, message, progress, queue}."""
    try:
        import firebase_reporter as fr
        url = fr._rtdb_url(f"pending_updates/{path}")
        import requests
        resp = requests.get(url, timeout=10)
        if resp.ok:
            data = resp.json()
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _rtdb_put(path: str, data) -> bool:
    """Write JSON to Firebase RTDB using API key auth."""
    try:
        import firebase_reporter as fr
        import requests as _req
        url = fr._rtdb_url(path)  # type: ignore[attr-defined]
        resp = _req.put(url, json=data, timeout=15)
        return resp.ok
    except Exception:
        return False


def write_pending_queue(tanks: list, updated_at: str = None) -> None:
    """Write full queue list to pending_updates/queue in RTDB for website sync.
    tanks: [{"tag": "...", "name": "...", "tier": "10", "status": "waiting"}, ...]
    status: "waiting" | "generating" | "ok" | "fail"
    """
    import time as _time
    if updated_at is None:
        updated_at = _time.strftime("%Y-%m-%dT%H:%M:%S")
    _rtdb_put("pending_updates/queue", {"tanks": tanks, "updated_at": updated_at})


def update_queue_tank_status(tag: str, status: str) -> None:
    """Update a single tank's status in pending_updates/queue in RTDB."""
    try:
        import firebase_reporter as fr
        import requests as _req
        import time as _time
        url = fr._rtdb_url("pending_updates/queue")  # type: ignore[attr-defined]
        resp = _req.get(url, timeout=10)
        if resp.ok and resp.json():
            data = resp.json()
            tanks = data.get("tanks", [])
            for t in tanks:
                if t.get("tag") == tag:
                    t["status"] = status
                    break
            data["updated_at"] = _time.strftime("%Y-%m-%dT%H:%M:%S")
            _req.put(url, json=data, timeout=15)
    except Exception:
        pass


def write_pending_status(status: str, message: str = "") -> None:
    """Write final generation status (done/error) to pending_updates/builds in RTDB."""
    import time as _time
    data = {
        "status": status,
        "updated_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "message": message,
    }
    _rtdb_put("pending_updates/builds", data)


def get_errors_count() -> int:
    """Count error_reports from RTDB."""
    try:
        import firebase_reporter as fr
        url = fr._rtdb_url("error_reports?orderBy=%22timestamp%22&limitToLast=100")
        import requests
        resp = requests.get(url, timeout=10)
        if resp.ok:
            data = resp.json()
            return len(data) if data else 0
    except Exception:
        pass
    return 0


def get_error_reports() -> list:
    """Fetch error_reports from RTDB."""
    try:
        import firebase_reporter as fr
        url = fr._rtdb_url("error_reports?orderBy=%22timestamp%22&limitToLast=100")
        import requests
        resp = requests.get(url, timeout=10)
        if resp.ok:
            data = resp.json()
            if data:
                if isinstance(data, dict):
                    return list(data.values())
                return data
    except Exception:
        pass
    return []


def _rtdb_get(path: str, timeout: int = 10, use_admin_token: bool = False) -> Any:
    """GET from RTDB. First tries API key; if 401 and use_admin_token, retries with admin ID token."""
    import requests
    import firebase_reporter as fr
    url = fr._rtdb_url(path)
    resp = requests.get(url, timeout=timeout)
    if resp.ok:
        return resp.json()
    if resp.status_code == 401 and use_admin_token:
        try:
            from admin_auth import _rtdb_url_with_token
            auth_url = _rtdb_url_with_token(url)
            if auth_url:
                resp2 = requests.get(auth_url, timeout=timeout)
                if resp2.ok:
                    return resp2.json()
        except Exception:
            pass
    return None


def get_community_stats() -> Dict[str, Any]:
    """Aggregate community stats from RTDB + public APIs."""
    stats: Dict[str, Any] = {}
    try:
        stats["builds_ver"] = _rtdb_get("builds/version")
    except Exception:
        stats["builds_ver"] = None
    try:
        installs = _rtdb_get("installations", use_admin_token=True)
        stats["installs"] = len(installs) if isinstance(installs, dict) else 0
    except Exception:
        stats["installs"] = 0
    try:
        errors = _rtdb_get("error_reports?orderBy=%22timestamp%22&limitToLast=100")
        stats["errors"] = len(errors) if isinstance(errors, (dict, list)) else 0
    except Exception:
        stats["errors"] = 0
    try:
        import requests
        resp = requests.get("https://api.github.com/repos/SM-WoT-Assistant/SM-WoT-Assistant/releases", timeout=10)
        if resp.ok:
            releases = resp.json()
            total = sum(r.get("assets", [{}])[0].get("download_count", 0)
                        for r in releases if r.get("assets"))
            stats["github"] = {"total": total, "releases": len(releases)}
    except Exception:
        stats["github"] = None
    try:
        import requests
        resp = requests.get("https://www.patreon.com/api/campaigns/16413892", timeout=10,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.ok:
            data = resp.json()
            attrs = data.get("data", {}).get("attributes", {})
            stats["patreon"] = {
                "patrons": attrs.get("patron_count", 0),
                "pledge": attrs.get("pledge_url", ""),
            }
    except Exception:
        stats["patreon"] = None
    return stats


def get_status_color(wot_exists: bool, queue_len: int, errors_count: int) -> str:
    """Return status pill color based on state."""
    if errors_count > 0:
        return "#cc6666"
    if queue_len > 0:
        return "#ffaa00"
    if wot_exists:
        return "#66cc66"
    return "#888888"
