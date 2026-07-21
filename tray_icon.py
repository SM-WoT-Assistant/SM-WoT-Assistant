import ctypes
from ctypes import wintypes
import os
import uuid
import config

shell32 = ctypes.windll.shell32
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Fix argtypes for 64-bit compatibility
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = wintypes.LPARAM

WM_APP = 0x8000
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 1
NIF_ICON = 2
NIF_TIP = 4
NIF_GUID = 0x20
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
HWND_MESSAGE = -3
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
SM_CXSMICON = 49
SM_CYSMICON = 50

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hwnd", wintypes.HWND),
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

WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

_ACTIVE_TRAY = None
_CLASS_REGISTERED = False
_GLOBAL_WNDPROC = None
_TRAY_GUID = uuid.UUID("12345678-9abc-def0-1234-56789abcdef0")


def _global_wndproc_func(hwnd, msg, wparam, lparam):
    if msg == WM_APP and lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP):
        if _ACTIVE_TRAY is not None:
            _ACTIVE_TRAY._click_flag = True
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


WNDPROC_INSTANCE = WNDPROC(_global_wndproc_func)


def _ensure_class_registered():
    global _CLASS_REGISTERED, _GLOBAL_WNDPROC
    if _CLASS_REGISTERED:
        return
    hinstance = kernel32.GetModuleHandleW(None)
    _GLOBAL_WNDPROC = ctypes.cast(WNDPROC_INSTANCE, ctypes.c_void_p).value
    wc = WNDCLASSW()
    wc.style = 0
    wc.lpfnWndProc = _GLOBAL_WNDPROC
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hinstance
    wc.hIcon = 0
    wc.hCursor = 0
    wc.hbrBackground = 0
    wc.lpszMenuName = None
    wc.lpszClassName = "SM_Tray_Message_Window"
    atom = user32.RegisterClassW(ctypes.byref(wc))
    if atom:
        _CLASS_REGISTERED = True


class TrayIcon:
    def __init__(self, root, on_click=None):
        global _ACTIVE_TRAY
        self.root = root
        self.on_click = on_click
        self._click_flag = False
        self._destroyed = False
        self._msg_hwnd = None
        self._nid = None
        self._poll_id = None
        self._hicon = None

        _ensure_class_registered()

        self._hicon = self._load_icon()
        if not self._hicon:
            print("[TRAY] Failed to load icon.ico")
            return

        hinstance = kernel32.GetModuleHandleW(None)
        self._msg_hwnd = user32.CreateWindowExW(
            0, "SM_Tray_Message_Window", "",
            0, 0, 0, 0, 0,
            None, None, hinstance, None
        )
        if not self._msg_hwnd:
            print("[TRAY] Failed to create message window")
            return

        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hwnd = self._msg_hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_GUID
        self._nid.uCallbackMessage = WM_APP
        self._nid.hIcon = self._hicon
        self._nid.szTip = "SM WoT Assistant v" + config.load_version()
        guid_bytes = _TRAY_GUID.bytes_le
        for i in range(16):
            self._nid.guidItem[i] = guid_bytes[i]

        if shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid)):
            _ACTIVE_TRAY = self
            self._poll_id = root.after(250, self._poll)
        else:
            print("[TRAY] Shell_NotifyIconW NIM_ADD failed")

    def _load_icon(self):
        small_w = user32.GetSystemMetrics(SM_CXSMICON)
        small_h = user32.GetSystemMetrics(SM_CYSMICON)
        if not os.path.exists(config.ICON_FILE):
            print(f"[TRAY] icon.ico not found at {config.ICON_FILE}")
            return None
        hicon = user32.LoadImageW(
            None, config.ICON_FILE, IMAGE_ICON,
            small_w, small_h,
            LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
        return hicon if hicon else None

    def _poll(self):
        if self._destroyed:
            return
        if self._click_flag:
            self._click_flag = False
            if self.on_click:
                try:
                    self.root.after_idle(self.on_click)
                except Exception:
                    pass
        if not self._destroyed:
            self._poll_id = self.root.after(250, self._poll)

    def remove(self):
        global _ACTIVE_TRAY
        self._destroyed = True
        if _ACTIVE_TRAY is self:
            _ACTIVE_TRAY = None
        if self._nid:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            self._nid = None
        if self._msg_hwnd:
            user32.DestroyWindow(self._msg_hwnd)
            self._msg_hwnd = None
        if self._poll_id:
            try:
                self.root.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        if self._hicon:
            user32.DestroyIcon(self._hicon)
            self._hicon = None

    def __del__(self):
        self.remove()
