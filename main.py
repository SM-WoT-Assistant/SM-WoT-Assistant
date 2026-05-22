            # -*- coding: utf-8 -*-
# main.py 4_43
# ==========================================
# ЧЕК-ЛИСТ ФУНКЦІОНАЛУ (НЕ ВИДАЛЯТИ І НЕ ЗМІНЮВАТИ БЕЗ ДОЗВОЛУ):
# [v] 1. UI: Три незалежні панелі (SETUP, TACTIC, MAPS), які повністю перемикаються. Нейтральний старт.
# [v] 2. UI: Блок фільтрів (РЕЖИМ БОЮ з Натиском + ТЕХНІКА), пакування без накладання. Строка стану над фільтрами.
# [v] 3. UI: Інструменти (painter.py). Магнітне прилипання. Захист від битих збережень.
# [v] 4. UI: Налаштування (Кнопка ⚙ з коректним згортанням, перейменування мапи, авто-фільтри, AI-key). Темні діалоги.
# [v] 5. ВІКНО: Гарячі клавіші (F10, E, Ctrl+Стрілки, Ctrl+ЛКМ). БЛОКУВАННЯ (Hotkey Lock) під час відкритих вікон.
# [v] 6. ВІКНО: Масштабування суворо з фіксацією правого нижнього кута (apply_anchor_resize).
# [v] 7. ВІКНО: Бойовий режим: click-through (ctypes) + приховування UI + незалежна пам'ять координат/розміру.
# [v] 8. ДАНІ: Збереження всіх налаштувань у settings.json (окремо edit_ та norm_).
# [v] 9. ДАНІ: Читання/запис custom_names.json та підміна назв у випадаючому списку.
# [v] 10. МАПА: Запуск із заставки. ПОВЕРНУТО НЕЙТРАЛЬНИЙ СТАРТ.
# [v] 11. МАПА: Дебаунс (затримка 100мс) при зміні розміру для уникнення мерехтіння.
# [v] 12. ВІКНО: Watcher та жорстка фіксація (easy_drag=False) для WebView2.
# [v] 13. МАПА: Кнопки ТАКТИКА / МАПИ, авто-перевірка version.xml та автономний парсинг.
# [v] 14. МАПА: Читання map_data.json, фільтрація за режимом та відмальовування порожніх білих кілець із тінями.
# [v] 15. UI: Універсальний вибір шляху до гри (wot_path + log_path) та автовизначення.

# ==========================================
# ЧЕК-ЛИСТ МОДУЛІВ ТА АРХІТЕКТУРИ:
# [v] config.py — Конфігурація, шляхи, локалізація, словники.
# [v] main.py — Головний GUI, масштабування, гарячі клавіші.
# [v] map_updater.py — TACTIC: Старий завантажувач з інтернету (ПІДКЛЮЧЕНО).
# [v] map_extractor.py — MAPS: Автономний екстрактор з клієнта гри (ПІДКЛЮЧЕНО).
# [v] painter.py — Логіка малювання, кольорові POI, магнітне прилипання, темна тема (ПІДКЛЮЧЕНО).
# [x] tomato_viewer.py — ВИДАЛЕНО (2026-05-20)
# [v] ai_assistant.py — СТАТ АІ: Персональний помічник Gemini для усереднення збірок (ПІДКЛЮЧЕНО).
# [v] tactics_manager.py — Новий модуль для імпорту/експорту тактик (ГОТОВО).
# [v] log_reader.py — Читання python.log та автоматичне перемикання (ГОТОВО).
# [v] help_system.py — Модуль ДОПОМОГИ (ГОТОВО).
# [ ] translator.py — Модуль перекладу на інші мови (UA/EN/PL) (У ПЛАНАХ).
# [x] tank_db.py — Модуль ТАНКИ: Локальна база ТТХ з клієнта (У ПЛАНАХ).
# [ ] Модуль оновлення данних які програма бере з клієнта гри при зміні версії клієнта гри
# ==========================================

import os, sys, json, ctypes, re

# Ensure UTF-8 output on Windows
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

import threading
import time
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps, ImageEnhance
import keyboard

import config
import tactics_manager
import log_reader
import help_system
# import ai_assistant  # ТИМЧАСОВО ВИМКНЕНО
import painter as pnt
import stats_ai
import window_manager
import map_renderer
import locale_manager
import map_manager
import data_manager
import ui_manager

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
        
        # Зворотна таблиця compactDescr -> інформація про танк (для авто-фільтрів)
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
        
        self.win_mgr = window_manager.WindowManager(self)
        self.win_mgr.initialize_window()
        
        self.map_list_eng = []
        self.current_map_eng = None
        self.current_tk_map = None
        self.drag = None
        self._menu_is_active = False
        self.help_manager = help_system.HelpManager(self)

        self.selected_battle_mode = tk.StringVar(value="Standard")
        self.selected_classes = {
            "ЛТ": tk.BooleanVar(value=False), "СТ": tk.BooleanVar(value=False),
            "ТТ": tk.BooleanVar(value=False), "ПТ": tk.BooleanVar(value=False),
            "САУ": tk.BooleanVar(value=False)
        }

        self.thread_queue = []
        self.process_queue()
        
        # Ініціалізація відстеження логів
        log_path = self.settings.get("log_path", "")
        # Нормалізуємо розділювачі шляху для поточної ОС
        if log_path:
            log_path = os.path.normpath(log_path)
            self.settings["log_path"] = log_path
        print(f"[INIT] log_path = {log_path}")
        if not log_path or not os.path.exists(log_path):
            self._auto_detect_log_path()
            log_path = self.settings.get("log_path", "")
            if log_path:
                log_path = os.path.normpath(log_path)
                self.settings["log_path"] = log_path
        if log_path and os.path.exists(log_path):
            print(f"[INIT] ✓ Лог знайдено: {log_path}")
        else:
            print(f"[INIT] ✗ Лог НЕ знайдено. Встановіть шлях у ⚙ -> WoT")
        
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
        
        self.selected_battle_mode.trace_add("write", lambda *args: self.map_mgr.load_map_list())
        for var in self.selected_classes.values():
            var.trace_add("write", lambda *args: self.painter.redraw())
            
        # self.ai_stats = ai_assistant.AIAssistant(self.settings.get("ai_key", ""))  # ТИМЧАСОВО ВИМКНЕНО

        # Стандартний старт: splash завжди показує прогрес фонового оновлення.
        # Для аварійного вимкнення лишаємо технічний прапорець у settings.
        if bool(self.settings.get("disable_startup_splash", False)):
            self._start_startup_checks()
        else:
            self.show_small_loading_splash()
            self.root.after(120, self._start_startup_checks)


    def _start_startup_checks(self):
        # Дозволяємо декодування мап на старті для автоматичного оновлення
        allow_decode = bool(self.settings.get("allow_map_decode_on_startup", True))
        self.map_mgr.check_game_version(
            progress_cb=self._on_startup_progress,
            done_cb=self._on_startup_ready,
            allow_map_decode=allow_decode,
        )

    # auto_detect_wot_path moved to map_manager

    def t(self, cat, key):
        if cat == "ui": return self.locale.t_ui(key)
        if cat == "tanks": return self.locale.t_tank(key, key)
        return self.locale.t_map(key)

    def get_edit_extra_height(self):
        """Висота службових панелей у режимі редагування (щоб мапа залишалася квадратною)."""
        # До побудови UI повертаємо старий безпечний fallback.
        if not hasattr(self, "top_bar"):
            return 130

        self.root.update_idletasks()
        top_h = self.top_bar.winfo_reqheight()
        filter_h = self.filter_panel.winfo_reqheight() if hasattr(self, "filter_panel") else 0
        status_h = self.status_label.winfo_reqheight() if hasattr(self, "status_label") else 0
        return top_h + filter_h + status_h

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

    # load_json and save_json moved to DataManager

    def save_settings(self):
        cx, cy = self.root.winfo_x(), self.root.winfo_y()
        if cx < -5000: return

        prefix = "edit_" if self.mode == "edit" else "norm_"
        self.settings[f"{prefix}w"] = self.w
        self.settings[f"{prefix}x"] = cx
        self.settings[f"{prefix}y"] = cy
        self.settings[f"{prefix}alpha"] = self.alpha
        self.settings[f"{prefix}contrast"] = self.contrast
        self.settings["auto_sync"] = self.auto_sync_var.get()
        self.settings["auto_battle"] = self.auto_battle_var.get()
        self.settings["auto_mode_filter"] = self.auto_mode_filter_var.get()
        self.settings["auto_vehicle_filter"] = self.auto_vehicle_filter_var.get()
        self.data_mgr.save_json(config.SETTINGS_FILE, self.settings)
        
        # Оновлюємо шлях у лог-рідері при зміні налаштувань
        if hasattr(self, 'log_watcher'):
            self.log_watcher.update_path(self.settings.get("log_path", ""))

    # load_tank_db moved to DataManager

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




    # check_game_version moved to map_manager

    def translate_map_name(self, eng):
        return self.locale.t_map(eng)

    # sort_map_list and get_eng_map_name moved to map_manager

    def ask_wot_path(self):
        self.dialog_open = True
        path = filedialog.askdirectory(title="Виберіть головну папку гри World of Tanks")
        self.dialog_open = False
        
        if path:
            self.settings["wot_path"] = path
            log_path = os.path.join(path, "python.log")
            self.settings["log_path"] = log_path
            self.save_settings()
            
            # Перевірка наявності лога
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
        """Підтвердження очищення міток (викликається з painter.MapPainter.clear_all)."""
        self.dialog_open = True
        ok = messagebox.askyesno(
            "Очистити малюнки",
            f"Видалити всі мітки на карті «{map_title}»?",
            parent=self.root,
        )
        self.dialog_open = False
        on_done(ok)

    def ask_ai_key(self):
        from tkinter import simpledialog
        new_key = simpledialog.askstring("Налаштування ШІ", "Вставте ваш Gemini API Key:", initialvalue=self.settings.get("ai_key", ""), parent=self.root)
        if new_key is not None:
            self.settings["ai_key"] = new_key.strip()
            self.save_settings()
            if hasattr(self, "ai_stats") and self.ai_stats:
                self.ai_stats.configure(self.settings["ai_key"])
            self.status_label.config(text="[СТАТ АІ] Ключ оновлено успішно!", fg="lime")

    # run_map_updater and load_map_list moved to map_manager

    def toggle_settings(self):
        if self._menu_is_active:
            self.settings_menu.unpost()
            self._menu_is_active = False
        else:
            x = self.settings_btn.winfo_rootx()
            y = self.settings_btn.winfo_rooty() + self.settings_btn.winfo_height()
            self.settings_menu.post(x, y)
            self._menu_is_active = True

    def _on_settings_unmap(self, event):
        self.root.after(100, self._set_menu_inactive)

    def _set_menu_inactive(self):
        self._menu_is_active = False

    def toggle_editor(self):
        if self.dialog_open: return 

        # Бойовий режим дозволено лише у режимі МАПИ.
        if self.mode == "edit" and self.active_view in ("stats", "ai_stats"):
            msg = "[РЕЖИМ] Перехід у БОЙОВИЙ недоступний. Спочатку виберіть режим МАПИ."
            if hasattr(self, "status_label"):
                self.status_label.config(text=msg, fg="#ffb347")
            print(msg)
            return

        self.save_settings() 
        self.battle_status_top.pack_forget()
        self.top_bar.pack_forget()
        self.map_toolbar.pack_forget()
        self.filter_panel.pack_forget()
        self.status_label.pack_forget()
        self.canvas.pack_forget()
        self.browser_frame.pack_forget()
        if hasattr(self, 'ai_frame'): self.ai_frame.pack_forget()

        if self.mode == "edit":
            self.mode = "norm"
            # У бойовому режимі click-through залежить від активності форматування (F8).
            self.win_mgr.set_clickthrough(not self.win_mgr.format_mode_enabled)
            # НЕ показувати top_bar у боєвому режимі - тільки мапа
            self.top_bar.pack_forget()
            if self.active_view == "maps":
                self.battle_status_top.pack(side="top", fill="x")
                self.canvas.pack(side="top", fill="both", expand=True)
            else:
                self.mode = "edit"
                self.win_mgr.set_clickthrough(False)
                self.top_bar.pack_forget()
                self.top_bar.pack(side="top", fill="x")
            
            if self.active_view == "maps":
                if self.btn_mode_maps_1.cget("bg") == "#ff4500" or self.btn_mode_maps_2.cget("bg") == "#ff4500":
                    toolbar_frame = tk.Frame(self.root, bg="#1a1a1a") # Container to help packing
                    self.map_toolbar.pack(side="left", fill="x", expand=True, padx=10) 
                    self.filter_panel.pack(side="bottom", fill="x") 
                self.status_label.pack(side="bottom", fill="x")
                self.canvas.pack(side="top", fill="both", expand=True) 
            elif self.active_view == "stats":
                self.status_label.pack(side="bottom", fill="x")
                self.browser_frame.pack(side="top", fill="both", expand=True)
            elif self.active_view == "ai_stats":
                self.ai_frame.pack(side="top", fill="both", expand=True)
                self.status_label.pack(side="bottom", fill="x")

        prefix = "edit_" if self.mode == "edit" else "norm_"
        self.w = self.settings.get(f"{prefix}w", 800 if self.mode=="edit" else 400)
        self.h = self.w + (self.get_edit_extra_height() if self.mode=="edit" else 0)
        self.alpha = self.settings.get(f"{prefix}alpha", 1.0)
        self.contrast = self.settings.get(f"{prefix}contrast", 1.0)
        px, py = self.settings.get(f"{prefix}x", 100), self.settings.get(f"{prefix}y", 100)
        
        self.root.geometry(f"{self.w}x{self.h}+{px}+{py}")
        self.root.attributes("-alpha", self.alpha)
        self.root.after(50, self.map_renderer.show_main_splash)
        self.refresh_mode_indicator()

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
            print("[HOTKEY] F8: ФОРМАТУВАННЯ увімкнено")
        else:
            if self.mode == "norm":
                self.win_mgr.set_clickthrough(True)
                self.win_mgr.focus_game_window()
            print("[HOTKEY] F8: ФОРМАТУВАННЯ вимкнено")
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
            print("[HOTKEY] F8: увімкнено РЕДАГУВАННЯ + ФОРМАТУВАННЯ")
        else:
            self.edit_focus_lock = False
            focused = self.win_mgr.focus_game_window()
            if focused:
                print("[HOTKEY] F8: увімкнено БОЙОВИЙ режим, форматування вимкнено")
            else:
                print("[HOTKEY] F8: увімкнено БОЙОВИЙ режим (вікно гри не знайдено)")

    def on_map_select(self, event=None):
        self.root.focus_set()
        selected_ua = self.map_var.get()
        self.current_map_eng = self.map_mgr.get_eng_map_name(selected_ua)
        self.map_renderer.show_main_splash()

    def set_painter_tool(self, tool):
        if hasattr(self, 'painter'):
            self.painter.set_tool(tool)
                
        if tool == "marker":
            self.draw_btn.config(text="МАРКЕР", bg="#ffaa00", fg="black")
        elif tool == "text":
            self.draw_btn.config(text="ТЕКСТ / ЗНАК", bg="#ffaa00", fg="black")
        else:
            self.draw_btn.config(text="МАЛЮВАТИ", bg="#444", fg="gray")

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
            self.painter.save_data()
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
        
        # Конвертуємо режим
        mode_map = {
            "ctf": "Standard",
            "domination": "Encounter",
            "assault": "Assault",
            "comp7": "Onslaught"
        }
        ui_mode = mode_map.get(mode, "Standard")
        self.safe_battle_sync(map_id, ui_mode)
        print(f"[BATTLE] Синхронізація карти після повернення: {map_id} (МАПИ {target_map_mode})")

    def safe_battle_sync(self, map_id, ui_mode):
        # Перевірка налаштування log_path
        if not self.settings.get("log_path", ""):
            self.status_label.config(text="[AUTO] ПОМИЛКА: Не встановлено log_path", fg="red")
            return

        # Якщо зараз відкрито СТАТИ, автоматично перемикаємо на МАПИ II (вони актуальніші)
        self.switch_to_maps(2)

        if self.auto_mode_filter_var.get():
            self.selected_battle_mode.set(ui_mode)
        else:
            print(f"[SYNC] Авто-вибір режиму бою вимкнено (auto_mode_filter={self.auto_mode_filter_var.get()})")
        
        # Біжи до перекладу карти з логуванням
        target_name = self.translate_map_name(map_id)
        print(f"[SYNC] map_id='{map_id}', ui_mode='{ui_mode}', target_name='{target_name}'")
        
        # Отримуємо список доступних карт
        tmaps = self.map_selector.cget("values")
        print(f"[SYNC] Available maps: {tmaps}")
        
        # 1. Спробуємо точний збіг
        if target_name in tmaps:
            self.map_var.set(target_name)
            self.on_map_select()
            self.status_label.config(text=f"[AUTO] Виявлено: {target_name} ({map_id})", fg="lime")
            return
            
        # 2. Пошук без врахування регістру
        for t in tmaps:
            if t.lower() == target_name.lower():
                self.map_var.set(t)
                self.on_map_select()
                self.status_label.config(text=f"[AUTO] Виявлено (регістр): {t} ({map_id})", fg="lime")
                return
        
        # 3. Частковий збіг (если перший фрагмент збігається)
        for t in tmaps:
            if target_name in t or t.lower() in target_name.lower():
                self.map_var.set(t)
                self.on_map_select()
                self.status_label.config(text=f"[AUTO] Виявлено (схоже): {t} ({map_id})", fg="yellow")
                return
        
        # 4. Якщо нічого не знайше - показуємо помилку з map_id
        self.status_label.config(text=f"[AUTO] ПОМИЛКА: Карта '{map_id}' ('{target_name}') не в списку", fg="red")

    def show_draw_menu(self):
        x = self.draw_btn.winfo_rootx()
        y = self.draw_btn.winfo_rooty() + self.draw_btn.winfo_height()
        self.draw_menu.post(x, y)

    def setup_ui(self):
        # Moved to UIManager
        pass

    # build_filters moved to UIManager



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
        keyboard.unhook_all() 
        self.root.destroy()
        sys.exit(0)

    def bind_events(self):
        keyboard.add_hotkey('F1', lambda: self.safe_execute(self.help_manager.toggle_overlay))
        keyboard.add_hotkey('F10', lambda: self.safe_execute(self.toggle_visibility))  # F10: Показати/Приховати вікно
        keyboard.add_hotkey('e', lambda: self.safe_execute(self.toggle_editor), suppress=False)
        try:
            keyboard.add_hotkey('f8', lambda: self.safe_execute(self.toggle_formatting_mode), suppress=False)
            print("[HOTKEY] ФОРМАТУВАННЯ: F8")
        except Exception as e:
            keyboard.add_hotkey('ctrl+e', lambda: self.safe_execute(self.toggle_formatting_mode), suppress=False)
            print(f"[HOTKEY] F8 недоступний: {e}")
            print("[HOTKEY] Fallback форматування: Ctrl+E")
        # Ctrl керування вікном у бойовому режимі (подвійний натиск для drag)
        # suppress=False дозволяє одинарному Ctrl залишатись прозорим для гри
        keyboard.add_hotkey('ctrl+up', lambda: self.safe_execute(self.win_mgr.resize_up_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+down', lambda: self.safe_execute(self.win_mgr.resize_down_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+right', lambda: self.safe_execute(self.win_mgr.alpha_up_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+left', lambda: self.safe_execute(self.win_mgr.alpha_down_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+shift+up', lambda: self.safe_execute(self.win_mgr.contrast_up_hotkey), suppress=False)
        keyboard.add_hotkey('ctrl+shift+down', lambda: self.safe_execute(self.win_mgr.contrast_down_hotkey), suppress=False)
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
        # Debug: check language setting
        lang_code = getattr(self.locale, 'lang', '?')
        test_key = self.t('ui', 'fetching_info')
        print(f"[INIT] lang={lang_code}, fetching_info='{test_key}'")
        # Check if AI refresh is needed (cache may be fresh)
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
        # Save current progress as AI base
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
            self._ai_timeout_id = self.root.after(120000, self._ai_safety_timeout)
        else:
            self.finish_startup_splash()

    def _ai_progress_creep(self):
        if not hasattr(self, '_startup_ai_start'):
            return
        elapsed = time.time() - self._startup_ai_start
        base = getattr(self, '_startup_ai_base', 40)
        # Phase 1: base → 93% over 20 seconds (typical AI response time)
        if elapsed < 20:
            pct = base + (93 - base) * elapsed / 20
        else:
            # Phase 2: 93% → 100% over next 30 seconds
            pct = 93 + 7 * min(elapsed - 20, 30) / 30
        pct = min(100, pct)
        self._startup_target_percent = int(pct)
        # Direct canvas update with float pct for sub-pixel smoothness
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
        # Only update text, progress is handled by creep
        self.root.after(0, lambda t=text: self.update_startup_progress(
            getattr(self, '_startup_target_percent', 40), t
        ))

    def _on_ai_ready(self):
        # Show "100% Готово" for 500ms before closing
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
            # During creep, direct smooth update handles the bar
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
        # Перевіряємо, чи splash відображався щонайменше 2 секунди
        shown_at = getattr(self, "_splash_shown_at", 0.0)
        elapsed_ms = int((time.time() - shown_at) * 1000) if shown_at else 9999
        min_visible_ms = 2000  # Принаймні 2 секунди
        if elapsed_ms < min_visible_ms:
            self.root.after(min_visible_ms - elapsed_ms, self.finish_startup_splash)
            return
        # Тепер знищуємо splash
        try:
            if hasattr(self, "splash"):
                if self.splash and self.splash.winfo_exists():
                    self.splash.destroy()
                    print("[INIT] Splash знищено")
                # Видаляємо атрибут незалежно від результату
                if hasattr(self, "splash"):
                    try:
                        del self.splash
                    except Exception:
                        pass
        except Exception as e:
            print(f"[INIT] Помилка знищення splash: {e}")
        finally:
            # Видаляємо атрибут незалежно від результату
            if hasattr(self, "splash"):
                try:
                    del self.splash
                except Exception:
                    pass
        # Показуємо головне вікно
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
        # Get version from git tag
        version = "1.03"
        try:
            import subprocess
            result = subprocess.run(['git', 'describe', '--tags', '--always'], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            if result.returncode == 0:
                git_version = result.stdout.strip()
                if git_version:
                    version = git_version
        except Exception:
            pass
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
        # Форсуємо первинне відмалювання splash до старту фонових задач.
        self.splash.deiconify()
        self.splash.lift()
        self.splash.update_idletasks()

    def _startup_show_failsafe(self):
        # Якщо вікно досі приховане через проблеми splash/таймерів — примусово показуємо.
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
    root = tk.Tk()
    app = WotAssistantHQ(root)
    root.mainloop()
# main.py 4_43
