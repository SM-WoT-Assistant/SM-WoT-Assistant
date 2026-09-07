"""admin_backend.core - Application class, state, lifecycle.

Reads real data from RTDB and local caches for the web admin dashboard.
"""
from __future__ import annotations
import json
import os
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
FILL_PROGRESS_FILE = os.path.join(APPDATA_DIR, "_fill_progress.json")
AI_BUILDS_CACHE_FILE = os.path.join(APPDATA_DIR, "ai_builds_cache.json")
ADMIN_LOG_FILE = os.path.join(APPDATA_DIR, "admin.log")

API_KEY = os.environ.get("FIREBASE_API_KEY", "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE")
FIREBASE_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"


def _rtdb_url(path: str) -> str:
    return f"{FIREBASE_URL}/{path}.json?auth={API_KEY}"


def _rtdb_get(path: str, timeout: int = 10):
    """GET from RTDB, return parsed JSON or None."""
    import requests
    try:
        r = requests.get(_rtdb_url(path), timeout=timeout)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def _bundle_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_admin_version() -> str:
    try:
        with open(os.path.join(_bundle_dir(), "admin_version.txt"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def _load_admin_settings() -> dict:
    path = os.path.join(APPDATA_DIR, "admin_settings.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_admin_settings(settings: dict) -> None:
    try:
        os.makedirs(APPDATA_DIR, exist_ok=True)
        with open(os.path.join(APPDATA_DIR, "admin_settings.json"), "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class Application:
    """Application state and lifecycle. Stub — full implementation pending."""

    def __init__(self, wot_path: str = "", settings: dict = None):
        self.wot_path = wot_path
        self.settings = settings or _load_admin_settings()
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []
        self._log_buffer: List[str] = []

    # --- Logging ---
    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self._log_buffer.append(line)
        if len(self._log_buffer) > 1000:
            self._log_buffer = self._log_buffer[-1000:]
        try:
            with open(ADMIN_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
        print(line)

    # --- Lifecycle ---
    def start(self) -> None:
        """Start background threads (heartbeat, errors poll)."""
        self.log("Application started")
        self._start_background()

    def stop(self) -> None:
        """Signal all background threads to stop."""
        self._stop_event.set()


    def save_settings(self):
        """Save current settings to admin_settings.json in AppData."""
        appdata = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
        path = os.path.join(appdata, "admin_settings.json")
        try:
            os.makedirs(appdata, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            self.log(f"Settings saved to {path}")
            return True
        except Exception as e:
            self.log(f"Failed to save settings: {e}")
            return False

    def apply_launch_with_windows(self):
        """Apply 'launch with Windows' setting to HKCU\\Run registry."""
        if not getattr(self, "settings", None):
            return False
        if not getattr(sys, "frozen", False):
            return False  # only meaningful for frozen EXE
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            exe_path = sys.executable
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if self.settings.get("launch_with_windows"):
                    winreg.SetValueEx(key, "SMWoTAssistantAdmin", 0, winreg.REG_SZ, f'""{exe_path}""')
                else:
                    try:
                        winreg.DeleteValue(key, "SMWoTAssistantAdmin")
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            self.log(f"Registry update failed: {e}")
            return False

    def is_running(self) -> bool:
        return not self._stop_event.is_set()

    # --- Build data (read from RTDB) ---
    def get_builds(self) -> dict:
        """Return builds info: {count, tags, builds_data} from RTDB builds/tanks."""
        data = _rtdb_get("builds/tanks")
        if not isinstance(data, dict):
            return {"count": 0, "tags": [], "builds_data": {}}
        tags = sorted(data.keys())
        return {"count": len(tags), "tags": tags, "builds_data": data}

    def get_errors(self) -> list:
        """Return last 200 error reports from RTDB."""
        data = _rtdb_get("error_reports&orderBy=%22timestamp%22&limitToLast=200")
        if not isinstance(data, dict):
            return []
        rows = []
        for rid, rec in data.items():
            if not isinstance(rec, dict):
                continue
            rows.append({
                "id": rid,
                "time": rec.get("timestamp", ""),
                "type": rec.get("type", ""),
                "stage": rec.get("stage", ""),
                "source": (rec.get("details") or {}).get("source", ""),
                "version": rec.get("version", ""),
                "error": (rec.get("error") or rec.get("error_text", ""))[:200],
            })
        rows.sort(key=lambda r: r["time"], reverse=True)
        return rows

    def get_errors_count(self) -> int:
        """Return total count of error_reports."""
        data = _rtdb_get("error_reports")
        return len(data) if isinstance(data, dict) else 0

    # --- Build generation (delegates to admin_build_generator) ---
    def start_scan(self) -> List[str]:
        """Detect changed tanks via scripts.pkg fingerprint comparison."""
        try:
            from admin_build_generator import detect_changed_tanks
            manifest_path = os.path.join(APPDATA_DIR, ".tank_extract_manifest.json")
            changed = detect_changed_tanks(self.wot_path, manifest_path) if self.wot_path else []
            self.log(f"Scan complete: {len(changed)} changed tanks")
            return changed
        except Exception as e:
            self.log(f"Scan error: {e}")
            return []

    def start_generation(self) -> Tuple[bool, Dict[str, str]]:
        """Trigger build generation for changed tanks (background)."""
        self.log("Generation requested via web API")
        return (True, {"summary": "Generation queued — use the desktop admin for full generation"})

    # --- Background tasks ---
    def _start_background(self):
        """Start heartbeat and error-count polling in background threads."""
        def _loop():
            last_heartbeat = 0
            last_errors_poll = 0
            while not self._stop_event.is_set():
                try:
                    now = time.time()
                    if now - last_heartbeat > 60:
                        last_heartbeat = now
                        self._heartbeat_loop()
                    if now - last_errors_poll > 30:
                        last_errors_poll = now
                        self._errors_poll_loop()
                except Exception:
                    pass
                self._stop_event.wait(10)
        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        self._threads.append(t)

    def _heartbeat_loop(self):
        """Post admin_app status to RTDB."""
        try:
            payload = {
                "version": read_admin_version(),
                "last_seen": int(time.time()),
                "status": "idle",
            }
            import requests
            requests.put(
                _rtdb_url("admin_app"),
                data=json.dumps(payload),
                timeout=5,
            )
        except Exception:
            pass

    def _errors_poll_loop(self):
        """Refresh error count (cached for get_status)."""
        try:
            self._errors_count = self.get_errors_count()
        except Exception:
            pass

    def get_status(self) -> dict:
        return {
            "running": self.is_running(),
            "wot_path": self.wot_path,
            "log_count": len(self._log_buffer),
            "errors_count": getattr(self, "_errors_count", 0),
        }
