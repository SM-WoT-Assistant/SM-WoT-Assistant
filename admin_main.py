"""Main entry for SM WoT Assistant Admin (web).

Architecture:
  - Backend: admin_backend.Application (Flask + background threads).
  - Frontend: pywebview window showing admin_web/ via http://127.0.0.1:8765/.
  - No tray icon — just a maximized browser window.
"""
from __future__ import annotations
import argparse
import ctypes
import os
import sys
import threading
import time

SW_MAXIMIZE = 3
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
HWND_TOP = 0


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


def _activate_window(hwnd: int) -> None:
    """Maximize + foreground + show window."""
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    try:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
    except Exception:
        pass
    try:
        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    except Exception:
        pass
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    try:
        user32.BringWindowToTop(hwnd)
    except Exception:
        pass
    print("[ADMIN] Window activated (maximized + foreground)")


def _set_window_icon(hwnd: int, ico_path: str) -> None:
    """Set window icon via WM_SETICON."""
    if not hwnd or not ico_path or not os.path.isfile(ico_path):
        return
    user32 = ctypes.windll.user32
    try:
        hicon = user32.LoadImageW(0, ico_path, 1, 0, 0, 0x0010)
        if hicon:
            user32.SendMessageW(hwnd, 0x0080, 0, hicon)
            user32.SendMessageW(hwnd, 0x0080, 1, hicon)
            print(f"[ADMIN] Window icon set from {os.path.basename(ico_path)}")
    except Exception as e:
        print(f"[ADMIN] Icon set failed: {e}")


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

    if not args.no_webview:
        try:
            import webview
            w = webview.create_window(
                "SM WoT Assistant Admin",
                f"http://127.0.0.1:{args.port}/",
                width=1100, height=700,
                maximized=True,
            )
            print("[ADMIN] Starting webview GUI (maximized)...")
            ico_path = _find_icon_path()

            def _post_start():
                """Called after webview GUI loop starts — activate and icon."""
                for _ in range(30):
                    time.sleep(0.5)
                    hwnd = _get_webview_hwnd()
                    if hwnd:
                        _activate_window(hwnd)
                        if ico_path:
                            _set_window_icon(hwnd, ico_path)
                        return
                print("[ADMIN] Could not find webview HWND after 15s")

            webview.start(func=_post_start)
            print("[ADMIN] webview closed")
        except ImportError:
            print("[ADMIN] pywebview not available, skipping GUI")
            print("[ADMIN] Falling back to default browser...")
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{args.port}/")
            try:
                input("Press Enter to exit...")
            except (KeyboardInterrupt, EOFError):
                pass

    cleanup()
    sys.exit(0)


if __name__ == "__main__":
    main()
    sys.exit(0)
