"""admin_backend.tank_db - load tank_db.json with _BAD_TAG_MARKERS filter,
and client-side data extraction (list.xml + vehicle XML via WotXmlParser).
Pure Python — no Tkinter.
"""
from __future__ import annotations
import json
import os
import re
import sys
import tempfile
import zipfile
from typing import Dict, Optional, Tuple

try:
    from admin_backend.manifest import is_bad_tag
except ImportError:
    def is_bad_tag(tag): return False


def _data_dir():
    base = os.environ.get("APPDATA", ".")
    return os.path.join(base, "SM WoT Assistant")


NATION_IDS = {
    "ussr": 1, "germany": 2, "usa": 3, "france": 4, "uk": 5,
    "china": 6, "japan": 7, "czech": 8, "sweden": 9,
    "poland": 10, "italy": 11,
}


def load_tank_db() -> dict:
    """Load tank_db.json from AppData, with fallback chain to extracted_data."""
    candidates = [
        os.path.join(_data_dir(), "tank_db.json"),
        "tank_db.json",
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        # Filter bad tags
        return {k: v for k, v in data.items() if not is_bad_tag(k)}
    return {}


def check_prompt_tank_mismatch(tank_db: dict, prompts: dict):
    """Return (prompts_only, tanks_only) sets for the mismatch banner."""
    db_tags = set(tank_db.keys())
    prompt_tags = set(prompts.keys())
    return (prompt_tags - db_tags, db_tags - prompt_tags)


def _clean_xml(data: bytes) -> bytes:
    """Sanitize raw binary XML — replace & < > markers in CData-ish blocks."""
    if not data:
        return b""
    out = data.replace(b"\x00", b"")
    return out
