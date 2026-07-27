#!/usr/bin/env python3
"""SM WoT Assistant — Admin Desktop Application
Monitors game changes via WG API + scripts.pkg scan,
auto-generates builds via AI Mode, notifies on results.

Usage:
  python admin_app.py --wot-path="C:/Games/World_of_Tanks_EU"
"""
import os, sys, json, time, threading, tkinter as tk
from tkinter import ttk, scrolledtext
import ctypes
from ctypes import wintypes

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from admin_build_generator import (
    detect_changed_tanks, generate_builds, generate_popular,
    load_tank_db, load_prompts, _create_driver,
    _put_json, _get_json, _rtdb_url, _update_builds_version,
    _update_pending_status, check_wg_tanks_version,
    _WG_API_URL, _is_build_complete,
    check_wg_game_version
)

BG = "#1a1a1a"
BG2 = "#222222"
FG = "#cccccc"
ACCENT = "#ffaa00"
GREEN = "#66cc66"
RED = "#cc6666"

_NID = 1
_WM_APP = 0x8000
_WM_TRAY_CALLBACK = _WM_APP + 1
_GUID = "{4A2C4E6B-3B1A-4B8A-9E1F-7D3A5F8C2B6E}"

# ── Auto-update ──────────────────────────────────
_ADMIN_VER_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app/versions/admin/latest.json?auth=AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"

def _read_admin_version():
    try:
        with open("VERSION", "r") as f:
            return f.read().strip()
    except:
        return "0.0.0"

def _check_admin_update():
    """Check for admin app update. Returns (new_version, download_url) or None."""
    import requests
    try:
        r = requests.get(_ADMIN_VER_URL, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data and data.get("version"):
                remote = tuple(int(n) for n in data["version"].split("."))
                local = tuple(int(n) for n in _read_admin_version().split("."))
                if remote > local:
                    return (data["version"], data.get("download_url", ""))
    except:
        pass
    return None

def _do_admin_update(new_ver, url):
    """Notify about new version (no auto-update for script mode)."""
    print(f"\n{'='*50}")
    print(f"[UPDATE] Admin v{new_ver} available!")
    print(f"[UPDATE] Update via: git pull")
    print(f"[UPDATE] Or download: {url}")
    print(f"{'='*50}\n")

class AdminTray:
    def __init__(self, parent):
        self.parent = parent
        self._tid = _NID
        self._hwnd = None
        self._create_window()
        self._add_icon()

    def _create_window(self):
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_long, ctypes.c_uint, ctypes.c_long, ctypes.c_long)
        def wndproc(hwnd, msg, wparam, lparam):
            if msg == _WM_TRAY_CALLBACK and lparam == 0x0203:
                self.parent.root.deiconify()
                self.parent.root.lift()
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        self._wndproc = WNDPROC(wndproc)
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        cls_name = "AdminTrayClass"
        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("style", ctypes.c_uint),
                ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p),
                ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
                ("hIconSm", ctypes.c_void_p),
            ]
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = cls_name
        ctypes.windll.user32.RegisterClassExW(ctypes.byref(wc))
        self._hwnd = ctypes.windll.user32.CreateWindowExW(0, cls_name, "", 0, 0, 0, 0, 0, 0, 0, hinst, None)

    def _add_icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        hicon = 0
        if os.path.exists(icon_path):
            hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010)
        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
                ("dwState", ctypes.c_uint),
                ("dwStateMask", ctypes.c_uint),
                ("szInfo", ctypes.c_wchar * 256),
                ("uVersion", ctypes.c_uint),
                ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", ctypes.c_uint),
                ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", ctypes.c_void_p),
            ]
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = self._tid
        nid.uFlags = 0x00000002 | 0x00000001 | 0x00000004
        nid.uCallbackMessage = _WM_TRAY_CALLBACK
        nid.hIcon = hicon or ctypes.windll.user32.LoadIconW(0, 32512)
        nid.szTip = "SM WoT Assistant Admin"
        ctypes.windll.shell32.Shell_NotifyIconW(0x00000000, ctypes.byref(nid))

    def show_notification(self, title, text, level="info"):
        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
                ("dwState", ctypes.c_uint),
                ("dwStateMask", ctypes.c_uint),
                ("szInfo", ctypes.c_wchar * 256),
                ("uVersion", ctypes.c_uint),
                ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", ctypes.c_uint),
                ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", ctypes.c_void_p),
            ]
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = self._tid
        nid.uFlags = 0x00000010
        nid.uTimeout = 5000
        nid.szInfoTitle = title[:64]
        nid.szInfo = text[:256]
        nid.dwInfoFlags = 0x00000001 if level == "error" else 0x00000000
        ctypes.windll.shell32.Shell_NotifyIconW(0x00000001, ctypes.byref(nid))

    def remove(self):
        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
                ("dwState", ctypes.c_uint),
                ("dwStateMask", ctypes.c_uint),
                ("szInfo", ctypes.c_wchar * 256),
                ("uVersion", ctypes.c_uint),
                ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", ctypes.c_uint),
                ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", ctypes.c_void_p),
            ]
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = self._tid
        ctypes.windll.shell32.Shell_NotifyIconW(0x00000002, ctypes.byref(nid))
        if self._hwnd:
            ctypes.windll.user32.DestroyWindow(self._hwnd)


class AdminApp:
    def __init__(self, root, wot_path=None):
        self.root = root
        self.wot_path = wot_path
        self._running = True
        self._scanning = False
        self._generating = False
        self._last_scan = -3600
        self._last_wg = -21600
        self._wg_ver = ""
        self._queue = []
        self._last_detected = []

        self.tank_db = load_tank_db()
        self.prompts = load_prompts()
        self.tray = AdminTray(self)

        # Check for updates
        update = _check_admin_update()
        if update:
            new_ver, url = update
            self._log(f"Admin v{new_ver} available, updating...")
            _do_admin_update(new_ver, url)

        self._build_ui()
        self._log(f"Admin started (WoT: {wot_path or 'not set'})")
        self._log(f"Tanks: {len(self.tank_db)}, Prompts: {len(self.prompts)}")
        self._start_background()

    def _build_ui(self):
        self.root.title("SM WoT Assistant Admin")
        self.root.geometry("860x620")
        self.root.configure(bg=BG)
        self.root.minsize(600, 400)
        try:
            self.root.iconbitmap(default="icon.ico")
        except Exception:
            pass

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(top, text="SM WoT Assistant", font=("Segoe UI", 16, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(top, text="Admin", font=("Segoe UI", 16, "bold"),
                 fg="#ff4500", bg=BG).pack(side="left")

        # Status bar
        self.status_lbl = tk.Label(self.root, text="Initializing...", font=("Segoe UI", 10),
                                    fg="#888888", bg=BG, anchor="w")
        self.status_lbl.pack(fill="x", padx=12, pady=(0, 4))

        # Main content
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Left panel: status cards
        left = tk.Frame(content, bg=BG2, padx=12, pady=10)
        left.pack(side="left", fill="y", padx=(0, 8))

        def _card(parent, label, id_suffix):
            f = tk.Frame(parent, bg=BG2, bd=1, relief="solid", highlightbackground="#333")
            tk.Label(f, text=label, font=("Segoe UI", 9), fg="#888", bg=BG2).pack(anchor="w")
            v = tk.Label(f, text="—", font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG2)
            v.pack(anchor="w", pady=(2, 0))
            f.pack(fill="x", pady=3)
            return v

        self._card_wg = _card(left, "WG Game Version", "wg")
        self._card_status = _card(left, "Game Status", "st")
        self._card_queue = _card(left, "Queue", "qu")
        self._card_last = _card(left, "Last Scan", "ls")

        # Right panel: buttons + log
        right = tk.Frame(content, bg=BG)
        right.pack(side="right", fill="both", expand=True)

        # Buttons
        btn_f = tk.Frame(right, bg=BG)
        btn_f.pack(fill="x", pady=(0, 6))

        self._scan_btn = tk.Button(btn_f, text="Scan Now", command=self._scan_now,
                                    bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._scan_btn.pack(side="left", padx=(0, 6))

        self._gen_btn = tk.Button(btn_f, text="Generate Queue", command=self._gen_queue,
                                   bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._gen_btn.pack(side="left", padx=(0, 6))

        self._popular_btn = tk.Button(btn_f, text="Generate Popular", command=self._gen_popular,
                                       bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._popular_btn.pack(side="left", padx=(0, 6))

        self._regen_all_btn = tk.Button(btn_f, text="Regen All", command=self._gen_all,
                                          bg="#553333", fg=RED, bd=0, padx=14, pady=4, cursor="hand2")
        self._regen_all_btn.pack(side="left")

        # Log
        self.log_text = scrolledtext.ScrolledText(right, bg="#111111", fg="#cccccc",
                                                   insertbackground="#cccccc",
                                                   font=("Consolas", 10), bd=0,
                                                   wrap="word", height=18)
        self.log_text.pack(fill="both", expand=True)

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)

    def _update_cards(self):
        self._card_wg.config(text=self._wg_ver or "—")
        status = "OK" if os.path.exists(os.path.join(self.wot_path or "", "version.xml")) else "No WoT"
        self._card_status.config(text=status, fg=GREEN if status == "OK" else RED)
        q = len(self._queue)
        self._card_queue.config(text=str(q), fg=ACCENT if q > 0 else "#888")
        self._card_last.config(text=time.strftime("%H:%M") if self._last_scan > 0 else "—")

    def _scan_now(self):
        if self._scanning:
            self._log("Scan already in progress")
            return
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        self._scanning = True
        self._scan_btn.config(state="disabled")
        self._log("Scanning scripts.pkg for changes...")
        try:
            changed = detect_changed_tanks(self.wot_path) if self.wot_path else []
            self._last_scan = time.time()
            if changed:
                self._queue = changed
                self._log(f"Detected {len(changed)} changed tanks!")
                for t in changed[:10]:
                    self._log(f"  {t}")
                self.tray.show_notification("Changes Detected", f"{len(changed)} tanks changed")
                self.root.after(0, self._update_cards)
                self._do_generate(changed)
            else:
                self._log("No changes detected")
                self.root.after(0, self._update_cards)
        except Exception as e:
            self._log(f"Scan error: {e}")
        finally:
            self._scanning = False
            self.root.after(0, lambda: self._scan_btn.config(state="normal"))

    def _gen_queue(self):
        if not self._queue:
            self._log("Queue is empty. Run Scan first.")
            return
        threading.Thread(target=self._do_generate, args=(list(self._queue),), daemon=True).start()

    def _do_generate(self, queue):
        self._generating = True
        self.root.after(0, lambda: self._gen_btn.config(state="disabled"))
        self._log(f"Generating builds for {len(queue)} tanks...")
        self.tray.show_notification("Generation Started", f"{len(queue)} tanks queued")
        try:
            driver = _create_driver()
            try:
                ok = generate_builds(driver, self.tank_db, self.prompts, queue=queue)
                if ok:
                    _update_builds_version()
                    self._queue = [t for t in self._queue if t not in queue]
                    self._log("Generation complete!")
                    self.tray.show_notification("Builds Updated", f"{len(queue)} tanks regenerated",
                                                 level="info")
                else:
                    self._log("Generation FAILED")
                    self.tray.show_notification("Generation Failed", "Check logs for details",
                                                 level="error")
            finally:
                driver.quit()
        except Exception as e:
            self._log(f"Generation error: {e}")
            self.tray.show_notification("Error", str(e)[:80], level="error")
        finally:
            self._generating = False
            self.root.after(0, lambda: self._gen_btn.config(state="normal"))
            self.root.after(0, self._update_cards)

    def _gen_popular(self):
        threading.Thread(target=self._do_popular, daemon=True).start()

    def _do_popular(self):
        self._log("Generating popular tanks...")
        self._popular_btn.config(state="disabled")
        try:
            driver = _create_driver()
            try:
                ok = generate_popular(driver, self.tank_db)
                if ok:
                    self._log("Popular tanks updated!")
                    self.tray.show_notification("Popular Tanks", "List updated successfully")
                else:
                    self._log("Popular tanks FAILED")
            finally:
                driver.quit()
        except Exception as e:
            self._log(f"Popular error: {e}")
        finally:
            self.root.after(0, lambda: self._popular_btn.config(state="normal"))

    def _gen_all(self):
        self._log("WARNING: Regen All will regenerate ALL tanks via AI!")
        self.tray.show_notification("Regen All", f"{len(self.tank_db)} tanks queued - this takes days",
                                     level="error")
        threading.Thread(target=self._do_generate,
                         args=(list(self.tank_db.keys()),), daemon=True).start()

    def _start_background(self):
        def _loop():
            while self._running:
                try:
                    now = time.time()
                    if now - self._last_wg > 1800:  # 30 min
                        self._last_wg = now
                        wg_ver, ts = check_wg_game_version()
                        if wg_ver:
                            self._wg_ver = wg_ver
                            self.root.after(0, self._update_cards)
                        if ts:
                            stored = _get_json(_rtdb_url("builds/tanks_updated_at")) or 0
                            if ts != stored:
                                _put_json(_rtdb_url("builds/tanks_updated_at"), ts)
                                self._log(f"WG tanks_updated_at changed: {ts}")
                                if self.wot_path:
                                    changed = detect_changed_tanks(self.wot_path)
                                    if changed:
                                        self._queue = changed
                                        self.root.after(0, self._update_cards)
                                        self._log(f"Auto-detected {len(changed)} changed tanks!")
                                        self.tray.show_notification(
                                            "Auto-Detected", f"{len(changed)} tanks changed via WG API")
                                        self._do_generate(changed)
                    if self.wot_path and now - self._last_scan > 3600:
                        self._last_scan = now
                        changed = detect_changed_tanks(self.wot_path)
                        if changed:
                            self._queue = changed
                            self.root.after(0, self._update_cards)
                            self._log(f"Periodic scan: {len(changed)} changed tanks!")
                            self.tray.show_notification(
                                "Changes Detected", f"{len(changed)} tanks changed")
                            self._do_generate(changed)
                except Exception as e:
                    self._log(f"Background error: {e}")
                time.sleep(10)
        threading.Thread(target=_loop, daemon=True).start()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(1000, self._scan_now)
        self.root.mainloop()

    def _on_close(self):
        self._running = False
        if hasattr(self, "tray"):
            self.tray.remove()
        self.root.destroy()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SM WoT Assistant Admin App")
    parser.add_argument("--wot-path", type=str, default=None, help="Path to WoT installation")
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()
    app = AdminApp(root, wot_path=args.wot_path)
    root.deiconify()
    app.run()

if __name__ == "__main__":
    main()
