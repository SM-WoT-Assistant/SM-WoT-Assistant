#!/usr/bin/env python3
"""SM WoT Assistant Launcher — lightweight pre-startup update checker.

Built as --onefile (PyInstaller). All DLLs extracted to %TEMP%,
so running setup.exe does NOT conflict with locked files in the install dir.
"""

import os, sys, tempfile, threading, subprocess, ctypes, time
import tkinter as tk
from PIL import Image, ImageTk, ImageOps
import requests

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

LOGO_FILE = os.path.join(BUNDLE_DIR, "logo.png")
VERSION_FILE = os.path.join(BUNDLE_DIR, "VERSION")

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

SPLASH_W, SPLASH_H = 450, 300


class Launcher:
    def __init__(self):
        self.mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "SM_WoT_Assistant_SingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183:
            sys.exit(0)

        self.version = load_version()
        self.install_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "SM WoT Assistant")

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

        self.canvas.create_text(SPLASH_W // 2, SPLASH_H - 62, text=self.version,
                                 fill="white", font=("Verdana", 12, "bold"))

        self.status_text = self.canvas.create_text(
            SPLASH_W // 2, SPLASH_H - 46,
            text="Checking for updates...", fill="#bbbbbb", font=("Arial", 9))

        self.pct_text = self.canvas.create_text(
            SPLASH_W - 34, SPLASH_H - 18,
            text="0%", fill="#dddddd", font=("Arial", 9, "bold"))

        self.pbar = self.canvas.create_rectangle(
            0, SPLASH_H - 8, 0, SPLASH_H, fill="#ff4500", outline="")

        self.splash.deiconify()
        self.splash.update()

    def run(self):
        self._show_splash()
        self.splash.after(100, self._check_and_proceed)
        self.splash.mainloop()

    def _check_and_proceed(self):
        latest = check_for_updates_sync()
        if latest and compare_versions(self.version, latest.get("version", "0.0.0")):
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
            self.canvas.coords(self.pbar, 0, SPLASH_H - 8, pct * SPLASH_W // 100, SPLASH_H)
            self.canvas.itemconfigure(self.pbar, fill=fill)
            self.canvas.itemconfigure(self.pct_text, text=f"{pct}%")
        except Exception:
            pass

    def _show_update_prompt(self, latest):
        latest_ver = latest.get("version", "")

        self._set_status(f"New version v{latest_ver} available!", "#ffaa00", ("Arial", 13, "bold"))
        self.canvas.itemconfigure(self.pct_text, text="")
        self.canvas.coords(self.pbar, 0, 0, 0, 0)

        self.canvas.create_text(SPLASH_W // 2, SPLASH_H - 92,
                                 text=f"You have v{self.version}", fill="#aaa", font=("Arial", 9))

        btn_w, btn_h = 140, 36
        lx = SPLASH_W // 2 - btn_w - 14
        rx = SPLASH_W // 2 + 14
        by = SPLASH_H - 68

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

        self._set_status(f"Downloading v{latest_ver}...", "#ffaa00", ("Arial", 11, "bold"))
        self.canvas.itemconfigure(self.pct_text, text="0%")
        self.canvas.coords(self.pbar, 0, SPLASH_H - 8, 0, SPLASH_H)
        self.canvas.itemconfigure(self.pbar, fill="#ff4500")

        def _download():
            tmp = None
            try:
                tmp = os.path.join(tempfile.gettempdir(), "SM_WoT_Assistant_Setup.exe")
                print(f"[LAUNCHER] Downloading: {dl_url}")

                r = requests.get(dl_url, stream=True, headers=HEADERS, timeout=120)
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
                    self._set_status("Installing...", "#ffaa00", ("Arial", 11, "bold"))
                ))

                result = subprocess.run([tmp, "/S", "/NCRC"], creationflags=0x08000000)
                if result.returncode != 0:
                    raise RuntimeError(f"Installer exit code {result.returncode}")

                install_exe = os.path.join(self.install_dir, f"SM WoT Assistant v{latest_ver}.exe")

                for f in os.listdir(self.install_dir):
                    if f.startswith("SM WoT Assistant v") and f.endswith(".exe"):
                        fp = os.path.join(self.install_dir, f)
                        try:
                            if os.path.abspath(fp) != os.path.abspath(install_exe):
                                os.remove(fp)
                        except Exception:
                            pass

                if not os.path.exists(install_exe):
                    raise RuntimeError(f"EXE not found: {install_exe}")

                try:
                    os.remove(tmp)
                except Exception:
                    pass

                self.splash.after(0, lambda: self._set_status(
                    f"Updated to v{latest_ver}", "#22cc44", ("Arial", 13, "bold")))

                def _finish():
                    self._set_status("Starting...", "#22cc44", ("Arial", 12, "bold"))
                    try:
                        ctypes.windll.kernel32.CloseHandle(self.mutex)
                    except Exception:
                        pass
                    subprocess.Popen([install_exe], creationflags=0x08000000)
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
                    self._set_status(f"Error: {str(e)[:80]}", "#ff4444", ("Arial", 10, "bold")),
                    self.canvas.itemconfigure(self.pct_text, text="")
                ))

        t = threading.Thread(target=_download, daemon=True)
        t.start()

    def _launch_main(self):
        exe_name = f"SM WoT Assistant v{self.version}.exe"
        main_exe = os.path.join(self.install_dir, exe_name)

        if not os.path.exists(main_exe):
            for f in os.listdir(self.install_dir):
                if f.startswith("SM WoT Assistant v") and f.endswith(".exe"):
                    main_exe = os.path.join(self.install_dir, f)
                    break

        if not os.path.exists(main_exe):
            self._set_status(f"Program not installed. Run setup first.", "#ff4444", ("Arial", 10))
            return

        geo = self.splash.geometry()

        try:
            ctypes.windll.kernel32.CloseHandle(self.mutex)
        except Exception:
            pass

        subprocess.Popen([main_exe, f"--splash-geometry={geo}"], creationflags=0x08000000)
        self.splash.after(100, lambda: (self.splash.destroy(), sys.exit(0)))


if __name__ == "__main__":
    Launcher().run()
