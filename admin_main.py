"""Main entry for SM WoT Assistant Admin (web).

Architecture:
  - Backend: admin_backend.Application (Flask + background threads).
  - Frontend: default browser via webbrowser.open().
  - Tray: pure Win32 Shell_NotifyIconW (no pystray/pywebview dependency).
"""
from __future__ import annotations
import argparse
import ctypes
import ctypes.wintypes
import os
import sys
import time
import webbrowser


# ── Win32 constants ──
WM_APP = 0x8000
WM_TRAY_CALLBACK = WM_APP + 1
NIF_ICON = 0x00000001
NIF_MESSAGE = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
SW_RESTORE = 9


MUTEX_NAME = "SM_WoT_Assistant_Admin_SingleInstance"


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hWnd", ctypes.wintypes.HWND),
        ("uID", ctypes.c_uint),
        ("uFlags", ctypes.c_uint),
        ("uCallbackMessage", ctypes.c_uint),
        ("hIcon", ctypes.wintypes.HICON),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", ctypes.c_uint),
        ("dwStateMask", ctypes.c_uint),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeoutOrVersion", ctypes.c_uint),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.c_uint),
        ("guidItem", ctypes.c_wchar * 39),
        ("hBalloonIcon", ctypes.wintypes.HICON),
    ]


class _Win32Tray:
    """Pure Win32 system tray icon — no pystray/tkinter dependency."""

    def __init__(self, app_name: str, icon_path: str, on_activate, on_exit):
        self._app_name = app_name
        self._icon_path = icon_path
        self._on_activate = on_activate
        self._on_exit = on_exit
        self._hwnd = None
        self._hicon = 0
        self._registered = False

    def start(self):
        user32 = ctypes.windll.user32
        user32.DefWindowProcW.argtypes = [
            ctypes.wintypes.HWND, ctypes.wintypes.UINT,
            ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
        ]
        user32.DefWindowProcW.restype = ctypes.wintypes.LPARAM
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)

        WNDCLASSEXW = type("WNDCLASSEXW", (ctypes.Structure,), {"_fields_": [
            ("cbSize", ctypes.c_uint), ("style", ctypes.c_uint),
            ("lpfnWndProc", ctypes.c_void_p), ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int), ("hInstance", ctypes.wintypes.HINSTANCE),
            ("hIcon", ctypes.wintypes.HICON), ("hCursor", ctypes.c_void_p),
            ("hbrBackground", ctypes.c_void_p), ("lpszMenuName", ctypes.c_wchar_p),
            ("lpszClassName", ctypes.c_wchar_p), ("hIconSm", ctypes.wintypes.HICON),
        ]})

        def wndproc(hwnd, msg, wparam, lparam):
            try:
                if msg == WM_TRAY_CALLBACK and (lparam & 0xFFFF) in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self._on_activate()
            except Exception:
                pass
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = ctypes.WINFUNCTYPE(
            ctypes.wintypes.LPARAM, ctypes.wintypes.HWND, ctypes.wintypes.UINT,
            ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
        )(wndproc)

        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(cls)
        cls.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        cls.hInstance = hinst
        cls.lpszClassName = "AdminTrayClass"
        user32.RegisterClassExW(ctypes.byref(cls))

        self._hwnd = user32.CreateWindowExW(
            0, "AdminTrayClass", "", 0, 0, 0, 0, 0, 0, 0, hinst, None
        )

        if os.path.isfile(self._icon_path):
            self._hicon = user32.LoadImageW(0, self._icon_path, 1, 0, 0, 0x0010)
        if not self._hicon:
            self._hicon = user32.LoadIconW(0, 32512)

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid.uCallbackMessage = WM_TRAY_CALLBACK
        nid.hIcon = self._hicon
        nid.szTip = self._app_name
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        self._registered = True

    def notify(self, title: str, message: str):
        if not self._registered:
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = title[:64]
        nid.szInfo = message[:256]
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def remove(self):
        if not self._registered:
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = 1
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        self._registered = False
        if self._hwnd:
            ctypes.windll.user32.DestroyWindow(self._hwnd)
            self._hwnd = None


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
    for p in (r"C:\Games\World_of_Tanks_EU", r"D:\Games\World_of_Tanks_EU",
              r"C:\Program Files (x86)\World_of_Tanks_EU"):
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


def main():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    k32.CreateMutexW.restype = ctypes.c_void_p
    mutex = k32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == 183:
        print("[ADMIN] Another instance is running")
        sys.exit(0)

    parser = argparse.ArgumentParser(description="SM WoT Assistant Admin (web)")
    parser.add_argument("--wot-path", default="", help="Path to WoT installation")
    parser.add_argument("--port", type=int, default=8765, help="API port (default 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
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

    url = f"http://127.0.0.1:{args.port}/"

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
        if tray:
            tray.remove()
        if mutex:
            try:
                k32.CloseHandle(mutex)
            except Exception:
                pass

    import atexit
    atexit.register(cleanup)

    tray = None
    icon_path = _find_icon_path()

    def on_tray_activate():
        webbrowser.open(url)

    def on_tray_exit():
        cleanup()
        os._exit(0)

    tray = _Win32Tray("SM WoT Assistant Admin", icon_path, on_tray_activate, on_tray_exit)
    tray.start()
    print("[ADMIN] Tray icon started")

    if not args.no_browser:
        webbrowser.open(url)
        print(f"[ADMIN] Opened {url}")

    tray.notify("SM WoT Assistant Admin", f"Running on {url}")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, EOFError):
        pass

    cleanup()
    sys.exit(0)


if __name__ == "__main__":
    main()
    sys.exit(0)
