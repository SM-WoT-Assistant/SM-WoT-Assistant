#!/usr/bin/env python3
"""SM WoT Assistant Tray Watcher — minimal process monitor (no tkinter/no PIL/no requests).

Built as --onefile (PyInstaller). Watches for WorldOfTanks.exe via
CreateToolhelp32Snapshot at 5s intervals. When game starts: launches
SM WoT Assistant Launcher.exe. When game stops + close_with_game setting:
closes SM WoT Assistant v*.exe. Then returns to monitoring.
"""

import os, sys, json, time, ctypes, subprocess, re
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001
# sizeof(PROCESSENTRY32W): 32-bit=556, 64-bit=568
PE_SIZE = 568 if ctypes.sizeof(ctypes.c_void_p) == 8 else 556

def _read_settings():
    appdata = os.environ.get("APPDATA", "")
    path = os.path.join(appdata, "SM WoT Assistant", "settings.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _install_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "SM WoT Assistant")

def _find_launcher_exe():
    install_dir = _install_dir()
    launcher = os.path.join(install_dir, "SM WoT Assistant Launcher.exe")
    if os.path.exists(launcher):
        return launcher
    exe_dir = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, 'frozen', False) else __file__))
    launcher2 = os.path.join(exe_dir, "SM WoT Assistant Launcher.exe")
    if os.path.exists(launcher2):
        return launcher2
    src_dir = os.path.dirname(os.path.abspath(__file__))
    launcher3 = os.path.join(src_dir, "SM WoT Assistant Launcher.exe")
    if os.path.exists(launcher3):
        return launcher3
    return None

def _is_wot_running():
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return False
    try:
        pe = (ctypes.c_byte * PE_SIZE)()
        ctypes.memset(pe, 0, PE_SIZE)
        ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            return False
        while True:
            exe_buf = ctypes.create_unicode_buffer(260)
            ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
            if exe_buf.value and "WorldOfTanks.exe" in exe_buf.value:
                return True
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        return False
    finally:
        kernel32.CloseHandle(snapshot)

def _find_dev_pid():
    """Прочитати dev_pid.txt, валідувати що PID живий і це python.exe/pythonw.exe."""
    appdata = os.environ.get("APPDATA", "")
    path = os.path.join(appdata, "SM WoT Assistant", "dev_pid.txt")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            target = int(f.read().strip())
    except (ValueError, OSError):
        return None
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return None
    try:
        pe = (ctypes.c_byte * PE_SIZE)()
        ctypes.memset(pe, 0, PE_SIZE)
        ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            return None
        while True:
            pid_bytes = (ctypes.c_byte * 4)()
            ctypes.memmove(pid_bytes, ctypes.byref(pe, 8), 4)
            pid = int.from_bytes(bytes(pid_bytes), 'little')
            exe_buf = ctypes.create_unicode_buffer(260)
            ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
            if pid == target and exe_buf.value:
                name = exe_buf.value.lower()
                if name in ("python.exe", "pythonw.exe"):
                    return target
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        return None
    finally:
        kernel32.CloseHandle(snapshot)

def _find_main_pids():
    pids = []
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return pids
    try:
        pe = (ctypes.c_byte * PE_SIZE)()
        ctypes.memset(pe, 0, PE_SIZE)
        ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            return pids
        while True:
            exe_buf = ctypes.create_unicode_buffer(260)
            ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
            name = exe_buf.value
            if name and re.match(r"SM WoT Assistant v\d+\.\d+\.\d+.*\.exe", name):
                pid_bytes = (ctypes.c_byte * 4)()
                ctypes.memmove(pid_bytes, ctypes.byref(pe, 8), 4)
                pid = int.from_bytes(bytes(pid_bytes), 'little')
                pids.append(pid)
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        return pids
    finally:
        kernel32.CloseHandle(snapshot)

def _get_main_pids():
    """Об'єднати frozen EXE + dev PID."""
    pids = _find_main_pids()
    dev_pid = _find_dev_pid()
    if dev_pid is not None and dev_pid not in pids:
        pids.append(dev_pid)
    return pids

def _close_main_app():
    pids = _get_main_pids()
    if not pids:
        return
    for pid in pids:
        h = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if h:
            kernel32.TerminateProcess(h, 0)
            kernel32.CloseHandle(h)

def _launch_app():
    if _get_main_pids():
        return
    launcher = _find_launcher_exe()
    if launcher:
        subprocess.Popen([launcher], creationflags=0x08000000)
        return
    install_dir = _install_dir()
    if os.path.isdir(install_dir):
        for f in os.listdir(install_dir):
            if f.startswith("SM WoT Assistant v") and f.endswith(".exe"):
                exe = os.path.join(install_dir, f)
                settings = _read_settings()
                args = [exe]
                if settings.get("start_minimized", False):
                    args.append("--tray")
                subprocess.Popen(args, creationflags=0x08000000)
                return

def main():
    mutex = kernel32.CreateMutexW(None, False, "SM_WoT_Assistant_TrayWatcher")
    if kernel32.GetLastError() == 183:
        sys.exit(0)
    game_was = _is_wot_running()
    launched = False
    while True:
        settings = _read_settings()
        close_game = settings.get("close_with_game", False)
        game_is = _is_wot_running()
        if game_is and not game_was and not launched:
            _launch_app()
            launched = True
        elif not game_is and game_was and launched:
            if close_game:
                _close_main_app()
            launched = False
        game_was = game_is
        if launched:
            if not _get_main_pids() and game_is:
                launched = False
        time.sleep(5)

if __name__ == "__main__":
    main()
