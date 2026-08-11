#!/usr/bin/env python3
"""SM WoT Assistant — Admin Desktop Application
Monitors game changes via WG API + scripts.pkg scan,
auto-generates builds via AI Mode, notifies on results.

Usage:
  python admin_app.py --wot-path="C:/Games/World_of_Tanks_EU"
"""
import os, sys, json, time, re, threading, shutil, datetime, tkinter as tk
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
    check_wg_game_version, snapshot_manifest, update_manifest_for_tags,
    scan_incomplete_builds
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

# ── i18n (EN authoritative, UK cached) ────────────
_ADMIN_UK_CACHE = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "admin_uk_cache.json")

_TR_EN = {
    "lang_en": "EN",
    "lang_uk": "UK",
    "not_set": "not set",
    "on": "ON",
    "off": "OFF",
    "label_admin": "Admin",
    "status_init": "Initializing...",
    "status_ok": "OK",
    "status_no_wot": "No WoT",
    "card_admin_ver": "Admin Version",
    "card_wg_ver": "WG Game Version",
    "card_game_status": "Game Status",
    "card_queue": "Queue",
    "card_last_scan": "Last Scan",
    "btn_scan": "Scan Now",
    "btn_gen_queue": "Generate Queue",
    "btn_gen_popular": "Generate Popular",
    "btn_regen_all": "Regen All",
    "menu_start_windows": "Start with Windows",
    "menu_start_minimized": "Start minimized to tray",
    "menu_wot_path": "WoT Path...",
    "menu_exit": "Exit",
    "menu_help": "Help",
    "menu_copy": "Copy",
    "menu_select_all": "Select All",
    "dlg_wot_path": "WoT Path",
    "dlg_wot_path_label": "WoT Path:",
    "dlg_save": "Save",
    "log_started": "Admin started (WoT: {path})",
    "log_tanks_prompts": "Tanks: {tanks}, Prompts: {prompts}",
    "log_manifest_seeded": "Manifest seeded from dev copy",
    "log_manifest_baseline": "Manifest baseline created from scripts.pkg",
    "log_manifest_baseline_fail": "Manifest baseline failed: {err}",
    "log_wot_path_set": "WoT path set to: {val}",
    "log_start_windows": "Start with Windows: {state}",
    "log_scan_running": "Scan already in progress",
    "log_scanning": "Scanning scripts.pkg for changes...",
    "log_changed": "Detected {n} changed tanks!",
    "log_no_changes": "No changes detected",
    "log_scan_error": "Scan error: {err}",
    "log_queue_empty": "Queue is empty. Run Scan first.",
    "log_generating": "Generating builds for {n} tanks...",
    "log_gen_done": "Generation complete!",
    "log_gen_failed": "Generation FAILED",
    "log_gen_error": "Generation error: {err}",
    "log_popular_start": "Generating popular tanks...",
    "log_popular_ok": "Popular tanks updated!",
    "log_popular_fail": "Popular tanks FAILED",
    "log_popular_error": "Popular error: {err}",
    "log_regen_warn": "WARNING: Regen All will regenerate ALL tanks via AI!",
    "log_wg_ts": "WG tanks_updated_at changed: {ts}",
    "log_auto_detected": "Auto-detected {n} changed tanks!",
    "log_periodic": "Periodic scan: {n} changed tanks!",
    "log_bg_error": "Background error: {err}",
    "log_tray_started": "Started minimized to tray",
    "log_tray_running": "Running in tray (WoT: {path})",
    "log_cleanup_done": "Cleaned {n} old error reports (>60 days)",
    "log_sweep_queued": "Incomplete builds queued for regeneration",
    "log_sweep_error": "Fill sweep failed: {err}",
    "notif_changes": "Changes Detected",
    "notif_changes_body": "{n} tanks changed",
    "notif_gen_started": "Generation Started",
    "notif_gen_started_body": "{n} tanks queued",
    "notif_builds_updated": "Builds Updated",
    "notif_builds_updated_body": "{n} tanks regenerated",
    "notif_gen_failed": "Generation Failed",
    "notif_gen_failed_body": "Check logs for details",
    "notif_error": "Error",
    "notif_popular": "Popular Tanks",
    "notif_popular_body": "List updated successfully",
    "notif_regen_all": "Regen All",
    "notif_regen_all_body": "{n} tanks queued - this takes days",
    "notif_auto_detected": "Auto-Detected",
    "notif_auto_detected_body": "{n} tanks changed via WG API",
    "help_title": "Help",
    "help_intro": "SM WoT Assistant Admin monitors World of Tanks changes and generates AI builds automatically. Below is a description of all functions and buttons.",
    "h_sec_buttons": "Buttons",
    "h_btn_scan_t": "Scan Now",
    "h_btn_scan_d": "Scans scripts.pkg for changed tanks and queues them for generation.",
    "h_btn_gen_queue_t": "Generate Queue",
    "h_btn_gen_queue_d": "Generates builds for all tanks in the queue (the changed tanks).",
    "h_btn_gen_popular_t": "Generate Popular",
    "h_btn_gen_popular_d": "Regenerates the popular tanks list (tiers 8-11).",
    "h_btn_regen_all_t": "Regen All",
    "h_btn_regen_all_d": "Regenerates ALL tanks via AI. Takes a very long time - use with caution.",
    "h_sec_settings": "Settings (gear icon)",
    "h_menu_start_windows_d": "Starts the app automatically with Windows.",
    "h_menu_start_minimized_d": "Starts the app minimized to the system tray.",
    "h_menu_wot_path_d": "Sets the path to the World of Tanks installation.",
    "h_menu_exit_d": "Fully exits the app (the X button only minimizes to tray).",
    "h_menu_help_d": "Opens this help window.",
    "h_lang_d": "Switches the interface language between English and Ukrainian.",
    "h_sec_tray": "Tray",
    "h_tray_x_d": "The X button minimizes the app to the tray. The app keeps working in the background.",
    "h_tray_click_d": "Clicking the tray icon restores the window.",
    "h_sec_background": "Background automation",
    "h_bg_wg_d": "Checks the WG API every 30 minutes for new tanks. On changes - automatically generates builds.",
    "h_bg_scan_d": "Scans scripts.pkg every 60 minutes for changed tanks.",
    "h_sec_log": "Log",
    "h_log_newest_d": "Newest messages appear at the top; older ones move down.",
    "h_log_copy_d": "Right-click the log to copy a message (Copy / Select All).",
    "h_f1_d": "Press F1 to open this help at any time.",
}

_SHIELD_TOKENS = [
    "SM WoT Assistant", "scripts.pkg", "tanks_updated_at",
    "World of Tanks", "F1", "Ctrl", "WG", "AI", "WoT", "EN", "UK",
    "admin.log", "OK", "HKCU", "AppData",
]
_SHIELD_RE = re.compile(r"\{[a-z0-9_ '\.\-]+\}")


def _shield(text):
    """Protect placeholders {..} and known tokens from Google Translate."""
    parts = []

    def _ph(m):
        parts.append(m.group(0))
        return "\ue000%d\ue001" % (len(parts) - 1)

    t = _SHIELD_RE.sub(_ph, text)
    for tok in sorted(_SHIELD_TOKENS, key=len, reverse=True):
        if tok in t:
            t = t.replace(tok, "\ue000%d\ue001" % len(parts))
            parts.append(tok)
    return t, parts


def _unshield(text, parts):
    for i, p in enumerate(parts):
        text = text.replace("\ue000%d\ue001" % i, p)
    return text


def _translate_en2uk(text):
    try:
        from deep_translator import GoogleTranslator
        shielded, parts = _shield(text)
        res = GoogleTranslator(source="en", target="uk").translate(shielded)
        if not res:
            return text
        return _unshield(res, parts)
    except Exception:
        return text


def _load_uk_translations():
    """Load cached UK translations; re-translate only changed/new keys."""
    data = None
    try:
        if os.path.exists(_ADMIN_UK_CACHE):
            with open(_ADMIN_UK_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        data = None
    if not data:
        seed = os.path.join(_BUNDLE_DIR, "admin_uk_seed.json")
        if os.path.exists(seed):
            try:
                with open(seed, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None
    uk = dict((data or {}).get("uk", {}) or {})
    old_snapshot = (data or {}).get("en_snapshot", {}) or {}
    changed = {k: v for k, v in _TR_EN.items() if old_snapshot.get(k) != v}
    if changed:
        for k, v in changed.items():
            uk[k] = _translate_en2uk(v)
        try:
            with open(_ADMIN_UK_CACHE, "w", encoding="utf-8") as f:
                json.dump({"en_snapshot": _TR_EN, "uk": uk,
                           "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass
    return uk

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
        user32 = ctypes.windll.user32
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = wintypes.LPARAM
        WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        def wndproc(hwnd, msg, wparam, lparam):
            try:
                if msg == _WM_TRAY_CALLBACK and (lparam & 0xFFFF) in (0x0202, 0x0203):
                    self.parent.root.deiconify()
                    self.parent.root.lift()
            except Exception:
                pass
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
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
        self._lang = self._admin_settings.get("lang", "en")
        if self._lang not in ("en", "uk"):
            self._lang = "en"
        self._tr_uk: dict = _load_uk_translations()
        self._wot_path = self._resolve_wot_path(wot_path)
        if self._wot_path and not self._admin_settings.get("wot_path"):
            self._admin_settings["wot_path"] = self._wot_path
            _save_admin_settings(self._admin_settings)
        self._manifest_path = self._resolve_manifest()

        self.tank_db = load_tank_db()
        self.prompts = load_prompts()
        self.tray = AdminTray(self)

        self._build_ui()
        self._log(self.t("log_started", path=self._wot_path or self.t("not_set")))
        self._log(self.t("log_tanks_prompts", tanks=len(self.tank_db), prompts=len(self.prompts)))
        self._last_heartbeat = 0.0
        self._last_cleanup = 0.0
        self._last_sweep = -86280.0  # first fill sweep ~120s after start, then every 24h
        threading.Thread(target=self._report_admin_status,
                         kwargs={"status": "idle"}, daemon=True).start()
        self._start_background()

    def _report_admin_status(self, status=None):
        """Publish admin app info to RTDB admin_app/ node (fire-and-forget)."""
        try:
            if status:
                _put_json(_rtdb_url("admin_app/status"), status)
            _put_json(_rtdb_url("admin_app/version"), _read_admin_version())
            _put_json(_rtdb_url("admin_app/last_seen"), int(time.time()))
        except Exception:
            pass

    def _cleanup_old_error_reports(self):
        """Видаляє error_reports старші 60 днів (fire-and-forget)."""
        try:
            now_utc = datetime.datetime.utcnow()
            cutoff = (now_utc - datetime.timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
            url = _rtdb_url("error_reports") + '?orderBy="timestamp"&endAt="' + cutoff + '"'
            old = _get_json(url) or {}
            n = 0
            for key, entry in list(old.items()):
                if not isinstance(entry, dict):
                    continue
                try:
                    ts = datetime.datetime.strptime(str(entry.get("timestamp", "")),
                                                    "%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    continue
                if ts >= now_utc - datetime.timedelta(days=60):
                    continue
                try:
                    _put_json(_rtdb_url("error_reports/" + str(key)), None)
                    n += 1
                except Exception:
                    pass
            if n:
                self._log(self.t("log_cleanup_done", n=n))
        except Exception:
            pass

    def _run_build_fill_sweep(self):
        """Generate strictly incomplete builds (daily self-heal, direct GUI path).

        Generates directly (no pending_updates trigger) so a concurrently running
        daemon --listen does not pick up the same queue and double-generate."""
        try:
            if self._generating:
                return
            st = _get_json(_rtdb_url("pending_updates/builds"))
            if st and st.get("status") == "generating":
                return
            queue = sorted(scan_incomplete_builds().keys())
            if queue:
                self._log(self.t("log_sweep_queued"))
                threading.Thread(target=self._do_generate,
                                 args=(queue,), daemon=True).start()
        except Exception as e:
            self._log(self.t("log_sweep_error", err=e))

    def t(self, key, **kw) -> str:
        v = str(_TR_EN.get(key, key))
        if self._lang == "uk":
            ukv = self._tr_uk.get(key)
            if isinstance(ukv, str) and ukv:
                v = str(ukv)
        if kw:
            try:
                return v.format(**kw)
            except Exception:
                return v
        return v

    def _toggle_lang(self):
        self._lang = "uk" if self._lang == "en" else "en"
        self._admin_settings["lang"] = self._lang
        _save_admin_settings(self._admin_settings)
        self._apply_lang()

    def _apply_lang(self):
        if hasattr(self, "_lang_btn") and self._lang_btn:
            self._lang_btn.config(text=self.t("lang_uk") if self._lang == "en" else self.t("lang_en"))
        for w, key in getattr(self, "_tr_widgets", []):
            try:
                w.config(text=self.t(key))
            except Exception:
                pass
        self._update_cards()

    def _show_help(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("help_title"))
        dlg.configure(bg=BG)
        dlg.geometry("680x560")
        dlg.minsize(500, 400)
        dlg.transient(self.root)

        def _help_popup(e):
            m = tk.Menu(dlg, tearoff=0, bg="#222222", fg=FG,
                        activebackground="#333333", activeforeground=ACCENT, bd=1)
            m.add_command(label=self.t("menu_copy"),
                          command=lambda: self._copy_selection(txt))
            m.add_separator()
            m.add_command(label=self.t("menu_select_all"),
                          command=lambda: txt.tag_add("sel", "1.0", "end-1c"))
            try:
                m.tk_popup(e.x_root, e.y_root)
            finally:
                m.grab_release()

        txt = scrolledtext.ScrolledText(dlg, bg="#111111", fg="#cccccc",
                                        insertbackground="#cccccc",
                                        font=("Consolas", 10), bd=0, wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", self._help_text())
        txt.config(state="disabled")
        txt.bind("<Button-3>", _help_popup)

    def _help_text(self):
        L = [self.t("help_intro"), ""]
        L.append("== " + self.t("h_sec_buttons") + " ==")
        for b in ("scan", "gen_queue", "gen_popular", "regen_all"):
            L.append("\u2022 " + self.t("h_btn_" + b + "_t") + " \u2014 " + self.t("h_btn_" + b + "_d"))
        L.append("")
        L.append("== " + self.t("h_sec_settings") + " ==")
        L.append("\u2022 " + self.t("menu_start_windows") + " \u2014 " + self.t("h_menu_start_windows_d"))
        L.append("\u2022 " + self.t("menu_start_minimized") + " \u2014 " + self.t("h_menu_start_minimized_d"))
        L.append("\u2022 " + self.t("menu_wot_path") + " \u2014 " + self.t("h_menu_wot_path_d"))
        L.append("\u2022 " + self.t("menu_exit") + " \u2014 " + self.t("h_menu_exit_d"))
        L.append("\u2022 " + self.t("menu_help") + " \u2014 " + self.t("h_menu_help_d"))
        L.append("\u2022 " + self.t("lang_en") + "/" + self.t("lang_uk") + " \u2014 " + self.t("h_lang_d"))
        L.append("")
        L.append("== " + self.t("h_sec_tray") + " ==")
        L.append("\u2022 " + self.t("h_tray_x_d"))
        L.append("\u2022 " + self.t("h_tray_click_d"))
        L.append("")
        L.append("== " + self.t("h_sec_background") + " ==")
        L.append("\u2022 " + self.t("h_bg_wg_d"))
        L.append("\u2022 " + self.t("h_bg_scan_d"))
        L.append("")
        L.append("== " + self.t("h_sec_log") + " ==")
        L.append("\u2022 " + self.t("h_log_newest_d"))
        L.append("\u2022 " + self.t("h_log_copy_d"))
        L.append("\u2022 " + self.t("h_f1_d"))
        return "\n".join(L)

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
                        self._log(self.t("log_manifest_seeded"))
                        return path
                except Exception:
                    pass
            try:
                if snapshot_manifest(self._wot_path, path):
                    self._log(self.t("log_manifest_baseline"))
                    return path
            except Exception as e:
                self._log(self.t("log_manifest_baseline_fail", err=e))
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

        self._tr_widgets = []

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(top, text="SM WoT Assistant", font=("Segoe UI", 16, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        self._lbl_admin = tk.Label(top, text=self.t("label_admin"), font=("Segoe UI", 16, "bold"),
                                   fg="#ff4500", bg=BG)
        self._lbl_admin.pack(side="left")
        self._tr_widgets.append((self._lbl_admin, "label_admin"))

        self._settings_btn = tk.Button(top, text="⚙", font=("Segoe UI", 14), bg=BG, fg="#aaa", bd=0,
                                       command=self._show_settings_menu)
        self._settings_btn.pack(side="right", padx=(0, 4))

        self._lang_btn = tk.Button(top, font=("Segoe UI", 10, "bold"), bg=BG, fg=ACCENT, bd=0,
                                   cursor="hand2", command=self._toggle_lang)
        self._lang_btn.pack(side="right", padx=(0, 8))

        # Status bar
        self.status_lbl = tk.Label(self.root, text=self.t("status_init"), font=("Segoe UI", 10),
                                   fg="#888888", bg=BG, anchor="w")
        self.status_lbl.pack(fill="x", padx=12, pady=(0, 4))
        self._tr_widgets.append((self.status_lbl, "status_init"))

        # Main content
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Left panel: status cards
        left = tk.Frame(content, bg=BG2, padx=12, pady=10)
        left.pack(side="left", fill="y", padx=(0, 8))

        def _card(parent, key):
            f = tk.Frame(parent, bg=BG2, bd=1, relief="solid", highlightbackground="#333")
            lbl = tk.Label(f, text=self.t(key), font=("Segoe UI", 9), fg="#888", bg=BG2)
            lbl.pack(anchor="w")
            self._tr_widgets.append((lbl, key))
            v = tk.Label(f, text="—", font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG2)
            v.pack(anchor="w", pady=(2, 0))
            f.pack(fill="x", pady=3)
            return v

        self._card_ver = _card(left, "card_admin_ver")
        self._card_wg = _card(left, "card_wg_ver")
        self._card_status = _card(left, "card_game_status")
        self._card_queue = _card(left, "card_queue")
        self._card_last = _card(left, "card_last_scan")

        # Right panel: buttons + log
        right = tk.Frame(content, bg=BG)
        right.pack(side="right", fill="both", expand=True)

        # Buttons
        btn_f = tk.Frame(right, bg=BG)
        btn_f.pack(fill="x", pady=(0, 6))

        self._scan_btn = tk.Button(btn_f, text=self.t("btn_scan"), command=self._scan_now,
                                    bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._scan_btn.pack(side="left", padx=(0, 6))
        self._tr_widgets.append((self._scan_btn, "btn_scan"))

        self._gen_btn = tk.Button(btn_f, text=self.t("btn_gen_queue"), command=self._gen_queue,
                                   bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._gen_btn.pack(side="left", padx=(0, 6))
        self._tr_widgets.append((self._gen_btn, "btn_gen_queue"))

        self._popular_btn = tk.Button(btn_f, text=self.t("btn_gen_popular"), command=self._gen_popular,
                                       bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._popular_btn.pack(side="left", padx=(0, 6))
        self._tr_widgets.append((self._popular_btn, "btn_gen_popular"))

        self._regen_all_btn = tk.Button(btn_f, text=self.t("btn_regen_all"), command=self._gen_all,
                                          bg="#553333", fg=RED, bd=0, padx=14, pady=4, cursor="hand2")
        self._regen_all_btn.pack(side="left")
        self._tr_widgets.append((self._regen_all_btn, "btn_regen_all"))

        # Log
        self.log_text = scrolledtext.ScrolledText(right, bg="#111111", fg="#cccccc",
                                                   insertbackground="#cccccc",
                                                   font=("Consolas", 10), bd=0,
                                                   wrap="word", height=18)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.bind("<Button-3>", self._show_log_menu)

        self.root.bind("<F1>", lambda e: self._show_help())

        self._apply_lang()

    def _show_log_menu(self, event):
        m = tk.Menu(self.root, tearoff=0, bg="#222222", fg=FG,
                    activebackground="#333333", activeforeground=ACCENT, bd=1)
        m.add_command(label=self.t("menu_copy"), command=self._copy_log_selection)
        m.add_separator()
        m.add_command(label=self.t("menu_select_all"),
                      command=lambda: self.log_text.tag_add("sel", "1.0", "end-1c"))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _copy_log_selection(self):
        self._copy_selection(self.log_text)

    def _copy_help_selection(self, txt):
        self._copy_selection(txt)

    def _copy_selection(self, widget):
        try:
            sel = widget.get("sel.first", "sel.last")
        except tk.TclError:
            sel = ""
        if sel:
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)

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
            self.log_text.insert("1.0", line + "\n")
            self.log_text.delete("1000.0", tk.END)
            self.log_text.see("1.0")
        else:
            print(line)

    def _update_cards(self):
        self._card_ver.config(text=_read_admin_version())
        self._card_wg.config(text=self._wg_ver or "—")
        if os.path.exists(os.path.join(self._wot_path or "", "version.xml")):
            status = self.t("status_ok")
            color = GREEN
        else:
            status = self.t("status_no_wot")
            color = RED
        self._card_status.config(text=status, fg=color)
        q = len(self._queue)
        self._card_queue.config(text=str(q), fg=ACCENT if q > 0 else "#888")
        self._card_last.config(text=time.strftime("%H:%M") if self._last_scan > 0 else "—")

    def _show_settings_menu(self):
        """Gear button opens a dropdown menu (same pattern as the main app)."""
        menu = tk.Menu(self.root, tearoff=0, bg="#222222", fg=FG,
                       activebackground="#333333", activeforeground=ACCENT, bd=1)
        sw = tk.BooleanVar(value=self._admin_settings.get("start_with_windows", False))
        menu.add_checkbutton(label=self.t("menu_start_windows"), variable=sw,
                             command=lambda: self._on_settings_change("start_with_windows", sw.get()))
        sm = tk.BooleanVar(value=self._admin_settings.get("start_minimized", False))
        menu.add_checkbutton(label=self.t("menu_start_minimized"), variable=sm,
                             command=lambda: self._on_settings_change("start_minimized", sm.get()))
        menu.add_separator()
        menu.add_command(label=self.t("menu_wot_path"), command=self._show_wot_path_dialog)
        menu.add_separator()
        menu.add_command(label=self.t("menu_help"), command=self._show_help)
        menu.add_separator()
        menu.add_command(label=self.t("menu_exit"), command=self._exit_app)
        try:
            x = self._settings_btn.winfo_rootx()
            y = self._settings_btn.winfo_rooty() + self._settings_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _show_wot_path_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.configure(bg=BG)
        dlg.title(self.t("dlg_wot_path"))
        dlg.geometry("420x120")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=self.t("dlg_wot_path_label"), bg=BG, fg="#aaa",
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
            self._log(self.t("log_wot_path_set", val=val))
            dlg.destroy()

        tk.Button(dlg, text=self.t("dlg_save"), bg="#333", fg=FG, bd=0, padx=20, pady=4,
                  command=_save_wp).pack(pady=6)

    def _on_settings_change(self, key, value):
        self._admin_settings[key] = value
        _save_admin_settings(self._admin_settings)
        if key == "start_with_windows":
            _set_windows_startup(value)
            self._log(self.t("log_start_windows",
                             state=self.t("on") if value else self.t("off")))

    def _scan_now(self):
        if self._scanning:
            self._log(self.t("log_scan_running"))
            return
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        self._scanning = True
        self._scan_btn.config(state="disabled")
        self._log(self.t("log_scanning"))
        try:
            changed = detect_changed_tanks(self._wot_path, self._manifest_path) if self._wot_path else []
            self._last_scan = time.time()
            if changed:
                self._queue = changed
                self._log(self.t("log_changed", n=len(changed)))
                for t in changed[:10]:
                    self._log(f"  {t}")
                self.tray.show_notification(self.t("notif_changes"),
                                            self.t("notif_changes_body", n=len(changed)))
                self.root.after(0, self._update_cards)
                self._do_generate(changed)
            else:
                self._log(self.t("log_no_changes"))
                self.root.after(0, self._update_cards)
        except Exception as e:
            self._log(self.t("log_scan_error", err=e))
        finally:
            self._scanning = False
            self.root.after(0, lambda: self._scan_btn.config(state="normal"))

    def _gen_queue(self):
        if not self._queue:
            self._log(self.t("log_queue_empty"))
            return
        threading.Thread(target=self._do_generate, args=(list(self._queue),), daemon=True).start()

    def _do_generate(self, queue):
        self._generating = True
        self.root.after(0, lambda: self._gen_btn.config(state="disabled"))
        self._log(self.t("log_generating", n=len(queue)))
        _update_pending_status("builds", "generating",
                               message=self.t("log_generating", n=len(queue)))
        self._report_admin_status(status="generating")
        self.tray.show_notification(self.t("notif_gen_started"),
                                    self.t("notif_gen_started_body", n=len(queue)))
        try:
            driver = _create_driver()
            try:
                ok, done_tags = generate_builds(driver, self.tank_db, self.prompts, queue=queue,
                                                wot_path=self._wot_path)
                if ok and done_tags:
                    _update_builds_version()
                    self._queue = [t for t in self._queue if t not in done_tags]
                    try:
                        update_manifest_for_tags(self._wot_path, self._manifest_path, done_tags)
                    except Exception:
                        pass
                    iso = time.strftime("%Y-%m-%dT%H:%M:%S")
                    _put_json(_rtdb_url("builds/last_generated_at"), iso)
                    _put_json(_rtdb_url("prompts/last_generated_at"), iso)
                    _put_json(_rtdb_url("admin_app/last_generation"),
                              {"at": iso, "count": len(done_tags), "ok": True})
                    _update_pending_status("builds", "done",
                                           message=self.t("notif_builds_updated_body", n=len(done_tags)))
                    self._log(self.t("log_gen_done"))
                    self.tray.show_notification(self.t("notif_builds_updated"),
                                                self.t("notif_builds_updated_body", n=len(done_tags)),
                                                level="info")
                else:
                    _update_pending_status("builds", "error", message="generation failed")
                    self._log(self.t("log_gen_failed"))
                    self.tray.show_notification(self.t("notif_gen_failed"),
                                                self.t("notif_gen_failed_body"),
                                                level="error")
            finally:
                driver.quit()
        except Exception as e:
            _update_pending_status("builds", "error", message=str(e)[:200])
            self._log(self.t("log_gen_error", err=e))
            self.tray.show_notification(self.t("notif_error"), str(e)[:80], level="error")
        finally:
            self._generating = False
            self._report_admin_status(status="idle")
            self.root.after(0, lambda: self._gen_btn.config(state="normal"))
            self.root.after(0, self._update_cards)

    def _gen_popular(self):
        threading.Thread(target=self._do_popular, daemon=True).start()

    def _do_popular(self):
        self._log(self.t("log_popular_start"))
        self._popular_btn.config(state="disabled")
        try:
            driver = _create_driver()
            try:
                ok = generate_popular(driver, self.tank_db)
                if ok:
                    _put_json(_rtdb_url("popular_tanks/last_generated_at"),
                              time.strftime("%Y-%m-%dT%H:%M:%S"))
                    self._log(self.t("log_popular_ok"))
                    self.tray.show_notification(self.t("notif_popular"),
                                                self.t("notif_popular_body"))
                else:
                    self._log(self.t("log_popular_fail"))
            finally:
                driver.quit()
        except Exception as e:
            self._log(self.t("log_popular_error", err=e))
        finally:
            self.root.after(0, lambda: self._popular_btn.config(state="normal"))

    def _gen_all(self):
        self._log(self.t("log_regen_warn"))
        self.tray.show_notification(self.t("notif_regen_all"),
                                    self.t("notif_regen_all_body", n=len(self.tank_db)),
                                    level="error")
        threading.Thread(target=self._do_generate,
                         args=(list(self.tank_db.keys()),), daemon=True).start()

    def _start_background(self):
        def _loop():
            while self._running:
                try:
                    now = time.time()
                    if now - self._last_heartbeat > 60:
                        self._last_heartbeat = now
                        self._report_admin_status()
                    if now - self._last_cleanup > 86400:  # 24 h
                        self._last_cleanup = now
                        self._cleanup_old_error_reports()
                    if now - self._last_sweep > 86400:  # 24 h fill sweep
                        self._last_sweep = now
                        self._run_build_fill_sweep()
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
                                self._log(self.t("log_wg_ts", ts=ts))
                                if self._wot_path:
                                    changed = detect_changed_tanks(self._wot_path, self._manifest_path)
                                    if changed:
                                        self._queue = changed
                                        self.root.after(0, self._update_cards)
                                        self._log(self.t("log_auto_detected", n=len(changed)))
                                        self.tray.show_notification(
                                            self.t("notif_auto_detected"),
                                            self.t("notif_auto_detected_body", n=len(changed)))
                                        self._do_generate(changed)
                    if self._wot_path and now - self._last_scan > 3600:
                        self._last_scan = now
                        changed = detect_changed_tanks(self._wot_path, self._manifest_path)
                        if changed:
                            self._queue = changed
                            self.root.after(0, self._update_cards)
                            self._log(self.t("log_periodic", n=len(changed)))
                            self.tray.show_notification(
                                self.t("notif_changes"),
                                self.t("notif_changes_body", n=len(changed)))
                            self._do_generate(changed)
                except Exception as e:
                    self._log(self.t("log_bg_error", err=e))
                time.sleep(10)
        threading.Thread(target=_loop, daemon=True).start()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(1000, self._scan_now)
        self.root.mainloop()

    def _on_close(self):
        """X button minimizes to tray; full exit via Settings gear -> Exit."""
        self.root.withdraw()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()

    def _exit_app(self):
        self._running = False
        try:
            threading.Thread(target=self._report_admin_status,
                             kwargs={"status": "offline"}, daemon=True).start()
        except Exception:
            pass
        if hasattr(self, "tray"):
            self.tray.remove()
        self.root.destroy()


def main():
    import argparse

    # Single-instance mutex
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    _k32.CreateMutexW.restype = ctypes.c_void_p
    mutex = _k32.CreateMutexW(None, False, "SM_WoT_Assistant_Admin_SingleInstance")
    if ctypes.get_last_error() == 183:
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
        app.root.after(100, app._log, app.t("log_tray_started"))
        app.root.after(300, lambda: app.tray.show_notification(
            "SM WoT Assistant Admin", app.t("log_tray_running",
                                             path=app._wot_path or app.t("not_set"))))
    else:
        root.deiconify()
    app.run()
    ctypes.windll.kernel32.CloseHandle(mutex)

if __name__ == "__main__":
    main()
