"""admin_backend.core - Application class, state, lifecycle.

Extracted from admin_app.py:AdminApp.__init__ (state setup) and the
periodic background tasks (scan, generate, heartbeat, errors poll, sweep).

NOTE: Reconstructed from PYZ-00.pyc bytecode. Functions exist with correct
signatures but the bodies are stubs. Full re-implementation pending.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
FILL_PROGRESS_FILE = os.path.join(APPDATA_DIR, "_fill_progress.json")
AI_BUILDS_CACHE_FILE = os.path.join(APPDATA_DIR, "ai_builds_cache.json")
ADMIN_LOG_FILE = os.path.join(APPDATA_DIR, "admin.log")


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
        """Start background threads (heartbeat, scan, sweep, errors poll)."""
        self.log("Application started (stub)")

    def stop(self) -> None:
        """Signal all background threads to stop."""
        self._stop_event.set()

    def is_running(self) -> bool:
        return not self._stop_event.is_set()

    # --- Background tasks (stubs) ---
    def _heartbeat_loop(self):
        pass

    def _scan_loop(self):
        pass

    def _errors_poll_loop(self):
        pass

    def _sweep_loop(self):
        pass

    # --- Build generation (stubs) ---
    def start_scan(self) -> List[str]:
        return []

    def start_generation(self) -> Tuple[int, Dict[str, str]]:
        return (0, {})

    def get_status(self) -> dict:
        return {
            "running": self.is_running(),
            "wot_path": self.wot_path,
            "log_count": len(self._log_buffer),
        }
