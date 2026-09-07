"""admin_backend.tray - pystray-based system tray icon.

Replaces the old AdminTray from admin_app.py. Pure pystray, no Tkinter
or pywebview dependency — safe to import from backend (Flask API thread)
without UI thread collisions.
"""
from __future__ import annotations
import os
import sys
import threading
from typing import Callable, Optional

_HAS_PYSTRAY = False
try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image
    _HAS_PYSTRAY = True
except ImportError:
    pass


class AdminTray:
    """pystray-based tray icon. Click 'Open Admin Window' to show the webview."""

    def __init__(self, on_open: Callable, on_exit: Callable, icon_path: Optional[str] = None):
        self._on_open = on_open
        self._on_exit = on_exit
        self._icon_path = icon_path or os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "admin_icon.ico")
        self._icon: Optional["Icon"] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the tray icon in a daemon thread."""
        if not _HAS_PYSTRAY:
            return
        if self._icon is not None:
            return
        try:
            image = Image.open(self._icon_path) if os.path.exists(self._icon_path) else None
            if image is None:
                # Fallback: 1x1 black image
                image = Image.new("RGBA", (16, 16), (0, 0, 0, 255))
        except Exception:
            image = Image.new("RGBA", (16, 16), (0, 0, 0, 255))
        menu = Menu(
            MenuItem("Open Admin Window", lambda *_: self._on_open()),
            MenuItem("Exit", lambda *_: self._on_exit()),
        )
        self._icon = Icon("SM WoT Assistant Admin", image, "SM WoT Assistant Admin", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
            self._thread = None

    def notify(self, title: str, message: str):
        """Show a balloon notification (best-effort)."""
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass
