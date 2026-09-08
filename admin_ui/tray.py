"""Admin tray icon — pure Win32 ctypes (Shell_NotifyIconW).

Pattern taken from the main app's tray_icon.py and old admin_app.py.
Single-instance mutex via CreateMutexW + get_last_error()==183.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

SHELL32 = ctypes.WinDLL("shell32", use_last_error=True)
USER32 = ctypes.WinDLL("user32", use_last_error=True)

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
WM_USER = 0x0400

ICON_PATH = Path(__file__).parent.parent / "admin_icon.ico"

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

USER32.DefWindowProcW.argtypes = (
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)
USER32.DefWindowProcW.restype = ctypes.c_long


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", getattr(wintypes, 'HCURSOR', ctypes.c_void_p)),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", _GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


def _load_icon(path: Optional[str] = None) -> int:
    p = path or str(ICON_PATH)
    if not os.path.exists(p):
        p = str(Path(sys.executable).parent / "admin_icon.ico") if getattr(sys, 'frozen', False) else p
    try:
        hicon = ctypes.windll.user32.LoadImageW(
            0, p, 1, 0, 0, 0x00000010)
        if hicon:
            return hicon
    except Exception:
        pass
    return 0


class AdminTray:
    """System tray icon for the admin application."""

    def __init__(self, on_open: Optional[Callable] = None, on_exit: Optional[Callable] = None) -> None:
        self.on_open = on_open
        self.on_exit = on_exit
        self._hwnd: Optional[int] = None
        self._icon = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._wndproc_ref = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._hwnd:
            try:
                SHELL32.Shell_NotifyIconW(NIM_DELETE, self._nid(self._hwnd))
            except Exception:
                pass
            try:
                USER32.DestroyWindow(self._hwnd)
            except Exception:
                pass

    def show_notification(self, title: str, message: str) -> None:
        if not self._hwnd:
            return
        try:
            nid = self._nid(self._hwnd)
            nid.uFlags |= NIF_INFO
            nid.szInfoTitle = title[:64]
            nid.szInfo = message[:256]
            SHELL32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        except Exception:
            logger.warning("Failed to show notification", exc_info=True)

    def _run(self) -> None:
        h_instance = ctypes.windll.kernel32.GetModuleHandleW(None)

        self._wndproc_ref = WNDPROC(self._wndproc)
        wc = _WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(_WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = h_instance
        wc.lpszClassName = "SMAdminTray"
        wc.hCursor = ctypes.windll.user32.LoadCursorW(0, 32512)
        USER32.RegisterClassExW(ctypes.byref(wc))

        self._hwnd = int(ctypes.windll.user32.CreateWindowExW(
            0, "SMAdminTray", "SMAdminTray", 0, 0, 0, 0, 0,
            0, 0, h_instance, None))

        self._icon = _load_icon()
        nid = self._nid(self._hwnd)
        SHELL32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

        msg = wintypes.MSG()
        while self._running and ctypes.windll.user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    def _wndproc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        try:
            if msg == 0x0400:  # WM_USER (callback)
                if lparam == 0x0205:  # WM_RBUTTONUP
                    self._show_menu(hwnd)
                elif lparam == 0x0202:  # WM_LBUTTONUP
                    if self.on_open:
                        try:
                            self.on_open()
                        except Exception:
                            pass
            elif msg == 0x0002:  # WM_DESTROY
                self._running = False
                ctypes.windll.user32.PostQuitMessage(0)
        except Exception:
            pass
        return int(ctypes.windll.user32.DefWindowProcW(
            hwnd, msg, wintypes.WPARAM(wparam), wintypes.LPARAM(lparam)))

    def _show_menu(self, hwnd: int) -> None:
        hmenu = ctypes.windll.user32.CreatePopupMenu()
        ctypes.windll.user32.AppendMenuW(hmenu, 0x0000, 1, "Open Admin")
        ctypes.windll.user32.AppendMenuW(hmenu, 0x0000, 2, "Exit")
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        cmd = ctypes.windll.user32.TrackPopupMenu(
            hmenu, 0x0100, pt.x, pt.y, 0, hwnd, None)
        ctypes.windll.user32.DestroyMenu(hmenu)
        if cmd == 1:
            if self.on_open:
                try:
                    self.on_open()
                except Exception:
                    pass
        elif cmd == 2:
            if self.on_exit:
                try:
                    self.on_exit()
                except Exception:
                    pass

    def _nid(self, hwnd: int) -> _NOTIFYICONDATAW:
        nid = _NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid.uCallbackMessage = 0x0400
        nid.hIcon = self._icon
        nid.szTip = "SM WoT Assistant Admin"
        return nid
