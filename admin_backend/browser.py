"""admin_backend.browser - Selenium Chrome for community platform login.

Provides a visible Chrome window for manual login to YouTube/Reddit/Ko-fi.
Session data persists in community_chrome_profile across restarts.
"""
from __future__ import annotations
import os
import subprocess
import sys
import threading
import time

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
COMMUNITY_PROFILE_DIR = os.path.join(APPDATA_DIR, "community_chrome_profile")
CHROME_PROFILE = os.environ.get("CHROME_PROFILE",
    r"C:\Users\PRO\AppData\Local\Google\Chrome\User Data")
CHROME_PROFILE_DIR = "Default"

PLATFORM_LOGIN_URLS = {
    "youtube": "https://accounts.google.com/",
    "reddit": "https://www.reddit.com/login/",
    "kofi": "https://ko-fi.com/account/login/",
    "patreon": "https://www.patreon.com/login",
}

PLATFORM_CHECK_URLS = {
    "youtube": "https://www.youtube.com/",
    "reddit": "https://www.reddit.com/",
    "kofi": "https://ko-fi.com/Manage/",
    "patreon": "https://www.patreon.com/cw/SMWoTAssistant",
}

_DRIVER_RETRY_MARKERS = (
    "session not created", "DevToolsActivePort", "cannot connect",
    "Chrome failed to start", "chrome not reachable",
)


def _bundle_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_state = {
    "driver": None,
    "platform": None,
    "lock": threading.Lock(),
    "hwnd": None,
}


def _kill_chrome_matching(pattern):
    """Kill chrome.exe processes whose CommandLine contains pattern."""
    try:
        import ctypes
        from ctypes import wintypes
        TH32CS_SNAPPROCESS = 0x00000002
        PROCESSENTRY32W_size = ctypes.sizeof(ctypes.c_void_p) == 8 and 568 or 556
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == wintypes.HANDLE(-1).value:
            return
        pe = PROCESSENTRY32W()
        pe.dwSize = PROCESSENTRY32W_size
        pids = []
        if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                if pe.szExeFile.lower() == "chrome.exe":
                    pids.append(pe.th32ProcessID)
                if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                    break
        kernel32.CloseHandle(snap)
        for pid in pids:
            try:
                import win32api
                proc = win32api.OpenProcess(0x0401, False, pid)
                try:
                    for info in win32api.EnumProcessModules(proc):
                        pass
                except Exception:
                    pass
                try:
                    cmdline = win32api.GetCommandLineEx(proc)
                except Exception:
                    cmdline = ""
                win32api.CloseHandle(proc)
                if pattern.lower() in cmdline.lower():
                    os.kill(pid, 9)
            except Exception:
                pass
    except Exception:
        pass


def _copy_chrome_profile(src, dst):
    """Seed community profile from real Chrome profile."""
    import shutil
    if os.path.isdir(dst):
        return
    os.makedirs(dst, exist_ok=True)
    if not os.path.isdir(src):
        return
    for item in ("Default", "Local State"):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isfile(s):
            try:
                shutil.copy2(s, d)
            except Exception:
                pass
        elif os.path.isdir(s):
            try:
                shutil.copytree(s, d, dirs_exist_ok=True)
            except Exception:
                pass


def _fix_crashed_profile_prefs():
    """Rewrite Preferences exit_type=Crashed to Normal."""
    prefs_path = os.path.join(COMMUNITY_PROFILE_DIR, "Default", "Preferences")
    if not os.path.isfile(prefs_path):
        return
    try:
        import json
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefs = json.load(f)
        exit_info = prefs.get("profile", {}).get("exit_info", {})
        if exit_info.get("exit_type") == "Crashed":
            prefs["profile"]["exit_info"]["exit_type"] = "Normal"
            prefs["profile"]["exit_info"]["exit_time"] = ""
            prefs["profile"]["exit_info"]["restore_count"] = 0
            with open(prefs_path, "w", encoding="utf-8") as f:
                json.dump(prefs, f)
    except Exception:
        pass


def _create_driver(visible=True):
    """Create Selenium Chrome driver."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    if not os.path.isdir(COMMUNITY_PROFILE_DIR):
        _kill_chrome_matching(COMMUNITY_PROFILE_DIR)
        _copy_chrome_profile(CHROME_PROFILE, COMMUNITY_PROFILE_DIR)

    _fix_crashed_profile_prefs()

    opts = Options()
    opts.add_argument(f"--user-data-dir={COMMUNITY_PROFILE_DIR}")
    opts.add_argument(f"--profile-directory={CHROME_PROFILE_DIR}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--window-size=1200,800")
    opts.add_argument("--disable-session-crashed-bubble")
    if not visible:
        opts.add_argument("--window-position=-32000,-32000")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    last_err = None
    for attempt in (1, 2, 3):
        try:
            drv = webdriver.Chrome(
                options=opts,
                service=Service(creation_flags=subprocess.CREATE_NO_WINDOW if not visible else 0),
            )
            drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """})
            return drv
        except Exception as e:
            last_err = e
            msg = str(e)
            if not any(m in msg.lower() for m in _DRIVER_RETRY_MARKERS):
                raise
            time.sleep(3 if attempt < 3 else 15)
            _kill_chrome_matching(COMMUNITY_PROFILE_DIR)
    raise RuntimeError(f"Chrome driver failed after 3 attempts: {str(last_err)[:120]}")


def open_login(platform: str) -> dict:
    """Open a visible Chrome window for manual login to a platform."""
    with _state["lock"]:
        if _state["driver"] is not None:
            try:
                _state["driver"].current_url
                return {"ok": True, "message": "Browser already open"}
            except Exception:
                _state["driver"] = None

        url = PLATFORM_LOGIN_URLS.get(platform)
        if not url:
            return {"ok": False, "error": f"Unknown platform: {platform}"}

        try:
            drv = _create_driver(visible=True)
            drv.get(url)
            _state["driver"] = drv
            _state["platform"] = platform
            return {"ok": True, "message": f"Opened {platform} login page"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}


def get_login_status(platform: str) -> dict:
    """Check if user is logged in to a platform by navigating to check URL."""
    with _state["lock"]:
        drv = _state["driver"]
        if drv is None:
            return {"ok": True, "logged_in": False, "message": "No browser open"}

        try:
            current = drv.current_url.lower()
        except Exception:
            _state["driver"] = None
            return {"ok": True, "logged_in": False, "message": "Browser closed"}

        check_url = PLATFORM_CHECK_URLS.get(platform, "")
        if platform == "youtube":
            logged_in = "accounts.google.com" not in current
        elif platform == "reddit":
            logged_in = "reddit.com/login" not in current and "reddit.com" in current
        elif platform == "kofi":
            logged_in = "ko-fi.com" in current and "login" not in current
        elif platform == "patreon":
            logged_in = "patreon.com" in current and "login" not in current
        else:
            logged_in = False

        return {"ok": True, "logged_in": logged_in, "url": current}


def close_browser():
    """Close Chrome and clean up."""
    with _state["lock"]:
        drv = _state["driver"]
        _state["driver"] = None
        _state["platform"] = None
        if drv is not None:
            try:
                drv.quit()
            except Exception:
                pass
        _kill_chrome_matching(COMMUNITY_PROFILE_DIR)


def is_browser_running() -> bool:
    with _state["lock"]:
        drv = _state["driver"]
        if drv is None:
            return False
        try:
            drv.current_url
            return True
        except Exception:
            _state["driver"] = None
            return False
