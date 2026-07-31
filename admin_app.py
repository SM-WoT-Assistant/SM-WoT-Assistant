#!/usr/bin/env python3
"""SM WoT Assistant — Admin Desktop Application
Monitors game changes via WG API + scripts.pkg scan,
auto-generates builds via AI Mode, notifies on results.

Usage:
  python admin_app.py --wot-path="C:/Games/World_of_Tanks_EU"
"""
import os, sys, json, time, threading, shutil, tkinter as tk
from tkinter import ttk, scrolledtext
import ctypes
from ctypes import wintypes

if getattr(sys, 'frozen', False):
    _BUNDLE_DIR = sys._MEIPASS
else:
    _BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(_BUNDLE_DIR)
sys.path.insert(0, _BUNDLE_DIR)

from admin_build_generator import (
    detect_changed_tanks, generate_builds, generate_popular,
    load_tank_db, load_prompts, _create_driver,
    _put_json, _get_json, _rtdb_url, _update_builds_version,
    _update_pending_status, check_wg_tanks_version,
    _WG_API_URL, _is_build_complete,
    check_wg_game_version, snapshot_manifest, update_manifest_for_tags
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

# ── Settings ─────────────────────────────────────
_ADMIN_SETTINGS_PATH = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "admin_settings.json")

def _load_admin_settings():
    defaults = {"start_with_windows": False, "start_minimized": False, "wot_path": ""}
    try:
        if os.path.exists(_ADMIN_SETTINGS_PATH):
            with open(_ADMIN_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
    except:
        pass
    return defaults

def _save_admin_settings(settings):
    try:
        os.makedirs(os.path.dirname(_ADMIN_SETTINGS_PATH), exist_ok=True)
        with open(_ADMIN_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except:
        pass

def _set_windows_startup(enable):
    """Add/remove HKCU\\Run entry for admin app."""
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
        if enable:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else __file__
            winreg.SetValueEx(key, "SM WoT Assistant Admin", 0, winreg.REG_SZ, f'"{exe_path}" --tray')
        else:
            try:
                winreg.DeleteValue(key, "SM WoT Assistant Admin")
            except:
                pass
        winreg.CloseKey(key)
    except:
        pass

def _read_admin_version():
    try:
        with open(os.path.join(_BUNDLE_DIR, "admin_version.txt"), "r") as f:
            return f.read().strip()
    except:
        return "0.0.0"

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
            if msg == _WM_TRAY_CALLBACK:
                if lparam == 0x0202 or lparam == 0x0203:
                    self.parent.root.deiconify()
                    self.parent.root.lift()
                elif lparam == 0x0205:
                    self.parent.root.after(0, self.parent._show_tray_menu)
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
        icon_path = os.path.join(_BUNDLE_DIR, "admin_icon.ico")
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
        self._wot_path = wot_path
        self._running = True
        self._scanning = False
        self._generating = False
        self._last_scan = -3600
        self._last_wg = -21600
        self._wg_ver = ""
        self._queue = []
        self._last_detected = []
        self._admin_settings = _load_admin_settings()
        self._wot_path = self._resolve_wot_path(wot_path)
        if self._wot_path and not self._admin_settings.get("wot_path"):
            self._admin_settings["wot_path"] = self._wot_path
            _save_admin_settings(self._admin_settings)
        self._manifest_path = self._resolve_manifest()

        self.tank_db = load_tank_db()
        self.prompts = load_prompts()
        self.tray = AdminTray(self)

        self._build_ui()
        self._log(f"Admin started (WoT: {self._wot_path or 'not set'})")
        self._log(f"Tanks: {len(self.tank_db)}, Prompts: {len(self.prompts)}")
        self._start_background()

    def _resolve_wot_path(self, cli_wot_path):
        """Resolve WoT path: CLI arg → admin settings → main app settings → common paths."""
        candidates = []
        if cli_wot_path:
            candidates.append(cli_wot_path)
        if self._admin_settings.get("wot_path"):
            candidates.append(self._admin_settings["wot_path"])
        try:
            main_settings_path = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "settings.json")
            with open(main_settings_path, "r", encoding="utf-8") as f:
                main_settings = json.load(f)
                if main_settings.get("wot_path"):
                    candidates.append(main_settings["wot_path"])
        except:
            pass
        candidates.extend([
            "C:/Games/World_of_Tanks_EU", "D:/Games/World_of_Tanks_EU",
            "E:/Games/World_of_Tanks_EU", "C:/Games/World_of_Tanks",
            "D:/Games/World_of_Tanks", "E:/Games/World_of_Tanks"
        ])
        for p in candidates:
            p = (p or "").strip()
            if p and os.path.exists(os.path.join(p, "version.xml")):
                return p
        return ""

    def _resolve_manifest(self):
        """Persistent change-tracking manifest in AppData.
        Seeded from a fresh dev manifest (CWD) or a baseline snapshot of scripts.pkg
        so the first scan never reports every tank as changed."""
        manifest_dir = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
        path = os.path.join(manifest_dir, ".tank_extract_manifest.json")
        if os.path.exists(path):
            return path
        if self._wot_path:
            cwd_manifest = os.path.join(_BUNDLE_DIR, ".tank_extract_manifest.json")
            if os.path.exists(cwd_manifest):
                try:
                    if not detect_changed_tanks(self._wot_path, cwd_manifest):
                        os.makedirs(manifest_dir, exist_ok=True)
                        shutil.copy(cwd_manifest, path)
                        self._log("Manifest seeded from dev copy")
                        return path
                except Exception:
                    pass
            try:
                if snapshot_manifest(self._wot_path, path):
                    self._log("Manifest baseline created from scripts.pkg")
                    return path
            except Exception as e:
                self._log(f"Manifest baseline failed: {e}")
        return path

    def _build_ui(self):
        ver = _read_admin_version()
        self.root.title(f"SM WoT Assistant Admin v{ver}")
        self.root.geometry("860x620")
        self.root.configure(bg=BG)
        self.root.minsize(600, 400)
        try:
            self.root.iconbitmap(default=os.path.join(_BUNDLE_DIR, "admin_icon.ico"))
        except Exception:
            pass

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(top, text="SM WoT Assistant", font=("Segoe UI", 16, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(top, text="Admin", font=("Segoe UI", 16, "bold"),
                 fg="#ff4500", bg=BG).pack(side="left")

        self._settings_btn = tk.Button(top, text="⚙", font=("Segoe UI", 14), bg=BG, fg="#aaa", bd=0,
                                       command=self._show_settings_menu)
        self._settings_btn.pack(side="right", padx=(0, 4))

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

        self._card_ver = _card(left, "Admin Version", "ver")
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
        line = f"[{ts}] {msg}"
        try:
            log_dir = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "admin.log"), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except:
            pass
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)
        else:
            print(line)

    def _update_cards(self):
        self._card_ver.config(text=_read_admin_version())
        self._card_wg.config(text=self._wg_ver or "—")
        status = "OK" if os.path.exists(os.path.join(self._wot_path or "", "version.xml")) else "No WoT"
        self._card_status.config(text=status, fg=GREEN if status == "OK" else RED)
        q = len(self._queue)
        self._card_queue.config(text=str(q), fg=ACCENT if q > 0 else "#888")
        self._card_last.config(text=time.strftime("%H:%M") if self._last_scan > 0 else "—")

    def _show_settings_menu(self):
        """Gear button opens a dropdown menu (same pattern as the main app)."""
        menu = tk.Menu(self.root, tearoff=0, bg="#222222", fg=FG,
                       activebackground="#333333", activeforeground=ACCENT, bd=1)
        sw = tk.BooleanVar(value=self._admin_settings.get("start_with_windows", False))
        menu.add_checkbutton(label="Start with Windows", variable=sw,
                             command=lambda: self._on_settings_change("start_with_windows", sw.get()))
        sm = tk.BooleanVar(value=self._admin_settings.get("start_minimized", False))
        menu.add_checkbutton(label="Start minimized to tray", variable=sm,
                             command=lambda: self._on_settings_change("start_minimized", sm.get()))
        menu.add_separator()
        menu.add_command(label="WoT Path...", command=self._show_wot_path_dialog)
        try:
            x = self._settings_btn.winfo_rootx()
            y = self._settings_btn.winfo_rooty() + self._settings_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _show_wot_path_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.configure(bg=BG)
        dlg.title("WoT Path")
        dlg.geometry("420x120")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="WoT Path:", bg=BG, fg="#aaa",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(12, 2))
        wp = tk.Entry(dlg, bg="#222", fg=FG, bd=0, insertbackground=FG,
                      font=("Segoe UI", 9))
        wp.insert(0, self._admin_settings.get("wot_path", self._wot_path or ""))
        wp.pack(fill="x", padx=20, pady=(0, 4))

        def _save_wp():
            val = wp.get().strip()
            self._admin_settings["wot_path"] = val
            self._wot_path = val
            _save_admin_settings(self._admin_settings)
            self._log(f"WoT path set to: {val}")
            dlg.destroy()

        tk.Button(dlg, text="Save", bg="#333", fg=FG, bd=0, padx=20, pady=4,
                  command=_save_wp).pack(pady=6)

    def _on_settings_change(self, key, value):
        self._admin_settings[key] = value
        _save_admin_settings(self._admin_settings)
        if key == "start_with_windows":
            _set_windows_startup(value)
            self._log(f"Start with Windows: {'ON' if value else 'OFF'}")

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
            changed = detect_changed_tanks(self._wot_path, self._manifest_path) if self._wot_path else []
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
                    try:
                        update_manifest_for_tags(self._wot_path, self._manifest_path, queue)
                    except Exception:
                        pass
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
                                if self._wot_path:
                                    changed = detect_changed_tanks(self._wot_path, self._manifest_path)
                                    if changed:
                                        self._queue = changed
                                        self.root.after(0, self._update_cards)
                                        self._log(f"Auto-detected {len(changed)} changed tanks!")
                                        self.tray.show_notification(
                                            "Auto-Detected", f"{len(changed)} tanks changed via WG API")
                                        self._do_generate(changed)
                    if self._wot_path and now - self._last_scan > 3600:
                        self._last_scan = now
                        changed = detect_changed_tanks(self._wot_path, self._manifest_path)
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
        """X button minimizes to tray; exit only via tray menu."""
        self.root.withdraw()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()

    def _show_tray_menu(self):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Show", command=self._show_window)
        menu.add_separator()
        menu.add_command(label="Exit", command=self._exit_app)
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        try:
            menu.tk_popup(pt.x, pt.y)
        finally:
            menu.grab_release()

    def _exit_app(self):
        self._running = False
        if hasattr(self, "tray"):
            self.tray.remove()
        self.root.destroy()


def main():
    import argparse

    # Single-instance mutex
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "SM_WoT_Assistant_Admin_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:
        hwnd = ctypes.windll.user32.FindWindowW(None, f"SM WoT Assistant Admin v{_read_admin_version()}")
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        sys.exit(0)

    parser = argparse.ArgumentParser(description="SM WoT Assistant Admin App")
    parser.add_argument("--wot-path", type=str, default=None, help="Path to WoT installation")
    parser.add_argument("--tray", action="store_true", help="Start minimized to tray")
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()
    app = AdminApp(root, wot_path=args.wot_path)
    # Check if should start minimized
    settings = _load_admin_settings()
    if args.tray or settings.get("start_minimized", False):
        # Start in tray - window stays withdrawn, tray icon is visible
        app.root.after(100, app._log, "Started minimized to tray")
        app.root.after(300, lambda: app.tray.show_notification(
            "SM WoT Assistant Admin", f"Running in tray (WoT: {app._wot_path or 'not set'})"))
    else:
        root.deiconify()
    app.run()
    ctypes.windll.kernel32.CloseHandle(mutex)

if __name__ == "__main__":
    main()
