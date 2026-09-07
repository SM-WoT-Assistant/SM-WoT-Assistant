"""Main entry for SM WoT Assistant Admin (replaces admin_app.py).

Architecture:
  - CustomTkinter shell: skipped (pywebview is the only window now).
  - Backend: admin_backend.Application (Flask + background threads).
  - Frontend: pywebview window showing admin_web/ via http://127.0.0.1:8765/.
  - Tray: pystray (optional, --no-tray to disable).

Modes:
  - default:       API + webview + tray
  - --no-webview:  API + tray (backend-only testing)
  - --no-tray:     API + webview (no tray icon)
"""
from __future__ import annotations
import argparse
import os
import sys
import threading
import time


def _resolve_wot_path(cli_path: str = "") -> str:
    """Resolve WoT path: CLI arg > admin_settings.json > settings.json > common paths."""
    if cli_path and os.path.isdir(cli_path):
        return cli_path
    appdata = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
    for fname in ("admin_settings.json", "settings.json"):
        path = os.path.join(appdata, fname)
        if not os.path.exists(path):
            continue
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            wp = cfg.get("wot_path", "")
            if wp and os.path.isdir(wp):
                return wp
        except Exception:
            pass
    common_paths = [
        r"C:\Games\World_of_Tanks_EU",
        r"D:\Games\World_of_Tanks_EU",
        r"C:\Program Files (x86)\World_of_Tanks_EU",
    ]
    for p in common_paths:
        if os.path.isdir(p):
            return p
    return ""


def main():
    parser = argparse.ArgumentParser(description="SM WoT Assistant Admin (web)")
    parser.add_argument("--wot-path", default="", help="Path to WoT installation")
    parser.add_argument("--port", type=int, default=8765, help="API port (default 8765)")
    parser.add_argument("--no-webview", action="store_true", help="Run API only (no webview window)")
    parser.add_argument("--no-tray", action="store_true", help="Skip pystray tray icon")
    parser.add_argument("--tray", dest="tray", action="store_true", default=True)
    args = parser.parse_args()

    wot_path = _resolve_wot_path(args.wot_path)

    # Start backend
    from admin_backend.core import Application
    from admin_backend.api import set_app, run_api_threaded
    app = Application(wot_path=wot_path)
    set_app(app)
    app.start()
    api_thread = run_api_threaded(port=args.port)
    print(f"[ADMIN] API listening on http://127.0.0.1:{args.port}/")

    # Start webview
    if not args.no_webview:
        try:
            import webview
            def open_window():
                webview.create_window(
                    "SM WoT Assistant Admin",
                    f"http://127.0.0.1:{args.port}/",
                    width=1100, height=700,
                )
            threading.Thread(target=open_window, daemon=True).start()
        except ImportError:
            print("[ADMIN] pywebview not available, skipping GUI")

    # Start tray
    if not args.no_tray:
        try:
            from admin_backend.tray import AdminTray
            def on_open():
                print("[ADMIN] Open Admin Window clicked")
            def on_exit():
                print("[ADMIN] Exit clicked")
                app.stop()
                sys.exit(0)
            tray = AdminTray(on_open=on_open, on_exit=on_exit)
            tray.start()
        except ImportError:
            print("[ADMIN] pystray not available, skipping tray")

    # Block main thread
    try:
        while app.is_running():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[ADMIN] KeyboardInterrupt, stopping")
        app.stop()


if __name__ == "__main__":
    main()
    sys.exit(0)
