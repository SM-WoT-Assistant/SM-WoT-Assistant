#!/usr/bin/env python3
"""SM WoT Assistant Tray Watcher — minimal process monitor (no tkinter/no PIL/no requests).

Built as --onefile (PyInstaller). Watches for WorldOfTanks.exe via
CreateToolhelp32Snapshot at 5s intervals. When game starts: launches
SM WoT Assistant Launcher.exe. When game stops + close_with_game setting:
closes SM WoT Assistant v*.exe. Then returns to monitoring.
"""

import os, sys, json, time, ctypes, subprocess, re
from ctypes import wintypes

DEBUG = True

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001
# sizeof(PROCESSENTRY32W): 32-bit=556, 64-bit=568
PE_SIZE = 568 if ctypes.sizeof(ctypes.c_void_p) == 8 else 556
if DEBUG: print(f"[DEBUG] tray_watcher PE_SIZE={PE_SIZE}")

def _read_settings():
    appdata = os.environ.get("APPDATA", "")
    path = os.path.join(appdata, "SM WoT Assistant", "settings.json")
    if not os.path.exists(path):
        if DEBUG: print(f"[DEBUG] _read_settings: {path} NOT FOUND")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if DEBUG: print(f"[DEBUG] _read_settings: loaded {len(data)} keys")
            return data
    except Exception as e:
        if DEBUG: print(f"[DEBUG] _read_settings error: {e}")
        return {}

def _install_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "SM WoT Assistant")

def _find_launcher_exe():
    install_dir = _install_dir()
    launcher = os.path.join(install_dir, "SM WoT Assistant Launcher.exe")
    if DEBUG: print(f"[DEBUG] _find_launcher_exe: install_dir={install_dir}")
    if os.path.exists(launcher):
        if DEBUG: print(f"[DEBUG] _find_launcher_exe: found at {launcher}")
        return launcher
    exe_dir = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, 'frozen', False) else __file__))
    launcher2 = os.path.join(exe_dir, "SM WoT Assistant Launcher.exe")
    if DEBUG: print(f"[DEBUG] _find_launcher_exe: exe_dir={exe_dir}")
    if os.path.exists(launcher2):
        if DEBUG: print(f"[DEBUG] _find_launcher_exe: found at {launcher2}")
        return launcher2
    src_dir = os.path.dirname(os.path.abspath(__file__))
    launcher3 = os.path.join(src_dir, "SM WoT Assistant Launcher.exe")
    if DEBUG: print(f"[DEBUG] _find_launcher_exe: src_dir={src_dir}")
    if os.path.exists(launcher3):
        if DEBUG: print(f"[DEBUG] _find_launcher_exe: found at {launcher3}")
        return launcher3
    if DEBUG: print(f"[DEBUG] _find_launcher_exe: NOT FOUND in any location")
    return None

def _is_wot_running():
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        if DEBUG: print(f"[DEBUG] _is_wot_running: CreateToolhelp32Snapshot returned INVALID_HANDLE_VALUE")
        return False
    try:
        pe = (ctypes.c_byte * PE_SIZE)()
        ctypes.memset(pe, 0, PE_SIZE)
        ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            err = kernel32.GetLastError()
            if DEBUG: print(f"[DEBUG] _is_wot_running: Process32FirstW failed, GetLastError={err}")
            return False
        wot_count = 0
        while True:
            exe_buf = ctypes.create_unicode_buffer(260)
            ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
            if exe_buf.value and "WorldOfTanks.exe" in exe_buf.value:
                wot_count += 1
                return True  # found at least one
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        if DEBUG: print(f"[DEBUG] _is_wot_running: not found (scanned all processes)")
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
            err = kernel32.GetLastError()
            if DEBUG: print(f"[DEBUG] _find_dev_pid: Process32FirstW failed, GetLastError={err}")
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
                    if DEBUG: print(f"[DEBUG] _find_dev_pid: found valid dev PID {target}")
                    return target
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        if DEBUG: print(f"[DEBUG] _find_dev_pid: PID {target} not found or not python")
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
            err = kernel32.GetLastError()
            if DEBUG: print(f"[DEBUG] _find_main_pids: Process32FirstW failed, GetLastError={err}")
            return pids
        while True:
            exe_buf = ctypes.create_unicode_buffer(260)
            ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
            name = exe_buf.value
            if name and re.match(r"SM WoT Assistant v\d+\.\d+\.\d+.*\.exe", name):
                pid_bytes = (ctypes.c_byte * 4)()
                ctypes.memmove(pid_bytes, ctypes.byref(pe, 8), 4)
                pid = int.from_bytes(bytes(pid_bytes), 'little')
                if DEBUG: print(f"[DEBUG] _find_main_pids: found main PID {pid} ({name})")
                pids.append(pid)
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        if DEBUG and not pids: print(f"[DEBUG] _find_main_pids: no main processes found")
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
        if DEBUG: print(f"[DEBUG] _close_main_app: no main pids to close")
        return
    if DEBUG: print(f"[DEBUG] _close_main_app: closing PIDs {pids}")
    for pid in pids:
        h = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if h:
            if DEBUG: print(f"[DEBUG] _close_main_app: TerminateProcess PID {pid}")
            kernel32.TerminateProcess(h, 0)
            kernel32.CloseHandle(h)
        else:
            if DEBUG: print(f"[DEBUG] _close_main_app: OpenProcess failed for PID {pid}, err={kernel32.GetLastError()}")

def _launch_app():
    main_pids = _get_main_pids()
    if DEBUG: print(f"[DEBUG] _launch_app: _get_main_pids()={main_pids}")
    if main_pids:
        if DEBUG: print(f"[DEBUG] _launch_app: main already running, skipping")
        return
    launcher = _find_launcher_exe()
    if launcher:
        if DEBUG: print(f"[DEBUG] _launch_app: launching {launcher}")
        subprocess.Popen([launcher], creationflags=0x08000000)
        return
    install_dir = _install_dir()
    if DEBUG: print(f"[DEBUG] _launch_app: launcher not found, checking install_dir={install_dir}")
    if os.path.isdir(install_dir):
        for f in os.listdir(install_dir):
            if f.startswith("SM WoT Assistant v") and f.endswith(".exe"):
                exe = os.path.join(install_dir, f)
                settings = _read_settings()
                args = [exe]
                if settings.get("start_minimized", False):
                    args.append("--tray")
                if DEBUG: print(f"[DEBUG] _launch_app: fallback launching {exe} args={args}")
                subprocess.Popen(args, creationflags=0x08000000)
                return
    if DEBUG: print(f"[DEBUG] _launch_app: NOTHING to launch — all paths failed")

def main():
    mutex = kernel32.CreateMutexW(None, False, "SM_WoT_Assistant_TrayWatcher")
    if kernel32.GetLastError() == 183:
        if DEBUG: print(f"[DEBUG] main: another tray watcher already running, exiting")
        sys.exit(0)
    if DEBUG: print(f"[DEBUG] main: tray watcher started, PID={os.getpid()}")
    game_was = _is_wot_running()
    if DEBUG: print(f"[DEBUG] main: initial game_was={game_was}")
    launched = False
    cycle = 0
    while True:
        cycle += 1
        settings = _read_settings()
        close_game = settings.get("close_with_game", False)
        game_is = _is_wot_running()
        if game_is and not game_was and not launched:
            if DEBUG: print(f"[DEBUG] main cycle {cycle}: game DETECTED (game_was={game_was}, game_is={game_is}), launching app")
            _launch_app()
            launched = True
        elif not game_is and game_was and launched:
            if DEBUG: print(f"[DEBUG] main cycle {cycle}: game STOPPED, close_game={close_game}")
            if close_game:
                _close_main_app()
            launched = False
        game_was = game_is
        if cycle % 12 == 0:  # every ~60s
            if DEBUG: print(f"[DEBUG] main cycle {cycle}: game_is={game_is}, launched={launched}, pids={_get_main_pids()}")
        time.sleep(5)

if __name__ == "__main__":
    main()
