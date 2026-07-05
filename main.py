            

import os, sys, json, ctypes, re

if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

import time
import threading
import subprocess
import tempfile
import requests
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk, ImageOps, ImageEnhance
import keyboard

import config
import tactics_manager
import log_reader
import help_system
import painter as pnt
import painting_palette
import stats_ai
import window_manager
import map_renderer
import locale_manager
import map_manager
import data_manager
import ui_manager
import dialog_utils
import firebase_identity
import firebase_reporter
import firebase_drawings
import firebase_groups
import tray_icon

try:
    import map_extractor
except ImportError:
    map_extractor = None

class WotAssistantHQ:
    def __init__(self, root, splash_geometry=None):
        self.root = root
        self.root.withdraw()
        self._splash_geometry = splash_geometry

        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "SM_WoT_Assistant_SingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183:
            sys.exit(0)
        self._update_mutex = mutex

        self.mode = "edit" 
        self.map_mode = 1 
        self.dialog_open = False 
        self.edit_focus_lock = False
        self._last_mode_hotkey_ts = 0.0
        self.active_view = ""
        self._startup_complete = False
        self._tray_icon = None
        self._hidden_by_f10 = False
        self.active_group_id = "public"
        self._cached_groups = {}
        self._group_id_map = {}
        self._sync_running = False
        
        self.data_mgr = data_manager.DataManager()
        self.settings = self.data_mgr.load_json(config.SETTINGS_FILE)
        self._dot_anim_active = False
        self.map_mgr = map_manager.MapManager(self)
        self.map_mgr.auto_detect_wot_path()
        self.custom_names = self.data_mgr.load_json(config.CUSTOM_NAMES_FILE)
        
        import language_module
        self.lang = language_module.setup(
            self.settings.get("wot_path", ""),
            self.settings,
            self.save_settings
        )
        
        self.locale = locale_manager.LocaleManager(self)
        self.map_renderer = map_renderer.MapRenderer(self)
        
        self.extractor_names = {}
        self.map_list = []
        self.tank_db = self.data_mgr.load_tank_db()
        self.popular_tanks = []
        self.ai_icons = {} # Кеш іконок для Treeview
        self.ai_filters = {"nation": None, "class": None, "tier": None}
        
        self.compact_descr_map = {
            v["compact_descr"]: {"key": k, "class": v["class"], "name": v["name"]}
            for k, v in self.tank_db.items()
            if v.get("compact_descr")
        }
        
        self.w = self.settings.get("edit_w", 800)
        self.h = self.w + 160
        self.alpha = self.settings.get("edit_alpha", 1.0)
        self.contrast = self.settings.get("edit_contrast", 1.0)
        
        self.auto_sync_var = tk.BooleanVar(value=self.settings.get("auto_sync", False))
        self.auto_battle_var = tk.BooleanVar(value=self.settings.get("auto_battle", False))
        self.auto_mode_filter_var = tk.BooleanVar(value=self.settings.get("auto_mode_filter", True))
        self.auto_vehicle_filter_var = tk.BooleanVar(value=self.settings.get("auto_vehicle_filter", True))
        self.auto_update_var = tk.BooleanVar(value=self.settings.get("auto_update", True))
        
        self.win_mgr = window_manager.WindowManager(self)
        self.win_mgr.initialize_window()
        
        self.map_list_eng = []
        self.current_map_eng = None
        self.current_tk_map = None
        self.drag = None
        self.help_manager = help_system.HelpManager(self)

        self.selected_battle_mode = tk.StringVar(value="Standard")
        self.selected_classes = {
            "LT": tk.BooleanVar(value=True), "MT": tk.BooleanVar(value=True),
            "HT": tk.BooleanVar(value=True), "TD": tk.BooleanVar(value=True),
            "SPG": tk.BooleanVar(value=True)
        }

        self.thread_queue = []
        self.process_queue()
        
        log_path = self.settings.get("log_path", "")
        wot_path = self.settings.get("wot_path", "")
        
        if log_path:
            log_path = os.path.normpath(log_path)
            self.settings["log_path"] = log_path
        
        print(f"[INIT] log_path = {log_path}")
        print(f"[INIT] wot_path = {wot_path}")
        
        game_exists = wot_path and os.path.exists(os.path.join(wot_path, "WorldOfTanks.exe"))
        
        if not (log_path and os.path.exists(log_path)):
            self._auto_detect_log_path()
            new_log = self.settings.get("log_path", "")
            if new_log:
                log_path = os.path.normpath(new_log)
                self.settings["log_path"] = log_path
            elif game_exists:
                # Вивести шлях із wot_path, якщо common_logs не знайшли
                for suffix in ["python.log", os.path.join("logs", "python.log")]:
                    p = os.path.normpath(os.path.join(wot_path, suffix))
                    log_path = p
                    self.settings["log_path"] = p
                    break
        
        # Якщо шлях відомий, але файлу немає — створюємо пустий
        if log_path and not os.path.exists(log_path):
            try:
                d = os.path.dirname(log_path)
                if d and not os.path.exists(d):
                    os.makedirs(d, exist_ok=True)
                with open(log_path, "w", encoding="utf-8") as _:
                    pass
                print(f"[INIT] Created empty log at: {log_path}")
            except Exception as e:
                print(f"[INIT] Cannot create log at {log_path}: {e}")
        
        if log_path and os.path.exists(log_path):
            print(f"[INIT] {self.t('ui', 'log_found').format(path=log_path)}")
        elif game_exists:
            print(f"[INIT] {self.t('ui', 'log_waiting').format(path=wot_path)}")
        else:
            print(f"[INIT] {self.t('ui', 'game_not_found')}")
        
        self.last_battle_map = None
        self.last_battle_mode = None
        self.last_battle_map_mode = 2
        self.log_watcher = log_reader.LogWatcher(
            log_path,
            self.on_battle_detected,
            self.on_battle_ended,
            self.on_minimap_appeared,
            self.on_battle_countdown_started,
            self.on_vehicle_detected,
        )
        self.log_watcher.start()

        self.ui_mgr = ui_manager.UIManager(self)

        self.load_logo()

        firebase_reporter.setup_global_excepthook(self)
        firebase_reporter.ping_version_async(self)

        if bool(self.settings.get("disable_startup_splash", False)):
            self._start_startup_checks()
        else:
            self.show_small_loading_splash()
            if self._splash_geometry:
                self.root.after(120, self._start_startup_checks_continue)
            else:
                self.root.after(120, self._start_startup_checks)

    def _start_startup_checks(self):
        if self.auto_update_var.get() and hasattr(self, 'splash'):
            self.update_startup_progress(10, self.t('ui', 'checking_updates'))
            self.root.update_idletasks()
            try:
                latest = firebase_reporter.check_for_updates_sync()
                if latest:
                    latest_ver = latest.get("version", "")
                    current_ver = config.load_version()
                    if firebase_reporter.compare_versions(current_ver, latest_ver):
                        self._show_splash_update(latest)
                        return
            except Exception as e:
                print(f"[INIT] Update check error: {e}")
        elif self.auto_update_var.get():
            self._check_for_app_updates()

        self._start_startup_checks_continue()

    def _start_startup_checks_continue(self):
        # 1. Batch translate UI on splash (atomic — all or nothing)
        if hasattr(self, 'locale'):
            self.locale.batch_translate_ui(progress_cb=self._on_startup_progress)

        # 2. Build UI — t_ui() reads from cache (translated if batch OK, EN if batch failed)
        self.ui_mgr.setup_ui()
        self.refresh_mode_indicator()
        self.bind_events()

        self.painter = pnt.MapPainter(self.canvas, self, self.data_mgr)
        self.painter.bind_events_to(self.canvas)
        self._init_painter_overlay()
        self.drawing_palette = painting_palette.DrawingPalette(self.root, self.painter, self)
        self.drawing_palette.withdraw()

        self.map_mgr.load_map_list()

        self.selected_battle_mode.trace_add("write", lambda *args: self.map_mgr.load_map_list())
        for var in self.selected_classes.values():
            var.trace_add("write", lambda *args: self.painter.redraw())

        # 3. Game version check with progress on splash
        allow_decode = bool(self.settings.get("allow_map_decode_on_startup", True))
        self.map_mgr.check_game_version(
            progress_cb=self._on_startup_progress,
            done_cb=self._on_startup_ready,
            allow_map_decode=allow_decode,
        )


    def t(self, cat, key):
        if cat == "ui": return self.locale.t_ui(key)
        if cat == "tanks": return self.locale.t_tank(key, key)
        return self.locale.t_map(key)

    def _init_painter_overlay(self):
        self._po_win = tk.Toplevel(self.root)
        self._po_win.withdraw()
        self._po_win.overrideredirect(True)
        self._po_win.attributes("-topmost", True)
        self._po_win.attributes("-transparentcolor", "#010101")
        self._po_win.wm_attributes("-alpha", 1.0)
        self._po_win.transient(self.root)
        self.root.lower(self._po_win)
        self._po_canvas = tk.Canvas(self._po_win, bg="#010101", highlightthickness=0)
        self._po_canvas.pack(fill="both", expand=True)
        self.painter.bind_events_to(self._po_canvas)
        self.painter.canvas = self._po_canvas
        self.canvas.bind("<Configure>", self._sync_po_pos, "+")
        self.root.bind("<Configure>", self._sync_po_pos, "+")
        self.root.bind("<Unmap>", self._on_root_hide, "+")
        self.root.bind("<Map>", self._on_root_show, "+")
        self.root.bind("<FocusIn>", self._on_root_focus_in, add="+")

    def _sync_po_pos(self, event=None):
        palette = getattr(self, 'drawing_palette', None)
        if palette and palette.winfo_exists() and palette.state() != 'withdrawn':
            palette.lift()
        if not hasattr(self, '_po_win') or not self._po_win.winfo_exists():
            return
        if self._po_win.state() == "withdrawn":
            return
        cx = self.canvas.winfo_rootx()
        cy = self.canvas.winfo_rooty()
        if cx <= 0 or cy <= 0:
            return
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw > 50 and ch > 50:
            try:
                self._po_win.geometry(f"{cw}x{ch}+{cx}+{cy}")
            except Exception:
                pass

    def _lift_overlay(self):
        if self._hidden_by_f10:
            return
        if hasattr(self, '_po_win') and self._po_win.winfo_exists() and self._po_win.state() != "withdrawn":
            self._po_win.lift()

    def _on_root_focus_in(self, event=None):
        self.root.after_idle(self._lift_overlay)

    def _on_root_hide(self, event=None):
        if hasattr(self, '_po_win') and self._po_win.winfo_exists() and self._po_win.state() != "withdrawn":
            self._po_win.withdraw()

    def _on_root_show(self, event=None):
        if self._hidden_by_f10:
            return
        if self.active_view == "maps" and hasattr(self, '_po_win') and self._po_win.winfo_exists():
            if not getattr(self, '_startup_complete', False):
                return
            if self._po_win.state() != "withdrawn":
                return
            if not self.current_map_eng:
                return
            self._po_win.deiconify()
            self._sync_po_pos()
            self._po_win.lift()

    def get_edit_extra_height(self):
        """Висота службових панелей у режимі редагування (щоб мапа залишалася квадратною)."""
        # Всі віджети мають існувати до виклику (initialize_window більше його не використовує)
        if not hasattr(self, "top_bar"):
            return 160

        self.root.update_idletasks()
        top_h = self.top_bar.winfo_reqheight()
        identity_h = self.identity_bar.winfo_reqheight() if hasattr(self, "identity_bar") else 0
        filter_h = self.filter_panel.winfo_reqheight() if hasattr(self, "filter_panel") else 0
        status_h = self.status_label.winfo_reqheight() if hasattr(self, "status_label") else 0
        return top_h + identity_h + filter_h + status_h

    def process_queue(self):
        while self.thread_queue:
            try:
                func = self.thread_queue.pop(0)
                func()
            except Exception as e:
                print(f"[ШТАБ] Помилка виконання з черги: {e}")
        self.root.after(50, self.process_queue)

    def safe_execute(self, func):
        self.thread_queue.append(func)


    def save_settings(self):
        try:
            cx, cy = self.root.winfo_x(), self.root.winfo_y()
        except tk.TclError:
            return
        if cx < -5000 or cx <= 0 or cy <= 0: return
        try:
            if self.root.winfo_width() < 100: return
        except tk.TclError:
            return

        prefix = "edit_" if self.mode == "edit" else "norm_"
        self.settings[f"{prefix}w"] = self.w
        self.settings[f"{prefix}h"] = self.h
        if self.mode == "edit":
            aw = self.root.winfo_width()
            ah = self.root.winfo_height()
            self.settings[f"{prefix}cx"] = cx + aw // 2
            self.settings[f"{prefix}cy"] = cy + ah // 2
            self.settings[f"{prefix}x"] = cx
            self.settings[f"{prefix}y"] = cy
        else:
            self.settings[f"{prefix}x"] = cx
            self.settings[f"{prefix}y"] = cy
        self.settings[f"{prefix}alpha"] = self.alpha
        self.settings[f"{prefix}contrast"] = self.contrast
        self.settings["auto_sync"] = self.auto_sync_var.get()
        self.settings["auto_battle"] = self.auto_battle_var.get()
        self.settings["auto_mode_filter"] = self.auto_mode_filter_var.get()
        self.settings["auto_vehicle_filter"] = self.auto_vehicle_filter_var.get()
        self.settings["auto_update"] = self.auto_update_var.get()
        self.data_mgr.save_json(config.SETTINGS_FILE, self.settings)
        
        if hasattr(self, 'log_watcher'):
            self.log_watcher.update_path(self.settings.get("log_path", ""))


    def reload_tank_data(self):
        self.tank_db = self.data_mgr.load_tank_db()
        self.compact_descr_map = {
            v["compact_descr"]: {"key": k, "class": v["class"], "name": v["name"]}
            for k, v in self.tank_db.items()
            if v.get("compact_descr")
        }
        if hasattr(self, "stats_ai_module") and self.stats_ai_module:
            self.stats_ai_module.tank_db = self.tank_db
            self.stats_ai_module.reload_tth_data()
            self.stats_ai_module.update_search_placeholder(self.t('ui', 'search_placeholder').format(count=len(self.tank_db)))
            self.stats_ai_module.refresh_ai_view()





    def translate_map_name(self, eng):
        return self.locale.t_map(eng)


    def ask_wot_path(self):
        self.dialog_open = True
        path = filedialog.askdirectory(title=self.t('ui', 'dialog_select_wot_path'))
        self.dialog_open = False
        
        if path:
            self.settings["wot_path"] = path
            log_path = os.path.join(path, "python.log")
            self.settings["log_path"] = log_path
            self.save_settings()
            
            if os.path.exists(log_path):
                print(f"[CONFIG] log_path встановлено: {log_path}")
                self.log_watcher.update_path(log_path)
            else:
                print(f"[CONFIG] ПОМИЛКА: log_path не існує: {log_path}")
            
            if self.btn_mode_maps_2.cget("bg") == "#ff4500":
                self.map_mgr.run_map_updater()

    def ask_clear_confirm(self, map_title, on_done):
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t('ui', 'dialog_clear_title'))
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        dlg.minsize(300, 120)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()

        cx = self.root.winfo_x() + self.root.winfo_width() // 2 - 150
        cy = self.root.winfo_y() + self.root.winfo_height() // 2 - 60
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text=self.t('ui', 'dialog_clear_msg').format(map_title=map_title),
                 font=("Arial", 10), bg="#2a2a2a", fg="#cccccc").pack(pady=(20, 15))

        bf = tk.Frame(dlg, bg="#2a2a2a")
        bf.pack(pady=(0, 15))
        result = {"ok": False}
        def on_yes(): result["ok"] = True; dlg.destroy()
        def on_no(): dlg.destroy()

        tk.Button(bf, text=f"  {self.t('ui', 'btn_yes')}  ", bg="#555", fg="white", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_yes).pack(side="left", padx=10)
        tk.Button(bf, text=f"  {self.t('ui', 'btn_no')}  ", bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_no).pack(side="left", padx=10)

        self.root.wait_window(dlg)
        on_done(result["ok"])

    def ask_ai_key(self):
        new_key = dialog_utils.dark_promptbox(self.root, self.t('ui', 'ai_key_title'), self.t('ui', 'ai_key_prompt'), initialvalue=self.settings.get("ai_key", ""))
        if new_key is not None:
            self.settings["ai_key"] = new_key.strip()
            self.save_settings()
            if hasattr(self, "ai_stats") and self.ai_stats:
                self.ai_stats.configure(self.settings["ai_key"])

        self._last_mode_hotkey_ts = 0

    def toggle_editor(self):
        if self.dialog_open: return 

        if self.mode == "edit" and self.active_view in ("stats", "ai_stats"):
            msg = self.t('ui', 'status_auto_mode_unavailable')
            print(msg)
            return

        self.save_settings() 
        if hasattr(self, '_rsz_timer'):
            self.root.after_cancel(self._rsz_timer)
        self.battle_status_top.pack_forget()
        self.top_bar.pack_forget()
        if hasattr(self, 'identity_bar'): self.identity_bar.pack_forget()
        self.map_toolbar.pack_forget()
        self.filter_panel.pack_forget()
        self.status_label.pack_forget()
        self.canvas.pack_forget()
        self.browser_frame.pack_forget()
        if hasattr(self, 'ai_frame'): self.ai_frame.pack_forget()

        if self.mode == "edit":
            self.mode = "norm"
            self.win_mgr.set_clickthrough(not self.win_mgr.format_mode_enabled)
            if self.active_view == "maps":
                self.battle_status_top.pack(side="top", fill="x")
                self.canvas.pack(side="top", fill="both", expand=True)
            elif self.active_view in ("stats", "ai_stats"):
                self.mode = "edit"
                self.win_mgr.set_clickthrough(False)
                self.top_bar.pack(side="top", fill="x")
                if hasattr(self, 'identity_bar'): self.identity_bar.pack(side="top", fill="x")
        else:
            self.mode = "edit"
            self.win_mgr.set_clickthrough(False)
            self.top_bar.pack(side="top", fill="x")
            if hasattr(self, 'identity_bar'): self.identity_bar.pack(side="top", fill="x")

        if self.active_view == "maps":
            self.status_label.pack_forget()
            if self.mode == "edit":
                self.map_toolbar.pack(side="left", fill="x", expand=True, padx=(0, 10))
                self.filter_panel.pack(side="bottom", fill="x")
                self.status_label.pack(side="bottom", fill="x")
                self.status_label.config(height=2, bg="#1a1a1a")
            self.canvas.pack(side="top", fill="both", expand=True)
            self.painter.redraw()
        elif self.active_view == "stats":
            if hasattr(self, 'drawing_palette'):
                self.drawing_palette.exit_edit_mode()
                if self.drawing_palette.state() != 'withdrawn':
                    self.drawing_palette.withdraw()
            self.status_label.pack(side="bottom", fill="x")
            self.browser_frame.pack(side="top", fill="both", expand=True)
        elif self.active_view == "ai_stats":
            if hasattr(self, 'drawing_palette'):
                self.drawing_palette.exit_edit_mode()
                if self.drawing_palette.state() != 'withdrawn':
                    self.drawing_palette.withdraw()
            self.ai_frame.pack(side="top", fill="both", expand=True)
            self.status_label.pack(side="bottom", fill="x")

        prefix = "edit_" if self.mode == "edit" else "norm_"
        self.w = self.settings.get(f"{prefix}w", 800 if self.mode=="edit" else 400)
        if self.mode == "edit":
            self.h = self.w + self.get_edit_extra_height()
        else:
            self.h = self.w + 18
        self.alpha = self.settings.get(f"{prefix}alpha", 1.0)
        self.contrast = self.settings.get(f"{prefix}contrast", 1.0)
        if self.mode == "edit":
            mid_x = self.settings.get(f"{prefix}cx", self.settings.get(f"{prefix}x", 100) + self.w // 2)
            mid_y = self.settings.get(f"{prefix}cy", self.settings.get(f"{prefix}y", 100) + self.h // 2)
            px = mid_x - self.w // 2
            py = mid_y - self.h // 2
        else:
            px = self.settings.get(f"{prefix}x", 100)
            py = self.settings.get(f"{prefix}y", 100)
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            px = max(0, min(int(px), max(0, sw - self.w)))
            py = max(0, min(int(py), max(0, sh - self.h)))
        
        self.root.geometry(f"{self.w}x{self.h}+{px}+{py}")
        self.root.attributes("-alpha", 0.0)
        if self.mode == "norm":
            self.root.aspect(1, 1, 1, 1)
            self.root.minsize(1, 1)
        elif self.mode == "edit":
            self.root.aspect(1, 1, 100, 1)
            self.root.minsize(500, 500 + self.get_edit_extra_height())
        if not hasattr(self, '_canvas_cfg_bound'):
            self.canvas.bind("<Configure>", self._on_canvas_resize, "+")
            self._canvas_cfg_bound = True
        self.map_renderer.show_main_splash()
        self.root.attributes("-alpha", self.alpha)
        self.refresh_mode_indicator()

    def _on_canvas_resize(self, event=None):
        if self.active_view != "maps":
            return
        if getattr(self, '_redrawing', False):
            return
        if self.mode == "norm":
            self.root.attributes("-alpha", 0.0)
        if hasattr(self, '_rsz_timer'):
            self.root.after_cancel(self._rsz_timer)
        self._rsz_timer = self.root.after(200, self._do_canvas_redraw)

    def _do_canvas_redraw(self):
        if getattr(self, '_redrawing', False):
            return
        self._redrawing = True
        if hasattr(self, '_rsz_timer'):
            self.root.after_cancel(self._rsz_timer)
        try:
            if self.mode == "norm":
                w = self.root.winfo_width()
                target_h = w + 18
                if abs(self.root.winfo_height() - target_h) > 1:
                    self.root.geometry(f"{w}x{int(target_h)}")
                    self.root.update_idletasks()
            self.root.update_idletasks()
            self.map_renderer.show_main_splash()
            self.root.attributes("-alpha", self.alpha)
            self._sync_po_pos()
        finally:
            self._redrawing = False

    def refresh_mode_indicator(self):
        fmt_enabled = self.win_mgr.format_mode_enabled
        fmt_text = "ON" if fmt_enabled else "OFF"
        text = f"[{self.t('ui', 'format_label')}] {fmt_text}"
        fg = "cyan" if self.mode == "edit" else "#bbbbbb"
        if hasattr(self, "status_label"):
            self.status_label.config(text=text, fg=fg)
        if hasattr(self, "battle_status_label"):
            self.battle_status_label.config(text=text, fg=fg)
        if hasattr(self, "btn_format_lock"):
            self.btn_format_lock.config(
                text=chr(0xF09C) if fmt_enabled else chr(0xF023),
                fg="#ffaa00" if fmt_enabled else "#bbbbbb"
            )

    def toggle_formatting_mode(self):
        """F8: вмикає/вимикає тільки режим форматування (без перемикання edit/norm)."""
        if self.dialog_open:
            return
        now = time.time()
        if now - self._last_mode_hotkey_ts < 0.2:
            return
        self._last_mode_hotkey_ts = now

        new_state = not self.win_mgr.format_mode_enabled
        self.win_mgr.set_format_mode(new_state)

        if new_state:
            self.win_mgr.set_clickthrough(False)
            self.root.lift()
            self.root.focus_force()
        else:
            if self.mode == "norm":
                self.win_mgr.set_clickthrough(True)
                self.win_mgr.focus_game_window()
        self.refresh_mode_indicator()
        if self.active_view == "maps" and hasattr(self, '_po_win') and self._po_win.winfo_exists():
            self._sync_po_pos()
            if self._po_win.state() != "withdrawn":
                self._po_win.lift()

    def toggle_visibility(self):
        """Приховати/Показати вікно (F10) — згортання в системний трей"""
        if self.root.state() == "withdrawn":
            self._restore_from_tray()
        else:
            self._minimize_to_tray()

    def _minimize_to_tray(self):
        """Згорнути програму в системний трей"""
        self._hidden_by_f10 = True
        self._stop_group_sync()
        if hasattr(self, '_po_win') and self._po_win.winfo_exists() and self._po_win.state() != "withdrawn":
            self._po_win.withdraw()
        if hasattr(self, 'stats_ai_module'):
            self.stats_ai_module.stop_browser()
        self.save_settings()
        if hasattr(self, 'drawing_palette') and self.drawing_palette.state() != 'withdrawn':
            self.drawing_palette._close()
        if not self._tray_icon:
            self._tray_icon = tray_icon.TrayIcon(
                self.root,
                on_click=self._on_tray_click
            )
        self.root.withdraw()

    def _restore_from_tray(self):
        """Відновити програму з системного трею"""
        if self._tray_icon:
            self._tray_icon.remove()
            self._tray_icon = None
        self._hidden_by_f10 = False
        if self.active_view == "maps" and self.active_group_id != firebase_groups.PUBLIC_GROUP_ID:
            self._start_group_sync()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self.active_view == "maps" and hasattr(self, '_po_win') and self._po_win.winfo_exists():
            self._po_win.deiconify()
            self._sync_po_pos()
            self._po_win.lift()

    def _on_tray_click(self):
        """Колбек при кліку на іконку в треї"""
        self._restore_from_tray()

    def _ensure_edit_focus(self):
        if not self.edit_focus_lock or self.mode != "edit" or self.root.state() == "withdrawn":
            return
        try:
            self.root.lift()
            self.root.focus_force()
            self.root.focus_set()
        except Exception:
            pass
        self.root.after(250, self._ensure_edit_focus)

    def toggle_editor_backspace(self):
        """Чітке перемикання режиму для бою: Tilde."""
        if self.dialog_open:
            return
        now = time.time()
        if now - self._last_mode_hotkey_ts < 0.2:
            return
        self._last_mode_hotkey_ts = now

        going_to_edit = self.mode != "edit"
        self.toggle_editor()

        if going_to_edit:
            self.edit_focus_lock = True
            self.root.after(10, self._ensure_edit_focus)
        else:
            self.edit_focus_lock = False
            self.win_mgr.focus_game_window()

    def on_map_select(self, event=None):
        self.root.focus_set()
        selected_ua = self.map_var.get()
        self.current_map_eng = self.map_mgr.get_eng_map_name(selected_ua)
        if hasattr(self, 'painter'):
            self.painter._creation_history.clear()
            self.painter._editing_idx = -1
        if hasattr(self, 'drawing_palette'):
            self.drawing_palette.exit_edit_mode()
        self.map_renderer.show_main_splash()
        if self.active_view == "maps" and hasattr(self, '_po_win') and self._po_win.winfo_exists() and not self._hidden_by_f10:
            if self._po_win.state() == "withdrawn":
                self._po_win.deiconify()
                self._sync_po_pos()
            else:
                self._po_win.lift()
        self.painter.redraw()

    def _combo_postcommand(self):
        if hasattr(self, '_po_win') and self._po_win.winfo_exists() and self._po_win.state() != "withdrawn":
            self._po_win.withdraw()
            self.root.update()
        self.root.after(100, self._poll_dropdown_closed)

    def _poll_dropdown_closed(self):
        if not hasattr(self, '_po_win') or not self._po_win.winfo_exists():
            return
        if self._po_win.state() != "withdrawn":
            return
        lb = self.map_selector._w + '.popdown.f.l'
        mapped = self.root.tk.eval('winfo ismapped ' + lb) == '1'
        if mapped:
            self.root.after(100, self._poll_dropdown_closed)
            return
        self._restore_overlay_state()

    def _restore_overlay_state(self):
        if self._hidden_by_f10:
            return
        if not hasattr(self, '_po_win') or not self._po_win.winfo_exists():
            return
        if self._po_win.state() != "withdrawn":
            return
        self.root.update_idletasks()
        self._po_win.deiconify()
        self._sync_po_pos()
        self._po_win.lift()

    def _handle_ctrl_up(self):
        import time
        now = time.time()
        if hasattr(self, '_last_ctrl_up_time') and now - self._last_ctrl_up_time < 0.15:
            return
        self._last_ctrl_up_time = now
        if hasattr(self, 'drawing_palette') and self.drawing_palette.state() != 'withdrawn' and self.drawing_palette.is_in_edit_mode():
            self.painter.resize_selected(1)
        else:
            self.win_mgr.resize_up_hotkey()

    def _handle_ctrl_down(self):
        import time
        now = time.time()
        if hasattr(self, '_last_ctrl_down_time') and now - self._last_ctrl_down_time < 0.15:
            return
        self._last_ctrl_down_time = now
        if hasattr(self, 'drawing_palette') and self.drawing_palette.state() != 'withdrawn' and self.drawing_palette.is_in_edit_mode():
            self.painter.resize_selected(-1)
        else:
            self.win_mgr.resize_down_hotkey()

    def set_painter_tool(self, tool):
        if hasattr(self, 'drawing_palette'):
            self.drawing_palette.exit_edit_mode()

    def toggle_palette(self):
        if self.active_view != "maps":
            return
        if self.drawing_palette.state() != 'withdrawn':
            self.drawing_palette._close()
            self.draw_btn.config(bg="#444", fg="gray")
        else:
            self.drawing_palette.show()
            self.draw_btn.config(bg="#ffaa00", fg="black")

    def export_current_tactic(self):
        if not self.current_map_eng: return
        tactics_manager.export_tactic(
            self.root, 
            self.current_map_eng, 
            self.translate_map_name(self.current_map_eng), 
            self.painter.drawings
        )

    def import_external_tactic(self):
        if not self.current_map_eng: return
        def on_success():
            self.painter.save_drawings()
            self.painter.redraw()
        
        tactics_manager.import_tactic(
            self.root,
            self.current_map_eng,
            self.translate_map_name(self.current_map_eng),
            self.painter.drawings,
            on_success
        )

    def export_all_tactics(self):
        tactics_manager.export_all_tactics(self.root, self.painter.drawings)

    def import_all_tactics(self):
        def on_success():
            self.painter.save_drawings()
            self.painter.redraw()
        tactics_manager.import_all_tactics(
            self.root, self.painter.drawings, on_success
        )

    def import_tactic_unified(self):
        def on_success():
            self.painter.save_drawings()
            self.painter.redraw()
        tactics_manager.import_unified(
            self.root, self.current_map_eng,
            self.translate_map_name(self.current_map_eng) if self.current_map_eng else "",
            self.painter.drawings, on_success
        )

    def on_minimap_appeared(self, map_id, mode):
        pass  # Silent

    def on_vehicle_detected(self, compact_descr):
        if not self.auto_sync_var.get():
            return
        if not self.auto_vehicle_filter_var.get():
            return
        info = self.compact_descr_map.get(compact_descr)
        if not info:
            return

        cls = info["class"]
        cls_map = {"LT": "LT", "MT": "MT", "HT": "HT", "TD": "TD", "SPG": "SPG"}
        ui_cls = cls_map.get(cls)
        if not ui_cls:
            return

        def apply_class_filter():
            for c, var in self.selected_classes.items():
                var.set(c == ui_cls)

        self.root.after(0, apply_class_filter)

    def on_battle_countdown_started(self, map_id, arena_type):
        print(f"[BATTLE] countdown_started: map={map_id}, arena_type={arena_type}, auto_battle={self.auto_battle_var.get()}, mode={self.mode}")
        if not self.auto_battle_var.get():
            return
        if self.mode != "norm":
            self.root.after(100, self.toggle_editor)

    def on_battle_detected(self, map_id, mode):
        self.last_battle_map = map_id
        self.last_battle_mode = mode
        self.last_battle_map_mode = self.map_mode
        print(f"[BATTLE] on_battle_detected: map={map_id}, mode={mode}, auto_sync={self.auto_sync_var.get()}, auto_battle={self.auto_battle_var.get()}")
        
        if not self.auto_sync_var.get():
            return
        
        mode_map = {
            "ctf": "Standard",
            "domination": "Encounter",
            "assault": "Assault",
            "comp7": "Onslaught"
        }
        ui_mode = mode_map.get(mode, "Standard")
        self.root.after(0, lambda: self.safe_battle_sync(map_id, ui_mode))

    def on_battle_ended(self):
        self.save_settings()
        print(f"[BATTLE] battle_ended: last_map={self.last_battle_map}, auto_battle={self.auto_battle_var.get()}")
        
        if not self.last_battle_map or not self.auto_battle_var.get():
            return
        
        self.root.after(200, lambda: self._return_to_editor_with_map(self.last_battle_map, self.last_battle_mode, self.last_battle_map_mode))
    
    def _return_to_editor_with_map(self, map_id, mode, map_source_mode=2):
        if self.mode != "edit":
            self.toggle_editor()
            self.root.after(100, lambda: self._sync_battle_map_after_return(map_id, mode, map_source_mode))
    
    def _sync_battle_map_after_return(self, map_id, mode, map_source_mode=2):
        """Синхронізуємо фільтри після повернення до редагування"""
        target_map_mode = map_source_mode if map_source_mode in (1, 2) else 2
        self.switch_to_maps(target_map_mode)
        
        mode_map = {
            "ctf": "Standard",
            "domination": "Encounter",
            "assault": "Assault",
            "comp7": "Onslaught"
        }
        ui_mode = mode_map.get(mode, "Standard")
        self.safe_battle_sync(map_id, ui_mode)

    def safe_battle_sync(self, map_id, ui_mode):
        print(f"[BATTLE] safe_battle_sync: map={map_id}, ui_mode={ui_mode}, log_path={self.settings.get('log_path','')}")
        if not self.settings.get("log_path", ""):
            print(f"[BATTLE] EARLY EXIT: log_path empty")
            return

        self.switch_to_maps(2)

        if self.auto_mode_filter_var.get():
            self.selected_battle_mode.set(ui_mode)
        else:
            print(f"[SYNC] Авто-вибір режиму бою вимкнено (auto_mode_filter={self.auto_mode_filter_var.get()})")
        
        target_name = self.translate_map_name(map_id)
        
        tmaps = self.map_selector.cget("values")
        
        if target_name in tmaps:
            self.map_var.set(target_name)
            self.on_map_select()
            return
            
        for t in tmaps:
            if t.lower() == target_name.lower():
                self.map_var.set(t)
                self.on_map_select()
                return
            
        for t in tmaps:
            if target_name in t or t.lower() in target_name.lower():
                self.map_var.set(t)
                self.on_map_select()
                return

    def setup_ui(self):
        pass




    def switch_to_maps(self, mode=1):
        self.ui_mgr.show_view("maps", mode=mode)

    def switch_to_stats(self):
        self.ui_mgr.show_view("stats")

    def switch_to_ai_stats(self):
        self.ui_mgr.show_view("ai_stats")

    def quit_app(self):
        self._sync_running = False
        if self._tray_icon:
            self._tray_icon.remove()
            self._tray_icon = None
        if hasattr(self, 'stats_ai_module'):
            self.stats_ai_module.stop_browser()
        self._save_group_schemes_to_cache()
        self.save_settings()
        firebase_identity._save(firebase_identity._load())
        firebase_reporter.try_flush_service_messages(self)
        keyboard.unhook_all()
        self.root.destroy()
        sys.exit(0)

    def _check_for_app_updates(self):
        def _on_result(latest):
            if not latest:
                return
            latest_ver = latest.get("version", "")
            current_ver = config.load_version()
            if not firebase_reporter.compare_versions(current_ver, latest_ver):
                return
            dl = latest.get("download_url", "")
            msg = self.t('ui', 'status_update_available').format(latest=latest_ver, current=current_ver)
            print(msg)
            def _show():
                if self.auto_update_var.get():
                    self._show_update_dialog(latest_ver, current_ver, dl)
            self.root.after(0, _show)
        firebase_reporter.check_for_updates(on_done=_on_result)

    def _show_update_dialog(self, latest_ver, current_ver, download_url):
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t('ui', 'dialog_update_title'))
        dlg.configure(bg="#222")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()

        cx = self.root.winfo_x() + self.root.winfo_width() // 2 - 150
        cy = self.root.winfo_y() + self.root.winfo_height() // 2 - 80
        dlg.geometry(f"300x180+{cx}+{cy}")

        tk.Label(dlg, text=self.t('ui', 'dialog_update_available'), font=("Arial", 12, "bold"),
                 bg="#222", fg="#ffaa00").pack(pady=(15, 5))
        tk.Label(dlg, text=f"SM WoT Assistant v{latest_ver}",
                 font=("Arial", 11), bg="#222", fg="#ff4500").pack()
        tk.Label(dlg, text=self.t('ui', 'dialog_update_ready').format(current=current_ver),
                 font=("Arial", 9), bg="#222", fg="#aaa", justify="center").pack(pady=(4, 12))

        bf = tk.Frame(dlg, bg="#222")
        bf.pack()

        def do_update():
            dlg.destroy()
            if download_url:
                self._download_and_install(download_url, latest_ver)

        def do_later():
            dlg.destroy()

        tk.Button(bf, text=self.t('ui', 'btn_update_now'), bg="#335533", fg="#99cc99", bd=0,
                  font=("Arial", 10, "bold"), padx=12, pady=6,
                  command=do_update).pack(side="left", padx=8)
        tk.Button(bf, text=self.t('ui', 'btn_later'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 10), padx=12, pady=6,
                  command=do_later).pack(side="left", padx=8)

        self.root.wait_window(dlg)

    def _download_and_install(self, url, latest_ver):
        pw = tk.Toplevel(self.root)
        pw.title(self.t('ui', 'dialog_update_title'))
        pw.configure(bg="#222")
        pw.resizable(False, False)
        pw.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(pw)

        sw, sh = 380, 160
        cx = self.root.winfo_screenwidth() // 2 - sw // 2
        cy = self.root.winfo_screenheight() // 2 - sh // 2
        pw.geometry(f"{sw}x{sh}+{cx}+{cy}")

        status_var = tk.StringVar(value=self.t('ui', 'dialog_update_downloading').format(version=latest_ver))
        tk.Label(pw, textvariable=status_var, font=("Arial", 10, "bold"),
                 bg="#222", fg="#ffaa00").pack(pady=(20, 8))

        pf = tk.Frame(pw, bg="#222")
        pf.pack(fill="x", padx=40)

        pbar_canvas = tk.Canvas(pf, height=16, bg="#333", highlightthickness=0)
        pbar_canvas.pack(fill="x")

        pct_var = tk.StringVar(value="0%")
        tk.Label(pw, textvariable=pct_var, font=("Arial", 9, "bold"),
                 bg="#222", fg="#ddd").pack(pady=(4, 0))

        close_btn = tk.Button(pw, text="Close", bg="#444", fg="#aaa", bd=0,
                              font=("Arial", 9), padx=14, pady=3,
                              command=lambda: pw.destroy())

        error_var = tk.StringVar()
        err_label = tk.Label(pw, textvariable=error_var, font=("Arial", 8),
                             bg="#222", fg="#ff4444", wraplength=sw - 40)

        def _run():
            tmp = None
            try:
                tmp = os.path.join(tempfile.gettempdir(), "SM_WoT_Assistant_Setup.exe")
                print(f"[UPDATE] Downloading: {url}")

                r = requests.get(url, stream=True, headers=config.HEADERS, timeout=120)
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                last_pct = -1
                pb_w = 340

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
                                _pct = pct
                                pw.after(0, lambda p=_pct: (
                                    pbar_canvas.delete("bar"),
                                    pbar_canvas.create_rectangle(0, 0, p * pb_w // 100, 16, fill="#ff4500", outline="", tags="bar"),
                                    pct_var.set(f"{p}%")
                                ))

                print(f"[UPDATE] Downloaded: {downloaded / (1024*1024):.0f} MB")

                install_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "SM WoT Assistant")
                install_exe = os.path.join(install_dir, f"SM WoT Assistant v{latest_ver}.exe")

                pw.after(0, lambda: (
                    pbar_canvas.delete("bar"),
                    pbar_canvas.create_rectangle(0, 0, pb_w, 16, fill="#22cc44", outline="", tags="bar"),
                    pct_var.set("100%"),
                    status_var.set(self.t('ui', 'dialog_update_installing'))
                ))

                result = subprocess.run([tmp, "/S", "/NCRC"], creationflags=0x08000000)
                if result.returncode != 0:
                    raise RuntimeError(f"Installer exit code {result.returncode}")

                for f in os.listdir(install_dir):
                    if f.startswith("SM WoT Assistant") and f.endswith(".exe"):
                        fp = os.path.join(install_dir, f)
                        try:
                            if os.path.abspath(fp) != os.path.abspath(sys.executable):
                                os.remove(fp)
                        except Exception:
                            pass

                if not os.path.exists(install_exe):
                    raise RuntimeError(f"EXE not found: {install_exe}")

                pw.after(0, lambda: status_var.set(f"Updated to v{latest_ver}"))
                def _finish():
                    status_var.set(self.t('ui', 'dialog_update_starting'))
                    try:
                        ctypes.windll.kernel32.CloseHandle(self._update_mutex)
                    except Exception:
                        pass
                    subprocess.Popen([install_exe], creationflags=0x08000000)
                    pw.after(200, lambda: (pw.destroy(), self.save_settings(), sys.exit(0)))
                pw.after(3000, _finish)

            except Exception as e:
                print(f"[UPDATE] Error: {e}")
                def _err():
                    status_var.set(self.t('ui', 'status_update_error').format(error=str(e)[:50]))
                    pct_var.set("")
                    error_var.set(str(e)[:120])
                    err_label.pack(pady=(0, 4))
                    close_btn.pack(pady=(0, 12))
                pw.after(0, _err)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _show_splash_update(self, latest):
        latest_ver = latest.get("version", "")
        current_ver = config.load_version()
        dl_url = latest.get("download_url", "")

        if not hasattr(self, 'splash') or not self.splash.winfo_exists():
            self._start_startup_checks_continue()
            return

        self._startup_target_percent = 100
        self._startup_display_percent = 100
        sw = int(self.splash_canvas["width"])
        sh = int(self.splash_canvas["height"])

        self.splash_canvas.itemconfigure(self.splash_percent_text, text="")
        self.splash_canvas.coords(self.pbar, 0, 0, 0, 0)

        self.splash_canvas.itemconfigure(self.splash_status_text,
            text=f"New version v{latest_ver} available!",
            fill="#ffaa00", font=("Arial", 13, "bold"))

        self._splash_ver_info = self.splash_canvas.create_text(
            sw // 2, sh - 92,
            text=f"You have v{current_ver}",
            fill="#aaa", font=("Arial", 9))

        btn_w, btn_h = 140, 36
        lx = sw // 2 - btn_w - 14
        rx = sw // 2 + 14
        by = sh - 68

        self._splash_update_rect = self.splash_canvas.create_rectangle(
            lx, by, lx + btn_w, by + btn_h,
            fill="#335533", outline="#66aa66", tags="splash_btn")
        self._splash_update_txt = self.splash_canvas.create_text(
            lx + btn_w // 2, by + btn_h // 2,
            text=self.t('ui', 'btn_update_now').upper(),
            fill="#99cc99", font=("Arial", 10, "bold"), tags="splash_btn")

        self._splash_later_rect = self.splash_canvas.create_rectangle(
            rx, by, rx + btn_w, by + btn_h,
            fill="#444", outline="#666", tags="splash_btn")
        self._splash_later_txt = self.splash_canvas.create_text(
            rx + btn_w // 2, by + btn_h // 2,
            text=self.t('ui', 'btn_later').upper(),
            fill="#aaa", font=("Arial", 10), tags="splash_btn")

        self._splash_latest = latest
        self.splash_canvas.tag_bind("splash_btn", "<Button-1>",
            lambda e: self._on_splash_btn_click(e))
        self.splash_canvas.tag_bind("splash_btn", "<Enter>",
            lambda e: self.splash.config(cursor="hand2"))
        self.splash_canvas.tag_bind("splash_btn", "<Leave>",
            lambda e: self.splash.config(cursor=""))

    def _on_splash_btn_click(self, event):
        sw = int(self.splash_canvas["width"])
        bx = sw // 2 - 140 - 14
        if bx <= event.x <= bx + 140:
            self._download_on_splash(self._splash_latest)
        else:
            self._splash_proceed_to_main()

    def _splash_proceed_to_main(self):
        self.splash_canvas.delete("splash_btn")
        if hasattr(self, '_splash_ver_info'):
            self.splash_canvas.delete(self._splash_ver_info)
        self.splash_canvas.itemconfigure(self.splash_status_text,
            text=self.t('ui', 'checking_updates'), fill="#bbbbbb", font=("Arial", 9))
        self.splash_canvas.itemconfigure(self.splash_percent_text, text="0%")
        sw = int(self.splash_canvas["width"])
        sh = int(self.splash_canvas["height"])
        self.splash_canvas.coords(self.pbar, 0, sh - 8, 0, sh)
        self._startup_target_percent = 0
        self._startup_display_percent = 0
        self._animate_startup_progress()
        self._start_startup_checks_continue()

    def _download_on_splash(self, latest):
        self.splash_canvas.delete("splash_btn")
        if hasattr(self, '_splash_ver_info'):
            self.splash_canvas.delete(self._splash_ver_info)

        latest_ver = latest.get("version", "")
        dl_url = latest.get("download_url", "")

        sw = int(self.splash_canvas["width"])
        sh = int(self.splash_canvas["height"])

        self.splash_canvas.itemconfigure(self.splash_status_text,
            text=self.t('ui', 'dialog_update_downloading').format(version=latest_ver),
            fill="#ffaa00", font=("Arial", 11, "bold"))

        self.splash_canvas.itemconfigure(self.splash_percent_text, text="0%")
        self.splash_canvas.coords(self.pbar, 0, sh - 8, 0, sh)
        self.splash_canvas.itemconfigure(self.pbar, fill="#ff4500")

        self._splash_dl_url = dl_url
        self._splash_dl_latest = latest
        t = threading.Thread(target=self._splash_download_thread, daemon=True)
        t.start()

    def _splash_download_thread(self):
        url = self._splash_dl_url
        latest = self._splash_dl_latest
        latest_ver = latest.get("version", "")
        tmp = None
        try:
            if not hasattr(self, 'splash') or not self.splash.winfo_exists():
                return
            tmp = os.path.join(tempfile.gettempdir(), "SM_WoT_Assistant_Setup.exe")
            print(f"[UPDATE] Downloading: {url}")

            r = requests.get(url, stream=True, headers=config.HEADERS, timeout=120)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            last_pct = -1
            sw = int(self.splash_canvas["width"])
            sh = int(self.splash_canvas["height"])

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
                            _pct = pct
                            self.root.after(0, lambda p=_pct: self._splash_update_pbar(p, sh, sw))

            print(f"[UPDATE] Downloaded: {downloaded / (1024 * 1024):.0f} MB")

            install_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "SM WoT Assistant")
            install_exe = os.path.join(install_dir, f"SM WoT Assistant v{latest_ver}.exe")

            self.root.after(0, lambda: self._splash_status_safe(
                self.t('ui', 'dialog_update_installing'), "#ffaa00", ("Arial", 11, "bold")))

            result = subprocess.run([tmp, "/S", "/NCRC"], creationflags=0x08000000)
            if result.returncode != 0:
                raise RuntimeError(f"Installer exit code {result.returncode}")

            for f in os.listdir(install_dir):
                if f.startswith("SM WoT Assistant") and f.endswith(".exe"):
                    fp = os.path.join(install_dir, f)
                    try:
                        if os.path.abspath(fp) != os.path.abspath(sys.executable):
                            os.remove(fp)
                    except Exception:
                        pass

            if not os.path.exists(install_exe):
                raise RuntimeError(f"EXE not found: {install_exe}")

            self.root.after(0, lambda: self._splash_status_safe(
                f"Updated to v{latest_ver}", "#22cc44", ("Arial", 13, "bold")))
            def _finish():
                self._splash_status_safe(
                    self.t('ui', 'dialog_update_starting'), "#22cc44", ("Arial", 12, "bold"))
                try:
                    ctypes.windll.kernel32.CloseHandle(self._update_mutex)
                except Exception:
                    pass
                subprocess.Popen([install_exe], creationflags=0x08000000)
                self.root.after(200, self._quit_app_for_update)
            self.root.after(3000, _finish)

        except Exception as e:
            print(f"[UPDATE] Error: {e}")
            self.root.after(0, lambda: (
                self._splash_status_safe(
                    self.t('ui', 'status_update_error').format(error=str(e)[:50]),
                    "#ff4444", ("Arial", 10, "bold")),
                self._splash_pct_safe("")
            ))

    def _quit_app_for_update(self):
        try:
            ctypes.windll.kernel32.CloseHandle(self._update_mutex)
        except Exception:
            pass
        self.save_settings()
        sys.exit(0)

    def _splash_update_pbar(self, pct, sh, sw):
        try:
            if not hasattr(self, 'splash') or not self.splash.winfo_exists():
                return
            self.splash_canvas.coords(self.pbar, 0, sh - 8, pct * sw // 100, sh)
            self.splash_canvas.itemconfigure(self.splash_percent_text, text=f"{pct}%")
        except Exception:
            pass

    def _splash_dl_complete(self, sw, sh):
        try:
            if not hasattr(self, 'splash') or not self.splash.winfo_exists():
                return
            self.splash_canvas.coords(self.pbar, 0, sh - 8, sw, sh)
            self.splash_canvas.itemconfigure(self.pbar, fill="#22cc44")
            self.splash_canvas.itemconfigure(self.splash_percent_text, text="100%")
            self.splash_canvas.itemconfigure(self.splash_status_text,
                text=self.t('ui', 'dialog_update_installing'))
            self._dot_anim_step = 0
            self._dot_anim_active = True
            self._splash_animate_dots()
        except Exception:
            pass

    def _splash_animate_dots(self):
        try:
            if not self._dot_anim_active:
                return
            if not hasattr(self, 'splash') or not self.splash.winfo_exists():
                self._dot_anim_active = False
                return
            dots = [".  ", ".. ", "...", "   "]
            self._dot_anim_step = (self._dot_anim_step + 1) % len(dots)
            base = self.t('ui', 'dialog_update_installing')
            self.splash_canvas.itemconfigure(self.splash_status_text,
                text=base + dots[self._dot_anim_step])
            self.root.after(500, self._splash_animate_dots)
        except Exception:
            self._dot_anim_active = False

    def _splash_status_safe(self, text, fill="#ffaa00", font=("Arial", 11, "bold")):
        try:
            if not hasattr(self, 'splash') or not self.splash.winfo_exists():
                return
            self.splash_canvas.itemconfigure(self.splash_status_text,
                text=text, fill=fill, font=font)
        except Exception:
            pass

    def _splash_pct_safe(self, text):
        try:
            if not hasattr(self, 'splash') or not self.splash.winfo_exists():
                return
            self.splash_canvas.itemconfigure(self.splash_percent_text, text=text)
        except Exception:
            pass

    def bind_events(self):
        keyboard.add_hotkey('F1', lambda: self.safe_execute(self.help_manager.toggle_overlay))
        keyboard.add_hotkey('F10', lambda: self.safe_execute(self.toggle_visibility))  # F10: Показати/Приховати вікно
        keyboard.add_hotkey('tab', lambda: self.safe_execute(self.toggle_editor), suppress=False)
        try:
            keyboard.add_hotkey('f8', lambda: self.safe_execute(self.toggle_formatting_mode), suppress=False)
        except Exception as e:
            keyboard.add_hotkey('ctrl+e', lambda: self.safe_execute(self.toggle_formatting_mode), suppress=False)
        keyboard.add_hotkey('ctrl+up', lambda: self.safe_execute(self._handle_ctrl_up), suppress=False)
        keyboard.add_hotkey('ctrl+down', lambda: self.safe_execute(self._handle_ctrl_down), suppress=False)
        keyboard.add_hotkey('ctrl+right', lambda: self.safe_execute(self.win_mgr.alpha_up_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+left', lambda: self.safe_execute(self.win_mgr.alpha_down_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+shift+up', lambda: self.safe_execute(self.win_mgr.contrast_up_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+shift+down', lambda: self.safe_execute(self.win_mgr.contrast_down_hotkey), suppress=False)
        # Без Ctrl — працюють тільки коли format_mode_enabled (замок відчинено)
        keyboard.add_hotkey('up', lambda: self.safe_execute(self._handle_ctrl_up), suppress=False)
        keyboard.add_hotkey('down', lambda: self.safe_execute(self._handle_ctrl_down), suppress=False)
        keyboard.add_hotkey('left', lambda: self.safe_execute(self.win_mgr.alpha_down_hotkey), suppress=False)
        keyboard.add_hotkey('right', lambda: self.safe_execute(self.win_mgr.alpha_up_hotkey), suppress=False)
        keyboard.add_hotkey('shift+up', lambda: self.safe_execute(self.win_mgr.contrast_up_hotkey), suppress=False)
        keyboard.add_hotkey('shift+down', lambda: self.safe_execute(self.win_mgr.contrast_down_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+z', lambda: self.safe_execute(self.painter.ctrl_z_undo), suppress=True)
        self.root.bind_all("<Control-Up>", lambda e: self.safe_execute(self._handle_ctrl_up))
        self.root.bind_all("<Control-Down>", lambda e: self.safe_execute(self._handle_ctrl_down))
        self.win_mgr.bind_controls(self.top_bar, self.canvas)

    def load_logo(self):
        try:
            img = Image.open(config.LOGO_FILE)
            self.logo_splash = ImageTk.PhotoImage(ImageOps.contain(img, (200, 200), Image.Resampling.LANCZOS))
            self.logo_image_object = img
        except: self.logo_splash = self.logo_image_object = None

    def _auto_detect_log_path(self):
        """Автоматичне визначення шляху до логу."""
        detected = None
        common_logs = [
            os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Wargaming.net", "World of Tanks", "logs", "python.log"),
            os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Wargaming.net", "World of Tanks EU", "logs", "python.log"),
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Wargaming.net", "World of Tanks", "logs", "python.log"),
            os.path.join("C:\\", "Games", "World_of_Tanks", "logs", "python.log"),
            os.path.join("D:\\", "Games", "World_of_Tanks", "logs", "python.log"),
            os.path.join("C:\\", "Games", "World_of_Tanks_EU", "python.log"),
            os.path.join("C:\\", "Games", "World_of_Tanks_EU", "logs", "python.log"),
            os.path.join("D:\\", "Games", "World_of_Tanks_EU", "python.log"),
            os.path.join("D:\\", "Games", "World_of_Tanks_EU", "logs", "python.log"),
            os.path.join(os.getcwd(), "logs", "python.log"),
        ]
        # Також спробуємо вивести з wot_path
        wot_path = self.settings.get("wot_path", "")
        if wot_path:
            for suffix in ["python.log", os.path.join("logs", "python.log")]:
                p = os.path.normpath(os.path.join(wot_path, suffix))
                if p not in common_logs:
                    common_logs.append(p)
        for p in common_logs:
            if os.path.exists(p):
                detected = p
                break
        if detected:
            self.settings["log_path"] = detected
            self.save_settings()
            print(f"[INIT] Автоматично визначено log_path: {detected}")

    def _on_startup_progress(self, percent, text):
        self.update_startup_progress(percent, text)

    def _on_startup_ready(self):
        """Startup data checks complete → launch AI → then close splash."""
        self._startup_ready_at = time.time()
        if hasattr(self, 'stats_ai_module') and not self.stats_ai_module.needs_ai_refresh():
            print("[INIT] Кеш свіжий, AI не потрібен")
            try:
                sw = int(self.splash_canvas["width"])
                sh = int(self.splash_canvas["height"])
                self.splash_canvas.coords(self.pbar, 0, sh - 8, sw, sh)
                self.splash_canvas.itemconfigure(self.splash_percent_text, text="100%")
            except Exception:
                pass
            self._startup_display_percent = 100
            self._startup_target_percent = 100
            self.root.after(200, self.finish_startup_splash)
            return
        self._startup_ai_base = max(30, getattr(self, '_startup_display_percent', 30))
        self._startup_ai_base = min(self._startup_ai_base, 80)
        self.update_startup_progress(self._startup_ai_base, self.t('ui', 'data_updating'))
        self.root.after(100, self._start_ai_phase)

    def _start_ai_phase(self):
        if hasattr(self, 'stats_ai_module'):
            self._startup_ai_base = max(30, getattr(self, '_startup_display_percent', 30))
            self._startup_ai_base = min(self._startup_ai_base, 80)
            self._startup_ai_start = time.time()
            self.stats_ai_module.launch_ai_browser(
                progress_cb=self._on_ai_progress,
                done_cb=self._on_ai_ready,
            )
            self._ai_creep_id = self.root.after(1000, self._ai_progress_creep)
            self._ai_timeout_id = self.root.after(60000, self._ai_safety_timeout)
        else:
            self.finish_startup_splash()

    def _ai_progress_creep(self):
        if not hasattr(self, '_startup_ai_start'):
            return
        elapsed = time.time() - self._startup_ai_start
        base = getattr(self, '_startup_ai_base', 40)
        if elapsed < 20:
            pct = base + (93 - base) * elapsed / 20
        else:
            pct = 93 + 6 * min(elapsed - 20, 30) / 30
        pct = min(99, pct)
        self._startup_target_percent = int(pct)
        try:
            self._startup_creep_active = True
            sw = int(self.splash_canvas["width"])
            sh = int(self.splash_canvas["height"])
            x2 = int((sw * pct) / 100)
            self.splash_canvas.coords(self.pbar, 0, sh - 8, x2, sh)
            self.splash_canvas.itemconfigure(
                self.splash_percent_text, text=f"{int(pct)}%"
            )
        except Exception:
            pass
        if pct < 100:
            self._ai_creep_id = self.root.after(100, self._ai_progress_creep)

    def _on_ai_progress(self, percent, text):
        self.root.after(0, lambda t=text: self.update_startup_progress(
            getattr(self, '_startup_target_percent', 40), t
        ))

    def _on_ai_ready(self):
        self.root.after(0, lambda: self.update_startup_progress(
            100, self.t('ui', 'ready')
        ))
        self.root.after(500, self._cancel_ai_timers)
        self.root.after(500, lambda: self.finish_startup_splash())

    def _cancel_ai_timers(self):
        self._startup_creep_active = False
        if hasattr(self, '_ai_creep_id') and self._ai_creep_id:
            try: self.root.after_cancel(self._ai_creep_id)
            except: pass
            self._ai_creep_id = None
        if hasattr(self, '_ai_timeout_id') and self._ai_timeout_id:
            try: self.root.after_cancel(self._ai_timeout_id)
            except: pass
            self._ai_timeout_id = None

    def _ai_safety_timeout(self):
        print("[AI Browser] SAFETY TIMEOUT — closing splash")
        self.root.after(0, self._cancel_ai_timers)
        self.root.after(0, self.finish_startup_splash)

    def update_startup_progress(self, percent, text=None):
        if not hasattr(self, "splash") or not self.splash or not self.splash.winfo_exists():
            return
        try:
            percent = max(0, min(100, int(percent)))
            self._startup_target_percent = percent
            self._startup_display_percent = percent
            if text:
                self._startup_status_text = text
                self.splash_canvas.itemconfigure(self.splash_status_text, text=text)
            self.splash_canvas.itemconfigure(
                self.splash_percent_text,
                text=f"{percent}%",
            )
            sw = int(self.splash_canvas["width"])
            sh = int(self.splash_canvas["height"])
            x2 = int((sw * percent) / 100)
            self.splash_canvas.coords(self.pbar, 0, sh - 8, x2, sh)
            self.root.update_idletasks()
        except Exception:
            pass

    def _animate_startup_progress(self):
        if not hasattr(self, "splash") or not self.splash or not self.splash.winfo_exists():
            return
        try:
            if not getattr(self, '_startup_creep_active', False):
                sw = int(self.splash_canvas["width"])
                sh = int(self.splash_canvas["height"])
                target = int(getattr(self, "_startup_target_percent", 0))
                current = int(getattr(self, "_startup_display_percent", 0))
                if current < target:
                    step = 2 if (target - current) > 8 else 1
                    current = min(target, current + step)
                    self._startup_display_percent = current
                    x2 = int((sw * current) / 100)
                    self.splash_canvas.coords(self.pbar, 0, sh - 8, x2, sh)
                    self.splash_canvas.itemconfigure(self.splash_percent_text, text=f"{current}%")
            self.root.after(45, self._animate_startup_progress)
        except Exception:
            pass

    def finish_startup_splash(self):
        """Знищує splash та показує головне вікно."""
        self._dot_anim_active = False
        shown_at = getattr(self, "_splash_shown_at", 0.0)
        elapsed_ms = int((time.time() - shown_at) * 1000) if shown_at else 9999
        min_visible_ms = 2000  # Принаймні 2 секунди
        if elapsed_ms < min_visible_ms:
            self.root.after(min_visible_ms - elapsed_ms, self.finish_startup_splash)
            return
        try:
            if hasattr(self, "splash"):
                if self.splash and self.splash.winfo_exists():
                    self.splash.destroy()
                if hasattr(self, "splash"):
                    try:
                        del self.splash
                    except Exception:
                        pass
        except Exception as e:
            print(f"[INIT] Помилка знищення splash: {e}")
        finally:
            if hasattr(self, "splash"):
                try:
                    del self.splash
                except Exception:
                    pass
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception as e:
            print(f"[INIT] Помилка показу головного вікна: {e}")

        # geometry after deiconify
        self.root.update_idletasks()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        self.root.geometry(f"{self.w}x{self.h}+{px}+{py}")
        self.root.update_idletasks()

        self.root.minsize(self.w, self.h)

        self.current_map_eng = None
        self.map_var.set("")
        self.map_renderer.show_main_splash()
        if hasattr(self, 'painter'):
            self.painter.canvas.delete("painter_obj")
        if hasattr(self, '_po_win') and self._po_win.winfo_exists() and self._po_win.state() != "withdrawn":
            self._po_win.withdraw()
        self._load_group_schemes_from_cache()
        self._startup_complete = True
        if self.active_view == "maps" and hasattr(self, '_po_win') and self._po_win.winfo_exists():
            self.root.after(100, self._finish_startup_overlay)

    def _finish_startup_overlay(self):
        if self.active_view != "maps" or self._hidden_by_f10:
            return
        if hasattr(self, '_po_win') and self._po_win.winfo_exists():
            self._po_win.deiconify()
            self._sync_po_pos()
            self.root.lower(self._po_win)

    def show_small_loading_splash(self):
        self.splash = tk.Toplevel(self.root)
        self._splash_shown_at = time.time()
        self._startup_target_percent = 0
        self._startup_display_percent = 0
        self._startup_ready_at = 0.0
        self._startup_status_text = self.t('ui', 'checking_updates')
        sw, sh = 450, 350
        if self._splash_geometry:
            self.splash.geometry(self._splash_geometry)
        else:
            self.splash.geometry(f"{sw}x{sh}+{int((self.root.winfo_screenwidth()/2)-(sw/2))}+{int((self.root.winfo_screenheight()/2)-(sh/2))}")
        self.splash.overrideredirect(True)
        self.splash.attributes("-topmost", True)
        self.splash.configure(bg="black")
        self.splash_canvas = tk.Canvas(self.splash, width=sw, height=sh, bg="black", highlightthickness=0)
        self.splash_canvas.pack()
        if self.logo_splash:
            self.splash_canvas.create_image(sw//2, sh//2 - 20, image=self.logo_splash)
        version = "v" + config.load_version()
        self.splash_canvas.create_text(sw//2, sh - 100, text=version, fill="white", font=("Verdana", 11))
        lang_text = self.t('ui', 'language_label').format(lang=self.lang.upper())
        self.splash_canvas.create_text(sw//2, sh - 87, text=lang_text, fill="#888888", font=("Arial", 9))
        self.splash_status_text = self.splash_canvas.create_text(
            sw//2,
            sh - 74,
            text=self.t('ui', 'checking_updates'),
            fill="#bbbbbb",
            font=("Arial", 9),
        )
        self.splash_percent_text = self.splash_canvas.create_text(
            sw - 34,
            sh - 20,
            text="0%",
            fill="#dddddd",
            font=("Arial", 9),
        )
        self.pbar = self.splash_canvas.create_rectangle(0, sh-10, 0, sh, fill="#ff4500", outline="")
        self.update_startup_progress(3, self.t('ui', 'preparing_check'))
        self._animate_startup_progress()
        self.splash.deiconify()
        self.splash.lift()
        self.splash.update_idletasks()

    def _startup_show_failsafe(self):
        try:
            if self.root.state() == "withdrawn":
                sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
                safe_w = max(320, min(int(self.w), max(320, sw - 40)))
                safe_h = max(240, min(int(self.h), max(240, sh - 40)))
                safe_x = max(0, (sw - safe_w) // 2)
                safe_y = max(0, (sh - safe_h) // 2)
                self.root.geometry(f"{safe_w}x{safe_h}+{safe_x}+{safe_y}")
                self.root.attributes("-alpha", max(0.1, min(float(self.alpha), 1.0)))
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                self.current_map_eng = None
                self.map_var.set("")
                self.map_renderer.show_main_splash()
                print("[INIT] Failsafe: головне вікно примусово показано")
        except Exception as e:
            print(f"[INIT] Failsafe error: {e}")

    # ─── Group cache methods ───

    def _load_group_schemes_from_cache(self):
        try:
            if not os.path.exists(config.GROUP_CACHE_FILE):
                return
            import json
            with open(config.GROUP_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if hasattr(self, 'painter') and self.painter:
                self.painter._group_schemes = data.get("schemes", {})
                self.painter._scheme_downloaded_at = data.get("downloaded_at", {})
                self.painter._hidden_download_schemes = set(data.get("hidden_schemes", []))
                print(f"[GROUPS] Завантажено {len(self.painter._group_schemes)} групових схем з кешу")
        except Exception as e:
            print(f"[GROUPS] Помилка завантаження кешу: {e}")

    def _save_group_schemes_to_cache(self):
        try:
            if not hasattr(self, 'painter') or not self.painter:
                return
            import json
            data = {
                "schemes": getattr(self.painter, '_group_schemes', {}),
                "downloaded_at": getattr(self.painter, '_scheme_downloaded_at', {}),
                "hidden_schemes": list(getattr(self.painter, '_hidden_download_schemes', set())),
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            os.makedirs(os.path.dirname(config.GROUP_CACHE_FILE), exist_ok=True)
            with open(config.GROUP_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GROUPS] Помилка збереження кешу: {e}")

    # ─── Group sync methods ───

    def _start_group_sync(self):
        if self._sync_running:
            return
        if self.active_group_id == firebase_groups.PUBLIC_GROUP_ID:
            return
        self._sync_running = True
        self._sync_schedule()

    def _stop_group_sync(self):
        self._sync_running = False

    def _sync_schedule(self):
        if not self._sync_running:
            return
        self._sync_cycle()
        self.root.after(60000, self._sync_schedule)

    def _sync_cycle(self):
        try:
            gid = self.active_group_id
            if not gid or gid == firebase_groups.PUBLIC_GROUP_ID:
                return
            if not hasattr(self, 'painter') or not self.painter:
                return

            meta = firebase_groups.get_group_schemes_meta(gid)
            if not meta:
                # All local schemes were deleted server-side
                if self.painter._group_schemes:
                    self.root.after(0, lambda: self._show_group_deleted_notification(
                        list(self.painter._group_schemes.keys())))
                return

            # Check for updates
            pending = []
            for drawing_id, remote in meta.items():
                local = self.painter._group_schemes.get(drawing_id)
                if local is None:
                    continue
                local_synced = local.get("_synced_at", "")
                remote_updated = remote.get("updated_at", "")
                if remote_updated > local_synced:
                    pending.append((drawing_id, remote.get("map_id", ""),
                                   remote.get("updated_by", "")))

            # Check for deleted schemes (in local but not in remote meta)
            deleted = []
            for drawing_id in list(self.painter._group_schemes.keys()):
                if drawing_id not in meta:
                    deleted.append(drawing_id)

            if pending:
                self.root.after(0, lambda: self._show_group_sync_notification(pending))

            if deleted:
                self.root.after(0, lambda: self._show_group_deleted_notification(deleted))
        except Exception as e:
            print(f"[GROUPS] Sync error: {e}")

    def _show_group_deleted_notification(self, deleted_ids):
        if not deleted_ids or not hasattr(self, 'painter') or not self.painter:
            return

        gid = self.active_group_id
        count = len(deleted_ids)

        dlg = tk.Toplevel(self.root)
        dlg.configure(bg="#222")
        dlg.overrideredirect(True)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.attributes("-topmost", True)
        dlg.lift()
        dlg.focus_force()

        hdr = tk.Frame(dlg, bg="#2a2a2a", height=28)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Scheme Deleted",
                 bg="#2a2a2a", fg="#ff6666", font=("Arial", 9, "bold")).pack(side="left", padx=8)
        tk.Button(hdr, text="\u2715", bg="#2a2a2a", fg="#aaa", bd=0,
                  font=("Arial", 10), activebackground="#c33", activeforeground="white",
                  command=dlg.destroy).pack(side="right", padx=4)
        dialog_utils._DragHelper(dlg, hdr)

        msg = f"{count} group scheme{'s' if count > 1 else ''} deleted by commander."
        tk.Label(dlg, text=msg, bg="#222", fg="#ccc",
                 font=("Arial", 9), wraplength=320).pack(padx=20, pady=(20, 4))

        def do_keep():
            try:
                for drawing_id in deleted_ids:
                    scheme = self.painter._group_schemes.get(drawing_id)
                    if not scheme:
                        continue
                    map_id = scheme.get("map_id", "")
                    elements = scheme.get("elements", [])
                    if not isinstance(elements, list):
                        continue
                    existing = self.painter.drawings.get(map_id, [])
                    self.painter.drawings[map_id] = existing + elements
                    del self.painter._group_schemes[drawing_id]
                    self.painter._scheme_downloaded_at.pop(drawing_id, None)
                self.painter.data_mgr.save_drawings(self.painter.drawings)
                self._save_group_schemes_to_cache()
                self.painter.redraw()
                if hasattr(self, 'palette') and self.palette and self.palette.winfo_exists():
                    self.palette._refresh_linked_schemes_list()
            except Exception as e:
                print(f"[GROUPS] Keep copy error: {e}")
            dlg.destroy()

        def do_remove():
            try:
                for drawing_id in deleted_ids:
                    self.painter._group_schemes.pop(drawing_id, None)
                    self.painter._scheme_downloaded_at.pop(drawing_id, None)
                self._save_group_schemes_to_cache()
                self.painter.redraw()
                if hasattr(self, 'palette') and self.palette and self.palette.winfo_exists():
                    self.palette._refresh_linked_schemes_list()
            except Exception as e:
                print(f"[GROUPS] Remove error: {e}")
            dlg.destroy()

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(12, 14))
        tk.Button(bf, text="Keep local copy", bg="#446644", fg="#cfc", bd=0,
                  font=("Arial", 9, "bold"), padx=12, pady=4,
                  command=do_keep).pack(side="left", padx=6)
        tk.Button(bf, text="Remove", bg="#553333", fg="#cc9999", bd=0,
                  font=("Arial", 9), padx=12, pady=4,
                  command=do_remove).pack(side="left", padx=6)

        dialog_utils._center_on_root(dlg, self.root)
        dlg.grab_set()
        self.root.wait_window(dlg)

    def _show_group_sync_notification(self, pending):
        if not pending:
            return
        first = pending[0]
        map_id = first[1]
        updated_by = first[2]
        count = len(pending)

        import config
        map_name = config.MAP_NAMES_EN.get(map_id, map_id)
        msg = f"Scheme{'s' if count > 1 else ''} on {map_name}"
        if count > 1:
            msg += f" (+{count - 1} more)"
        msg += f" updated by {updated_by}. Download now?"

        dlg = tk.Toplevel(self.root)
        dlg.configure(bg="#222")
        dlg.overrideredirect(True)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.attributes("-topmost", True)
        dlg.lift()
        dlg.focus_force()

        hdr = tk.Frame(dlg, bg="#2a2a2a", height=28)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Scheme Update Available",
                 bg="#2a2a2a", fg="white", font=("Arial", 9, "bold")).pack(side="left", padx=8)
        tk.Button(hdr, text="\u2715", bg="#2a2a2a", fg="#aaa", bd=0,
                  font=("Arial", 10), activebackground="#c33", activeforeground="white",
                  command=dlg.destroy).pack(side="right", padx=4)
        dialog_utils._DragHelper(dlg, hdr)

        tk.Label(dlg, text=msg, bg="#222", fg="#ccc",
                 font=("Arial", 9), wraplength=320).pack(padx=20, pady=(20, 12))

        result = [False]

        gid = self.active_group_id
        def do_update():
            result[0] = True
            try:
                schemes = firebase_groups.get_group_schemes(gid)
                for drawing_id, _, _ in pending:
                    remote = schemes.get(drawing_id)
                    if remote and isinstance(remote.get("elements"), list):
                        self.painter._group_schemes[drawing_id] = remote
                        self.painter._group_schemes[drawing_id]["_synced_at"] = \
                            remote.get("updated_at", "")
                        self.painter._scheme_downloaded_at[drawing_id] = \
                            remote.get("updated_at", "")
                self.painter.redraw()
                self._save_group_schemes_to_cache()
                if hasattr(self, 'palette') and self.palette and self.palette.winfo_exists():
                    self.palette._refresh_linked_schemes_list()
            except Exception as e:
                print(f"[GROUPS] Update error: {e}")
            dlg.destroy()

        def do_later():
            result[0] = False
            dlg.destroy()

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(0, 12))
        tk.Button(bf, text="Update", bg="#446644", fg="#cfc", bd=0,
                  font=("Arial", 10, "bold"), padx=14, pady=4,
                  command=do_update).pack(side="left", padx=6)
        tk.Button(bf, text="Later", bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 10), padx=14, pady=4,
                  command=do_later).pack(side="left", padx=6)

        dialog_utils._center_on_root(dlg, self.root)
        dlg.grab_set()
        self.root.wait_window(dlg)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    os.chdir(config.BASE_DIR)
    os.makedirs(config.USER_DATA_DIR, exist_ok=True)
    import shutil
    for fn in config.DEFAULT_FILES:
        dst = os.path.join(config.USER_DATA_DIR, fn)
        if not os.path.exists(dst):
            src = os.path.join(config.BUNDLE_DIR, fn)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass
    if "--ai-webview" in sys.argv:
        from ai_webview_gui import main as webview_main
        webview_main()
        sys.exit(0)
    splash_geometry = None
    for arg in sys.argv[1:]:
        if arg.startswith("--splash-geometry="):
            splash_geometry = arg.split("=", 1)[1]
            break
    root = tk.Tk()
    root.title(f"SM WoT Assistant v{config.load_version()}")
    app = WotAssistantHQ(root, splash_geometry=splash_geometry)
    root.mainloop()