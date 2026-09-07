"""Main entry for SM WoT Assistant Admin (web).

Architecture:
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
import ctypes
import os
import sys
import threading
import time


def _resolve_wot_path(cli_path: str = "") -> str:
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


def _find_icon_path() -> str:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, "admin_icon.ico"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_icon.ico"))
    candidates.append("admin_icon.ico")
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""


def _configure_window(hwnd: int, ico_path: str) -> bool:
    """Set window icon + WS_EX_TOOLWINDOW (no taskbar) + fix focus."""
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    try:
        exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_exstyle = (exstyle | WS_EX_TOOLWINDOW) & ~WS_EX_NOACTIVATEAPP & ~WS_EX_APPWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_exstyle)
        print(f"[ADMIN] WS_EX_TOOLWINDOW set (no taskbar icon)")
    except Exception as e:
        print(f"[ADMIN] SetWindowLongW failed: {e}")
    if ico_path and os.path.isfile(ico_path):
        try:
            hicon = user32.LoadImageW(0, ico_path, 1, 0, 0, 0x0010)
            if hicon:
                user32.SendMessageW(hwnd, 0x0080, 0, hicon)
                user32.SendMessageW(hwnd, 0x0080, 1, hicon)
                print(f"[ADMIN] Window icon set from {os.path.basename(ico_path)}")
        except Exception as e:
            print(f"[ADMIN] Icon set failed: {e}")
    try:
        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    except Exception:
        pass
    return True


GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATEAPP = 0x08000000
WS_EX_APPWINDOW = 0x00040000
HWND_TOP = 0
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


def _get_webview_hwnd() -> int:
    try:
        import webview as wv
        if wv.windows:
            w = wv.windows[0]
            native = getattr(w, "native", None)
            if native is not None:
                handle = getattr(native, "Handle", None)
                if handle is not None:
                    return int(handle.ToInt32())
    except Exception:
        pass
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "SM WoT Assistant Admin")
        if hwnd:
            return hwnd
    except Exception:
        pass
    return 0


def main():
    parser = argparse.ArgumentParser(description="SM WoT Assistant Admin (web)")
    parser.add_argument("--wot-path", default="", help="Path to WoT installation")
    parser.add_argument("--port", type=int, default=8765, help="API port (default 8765)")
    parser.add_argument("--no-webview", action="store_true", help="Run API only (no webview window)")
    parser.add_argument("--no-tray", action="store_true", help="Skip pystray tray icon")
    parser.add_argument("--tray", dest="tray", action="store_true", default=True)
    args = parser.parse_args()

    wot_path = _resolve_wot_path(args.wot_path)

    from admin_backend.core import Application
    from admin_backend.api import set_app, run_api_threaded
    app = Application(wot_path=wot_path)
    set_app(app)
    app.start()
    api_thread = run_api_threaded(port=args.port)
    print(f"[ADMIN] API listening on http://127.0.0.1:{args.port}/")

    import socket
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", args.port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.1)
    print(f"[ADMIN] Flask API ready on 127.0.0.1:{args.port}")

    def cleanup():
        print("[ADMIN] Cleaning up...")
        try:
            from admin_backend.browser import close_browser
            close_browser()
        except Exception:
            pass
        try:
            app.stop()
        except Exception:
            pass

    import atexit
    atexit.register(cleanup)

    tray = None
    if not args.no_tray:
        try:
            from admin_backend.tray import AdminTray
            def on_open():
                print("[ADMIN] Open Admin Window clicked")
                try:
                    import webview as wv
                    if wv.windows:
                        wv.windows[0].show()
                except Exception:
                    pass
            def on_exit():
                print("[ADMIN] Exit clicked")
                if tray:
                    tray.stop()
                cleanup()
                os._exit(0)
            tray = AdminTray(on_open=on_open, on_exit=on_exit)
            tray.start()
            print("[ADMIN] Tray icon started")
        except ImportError:
            print("[ADMIN] pystray not available, skipping tray")

    if not args.no_webview:
        try:
            import webview
            w = webview.create_window(
                "SM WoT Assistant Admin",
                f"http://127.0.0.1:{args.port}/",
                width=1100, height=700,
            )
            print("[ADMIN] Starting webview GUI...")
            ico_path = _find_icon_path()
            def _configure_window_delayed():
                for _ in range(30):
                    time.sleep(0.5)
                    hwnd = _get_webview_hwnd()
                    if hwnd:
                        _configure_window(hwnd, ico_path)
                        return
                print("[ADMIN] Could not find webview HWND after 15s")
            if ico_path:
                threading.Thread(target=_configure_window_delayed, daemon=True).start()
            else:
                print("[ADMIN] admin_icon.ico not found")
            webview.start()
            print("[ADMIN] webview closed")
        except ImportError:
            print("[ADMIN] pywebview not available, skipping GUI")

    if tray:
        tray.stop()
    cleanup()
    sys.exit(0)


if __name__ == "__main__":
    main()
    sys.exit(0)
