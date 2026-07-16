#!/usr/bin/env python3
"""SM WoT Assistant Launcher — lightweight pre-startup update checker.

Built as --onefile (PyInstaller). All DLLs extracted to %TEMP%,
so running setup.exe does NOT conflict with locked files in the install dir.
"""

import os, sys, tempfile, threading, subprocess, ctypes, time, re
from ctypes import wintypes
import tkinter as tk
from PIL import Image, ImageTk, ImageOps
import unicodedata  # force PyInstaller to bundle C extension for idna/requests
import requests

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

LOGO_FILE = os.path.join(BUNDLE_DIR, "logo.png")
VERSION_FILE = os.path.join(BUNDLE_DIR, "VERSION")
ICO_FILE = os.path.join(BUNDLE_DIR, "icon.ico")

# ─── WinAPI constants / structures for tray watcher ───
WM_APP = 0x8000
HWND_MESSAGE = -3
NIM_ADD = 0
NIM_DELETE = 2
NIF_MESSAGE = 1
NIF_ICON = 2
NIF_TIP = 4
NIS_HIDDEN = 1
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

# Global state for tray WNDPROC
_tray_click_flag = 0  # 0=none, 1=left, 2=right
_tray_class_registered = False
_tray_wndproc_instance = None
_tray_hicon = None
_tray_active_launcher = None  # Reference to active Launcher in --tray mode

WM_CLOSE = 0x0010

def load_version():
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

FIREBASE_API_KEY = "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"
RTDB_BASE = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"

def check_for_updates_sync():
    try:
        url = f"{RTDB_BASE}/versions.json?auth={FIREBASE_API_KEY}"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data:
                items = [v for v in data.values() if isinstance(v, dict) and v.get("version")]
                if items:
                    return max(items, key=lambda x: (
                        x.get("release_date", ""),
                        tuple(int(n) for n in x.get("version", "0.0.0").replace("v", "").split("."))
                    ))
    except Exception as e:
        print(f"[LAUNCHER] Update check error: {e}")
    return None

def compare_versions(current, latest):
    try:
        def _parts(v):
            return tuple(int(x) for x in str(v).replace("v", "").split(".")[:3])
        return _parts(latest) > _parts(current)
    except Exception:
        return False

SPLASH_W, SPLASH_H = 450, 350


class Launcher:
    def __init__(self):
        self.is_tray = "--tray" in sys.argv
        self.skip_splash = "--skip-splash" in sys.argv

        mutex_name = "SM_WoT_Assistant_Watcher" if self.is_tray else "SM_WoT_Assistant_SingleInstance"
        self.mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183:
            sys.exit(0)

        self.version = load_version()
        self.install_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "SM WoT Assistant")
        self.installed_version = self._detect_installed_version()
        self._clean_old_versions()
        self._dot_animating = False
        # Tray watcher state
        self._tray_root = None
        self._tray_nid = None
        self._tray_hwnd = None
        self._game_was_running = False

    def _detect_installed_version(self):
        """Визначає встановлену версію з імен EXE-файлів у директорії інсталяції."""
        if not os.path.isdir(self.install_dir):
            return self.version
        candidates = []
        try:
            for f in os.listdir(self.install_dir):
                m = re.match(r"SM WoT Assistant v(\d+\.\d+\.\d+(?: Beta)?)\.exe", f)
                if m:
                    ver_str = m.group(1).split()[0]  # "1.0.38 Beta" -> "1.0.38"
                    candidates.append((tuple(int(n) for n in ver_str.split(".")), m.group(1)))
        except Exception:
            return self.version
        if not candidates:
            return self.version
        candidates.sort(key=lambda x: x[0])
        return candidates[-1][1].split()[0]

    def _clean_old_versions(self):
        """При старті — видалити всі EXE крім поточного внесеної версії."""
        if not os.path.isdir(self.install_dir):
            return
        current_prefix = f"SM WoT Assistant v{self.installed_version}"
        for f in os.listdir(self.install_dir):
            if f.startswith("SM WoT Assistant v") and f.endswith(".exe"):
                if not f.startswith(current_prefix):
                    try:
                        os.remove(os.path.join(self.install_dir, f))
                    except Exception:
                        pass

    def _find_main_exe(self):
        """Знайти встановлений головний EXE."""
        exe_name = f"SM WoT Assistant v{self.installed_version}.exe"
        main_exe = os.path.join(self.install_dir, exe_name)
        if os.path.exists(main_exe):
            return main_exe
        if os.path.isdir(self.install_dir):
            for f in os.listdir(self.install_dir):
                if f.startswith("SM WoT Assistant v") and f.endswith(".exe"):
                    return os.path.join(self.install_dir, f)
        return None

    def _center_geometry(self):
        sw = self.splash.winfo_screenwidth()
        sh = self.splash.winfo_screenheight()
        x = (sw - SPLASH_W) // 2
        y = (sh - SPLASH_H) // 2
        return f"{SPLASH_W}x{SPLASH_H}+{x}+{y}"

    def _show_splash(self):
        self.splash = tk.Tk()
        self.splash.overrideredirect(True)
        self.splash.attributes("-topmost", True)
        self.splash.configure(bg="black")
        self.splash.geometry(self._center_geometry())

        self.canvas = tk.Canvas(self.splash, width=SPLASH_W, height=SPLASH_H,
                                bg="black", highlightthickness=0)
        self.canvas.pack()

        try:
            img = Image.open(LOGO_FILE)
            self._logo_img = ImageTk.PhotoImage(
                ImageOps.contain(img, (200, 200), Image.Resampling.LANCZOS))
            self.canvas.create_image(SPLASH_W // 2, SPLASH_H // 2 - 20, image=self._logo_img)
        except Exception:
            self._logo_img = None

        self.canvas.create_text(SPLASH_W // 2, SPLASH_H - 100, text=f"v{self.installed_version}",
                                 fill="white", font=("Verdana", 11))

        self.status_text = self.canvas.create_text(
            SPLASH_W // 2, SPLASH_H - 84,
            text="Checking for updates...", fill="#bbbbbb", font=("Arial", 9))

        self.pct_text = self.canvas.create_text(
            SPLASH_W - 34, SPLASH_H - 20,
            text="0%", fill="#dddddd", font=("Arial", 9))

        self.pbar = self.canvas.create_rectangle(
            0, SPLASH_H - 10, 0, SPLASH_H, fill="#ff4500", outline="")

        self.splash.deiconify()
        self.splash.update()

    def run(self):
        if self.is_tray:
            self._run_tray_watcher()
            return
        if self.skip_splash:
            exe = self._find_main_exe()
            if exe:
                try:
                    ctypes.windll.kernel32.CloseHandle(self.mutex)
                except Exception:
                    pass
                args = [exe]
                if "--tray" in sys.argv:
                    args.append("--tray")
                subprocess.Popen(args, creationflags=0x08000000)
            return
        self._show_splash()
        self.splash.after(100, self._check_and_proceed)
        self.splash.mainloop()

    def _check_and_proceed(self):
        latest = check_for_updates_sync()
        if latest and compare_versions(self.installed_version, latest.get("version", "0.0.0")):
            self._show_update_prompt(latest)
        else:
            self._launch_main()

    def _set_status(self, text, fill="#bbbbbb", font=("Arial", 9)):
        try:
            self.canvas.itemconfigure(self.status_text, text=text, fill=fill, font=font)
        except Exception:
            pass

    def _set_progress(self, pct, fill="#ff4500"):
        try:
            self.canvas.coords(self.pbar, 0, SPLASH_H - 10, pct * SPLASH_W // 100, SPLASH_H)
            self.canvas.itemconfigure(self.pbar, fill=fill)
            self.canvas.itemconfigure(self.pct_text, text=f"{pct}%")
        except Exception:
            pass

    def _start_dot_animation(self):
        self._dot_animating = True
        self._dot_state = 0
        self._animate_dots()

    def _stop_dot_animation(self):
        self._dot_animating = False

    def _animate_dots(self):
        if not self._dot_animating:
            return
        try:
            text = self.canvas.itemcget(self.status_text, "text")
            base = text.rstrip(".")
            self._dot_state = (self._dot_state + 1) % 3
            dots = "." * (self._dot_state + 1)
            self.canvas.itemconfigure(self.status_text, text=base + dots)
            self.splash.after(500, self._animate_dots)
        except Exception:
            pass

    def _show_update_prompt(self, latest):
        latest_ver = latest.get("version", "")

        self._set_status(f"New version v{latest_ver} available!", "#ffaa00", ("Arial", 13, "bold"))
        self.canvas.itemconfigure(self.pct_text, text="")
        self.canvas.coords(self.pbar, 0, 0, 0, 0)

        self.canvas.create_text(SPLASH_W // 2, SPLASH_H - 64,
                                 text=f"You have v{self.installed_version}", fill="#aaa", font=("Arial", 9))

        btn_w, btn_h = 140, 36
        lx = SPLASH_W // 2 - btn_w - 14
        rx = SPLASH_W // 2 + 14
        by = SPLASH_H - 58

        self.canvas.create_rectangle(lx, by, lx + btn_w, by + btn_h,
                                      fill="#335533", outline="#66aa66", tags="btn")
        self.canvas.create_text(lx + btn_w // 2, by + btn_h // 2,
                                 text="UPDATE NOW", fill="#99cc99",
                                 font=("Arial", 10, "bold"), tags="btn")

        self.canvas.create_rectangle(rx, by, rx + btn_w, by + btn_h,
                                      fill="#444", outline="#666", tags="btn")
        self.canvas.create_text(rx + btn_w // 2, by + btn_h // 2,
                                 text="LATER", fill="#aaa",
                                 font=("Arial", 10), tags="btn")

        self._latest = latest

        def on_click(event):
            if lx <= event.x <= lx + btn_w:
                self._download_and_install(latest)
            else:
                self._launch_main()

        self.canvas.tag_bind("btn", "<Button-1>", on_click)
        self.canvas.tag_bind("btn", "<Enter>", lambda e: self.splash.config(cursor="hand2"))
        self.canvas.tag_bind("btn", "<Leave>", lambda e: self.splash.config(cursor=""))

    def _download_and_install(self, latest):
        latest_ver = latest.get("version", "")
        dl_url = latest.get("download_url", "")

        self.canvas.delete("btn")

        self._set_status(f"Downloading v{latest_ver}...", "#ffaa00", ("Arial", 11))
        self.canvas.itemconfigure(self.pct_text, text="0%")
        self.canvas.coords(self.pbar, 0, SPLASH_H - 10, 0, SPLASH_H)
        self.canvas.itemconfigure(self.pbar, fill="#ff4500")

        def _download():
            tmp = None
            try:
                tmp = os.path.join(tempfile.gettempdir(), "SM_WoT_Assistant_Setup.exe")
                print(f"[LAUNCHER] Downloading: {dl_url}")

                r = requests.get(dl_url, stream=True, headers=HEADERS, timeout=120)
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                last_pct = -1

                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded * 100 // total
                            if pct != last_pct:
                                last_pct = pct
                                self.splash.after(0, lambda p=pct: self._set_progress(p))

                print(f"[LAUNCHER] Downloaded: {downloaded / (1024 * 1024):.0f} MB")

                self.splash.after(0, lambda: (
                    self._set_progress(100, "#22cc44"),
                    self._set_status("Installing...", "#ffaa00", ("Arial", 11)),
                    self._start_dot_animation()
                ))

                result = subprocess.run([tmp, "/S", "/NCRC"], creationflags=0x08000000)
                if result.returncode != 0:
                    raise RuntimeError(f"Installer exit code {result.returncode}")

                install_prefix = os.path.join(self.install_dir, f"SM WoT Assistant v{latest_ver}")

                for f in os.listdir(self.install_dir):
                    if f.startswith("SM WoT Assistant v") and f.endswith(".exe"):
                        fp = os.path.join(self.install_dir, f)
                        try:
                            if not fp.startswith(install_prefix):
                                os.remove(fp)
                        except Exception:
                            pass

                found = any(
                    f.startswith(f"SM WoT Assistant v{latest_ver}") and f.endswith(".exe")
                    for f in os.listdir(self.install_dir)
                )
                if not found:
                    raise RuntimeError(f"EXE not found for v{latest_ver} in {self.install_dir}")

                try:
                    os.remove(tmp)
                except Exception:
                    pass

                self.splash.after(0, lambda: (
                    self._stop_dot_animation(),
                    self._set_status(f"Updated to v{latest_ver}", "#22cc44", ("Arial", 13, "bold"))
                ))

                def _finish():
                    self._set_status("Starting...", "#22cc44", ("Arial", 12))
                    try:
                        ctypes.windll.kernel32.CloseHandle(self.mutex)
                    except Exception:
                        pass
                    launcher_exe = os.path.join(self.install_dir, "SM WoT Assistant Launcher.exe")
                    subprocess.Popen([launcher_exe, "--skip-splash"], creationflags=0x08000000)
                    self.splash.after(200, lambda: (self.splash.destroy(), sys.exit(0)))

                self.splash.after(3000, _finish)

            except Exception as e:
                print(f"[LAUNCHER] Error: {e}")
                if tmp and os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                self.splash.after(0, lambda: (
                    self._stop_dot_animation(),
                    self._set_status(f"Error: {str(e)[:80]}", "#ff4444", ("Arial", 10)),
                    self.canvas.itemconfigure(self.pct_text, text="")
                ))

        t = threading.Thread(target=_download, daemon=True)
        t.start()

    def _launch_main(self):
        main_exe = self._find_main_exe()

        if not main_exe or not os.path.exists(main_exe):
            self._set_status("Program not installed. Run setup first.", "#ff4444", ("Arial", 10))
            return

        geo = self.splash.geometry()

        try:
            ctypes.windll.kernel32.CloseHandle(self.mutex)
        except Exception:
            pass

        subprocess.Popen([main_exe, f"--splash-geometry={geo}"], creationflags=0x08000000)
        self.splash.after(100, lambda: (self.splash.destroy(), sys.exit(0)))

    # ═══════════════════════════════════════════════════════════════════
    #  Tray Watcher Mode (--tray)
    # ═══════════════════════════════════════════════════════════════════

    def _run_tray_watcher(self):
        """Lightweight tray-only mode: no window, polls for WoT launch."""
        global _tray_active_launcher
        _tray_active_launcher = self
        self._tray_root = tk.Tk()
        self._tray_root.withdraw()
        self._tray_root.title("SM WoT Assistant Watcher")
        self._tray_setup()
        self._game_was_running = self._is_wot_running()
        self._tray_poll()
        self._tray_root.mainloop()

    def _tray_setup(self):
        """Create tray icon via WinAPI Shell_NotifyIconW."""
        global _tray_class_registered, _tray_wndproc_instance, _tray_hicon
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32
        hinst = kernel32.GetModuleHandleW(None)

        if not _tray_class_registered:
            wndproc_type = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
            _tray_wndproc_instance = wndproc_type(_tray_wndproc_func)
            wc = WNDCLASSW()
            wc.style = 0
            wc.lpfnWndProc = ctypes.cast(_tray_wndproc_instance, ctypes.c_void_p).value
            wc.cbClsExtra = 0
            wc.cbWndExtra = 0
            wc.hInstance = hinst
            wc.hIcon = 0
            wc.hCursor = 0
            wc.hbrBackground = 0
            wc.lpszMenuName = None
            wc.lpszClassName = "SM_WoT_Watcher_Window"
            if user32.RegisterClassW(ctypes.byref(wc)):
                _tray_class_registered = True

        self._tray_hwnd = user32.CreateWindowExW(
            0, "SM_WoT_Watcher_Window", "", 0, 0, 0, 0, 0,
            None, None, hinst, None
        )

        # Load icon
        small_w = user32.GetSystemMetrics(SM_CXSMICON)
        small_h = user32.GetSystemMetrics(SM_CYSMICON)
        icon_path = os.path.join(BUNDLE_DIR, "icon.ico")
        if not os.path.exists(icon_path) and self.install_dir:
            candidate = os.path.join(self.install_dir, "_internal", "icon.ico")
            if os.path.exists(candidate):
                icon_path = candidate
        _tray_hicon = 0
        if os.path.exists(icon_path):
            _tray_hicon = user32.LoadImageW(
                None, icon_path, IMAGE_ICON, small_w, small_h, LR_LOADFROMFILE | LR_DEFAULTSIZE
            )

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hwnd = self._tray_hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_APP
        nid.hIcon = _tray_hicon
        nid.szTip = f"SM WoT Assistant v{self.version}"

        if shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            self._tray_nid = nid
            print(f"[LAUNCHER] Tray watcher started (v{self.version})")
        else:
            print("[LAUNCHER] Shell_NotifyIconW NIM_ADD failed")

    def _tray_remove(self):
        global _tray_hicon
        if self._tray_nid:
            try:
                ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._tray_nid))
            except Exception:
                pass
            self._tray_nid = None
        if self._tray_hwnd:
            try:
                ctypes.windll.user32.DestroyWindow(self._tray_hwnd)
            except Exception:
                pass
            self._tray_hwnd = None
        if _tray_hicon:
            try:
                ctypes.windll.user32.DestroyIcon(_tray_hicon)
            except Exception:
                pass
            _tray_hicon = None

    def _tray_poll(self):
        """Poll for clicks + game detection every 1 second."""
        global _tray_click_flag
        if _tray_click_flag == 1:
            _tray_click_flag = 0
            self._tray_launch_main()
        elif _tray_click_flag == 2:
            _tray_click_flag = 0
            self._tray_show_menu()

        settings = self._read_settings()
        launch_on_game = settings.get("launch_on_game_start", False)
        is_running = self._is_wot_running()
        if is_running and not self._game_was_running and launch_on_game:
            start_minimized = settings.get("start_minimized", False)
            print(f"[LAUNCHER] Game detected, launching main (minimized={start_minimized})")
            self._tray_launch_main(start_minimized=start_minimized)
        self._game_was_running = is_running

        try:
            if self._tray_root and self._tray_root.winfo_exists():
                self._tray_root.after(1000, self._tray_poll)
        except Exception:
            pass

    def _tray_launch_main(self, start_minimized=False):
        """Launch the main program from the tray watcher."""
        main_exe = self._find_main_exe()
        if not main_exe or not os.path.exists(main_exe):
            print("[LAUNCHER] Main EXE not found")
            return
        args = [main_exe]
        if start_minimized:
            args.append("--tray")
        try:
            subprocess.Popen(args, creationflags=0x08000000)
            print(f"[LAUNCHER] Launched main: {os.path.basename(main_exe)}")
        except Exception as e:
            print(f"[LAUNCHER] Failed to launch main: {e}")

    def _tray_show_menu(self):
        """Show right-click popup menu near cursor."""
        if not self._tray_root or not self._tray_root.winfo_exists():
            return
        menu = tk.Menu(self._tray_root, tearoff=False, bg="#252525", fg="#cccccc",
                       activebackground="#444", activeforeground="#ffffff",
                       font=("Arial", 9))
        menu.add_command(label="Launch SM WoT Assistant", command=self._tray_launch_main)
        menu.add_separator()
        menu.add_command(label="Exit", command=self._tray_exit)
        try:
            x, y = ctypes.windll.user32.GetCursorPos()
            menu.tk_popup(x, y)
        except Exception:
            pass
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _tray_exit(self):
        """Cleanup and exit the tray watcher."""
        global _tray_active_launcher
        _tray_active_launcher = None
        print("[LAUNCHER] Tray watcher exiting")
        self._tray_remove()
        try:
            ctypes.windll.kernel32.CloseHandle(self.mutex)
        except Exception:
            pass
        try:
            if self._tray_root and self._tray_root.winfo_exists():
                self._tray_root.destroy()
        except Exception:
            pass
        sys.exit(0)

    def _read_settings(self):
        """Read settings.json from user data dir."""
        settings_file = os.path.join(
            os.environ.get("APPDATA", ""), "SM WoT Assistant", "settings.json"
        )
        if not os.path.exists(settings_file):
            return {}
        try:
            import json
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _is_wot_running(self):
        """Check if WorldOfTanks.exe process is running via WinAPI."""
        try:
            kernel32 = ctypes.windll.kernel32
            TH32CS_SNAPPROCESS = 0x00000002
            snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if snapshot == -1:
                return False
            PE_SIZE = 556
            pe = (ctypes.c_byte * PE_SIZE)()
            ctypes.memset(pe, 0, PE_SIZE)
            ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
            found = False
            if kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
                while True:
                    exe_buf = ctypes.create_unicode_buffer(260)
                    ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
                    if exe_buf.value and "WorldOfTanks.exe" in exe_buf.value:
                        found = True
                        break
                    if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                        break
            kernel32.CloseHandle(snapshot)
            return found
        except Exception:
            return False


def stop_tray_watcher():
    """Signal the running tray watcher to exit (from another process)."""
    try:
        hwnd = ctypes.windll.user32.FindWindowW("SM_WoT_Watcher_Window", None)
        if hwnd:
            ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            print("[LAUNCHER] Tray watcher signalled to exit")
            return True
    except Exception as e:
        print(f"[LAUNCHER] Error stopping tray watcher: {e}")
    return False


def restart_tray_watcher():
    """Restart the tray watcher launcher (called after update)."""
    install_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "SM WoT Assistant")
    launcher_exe = os.path.join(install_dir, "SM WoT Assistant Launcher.exe")
    if os.path.exists(launcher_exe):
        try:
            subprocess.Popen([launcher_exe, "--tray"], creationflags=0x08000000)
            print("[LAUNCHER] Tray watcher restarted")
            return True
        except Exception as e:
            print(f"[LAUNCHER] Error restarting tray watcher: {e}")
    return False


def _tray_wndproc_func(hwnd, msg, wparam, lparam):
    """Tray message-only window procedure."""
    global _tray_click_flag, _tray_active_launcher
    if msg == WM_APP and lparam in (0x0202, 0x0205):
        if lparam == 0x0202:
            _tray_click_flag = 1
        elif lparam == 0x0205:
            _tray_click_flag = 2
    elif msg == WM_CLOSE:
        if _tray_active_launcher is not None:
            _tray_active_launcher._tray_exit()
    return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)


if __name__ == "__main__":
    Launcher().run()
