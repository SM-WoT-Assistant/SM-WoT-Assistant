"""admin_backend.manifest - scripts.pkg vehicle XML fingerprint detection.

Extracted from admin_app.py (lines 195-491) and admin_build_generator.py
(detect_changed_tanks, snapshot_manifest, update_manifest_for_tags).
Pure Python — no Tkinter, no admin app dependencies.
"""
from __future__ import annotations
import json
import os
import threading
import time
import zipfile
from typing import Dict, List, Optional, Set, Tuple


_BAD_TAG_MARKERS = (
    "_7x7", "_fallout", "_fl", "_sh", "_bootcamp", "_igr", "_test", "_training",
    "tutorial", "observer", "r05_kv", "r70_t_50_2", "sherman_crab", "g00_",
    "_cfe", "auto_s", "auto_test", "_shxxi", "_bomber", "pillbox", "env_artillery",
    "a08_t23", "a26_t18", "a15_t57", "_newonboarding", "_storymode",
)
_FAIL_THRESHOLD = 3
_MANIFEST_LOCK = threading.Lock()


def is_bad_tag(tag: str) -> bool:
    """True if the tank tag is an event clone that should not be generated."""
    if not tag:
        return True
    return any(m in tag for m in _BAD_TAG_MARKERS)


def manifest_default_path() -> str:
    return os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant",
                        ".tank_extract_manifest.json")


def _entry_fingerprint(name: str, data: bytes) -> dict:
    import zlib
    return {
        "name": name,
        "size": len(data),
        "crc": zlib.crc32(data) & 0xFFFFFFFF,
        "mtime": int(time.time() * 1000),
    }


def _fingerprint_equal(a: dict, b: dict) -> bool:
    if not a or not b:
        return False
    return a.get("size") == b.get("size") and a.get("crc") == b.get("crc")


def snapshot_manifest(wot_path: str, manifest_path: str) -> bool:
    """Create a fresh manifest with fingerprints for all current vehicle XMLs."""
    if not wot_path or not os.path.isdir(wot_path):
        return False
    scripts_pkg = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.isfile(scripts_pkg):
        return False
    new_manifest = {"tanks": {}, "_failures": {}, "_pending": {}}
    try:
        with zipfile.ZipFile(scripts_pkg) as z:
            for name in z.namelist():
                if not (name.startswith("item_defs/vehicles/") and name.endswith(".xml")):
                    continue
                tag = os.path.basename(name).rsplit(".", 1)[0]
                if is_bad_tag(tag):
                    continue
                data = z.read(name)
                new_manifest["tanks"][tag] = _entry_fingerprint(name, data)
    except Exception:
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(new_manifest, f, indent=2)
        return True
    except Exception:
        return False


def detect_changed_tanks(wot_path: str, manifest_path: str = None) -> List[str]:
    """Return tank tags whose vehicle XML changed in scripts.pkg."""
    if manifest_path is None:
        manifest_path = manifest_default_path()
    if not wot_path or not os.path.isdir(wot_path):
        return []
    scripts_pkg = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.isfile(scripts_pkg):
        return []
    with _MANIFEST_LOCK:
        old = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    old = data.get("tanks", {})
            except Exception:
                old = {}
        new_fps: Dict[str, dict] = {}
        try:
            with zipfile.ZipFile(scripts_pkg) as z:
                for name in z.namelist():
                    if not (name.startswith("item_defs/vehicles/") and name.endswith(".xml")):
                        continue
                    tag = os.path.basename(name).rsplit(".", 1)[0]
                    if is_bad_tag(tag):
                        continue
                    data = z.read(name)
                    new_fps[tag] = _entry_fingerprint(name, data)
        except Exception:
            return []
        changed = []
        for tag, fp in new_fps.items():
            if not _fingerprint_equal(old.get(tag, {}), fp):
                changed.append(tag)
        return changed


def _mark_pending(manifest_path: str, tags: List[str], fps: dict) -> None:
    if not tags or not manifest_path:
        return
    with _MANIFEST_LOCK:
        if not os.path.exists(manifest_path):
            return
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        pending = data.setdefault("_pending", {})
        for t in tags:
            pending[t] = fps.get(t, {})
        try:
            tmp = manifest_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, manifest_path)
        except Exception:
            pass


def _manifest_failures(manifest_path: str) -> dict:
    if not os.path.exists(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("_failures", {}) or {}
    except Exception:
        return {}


def update_manifest_for_tags(wot_path: str, manifest_path: str, tags: List[str]) -> bool:
    """After successful generation, advance manifest entries."""
    if not tags or not os.path.exists(manifest_path):
        return False
    with _MANIFEST_LOCK:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False
        scripts_pkg = os.path.join(wot_path or "", "res", "packages", "scripts.pkg")
        if not os.path.isfile(scripts_pkg):
            return False
        try:
            with zipfile.ZipFile(scripts_pkg) as z:
                for tag in tags:
                    name = f"item_defs/vehicles/{tag[:2]}/{tag}.xml"
                    if name in z.namelist():
                        z_data = z.read(name)
                        data.setdefault("tanks", {})[tag] = _entry_fingerprint(name, z_data)
                    data.setdefault("_failures", {}).pop(tag, None)
                    data.setdefault("_pending", {}).pop(tag, None)
        except Exception:
            return False
        try:
            tmp = manifest_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, manifest_path)
            return True
        except Exception:
            return False


def update_manifest_failures(wot_path: str, manifest_path: str, failed_tags: List[str]) -> bool:
    """Increment failure count for tags that failed generation."""
    if not failed_tags or not os.path.exists(manifest_path):
        return False
    with _MANIFEST_LOCK:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False
        scripts_pkg = os.path.join(wot_path or "", "res", "packages", "scripts.pkg")
        fps = {}
        if os.path.isfile(scripts_pkg):
            try:
                with zipfile.ZipFile(scripts_pkg) as z:
                    for tag in failed_tags:
                        name = f"item_defs/vehicles/{tag[:2]}/{tag}.xml"
                        if name in z.namelist():
                            fps[tag] = _entry_fingerprint(name, z.read(name))
            except Exception:
                pass
        failures = data.setdefault("_failures", {})
        for t in failed_tags:
            entry = failures.get(t, {"count": 0, "fp": None})
            entry["count"] = entry.get("count", 0) + 1
            if t in fps:
                entry["fp"] = fps[t]
            failures[t] = entry
        try:
            tmp = manifest_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, manifest_path)
            return True
        except Exception:
            return False


def exclude_failed_tags(tags: List[str], manifest_path: str, wot_path: str = "") -> List[str]:
    """Filter out tags that have failed >= _FAIL_THRESHOLD times with same fp."""
    fails = _manifest_failures(manifest_path)
    if not fails:
        return tags
    out = []
    for t in tags:
        if t in fails and fails[t].get("count", 0) >= _FAIL_THRESHOLD:
            continue
        out.append(t)
    return out
