    

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
import firebase_identity
import firebase_reporter
import firebase_drawings

try:
    import map_extractor
except ImportError:
    map_extractor = None

class WotAssistantHQ:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        
        self.lang = "ua"
        self.mode = "edit" 
        self.map_mode = 1 
        self.dialog_open = False 
        self.edit_focus_lock = False
        self._last_mode_hotkey_ts = 0.0
        self.active_view = "maps" # "maps", "stats", "ai_stats"
        
        self.data_mgr = data_manager.DataManager()
        self.settings = self.data_mgr.load_json(config.SETTINGS_FILE)
        self.map_mgr = map_manager.MapManager(self)
        self.map_mgr.auto_detect_wot_path()
        self.custom_names = self.data_mgr.load_json(config.CUSTOM_NAMES_FILE)
        
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
        self.h = self.w + 130
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
            "ЛТ": tk.BooleanVar(value=True), "СТ": tk.BooleanVar(value=True),
            "ТТ": tk.BooleanVar(value=True), "ПТ": tk.BooleanVar(value=True),
            "САУ": tk.BooleanVar(value=True)
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
        
        if log_path and os.path.exists(log_path):
            print(f"[INIT] {self.t('ui', 'log_found').format(path=log_path)}")
        elif game_exists:
            print(f"[INIT] {self.t('ui', 'log_waiting').format(path=wot_path)}")
            self._auto_detect_log_path()
            log_path = self.settings.get("log_path", "")
            if log_path:
                log_path = os.path.normpath(log_path)
                self.settings["log_path"] = log_path
        else:
            print(f"[INIT] {self.t('ui', 'game_not_found')}")
            self._auto_detect_log_path()
        
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
        self.ui_mgr.setup_ui()
        self.refresh_mode_indicator()
        self.bind_events()
        self.load_logo()
        
        self.painter = pnt.MapPainter(self.canvas, self, self.data_mgr)
        self.painter.bind_events_to(self.canvas)
        self.drawing_palette = painting_palette.DrawingPalette(self.root, self.painter, self)
        self.drawing_palette.withdraw()
        
        self.selected_battle_mode.trace_add("write", lambda *args: self.map_mgr.load_map_list())
        for var in self.selected_classes.values():
            var.trace_add("write", lambda *args: self.painter.redraw())

        firebase_reporter.setup_global_excepthook(self)
        firebase_reporter.ping_version_async(self)
        self._check_for_app_updates()

        if bool(self.settings.get("disable_startup_splash", False)):
            self._start_startup_checks()
        else:
            self.show_small_loading_splash()
            self.root.after(120, self._start_startup_checks)

    def _start_startup_checks(self):
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

    def get_edit_extra_height(self):
        """Висота службових панелей у режимі редагування (щоб мапа залишалася квадратною)."""
        if not hasattr(self, "top_bar"):
            return 130

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
        cx, cy = self.root.winfo_x(), self.root.winfo_y()
        if cx < -5000: return
        if self.root.winfo_width() < 100: return

        prefix = "edit_" if self.mode == "edit" else "norm_"
        self.settings[f"{prefix}w"] = self.w
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
            self.stats_ai_module.update_search_placeholder(f"Пошук серед {len(self.tank_db)} танків...")
            self.stats_ai_module.refresh_ai_view()





    def translate_map_name(self, eng):
        return self.locale.t_map(eng)


    def ask_wot_path(self):
        self.dialog_open = True
        path = filedialog.askdirectory(title="Виберіть головну папку гри World of Tanks")
        self.dialog_open = False
        
        if path:
            self.settings["wot_path"] = path
            log_path = os.path.join(path, "python.log")
            self.settings["log_path"] = log_path
            self.save_settings()
            
            if os.path.exists(log_path):
                self.status_label.config(text=f"[ШТАБ] Путь та логи збережено: {path}", fg="lime")
                print(f"[CONFIG] log_path встановлено: {log_path}")
                self.log_watcher.update_path(log_path)
            else:
                self.status_label.config(text=f"[ШТАБ] ⚠ Лог не знайдено: {log_path}", fg="orange")
                print(f"[CONFIG] ПОМИЛКА: log_path не існує: {log_path}")
            
            if self.btn_mode_maps_2.cget("bg") == "#ff4500":
                self.map_mgr.run_map_updater()

    def ask_clear_confirm(self, map_title, on_done):
        dlg = tk.Toplevel(self.root)
        dlg.title("\u041e\u0447\u0438\u0441\u0442\u0438\u0442\u0438 \u043c\u0430\u043b\u044e\u043d\u043a\u0438")
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        dlg.minsize(300, 120)
        dlg.attributes("-topmost", True)
        dlg.grab_set()

        cx = self.root.winfo_x() + self.root.winfo_width() // 2 - 150
        cy = self.root.winfo_y() + self.root.winfo_height() // 2 - 60
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text=f"\u0412\u0438\u0434\u0430\u043b\u0438\u0442\u0438 \u0432\u0441\u0456 \u043c\u0456\u0442\u043a\u0438 \u043d\u0430 \u043a\u0430\u0440\u0442\u0456 \u00ab{map_title}\u00bb?",
                 font=("Arial", 10), bg="#2a2a2a", fg="#cccccc").pack(pady=(20, 15))

        bf = tk.Frame(dlg, bg="#2a2a2a")
        bf.pack(pady=(0, 15))
        result = {"ok": False}
        def on_yes(): result["ok"] = True; dlg.destroy()
        def on_no(): dlg.destroy()

        tk.Button(bf, text="  \u0422\u0430\u043a  ", bg="#555", fg="white", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_yes).pack(side="left", padx=10)
        tk.Button(bf, text="  \u041d\u0456  ", bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_no).pack(side="left", padx=10)

        self.root.wait_window(dlg)
        on_done(result["ok"])

    def ask_ai_key(self):
        from tkinter import simpledialog
        new_key = simpledialog.askstring("Налаштування ШІ", "Вставте ваш Gemini API Key:", initialvalue=self.settings.get("ai_key", ""), parent=self.root)
        if new_key is not None:
            self.settings["ai_key"] = new_key.strip()
            self.save_settings()
            if hasattr(self, "ai_stats") and self.ai_stats:
                self.ai_stats.configure(self.settings["ai_key"])
            self.status_label.config(text="[СТАТ АІ] Ключ оновлено успішно!", fg="lime")


        self._last_mode_hotkey_ts = 0

    def toggle_editor(self):
        if self.dialog_open: return 

        if self.mode == "edit" and self.active_view in ("stats", "ai_stats"):
            msg = "[РЕЖИМ] Перехід у БОЙОВИЙ недоступний. Спочатку виберіть режим МАПИ."
            if hasattr(self, "status_label"):
                self.status_label.config(text=msg, fg="#ffb347")
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
                if self.map_mode == 2:
                    self.map_toolbar.pack(side="left", fill="x", expand=True, padx=10)
                    self.filter_panel.pack(side="bottom", fill="x")
                elif self.map_mode == 1:
                    self.map_toolbar.pack(side="left", fill="x", expand=True, padx=10)
                self.status_label.pack(side="bottom", fill="x")
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
        
        self.root.geometry(f"{self.w}x{self.h}+{px}+{py}")
        self.root.attributes("-alpha", 0.0)
        if self.mode == "norm":
            self.root.aspect(1, 1, 1, 1)
        elif self.mode == "edit":
            self.root.aspect(1, 1, 100, 1)
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
        finally:
            self._redrawing = False

    def refresh_mode_indicator(self):
        mode_text = "РЕДАГУВАННЯ" if self.mode == "edit" else "БОЙОВИЙ"
        fmt_text = "ON" if self.win_mgr.format_mode_enabled else "OFF"
        text = f"[РЕЖИМ] {mode_text} | [ФОРМАТУВАННЯ] {fmt_text}"
        fg = "cyan" if self.mode == "edit" else "#bbbbbb"
        if hasattr(self, "status_label"):
            self.status_label.config(text=text, fg=fg)
        if hasattr(self, "battle_status_label"):
            self.battle_status_label.config(text=text, fg=fg)

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

    def toggle_visibility(self):
        """Приховати/Показати вікно (F10)"""
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        else:
            if hasattr(self, 'stats_ai_module'):
                self.stats_ai_module.stop_browser()
            self.save_settings()
            self.root.withdraw()

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
        self.painter.redraw()

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
        if self.active_view != "maps" or self.map_mode != 2:
            msg = "[РЕЖИМ] Малювання доступне тільки в MAPS режимi."
            if hasattr(self, "status_label"):
                self.status_label.config(text=msg, fg="#ffb347")
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
            self.painter.data_mgr.save_drawings(self.painter.drawings)
            self.painter.redraw()
        
        tactics_manager.import_tactic(
            self.root,
            self.current_map_eng,
            self.translate_map_name(self.current_map_eng),
            self.painter.drawings,
            on_success
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
        cls_map = {"LT": "ЛТ", "MT": "СТ", "HT": "ТТ", "TD": "ПТ", "SPG": "САУ"}
        ui_cls = cls_map.get(cls)
        if not ui_cls:
            return

        def apply_class_filter():
            for c, var in self.selected_classes.items():
                var.set(c == ui_cls)

        self.root.after(0, apply_class_filter)

    def on_battle_countdown_started(self, map_id, arena_type):
        if not self.auto_battle_var.get():
            return
        if self.mode != "norm":
            self.root.after(100, self.toggle_editor)

    def on_battle_detected(self, map_id, mode):
        self.last_battle_map = map_id
        self.last_battle_mode = mode
        self.last_battle_map_mode = self.map_mode
        
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
        if not self.settings.get("log_path", ""):
            self.status_label.config(text="[AUTO] ПОМИЛКА: Не встановлено log_path", fg="red")
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
            self.status_label.config(text=f"[AUTO] Виявлено: {target_name}", fg="lime")
            return
            
        for t in tmaps:
            if t.lower() == target_name.lower():
                self.map_var.set(t)
                self.on_map_select()
                self.status_label.config(text=f"[AUTO] Виявлено (регістр): {t} ({map_id})", fg="lime")
                return
        
        for t in tmaps:
            if target_name in t or t.lower() in target_name.lower():
                self.map_var.set(t)
                self.on_map_select()
                self.status_label.config(text=f"[AUTO] Виявлено (схоже): {t} ({map_id})", fg="yellow")
                return
        
        self.status_label.config(text=f"[AUTO] ПОМИЛКА: Карта '{map_id}' ('{target_name}') не в списку", fg="red")

    def setup_ui(self):
        pass




    def switch_to_maps(self, mode=1):
        self.ui_mgr.show_view("maps", mode=mode)

    def switch_to_stats(self):
        self.ui_mgr.show_view("stats")

    def switch_to_ai_stats(self):
        self.ui_mgr.show_view("ai_stats")

    def quit_app(self):
        if hasattr(self, 'stats_ai_module'):
            self.stats_ai_module.stop_browser()
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
            msg = f"[ОНОВЛЕННЯ] Доступна v{latest_ver} (у вас v{current_ver})"
            print(msg)
            def _show():
                if hasattr(self, "status_label"):
                    self.status_label.config(text=msg, fg="lime")
                if self.auto_update_var.get():
                    self._show_update_dialog(latest_ver, current_ver, dl)
            self.root.after(0, _show)
        firebase_reporter.check_for_updates(on_done=_on_result)

    def _show_update_dialog(self, latest_ver, current_ver, download_url):
        dlg = tk.Toplevel(self.root)
        dlg.title("Оновлення")
        dlg.configure(bg="#222")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        dlg.grab_set()

        cx = self.root.winfo_x() + self.root.winfo_width() // 2 - 150
        cy = self.root.winfo_y() + self.root.winfo_height() // 2 - 80
        dlg.geometry(f"300x180+{cx}+{cy}")

        tk.Label(dlg, text="Доступне оновлення", font=("Arial", 12, "bold"),
                 bg="#222", fg="#ffaa00").pack(pady=(15, 5))
        tk.Label(dlg, text=f"SM WoT Assistant v{latest_ver}",
                 font=("Arial", 11), bg="#222", fg="#ff4500").pack()
        tk.Label(dlg, text=f"готовий до встановлення.\nУ вас: v{current_ver}",
                 font=("Arial", 9), bg="#222", fg="#aaa", justify="center").pack(pady=(4, 12))

        bf = tk.Frame(dlg, bg="#222")
        bf.pack()

        def do_update():
            dlg.destroy()
            if download_url:
                self._download_and_install(download_url)

        def do_later():
            dlg.destroy()

        tk.Button(bf, text="  Оновити зараз  ", bg="#335533", fg="#99cc99", bd=0,
                  font=("Arial", 10, "bold"), padx=12, pady=6,
                  command=do_update).pack(side="left", padx=8)
        tk.Button(bf, text="  Пізніше  ", bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 10), padx=12, pady=6,
                  command=do_later).pack(side="left", padx=8)

        self.root.wait_window(dlg)

    def _download_and_install(self, url):

        def _run():
            def status(msg, fg="cyan"):
                if hasattr(self, "status_label"):
                    self.root.after(0, lambda: self.status_label.config(text=msg, fg=fg))
            try:
                tmp = os.path.join(tempfile.gettempdir(), "SM_WoT_Assistant_Setup.exe")
                print(f"[ОНОВЛЕННЯ] Завантаження: {url}")
                status("[ОНОВЛЕННЯ] Завантаження...")
                r = requests.get(url, stream=True, headers=config.HEADERS, timeout=120)
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded * 100 // total
                            if pct % 10 == 0:
                                status(f"[ОНОВЛЕННЯ] Завантаження... {pct}%")
                print(f"[ОНОВЛЕННЯ] Завантажено: {downloaded / (1024*1024):.0f} MB")
                status("[ОНОВЛЕННЯ] Встановлення...", "lime")
                subprocess.Popen([tmp, "/S", "/NCRC"], shell=True)
                self.root.after(800, lambda: (self.save_settings(), sys.exit(0)))
            except Exception as e:
                print(f"[ОНОВЛЕННЯ] Помилка: {e}")
                status(f"[ОНОВЛЕННЯ] Помилка: {e}", "red")

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def bind_events(self):
        keyboard.add_hotkey('F1', lambda: self.safe_execute(self.help_manager.toggle_overlay))
        keyboard.add_hotkey('F10', lambda: self.safe_execute(self.toggle_visibility))  # F10: Показати/Приховати вікно
        keyboard.add_hotkey('e', lambda: self.safe_execute(self.toggle_editor), suppress=False)
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
        keyboard.add_hotkey('ctrl+z', lambda: self.safe_execute(self.painter.ctrl_z_undo), suppress=False)
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
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Wargaming.net", "World of Tanks", "logs", "python.log"),
            os.path.join("C:", "Games", "World_of_Tanks", "logs", "python.log"),
            os.path.join("D:", "Games", "World_of_Tanks", "logs", "python.log"),
            os.path.join("C:", "Games", "World_of_Tanks_EU", "python.log"),
            os.path.join("C:", "Games", "World_of_Tanks_EU", "logs", "python.log"),
            os.path.join("D:", "Games", "World_of_Tanks_EU", "python.log"),
            os.path.join("D:", "Games", "World_of_Tanks_EU", "logs", "python.log"),
            os.path.join(os.getcwd(), "logs", "python.log"),
        ]
        for p in common_logs:
            if os.path.exists(p):
                detected = p
                break
        if detected:
            self.settings["log_path"] = detected
            self.save_settings()
            print(f"[INIT] Автоматично визначено log_path: {detected}")
        else:
            print("[INIT] Не вдалося автоматично знайти лог. Вкажіть шлях у ⚙ -> WoT")

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
            if text:
                self._startup_status_text = text
                self.splash_canvas.itemconfigure(self.splash_status_text, text=text)
            self.splash_canvas.itemconfigure(
                self.splash_percent_text,
                text=f"{int(getattr(self, '_startup_display_percent', 0))}%",
            )
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
        self.current_map_eng = None
        self.map_var.set("")
        self.map_renderer.show_main_splash()

    def show_small_loading_splash(self):
        self.splash = tk.Toplevel(self.root)
        self._splash_shown_at = time.time()
        self._startup_target_percent = 0
        self._startup_display_percent = 0
        self._startup_ready_at = 0.0
        self._startup_status_text = self.t('ui', 'checking_updates')
        sw, sh = 450, 300
        self.splash.geometry(f"{sw}x{sh}+{int((self.root.winfo_screenwidth()/2)-(sw/2))}+{int((self.root.winfo_screenheight()/2)-(sh/2))}")
        self.splash.overrideredirect(True)
        self.splash.attributes("-topmost", True)
        self.splash.configure(bg="black")
        self.splash_canvas = tk.Canvas(self.splash, width=sw, height=sh, bg="black", highlightthickness=0)
        self.splash_canvas.pack()
        if self.logo_splash:
            self.splash_canvas.create_image(sw//2, sh//2 - 20, image=self.logo_splash)
        version = config.load_version()
        self.splash_canvas.create_text(sw//2, sh - 72, text=version, fill="white", font=("Verdana", 12, "bold"))
        self.splash_status_text = self.splash_canvas.create_text(
            sw//2,
            sh - 46,
            text=self.t('ui', 'checking_updates'),
            fill="#bbbbbb",
            font=("Arial", 9),
        )
        self.splash_percent_text = self.splash_canvas.create_text(
            sw - 34,
            sh - 18,
            text="0%",
            fill="#dddddd",
            font=("Arial", 9, "bold"),
        )
        self.pbar = self.splash_canvas.create_rectangle(0, sh-8, 0, sh, fill="#ff4500", outline="")
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
                self.root.attributes("-alpha", max(0.2, min(float(self.alpha), 1.0)))
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                self.current_map_eng = None
                self.map_var.set("")
                self.map_renderer.show_main_splash()
                print("[INIT] Failsafe: головне вікно примусово показано")
        except Exception as e:
            print(f"[INIT] Failsafe error: {e}")

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
    root = tk.Tk()
    root.title(f"SM WoT Assistant v{config.load_version()}")
    app = WotAssistantHQ(root)
    root.mainloop()