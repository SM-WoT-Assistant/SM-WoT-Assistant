"""Admin tray icon — pure Win32 ctypes (Shell_NotifyIconW).

Follows the same pattern as the main app's tray_icon.py:
message-only window, WNDPROC sets a flag, main thread polls.
Left click = open/restore window. Right click = context menu (Restore / Exit).
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

SHELL32 = ctypes.windll.shell32
USER32 = ctypes.windll.user32
KERNEL32 = ctypes.windll.kernel32

USER32.DefWindowProcW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
USER32.DefWindowProcW.restype = wintypes.LPARAM

WM_APP = 0x8000
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 1
NIF_ICON = 2
NIF_TIP = 4
NIF_INFO = 0x10
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_COMMAND = 0x0111
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

IDM_RESTORE = 1001
IDM_EXIT = 1002

TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100

ICON_PATH = Path(__file__).parent.parent / "admin_icon.ico"


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

_active_tray: Optional["AdminTray"] = None
_class_registered = False
_global_wndproc = None


def _global_wndproc_func(hwnd, msg, wparam, lparam):
    if msg == WM_APP and lparam == WM_LBUTTONUP:
        if _active_tray is not None:
            _active_tray._on_click_left()
    elif msg == WM_APP and lparam == WM_RBUTTONUP:
        if _active_tray is not None:
            _active_tray._show_menu_flag = True
    return USER32.DefWindowProcW(hwnd, msg, wparam, lparam)


_wndproc_instance = WNDPROC(_global_wndproc_func)


def _ensure_class_registered() -> None:
    global _class_registered, _global_wndproc
    if _class_registered:
        return
    hinstance = KERNEL32.GetModuleHandleW(None)
    _global_wndproc = ctypes.cast(_wndproc_instance, ctypes.c_void_p).value
    wc = WNDCLASSW()
    wc.lpfnWndProc = _global_wndproc
    wc.hInstance = hinstance
    wc.lpszClassName = "SMAdminTray"
    atom = USER32.RegisterClassW(ctypes.byref(wc))
    if atom:
        _class_registered = True


class AdminTray:
    """System tray icon for the admin application.

    Left click = open/restore window.
    Right click = context menu (Restore / Exit).
    Polling pattern — WNDPROC sets flags, main thread handles actions.
    """

    def __init__(
        self,
        on_open: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
    ) -> None:
        self.on_open = on_open
        self.on_exit = on_exit
        self._click_left = False
        self._show_menu_flag = False
        self._destroyed = False
        self._msg_hwnd = 0
        self._nid: Optional[NOTIFYICONDATAW] = None
        self._hicon = 0
        self._root: Any = None
        self._poll_id: Any = None

    def start(self, root: Any = None) -> None:
        global _active_tray
        if self._destroyed:
            return
        self._root = root
        _ensure_class_registered()

        self._hicon = self._load_icon()

        hinstance = KERNEL32.GetModuleHandleW(None)
        self._msg_hwnd = USER32.CreateWindowExW(
            0, "SMAdminTray", "",
            0, 0, 0, 0, 0,
            None, None, hinstance, None,
        )
        if not self._msg_hwnd:
            print("[TRAY] Failed to create message window")
            return

        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = self._msg_hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self._nid.uCallbackMessage = WM_APP
        self._nid.hIcon = self._hicon
        self._nid.szTip = "SM WoT Assistant Admin"

        if SHELL32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid)):
            _active_tray = self
            self._start_poll()
        else:
            print("[TRAY] Shell_NotifyIconW NIM_ADD failed")

    def _start_poll(self) -> None:
        if self._root is not None:
            self._poll_id = self._root.after(250, self._poll)

    def _poll(self) -> None:
        if self._destroyed:
            return
        if self._click_left:
            self._click_left = False
            if self.on_open:
                try:
                    self._root.after_idle(self.on_open)
                except Exception:
                    pass
        if self._show_menu_flag:
            self._show_menu_flag = False
            self._show_context_menu()
        if not self._destroyed:
            self._poll_id = self._root.after(250, self._poll)

    def _on_click_left(self) -> None:
        """Called from WNDPROC — just set flag, no Tk calls."""
        self._click_left = True

    def _show_context_menu(self) -> None:
        """Show right-click context menu on the main thread."""
        if self._destroyed or not self._msg_hwnd:
            return
        try:
            pt = wintypes.POINT()
            USER32.GetCursorPos(ctypes.byref(pt))
            USER32.SetForegroundWindow(self._msg_hwnd)

            h_menu = USER32.CreatePopupMenu()
            if not h_menu:
                return
            USER32.AppendMenuW(h_menu, 0, IDM_RESTORE, "Restore")
            USER32.AppendMenuW(h_menu, 0x0800, 0, None)  # MF_SEPARATOR
            USER32.AppendMenuW(h_menu, 0, IDM_EXIT, "Exit")

            cmd = USER32.TrackPopupMenu(
                h_menu,
                TPM_RIGHTBUTTON | TPM_NONOTIFY | TPM_RETURNCMD,
                pt.x, pt.y, 0, self._msg_hwnd, None,
            )
            USER32.DestroyMenu(h_menu)
            USER32.PostMessageW(self._msg_hwnd, WM_APP, 0, 0)

            if cmd == IDM_RESTORE:
                if self.on_open:
                    try:
                        self._root.after_idle(self.on_open)
                    except Exception:
                        pass
            elif cmd == IDM_EXIT:
                if self.on_exit:
                    try:
                        self._root.after_idle(self.on_exit)
                    except Exception:
                        pass
        except Exception:
            logger.warning("Context menu failed", exc_info=True)

    def _load_icon(self) -> int:
        p = str(ICON_PATH)
        if not os.path.exists(p):
            if getattr(sys, 'frozen', False):
                p = str(Path(sys.executable).parent / "admin_icon.ico")
        if not os.path.exists(p):
            return 0
        try:
            hicon = USER32.LoadImageW(0, p, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            return hicon if hicon else 0
        except Exception:
            return 0

    def stop(self) -> None:
        global _active_tray
        if _active_tray is self:
            _active_tray = None
        self._destroyed = True
        if self._nid:
            try:
                SHELL32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            except Exception:
                pass
            self._nid = None
        if self._msg_hwnd:
            try:
                USER32.DestroyWindow(self._msg_hwnd)
            except Exception:
                pass
            self._msg_hwnd = 0
        if self._poll_id and self._root:
            try:
                self._root.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        if self._hicon:
            try:
                USER32.DestroyIcon(self._hicon)
            except Exception:
                pass
            self._hicon = 0

    def show_notification(self, title: str, message: str) -> None:
        if not self._nid:
            return
        try:
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self._msg_hwnd
            nid.uID = 1
            nid.uFlags = NIF_INFO
            nid.szInfoTitle = title[:64]
            nid.szInfo = message[:256]
            SHELL32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        except Exception:
            logger.warning("Notification failed", exc_info=True)

    def __del__(self) -> None:
        self.stop()
