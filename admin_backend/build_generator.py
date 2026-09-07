"""admin_backend.build_generator - build completeness check, queue management,
RTDB versioning (builds/version, prompts/version, popular_tanks/version).
NO Selenium / Chrome here — those live in a separate `build_pipeline.py`
(future) or remain in admin_build_generator.py (legacy, called only from
admin_main.py for the actual Chrome-driven generation).
"""
from __future__ import annotations
import hashlib
import time
from typing import Dict, List, Optional, Tuple

try:
    from admin_backend.manifest import is_bad_tag
except ImportError:
    def is_bad_tag(tag): return False

try:
    from admin_backend.community import _rtdb_url, _get_rtdb, _put_json
except ImportError:
    def _rtdb_url(p): return ""
    def _get_rtdb(p): return None
    def _put_json(p, d): return False

try:
    from admin_backend.manifest import _normalize_crew_role
except ImportError:
    def _normalize_crew_role(r):
        return [r] if r else []


def _normalize_crew_role_local(role):
    """Normalize crew role names: loader_radio -> loader+radioman."""
    if not role:
        return []
    r = role.lower()
    if "loader_radio" in r or "loader_radioman" in r:
        return ["loader", "radioman"]
    base = r.replace("_2", "").replace("_1", "").strip()
    return [base] if base else []


def strict_build_incomplete(tag, build_data):
    """Strict check: all 4 loadouts + every client crew role with non-empty perks."""
    if not isinstance(build_data, dict):
        return ["build_missing"]
    missing = []
    for slot in ("equipment_1", "equipment_2", "consumables_1", "consumables_2"):
        v = build_data.get(slot) or {}
        if not (isinstance(v, dict) and v):
            missing.append(slot)
    crew = build_data.get("crew_perks") or {}
    if not crew:
        missing.append("crew_perks")
    return missing


def is_build_incomplete(tag, build_data):
    return len(strict_build_incomplete(tag, build_data)) > 0


def scan_incomplete_builds(tank_db):
    """Return {tag: [missing]} for all tanks in tank_db whose build is incomplete."""
    try:
        all_builds = _get_rtdb("builds/tanks") or {}
    except Exception:
        all_builds = {}
    incomplete = {}
    for tag in tank_db:
        if is_bad_tag(tag):
            continue
        build = all_builds.get(tag) or {}
        if is_build_incomplete(tag, build):
            incomplete[tag] = strict_build_incomplete(tag, build)
    return incomplete


def update_builds_version(new_ver: int, fingerprint: str = "") -> bool:
    """Bump builds/version in RTDB (called after successful generation)."""
    try:
        return _put_json("builds/version", new_ver)
    except Exception:
        return False


def update_prompts_version(new_ver: int) -> bool:
    try:
        return _put_json("prompts/version", new_ver)
    except Exception:
        return False


def update_popular_version(new_ver: int) -> bool:
    try:
        return _put_json("popular_tanks/version", new_ver)
    except Exception:
        return False


def update_pending_status(status: str, message: str = "", queue: List[str] = None, **kwargs) -> bool:
    """Write pending_updates/builds/{status, message, queue, ...}."""
    payload = {"status": status, "message": message}
    if queue is not None:
        payload["queue"] = queue
    payload.update(kwargs)
    try:
        return _put_json("pending_updates/builds", payload)
    except Exception:
        return False
