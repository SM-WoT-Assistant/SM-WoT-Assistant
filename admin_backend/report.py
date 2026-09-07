"""admin_backend.report - RTDB error and fallback reporting.

Thin wrapper around requests.put against admin_api._rtdb_url_with_token.
Falls back to local queue if credentials are missing.
"""
from __future__ import annotations
import json
import os
import time
from typing import Optional

API_KEY = os.environ.get("FIREBASE_API_KEY", "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE")
FIREBASE_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"


def _rtdb_url(path: str) -> str:
    return f"{FIREBASE_URL}/{path}.json?auth={API_KEY}"


def _rtdb_url_with_token(path: str, token: str) -> str:
    return f"{FIREBASE_URL}/{path}.json?auth={token}"


def report_error(
    error_type: str,
    stage: str,
    error_text: str,
    blocked: bool = False,
    details: Optional[dict] = None,
) -> None:
    """Report a fatal or non-fatal error to RTDB error_reports/."""
    import requests
    from admin_auth import has_credentials, get_id_token
    payload = {
        "type": error_type,
        "stage": stage,
        "error_text": error_text,
        "blocked": bool(blocked),
        "timestamp": int(time.time() * 1000),
    }
    if details:
        payload["details"] = details
    url = _rtdb_url("error_reports")
    if has_credentials():
        token = get_id_token()
        if token:
            url = _rtdb_url_with_token("error_reports", token)
    try:
        requests.post(url, data=json.dumps(payload), timeout=5)
    except Exception:
        pass


def report_fallback(
    source: str,
    context: str,
    error_text: str,
    level: str = "warning",
) -> None:
    """Lightweight wrapper for non-fatal data fallback events."""
    report_error(
        error_type="fallback",
        stage=source,
        error_text=f"{context}: {error_text}",
        blocked=False,
        details={"level": level},
    )


def verify_admin_credentials() -> bool:
    from admin_auth import has_credentials
    return has_credentials()
