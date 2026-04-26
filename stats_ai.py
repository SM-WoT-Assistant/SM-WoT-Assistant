import os
import re
import json
import random
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps, ImageDraw
import io

class StatsAI:
    def __init__(self, ai_frame, tank_db, popular_tanks, main_app):
        self.ai_frame = ai_frame
        self.tank_db = tank_db
        self.popular_tanks = popular_tanks
        self.main_app = main_app  # Reference to WotAssistantHQ
        self.locale_manager = getattr(main_app, 'locale_manager', None)  # Localization support
        
        self.ai_search_var = tk.StringVar()
        self.nation_filters = {}
        self.class_filters = {}
        self.tier_filters = {}
        self.filter_icons = {}
        self.composite_cache = {}
        self.ui_icons = {}
        self.loadout_icon_cache = {}
        self.tth_icon_cache = {}
        self._field_mod_pairs_cache = {}
        self._field_mod_pairs_by_tank = self._load_field_mod_pairs_by_tank()
        self._crew_builds = self._load_crew_builds()

        self.root = self.main_app.root
        self._search_timer = None
        self._filter_active = False
        self._filter_progress_canvas = None
        self._filter_progress_rect = None
        self._filter_hide_job = None
        
        self.active_tank = None
        self._last_cols = 0
        self._detail_side_by_side = False
        self._detail_compact_min_width = 440
        self._detail_compact_max_width = 440
        self._detail_tth_fixed_width = 250
        self._detail_info_fixed_width = 440
        self._detail_top_row_fixed_width = 440
        # Upward shift (px) for the tank sprite inside the detail image card.
        self._detail_image_lift_px = 36
        # TEST MODE: keep global layout debug disabled for users.
        self._layout_debug = False
        # TEST MODE: show borders only for subsection blocks (equipment/consumables/crew/field mod).
        self._sections_debug = False
        self.tank_tth = {}
        self.reload_tth_data()
        
        self.LOADOUT_ICON_DIR = os.path.join(os.path.dirname(__file__), 'extracted_icons', 'loadout')
        self.FIELD_MODS_ORIGINAL_DIR = os.path.join(
            self.LOADOUT_ICON_DIR,
            'field_mods_original',
            'pairModifications',
            '80x80',
        )
        self.TTH_ICON_DIR = os.path.join(os.path.dirname(__file__), 'extracted_icons', 'tth')
        
        # Cache for available icons in each category
        self._available_icons = {}
        self._load_available_icons()

        # Placeholder text should not affect filtering logic.
        self.search_placeholder = f"Пошук серед {len(self.tank_db)} танків..."
        
        self.build_ai_ui()

    def _load_crew_builds(self):
        """Завантажує crew_builds.json з рекомендованими будовами екіпажу."""
        path = os.path.join(os.path.dirname(__file__), 'crew_builds.json')
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _get_crew_rows_for_tank(self, tag):
        """Повертає список ({role, also}, [skill_names]) для конкретного танка."""
        builds = self._crew_builds
        default_skills = (builds.get('_default_skills') or {}) if builds else {}
        role_skill_pools = (builds.get('_role_skill_pools') or {}) if builds else {}
        tanks = (builds.get('tanks') or {}) if builds else {}

        # Crew members: new format with secondary roles.
        tank_entry = tanks.get(tag) or {}
        crew_members = tank_entry.get('crew_members')
        if not isinstance(crew_members, list) or not crew_members:
            # Legacy fallback: crew = [role1, role2, ...]
            crew_roles = tank_entry.get('crew')
            if crew_roles:
                crew_members = [{'role': r, 'also': []} for r in crew_roles]

        if not crew_members:
            tank_data = self.tank_db.get(tag, {}) if isinstance(self.tank_db, dict) else {}
            tank_class = (tank_data.get('class') or 'MT').upper()
            default_roles = (builds.get('_default_roles') or {}) if builds else {}
            crew_members = [
                {'role': r, 'also': []}
                for r in (default_roles.get(tank_class) or ['commander', 'gunner', 'driver', 'loader'])
            ]

        # Global perk policy (version-stable): tier-driven primary perks + bonus for secondary roles.
        policy = (builds.get('_perk_policy') or {}) if builds else {}
        tier_map = policy.get('primary_perk_count_by_tier') or {}
        default_primary = policy.get('default_primary_perk_count', 3)
        secondary_perk_bonus = policy.get('secondary_perk_bonus_per_role', 0)
        secondary_bonus_by_slot = policy.get('secondary_perk_bonus_by_custom_role_slots') or {}
        max_perks = policy.get('max_perks_per_member', 15)

        tank_data = self.tank_db.get(tag, {}) if isinstance(self.tank_db, dict) else {}
        try:
            tier = int((tank_data or {}).get('tier', 0) or 0)
        except Exception:
            tier = 0

        try:
            primary_perk_count = int(tier_map.get(str(tier), tier_map.get(tier, default_primary)) or default_primary)
        except Exception:
            primary_perk_count = 3

        try:
            secondary_perk_bonus = int(secondary_perk_bonus or 0)
        except Exception:
            secondary_perk_bonus = 0
        slot_options = str(tank_entry.get('custom_role_slot_options') or '').strip()
        if slot_options:
            try:
                secondary_perk_bonus = int(secondary_bonus_by_slot.get(slot_options, secondary_perk_bonus))
            except Exception:
                pass
        try:
            max_perks = int(max_perks or 15)
        except Exception:
            max_perks = 15

        primary_perk_count = max(1, min(primary_perk_count, 12))
        secondary_perk_bonus = max(0, min(secondary_perk_bonus, 6))
        max_perks = max(1, min(max_perks, 20))

        fallback_common = ['repair', 'camouflage', 'fireFighting', 'brotherhood']
        rows = []
        for member in crew_members:
            role = str((member or {}).get('role') or '').strip()
            also_roles = (member or {}).get('also') or []
            also_roles = [str(r).strip() for r in also_roles if str(r).strip()]
            if not role:
                continue

            member_target = primary_perk_count + (secondary_perk_bonus * len(also_roles))
            member_target = max(1, min(member_target, max_perks))

            # Build primary list first, then append secondary-role skills.
            skills = []

            def _append_unique(seq):
                for name in seq:
                    if name and name not in skills:
                        skills.append(name)

            # Primary role block.
            _append_unique(role_skill_pools.get(role) or [])
            _append_unique(default_skills.get(role) or [])
            _append_unique(fallback_common)
            primary_block = skills[:primary_perk_count]

            # Secondary role bonus block.
            extra_target = max(0, member_target - len(primary_block))
            if extra_target > 0:
                for sec_role in also_roles:
                    _append_unique(role_skill_pools.get(sec_role) or [])
                    _append_unique(default_skills.get(sec_role) or [])
                _append_unique(fallback_common)

            skills = (primary_block + [s for s in skills if s not in primary_block])[:member_target]

            rows.append(({'role': role, 'also': also_roles}, skills))
        return rows

    def reload_tth_data(self):
        tth_path = os.path.join(os.path.dirname(__file__), 'tank_tth.json')
        if os.path.exists(tth_path):
            try:
                with open(tth_path, 'r', encoding='utf-8') as f:
                    self.tank_tth = json.load(f)
            except Exception:
                self.tank_tth = {}
        else:
            self.tank_tth = {}

    def _load_available_icons(self):
        """Завантажує список доступних іконок для кожної категорії"""
        categories = ['artefacts', 'ammo', 'crew_skills', 'field_mods']
        for cat in categories:
            if cat == 'field_mods' and os.path.exists(self.FIELD_MODS_ORIGINAL_DIR):
                cat_dir = self.FIELD_MODS_ORIGINAL_DIR
            else:
                cat_dir = os.path.join(self.LOADOUT_ICON_DIR, cat)
            if os.path.exists(cat_dir):
                icons = [f[:-4] for f in os.listdir(cat_dir) if f.endswith('.png')]
                self._available_icons[cat] = icons
            else:
                self._available_icons[cat] = []
    
    def _get_random_icons(self, category, count=3):
        """Повертає випадкові іконки з категорії"""
        available = self._available_icons.get(category, [])
        if not available:
            return []
        return random.sample(available, min(count, len(available)))
    
    def t(self, key, default=None):
        """Отримати переклад UI елементу"""
        if self.locale_manager:
            return self.locale_manager.t_ui(key, default or key)
        return default or key

    def _normalize_tier(self, tier_value):
        try:
            return int(tier_value)
        except (TypeError, ValueError):
            return None

    def _normalize_class(self, class_value):
        if class_value is None:
            return ""
        return str(class_value).strip().upper()

    def _normalize_nation(self, nation_value):
        if nation_value is None:
            return ""
        return str(nation_value).strip().lower()

    def _active_filter_values(self):
        active_t = {self._normalize_tier(t) for t, v in self.tier_filters.items() if v["active"]}
        active_t.discard(None)
        active_c = {self._normalize_class(c) for c, v in self.class_filters.items() if v["active"]}
        active_n = {self._normalize_nation(n) for n, v in self.nation_filters.items() if v["active"]}
        return active_t, active_c, active_n

    def _show_grid_if_needed(self):
        if self.active_tank is not None:
            self.active_tank = None
            if hasattr(self, 'ai_res_f'):
                self.ai_res_f.pack_forget()
            if hasattr(self, 'ai_grid_container'):
                self.ai_grid_container.pack(side="top", fill="both", expand=True)

    def _parse_search_query(self):
        raw_q = self.ai_search_var.get() or ""
        q = raw_q.strip()
        if not q:
            return ""
        if q.casefold() == self.search_placeholder.casefold():
            return ""
        return q.casefold()

    def _on_search_changed(self, *args):
        if not hasattr(self, 'ai_grid_frame') or self.main_app.active_view != "ai_stats":
            return
        # Cancel any pending search
        if self._search_timer is not None:
            self.root.after_cancel(self._search_timer)
            self._search_timer = None
        # Schedule new search after 700ms delay
        self._search_timer = self.root.after(700, self._perform_search)

    def _perform_search(self):
        self._show_grid_if_needed()
        self.refresh_ai_view()

    def update_search_placeholder(self, new_placeholder):
        old_placeholder = self.search_placeholder
        current_text = (self.ai_search_var.get() or "").strip()
        self.search_placeholder = new_placeholder

        # Якщо в полі лишився старий плейсхолдер, не трактуємо його як реальний пошук.
        looks_like_placeholder = current_text.startswith("Пошук серед ") and current_text.endswith("танків...")
        if current_text == "" or current_text.casefold() == old_placeholder.casefold() or looks_like_placeholder:
            self.ai_search_var.set(new_placeholder)
            if hasattr(self, 'ai_search_entry') and self.ai_search_entry:
                self.ai_search_entry.config(fg="gray")

    def build_ai_ui(self):
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            style.configure("Dark.Vertical.TScrollbar", troughcolor="#0a0a0a", background="#2a2a2a", bordercolor="#0a0a0a", arrowcolor="#777777", borderwidth=0, lightcolor="#2a2a2a", darkcolor="#2a2a2a")
            style.map("Dark.Vertical.TScrollbar",
                background=[('active', '#3a3a3a'), ('pressed', '#4a4a4a')],
                lightcolor=[('active', '#3a3a3a'), ('pressed', '#4a4a4a')],
                darkcolor=[('active', '#3a3a3a'), ('pressed', '#4a4a4a')],
                arrowcolor=[('active', '#ffffff'), ('pressed', '#ffffff')]
            )
        # ПАНЕЛЬ ФІЛЬТРІВ (Масштабовані 2 строки)
        fb = tk.Frame(self.ai_frame, bg="#1a1a1a", pady=2)
        fb.pack(side="top", fill="x")
        
        # Строка 1: Пошук на всю ширину
        row1 = tk.Frame(fb, bg="#1a1a1a", height=46)
        row1.pack(side="top", fill="x", pady=2)
        row1.pack_propagate(False)
        
        self.ai_search_var.trace_add("write", self._on_search_changed)
        
        placeholder = self.search_placeholder
        
        # Кнопка Додому
        self.btn_home = tk.Button(row1, text="⌂", bg="#2a2a2a", fg="gray", activebackground="#333", activeforeground="white", font=("Arial", 28), bd=0, relief="flat", cursor="hand2", command=self.return_to_ai_home)
        self.btn_home.pack(side="left", fill="y", padx=(5, 0))

        # Світліший фон для строки пошуку для контрасту
        se_frame = tk.Frame(row1, bg="#2a2a2a") 
        se_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        s_icon = tk.Label(se_frame, text="🔍", bg="#2a2a2a", fg="gray", font=("Segoe UI Emoji", 14))
        s_icon.pack(side="left", padx=5)
        
        se = tk.Entry(se_frame, textvariable=self.ai_search_var, bg="#2a2a2a", fg="gray",
                     insertbackground="white", font=("Arial", 12), relief="flat", bd=0)
        se.insert(0, placeholder)
        se.pack(side="left", fill="both", expand=True, padx=5, pady=4)
        self.ai_search_entry = se
        
        def on_search_focus_in(e):
            if se.get() == placeholder:
                se.delete(0, 'end')
                se.config(fg="white")
                
        def on_search_focus_out(e):
            if not se.get():
                se.insert(0, placeholder)
                se.config(fg="gray")

        se.bind("<FocusIn>", on_search_focus_in)
        se.bind("<FocusOut>", on_search_focus_out)

        # Відступ між строкою 1 і 2
        tk.Frame(fb, height=2, bg="#111").pack(side="top", fill="x")

        # Строка 2: Рівні + Класи
        row3 = tk.Frame(fb, bg="#1a1a1a", height=46)
        row3.pack(side="top", fill="x", pady=2, padx=4)
        row3.pack_propagate(False)
        
        tier_f = tk.Frame(row3, bg="#1a1a1a")
        tier_f.pack(side="left", fill="y", expand=False, padx=(1, 2))
        tier_f.rowconfigure(0, weight=1)
        
        roman_tiers = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
        for t in range(1, 12):
            text_t = roman_tiers[t-1]
            btn = tk.Label(tier_f, text=text_t, bg="#333333", fg="#aaaaaa", 
                           cursor="hand2", font=("Arial", 12, "bold"), width=3)
            btn.bind("<Button-1>", lambda e, x=t: self.toggle_tier_filter(x))
            btn.grid(row=0, column=t-1, sticky="nsew", padx=1)
            self.tier_filters[t] = {"btn": btn, "active": False}
        for i in range(11): tier_f.columnconfigure(i, weight=1, uniform="eq2")

        class_f = tk.Frame(row3, bg="#1a1a1a")
        class_f.pack(side="left", fill="both", expand=True, padx=(1, 2))
        class_f.rowconfigure(0, weight=1)

        xvm_classes = {"LT": chr(0x3A), "MT": chr(0x3B), "HT": chr(0x3F), "TD": chr(0x2E), "SPG": chr(0x2D)}
        classes = ["LT", "MT", "HT", "TD", "SPG"]
        for i, c in enumerate(classes):
            sym = xvm_classes.get(c, "?")
            btn = tk.Label(class_f, text=sym, font=("XVMSymbol", 30), fg="#aaaaaa", bg="#333333", cursor="hand2")
            btn.bind("<Button-1>", lambda e, x=c: self.toggle_class_filter(x))
            btn.grid(row=0, column=i, sticky="nsew", padx=1)
            class_f.columnconfigure(i, weight=1, uniform="eq2")
            self.class_filters[c] = {"btn": btn, "active": False}

        # Відступ між строкою 2 і 3
        tk.Frame(fb, height=2, bg="#111").pack(side="top", fill="x")

        # Строка 3: Прапори на всю ширину
        row2 = tk.Frame(fb, bg="#1a1a1a", height=46)
        row2.pack(side="top", fill="x", pady=2)
        row2.pack_propagate(False)

        nf = tk.Frame(row2, bg="#1a1a1a")
        nf.pack(side="left", fill="both", expand=True, padx=5)

        nl = ["USA", "USSR", "Germany", "France", "UK", "China", "Japan", "Czech", "Poland", "Sweden", "Italy"]
        fm = {"USA": "usa", "USSR": "ussr", "Germany": "germany", "France": "france", "UK": "uk",
              "China": "china", "Japan": "japan", "Czech": "czech", "Poland": "poland", "Sweden": "sweden", "Italy": "italy"}

        flag_size = (38, 25)  # 54x36 reduced by ~30%
        for i, n in enumerate(nl):
            fn = fm.get(n)
            img = None
            fp = os.path.join("extracted_icons", "clean_nations", f"{fn}.png")
            if os.path.exists(fp):
                fi = Image.open(fp).convert("RGBA").resize(flag_size, Image.LANCZOS)
            else:
                fallback = os.path.join("extracted_icons", "nations", f"{fn}.png")
                fi = Image.open(fallback).convert("RGBA").resize(flag_size, Image.LANCZOS) if os.path.exists(fallback) else Image.new("RGBA", flag_size)

            img = ImageTk.PhotoImage(fi)
            self.filter_icons[f"f_n_{n}"] = img
            btn = tk.Label(nf, image=img if img else None, text="" if img else n[:2], bg="#333333", cursor="hand2")
            btn.bind("<Button-1>", lambda e, x=n: self.toggle_nation_filter(x))
            btn.grid(row=0, column=i, sticky="nsew", padx=1)
            nf.columnconfigure(i, weight=1, uniform="eq_nf")
            nf.rowconfigure(0, weight=1)
            self.nation_filters[n] = {"btn": btn, "active": False}
        
        # Контейнер для прогрес-бару (завжди запакований)
        self.progress_container = tk.Frame(fb, height=4, bg="#0a0a0a")
        self.progress_container.pack(side="top", fill="x")
        self.progress_container.pack_propagate(False)
        
        # Canvas для прогрес-бару (спочатку не запакований)
        self.filter_progress_canvas = tk.Canvas(self.progress_container, height=4, bg="#0a0a0a", highlightthickness=0)
        self._progress_rect = self.filter_progress_canvas.create_rectangle(0, 0, 0, 4, fill="#ff4500", outline="")
        
        # ОСНОВНА ЗОНА: СІТКА
        self.ai_grid_container = tk.Frame(self.ai_frame, bg="#000")
        self.ai_grid_container.pack(side="top", fill="both", expand=True)

        self.ai_canvas = tk.Canvas(self.ai_grid_container, bg="#000", highlightthickness=0)
        self.ai_scrollbar = ttk.Scrollbar(self.ai_grid_container, orient="vertical", command=self.ai_canvas.yview, style="Dark.Vertical.TScrollbar")

        self.ai_grid_frame = tk.Frame(self.ai_canvas, bg="#000", padx=0.5, pady=0.5)
        self.ai_canvas_window = self.ai_canvas.create_window((0, 0), window=self.ai_grid_frame, anchor="nw")
        self.ai_canvas.configure(yscrollcommand=self.ai_scrollbar.set)
        
        # Обробник прокрутки колесиком миші для всього режиму AI Stats.
        def _wheel_units(event):
            if getattr(event, "delta", 0):
                return int(-1 * (event.delta / 120))
            if getattr(event, "num", 0) == 4:
                return -1
            if getattr(event, "num", 0) == 5:
                return 1
            return 0

        def _on_ai_mousewheel(event):
            if self.main_app.active_view != "ai_stats":
                return
            units = _wheel_units(event)
            if units == 0:
                return
            if self.active_tank:
                self.detail_canvas.yview_scroll(units, "units")
            else:
                self.ai_canvas.yview_scroll(units, "units")

        self.ai_canvas.bind_all("<MouseWheel>", _on_ai_mousewheel)
        self.ai_canvas.bind_all("<Button-4>", _on_ai_mousewheel)
        self.ai_canvas.bind_all("<Button-5>", _on_ai_mousewheel)
        
        def _on_canvas_resize(event):
            self.ai_canvas.coords(self.ai_canvas_window, 0, 0)
            self.ai_canvas.itemconfig(self.ai_canvas_window, width=event.width)
            new_max_cols = max(1, event.width // 171)
            if self._last_cols != new_max_cols:
                self._last_cols = new_max_cols
                if self.active_tank is not None or True: # always refresh on resize to handle grid
                    self.refresh_ai_view()

        self.ai_canvas.bind("<Configure>", _on_canvas_resize)
        
        self.ai_canvas.pack(side="left", fill="both", expand=True)
        self.ai_scrollbar.pack(side="right", fill="y")
        self.ai_grid_frame.bind("<Configure>", lambda e: self.ai_canvas.configure(scrollregion=self.ai_canvas.bbox("all")))
        
        # Вікно результату — скролюємо весь вміст
        self.ai_res_f = tk.Frame(self.ai_frame, bg="#111111")
        
        # Скролюючий canvas для деталей танка
        self.detail_canvas = tk.Canvas(self.ai_res_f, bg="#111111", highlightthickness=0)
        self.detail_scroll = ttk.Scrollbar(self.ai_res_f, orient="vertical",
                                           command=self.detail_canvas.yview,
                                           style="Dark.Vertical.TScrollbar")
        self.detail_inner = tk.Frame(self.detail_canvas, bg="#111111")
        self.detail_canvas_win = self.detail_canvas.create_window((0,0), window=self.detail_inner, anchor="nw")
        self.detail_canvas.configure(yscrollcommand=self.detail_scroll.set)
        self.detail_inner.bind("<Configure>", lambda e: self.detail_canvas.configure(
            scrollregion=self.detail_canvas.bbox("all")))
        self.detail_canvas.bind("<Configure>", self._on_detail_canvas_resize)
        self.detail_canvas.pack(side="left", fill="both", expand=True)
        self.detail_scroll.pack(side="right", fill="y")
        
        # Назва: пряме пакування в detail_inner
        self.ai_title_frame = tk.Frame(self.detail_inner, bg="#111111")
        self.ai_title_frame.pack(side="top", anchor="center", pady=(2, 2))

        # Зображення танка: використовується в блоці ТТХ (ліворуч),
        # окремо під заголовком більше не показується.
        self.ai_image_frame = tk.Frame(self.detail_inner, bg="#111111")
        self.ai_tank_icon_lf = tk.Label(self.ai_image_frame, bg="#111111")

        # Контент-панель деталей: компактна центральна колонка, 500 px.
        self.ai_content_panel = tk.Frame(self.detail_inner, bg="#111111")
        self.ai_content_panel.pack(side="top", fill="x", padx=10, pady=(0, 5))
        self.ai_content_panel.grid_columnconfigure(0, weight=1)
        self.ai_content_panel.grid_columnconfigure(1, weight=0, minsize=self._detail_compact_max_width)
        self.ai_content_panel.grid_columnconfigure(2, weight=1)

        if self._layout_debug:
            self.ai_title_frame.configure(highlightthickness=1, highlightbackground="#ff6868")
            self.ai_image_frame.configure(highlightthickness=1, highlightbackground="#58c7ff")
            self.ai_tank_icon_lf.configure(highlightthickness=1, highlightbackground="#d7ff5f")
            self.ai_content_panel.configure(highlightthickness=1, highlightbackground="#ffb347")

        self.ai_tth_frame = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_top_loadout_row = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_equipment_frame = tk.Frame(self.ai_top_loadout_row, bg="#111111")
        self.ai_ammo_frame = tk.Frame(self.ai_top_loadout_row, bg="#111111")
        self.ai_consumables_frame = tk.Frame(self.ai_top_loadout_row, bg="#111111")
        # Row 2 - without headers
        self.ai_top_loadout_row_2 = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_equipment_frame_2 = tk.Frame(self.ai_top_loadout_row_2, bg="#111111")
        self.ai_ammo_frame_2 = tk.Frame(self.ai_top_loadout_row_2, bg="#111111")
        self.ai_consumables_frame_2 = tk.Frame(self.ai_top_loadout_row_2, bg="#111111")
        self.ai_crew_frame = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_field_mod_frame = tk.Frame(self.ai_content_panel, bg="#111111")
        
        self.refresh_ai_view()

    def _on_detail_canvas_resize(self, event):
        self.detail_canvas.itemconfig(self.detail_canvas_win, width=event.width)
        self._reflow_detail_layout(event.width)

    def _reflow_detail_layout(self, width=None):
        if width is None and hasattr(self, 'detail_canvas'):
            width = self.detail_canvas.winfo_width()
        if width is None:
            return

        # Keep detail center column fixed regardless of current window width.
        compact_w = self._detail_compact_max_width
        self.ai_content_panel.grid_columnconfigure(1, minsize=compact_w)
        
        # Configure row constraints to allow proper sizing
        self.ai_content_panel.grid_rowconfigure(0, weight=0)  # TTH (fixed height based on content)
        self.ai_content_panel.grid_rowconfigure(1, weight=0)  # Top row (fixed height)
        self.ai_content_panel.grid_rowconfigure(2, weight=0)  # Crew (fixed height)
        self.ai_content_panel.grid_rowconfigure(3, weight=0)  # Field mods (fixed height)

        sections = [
            self.ai_tth_frame,
            self.ai_top_loadout_row,
            self.ai_top_loadout_row_2,
            self.ai_crew_frame,
            self.ai_field_mod_frame,
        ]

        for sec in sections:
            sec.grid_forget()

        for idx, sec in enumerate(sections):
            if idx == 1:
                sec.grid(row=idx, column=1, sticky="nsew", padx=0, pady=(0, 0))
            elif idx == 2:
                sec.grid(row=idx, column=1, sticky="nsew", padx=0, pady=(0, 0))
            else:
                sec.grid(row=idx, column=1, sticky="nsew", padx=0, pady=(0, 8))

        # Hard-fixed widths in px for stable layout regardless of parent resize.
        fixed_w = min(self._detail_info_fixed_width, compact_w)
        self.ai_tth_frame.configure(width=fixed_w)
        self.ai_top_loadout_row.configure(width=fixed_w)
        self.ai_top_loadout_row_2.configure(width=fixed_w)
        self.ai_crew_frame.configure(width=fixed_w)
        self.ai_field_mod_frame.configure(width=fixed_w)
        self.ai_tth_frame.grid_propagate(False)
        # Don't use grid_propagate on loadout row - let it grow with content
        self.ai_crew_frame.grid_propagate(False)
        self.ai_field_mod_frame.grid_propagate(False)

        # Top row order: equipment -> ammo -> consumables.
        self.ai_equipment_frame.grid_forget()
        self.ai_ammo_frame.grid_forget()
        self.ai_consumables_frame.grid_forget()
        self.ai_top_loadout_row.grid_columnconfigure(0, weight=0)  # column for number
        self.ai_top_loadout_row.grid_columnconfigure(1, weight=1)  # equipment
        self.ai_top_loadout_row.grid_columnconfigure(2, weight=1)  # ammo
        self.ai_top_loadout_row.grid_columnconfigure(3, weight=1)  # consumables
        self.ai_equipment_frame.grid(row=0, column=1, sticky="ew", padx=(0, 2))
        self.ai_ammo_frame.grid(row=0, column=2, sticky="ew", padx=(1, 1))
        self.ai_consumables_frame.grid(row=0, column=3, sticky="ew", padx=(2, 0))

        # Номер варіанту "1" зліва від трьох секцій (тільки якщо ще не створено)
        existing_num = getattr(self, '_loadout_num_label', None)
        if existing_num is None or not existing_num.winfo_exists():
            self._loadout_num_label = tk.Label(self.ai_top_loadout_row, text="1", font=("Arial", 10, "bold"), fg="#666666", bg="#111111")
            self._loadout_num_label.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(5, 3), pady=(45, 0))

        # Row 2 - layout (without headers)
        self.ai_top_loadout_row_2.configure(width=fixed_w)
        self.ai_equipment_frame_2.grid_forget()
        self.ai_ammo_frame_2.grid_forget()
        self.ai_consumables_frame_2.grid_forget()
        self.ai_top_loadout_row_2.grid_columnconfigure(0, weight=0)  # column for number
        self.ai_top_loadout_row_2.grid_columnconfigure(1, weight=1)  # equipment
        self.ai_top_loadout_row_2.grid_columnconfigure(2, weight=1)  # ammo
        self.ai_top_loadout_row_2.grid_columnconfigure(3, weight=1)  # consumables
        self.ai_equipment_frame_2.grid(row=0, column=1, sticky="ew", padx=(0, 2))
        self.ai_ammo_frame_2.grid(row=0, column=2, sticky="ew", padx=(1, 1))
        self.ai_consumables_frame_2.grid(row=0, column=3, sticky="ew", padx=(2, 0))

        # Номер варіанту "2" зліва (тільки якщо ще не створено)
        existing_num_2 = getattr(self, '_loadout_num_label_2', None)
        if existing_num_2 is None or not existing_num_2.winfo_exists():
            self._loadout_num_label_2 = tk.Label(self.ai_top_loadout_row_2, text="2", font=("Arial", 10, "bold"), fg="#666666", bg="#111111")
            self._loadout_num_label_2.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(5, 3), pady=(5, 0))

    def _layout_tile_grid(self, container, slots, min_cell=68, gap=0, stretch=False):
        if not slots:
            return
        width = max(1, container.winfo_width())
        cols = max(1, width // min_cell)
        for s in slots:
            s.grid_forget()
            if self._sections_debug:
                s.configure(highlightthickness=1, highlightbackground="#4a4a4a")
        for i, s in enumerate(slots):
            r = i // cols
            c = i % cols
            s.grid(row=r, column=c, padx=gap, pady=gap, sticky="nw")
        for c in range(cols):
            container.columnconfigure(c, weight=1 if stretch else 0)

    def _layout_tile_row(self, container, slots, gap=0):
        """Укладає всі плитки в один рядок без обгортання"""
        if not slots:
            return
        for s in slots:
            s.grid_forget()
        for i, s in enumerate(slots):
            s.grid(row=0, column=i, padx=gap, pady=0, sticky="nw")
            container.columnconfigure(i, weight=0)

    def _layout_pair_tiles_wrap(self, container, slots, pair_gap=8, row_gap=4):
        """Переносить елементи-пари по рядках; всередині пари відступи задаються у самій парі."""
        if not slots:
            return
        container.update_idletasks()
        width = max(1, container.winfo_width())
        pair_w = max((s.winfo_reqwidth() for s in slots), default=1)
        # +pair_gap закладаємо як міжпарний інтервал.
        cols = max(1, width // max(1, pair_w + pair_gap))

        for s in slots:
            s.grid_forget()

        for i, s in enumerate(slots):
            r = i // cols
            c = i % cols
            padx = (0, pair_gap if c < cols - 1 else 0)
            s.grid(row=r, column=c, padx=padx, pady=(0, row_gap), sticky="nw")
            container.columnconfigure(c, weight=0)

    def _make_tiles_section(self, parent, title, icon_key):
        if self._sections_debug:
            parent.configure(highlightthickness=1, highlightbackground="#505050")
        self._make_section_header(parent, title, self._get_section_icon(icon_key))
        body = tk.Frame(parent, bg="#111111")
        if self._sections_debug:
            body.configure(highlightthickness=1, highlightbackground="#3f3f3f")
        body.pack(side="top", fill="x", pady=3)
        return body

    def toggle_tier_filter(self, t):
        self._show_grid_if_needed()
        was_active = self.tier_filters[t]["active"]
        for key, item in self.tier_filters.items():
            item["active"] = False
            item["btn"].config(bg="#333333", fg="#aaaaaa")
        if not was_active:
            self.tier_filters[t]["active"] = True
            self.tier_filters[t]["btn"].config(bg="#444444", fg="#ffffff")
        # Show progress bar
        if not self._filter_active:
            self._filter_active = True
            self.filter_progress_canvas.pack(fill="both", expand=True)
            self.filter_progress_canvas.update_idletasks()
        self.filter_progress_canvas.coords(self._progress_rect, 0, 0, 0, 4)
        # DO THE WORK (collect filtered items)
        items_to_show, is_default = self._collect_filtered_items()
        # Fill progress bar to 100% (simulate during work)
        try:
            canvas_width = self.filter_progress_canvas.winfo_width()
            if canvas_width > 1:
                self.filter_progress_canvas.coords(self._progress_rect, 0, 0, canvas_width, 4)
                self.filter_progress_canvas.update_idletasks()
        except Exception:
            pass
        # Don't show new page yet! Animation callback will do it.
        # Store items for the callback.
        self._filter_items_to_show = items_to_show
        # Start animation (2 seconds) - progress bar fills during this time.
        # The callback will show the new page when animation completes.
        self._animate_realtime(2.0, lambda: self._finish_filter_with_items(self._filter_items_to_show))
        
    def _do_filter_work(self):
        """Collect filtered items and store them for the callback."""
        items_to_show, is_default = self._collect_filtered_items()
        self._filter_items_to_show = items_to_show
        # Do NOT call callback here. Let the animation callback handle it.
        # The callback will use self._filter_items_to_show.
        pass
        
    def toggle_class_filter(self, c):
        self._show_grid_if_needed()
        was_active = self.class_filters[c]["active"]
        for key, item in self.class_filters.items():
            item["active"] = False
            item["btn"].config(bg="#333333", fg="#aaaaaa")
        if not was_active:
            self.class_filters[c]["active"] = True
            self.class_filters[c]["btn"].config(bg="#444444", fg="#ffffff")
        # Show progress bar instead of loading screen
        if not self._filter_active:
            self._filter_active = True
            self.filter_progress_canvas.pack(fill="both", expand=True)
        self.filter_progress_canvas.coords(self._progress_rect, 0, 0, 0, 4)
        # Measure filtering time
        start = time.time()
        items_to_show, is_default = self._collect_filtered_items()
        elapsed = time.time() - start
        duration = max(elapsed, 0.5)  # at least 0.5 seconds
        # Start realtime animation
        self._animate_realtime(duration, lambda: self._finish_filter_with_items(items_to_show))
        
    def toggle_nation_filter(self, n):
        self._show_grid_if_needed()
        was_active = self.nation_filters[n]["active"]
        for key, item in self.nation_filters.items():
            item["active"] = False
            item["btn"].config(bg="#333333")
        if not was_active:
            self.nation_filters[n]["active"] = True
            self.nation_filters[n]["btn"].config(bg="#444444")
        # Show progress bar instead of loading screen
        if not self._filter_active:
            self._filter_active = True
            self.filter_progress_canvas.pack(fill="both", expand=True)
        self.filter_progress_canvas.coords(self._progress_rect, 0, 0, 0, 4)
        # Measure filtering time
        start = time.time()
        items_to_show, is_default = self._collect_filtered_items()
        elapsed = time.time() - start
        duration = max(elapsed, 0.5)  # at least 0.5 seconds
        # Start realtime animation
        self._animate_realtime(duration, lambda: self._finish_filter_with_items(items_to_show))
        
    def show_loading_screen(self):
        self.loading_frame = tk.Frame(self.ai_grid_container, bg="black")
        self.loading_canvas = tk.Canvas(self.loading_frame, bg="black", highlightthickness=0)
        self.loading_canvas.pack(fill="both", expand=True)
        # Center content
        self.loading_canvas.update_idletasks()
        w = self.loading_canvas.winfo_width() or 400
        h = self.loading_canvas.winfo_height() or 300
        if self.main_app.logo_splash:
            self.loading_canvas.create_image(w//2, h//2 - 20, image=self.main_app.logo_splash)
        text = self.locale_manager.t_ui("loading", "Завантаження...") if self.locale_manager else "Завантаження..."
        self.loading_canvas.create_text(w//2, h - 46, text=text, fill="#bbbbbb", font=("Arial", 12))
        self.loading_frame.pack(side="top", fill="both", expand=True)

    def hide_loading_screen(self):
        if hasattr(self, 'loading_frame'):
            self.loading_frame.pack_forget()

    def get_small_flag(self, nation):
        cache_key = f"small_flag_{nation}"
        if cache_key in self.composite_cache: return self.composite_cache[cache_key]
        flag_map = {"USA": "usa", "USSR": "ussr", "Germany": "germany", "France": "france", "UK": "uk", 
                    "China": "china", "Japan": "japan", "Czech": "czech", "Poland": "poland", "Sweden": "sweden", "Italy": "italy"}
        f_name = flag_map.get(nation, nation.lower())
        flag_path = os.path.join("extracted_icons", "clean_nations", f"{f_name}.png")
        if not os.path.exists(flag_path):
            flag_path = None
            for p in [f"{f_name}_160x100.png", f"{f_name}_155x31.png", f"{f_name}_131x31.png"]:
                test_p = os.path.join("extracted_icons", "nations", p)
                if os.path.exists(test_p):
                    flag_path = test_p
                    break
        if flag_path:
            try:
                img = Image.open(flag_path).convert("RGBA").resize((26, 17), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.composite_cache[cache_key] = photo
                return photo
            except: pass
        return None

    def get_composite_icon(self, tag, nation, size=(170, 120)):
        cache_key = f"{tag}_v5_{size[0]}x{size[1]}"
        if cache_key in self.composite_cache: return self.composite_cache[cache_key]
        try:
            nl = nation.lower()
            tag_u = tag.replace('-', '_')
            tag_l = tag_u.lower()
            
            tests = [
                f"{tag}.png", f"{tag_u}.png", f"{tag_l}.png",
                f"{nl}-{tag}.png", f"{nl}-{tag_u}.png", f"{nl}-{tag_l}.png"
            ]
            tank_path = None
            for p in tests:
                fp = os.path.join("extracted_icons", p)
                if os.path.exists(fp):
                    tank_path = fp
                    break
            
            if not tank_path: return None
            tank_img = Image.open(tank_path).convert("RGBA")
            # Trim transparent padding from source icon so visual centering is accurate.
            bbox = tank_img.getbbox()
            if bbox:
                tank_img = tank_img.crop(bbox)

            card_w, card_h = size
            card = Image.new("RGBA", (card_w, card_h), (17, 17, 17, 255))
            work_w = int(card_w * 1.10)
            work_h = int(card_h * 1.10)
            
            if tank_img.width < 100:
                tank_img = tank_img.resize((round(tank_img.width * 1.5), round(tank_img.height * 1.5)), Image.NEAREST)
            else:
                tank_img = ImageOps.contain(tank_img, (work_w, work_h), Image.LANCZOS)
            
            y_top_margin = max(6, int(card_h * 0.08))
            base_y_offset = max(y_top_margin, (card_h - tank_img.height) // 2)
            y_offset = max(0, base_y_offset - self._detail_image_lift_px)
            card.paste(tank_img, ((card_w - tank_img.width)//2, y_offset), tank_img)

            if self._layout_debug:
                # Outer bounds + vertical guides for top margin and actual image start/end.
                dbg = ImageDraw.Draw(card)
                dbg.rectangle((0, 0, card_w - 1, card_h - 1), outline=(255, 96, 96, 255), width=2)
                dbg.line((0, y_top_margin, card_w - 1, y_top_margin), fill=(255, 210, 70, 255), width=1)
                dbg.line((0, y_offset, card_w - 1, y_offset), fill=(90, 220, 255, 255), width=1)
                img_bottom = min(card_h - 1, y_offset + tank_img.height - 1)
                dbg.line((0, img_bottom, card_w - 1, img_bottom), fill=(120, 255, 120, 255), width=1)

            mask = Image.new("L", (card_w, card_h), 0)
            radius = max(10, int(min(card_w, card_h) * 0.08))
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w, card_h), radius=radius, fill=255)
            card.putalpha(mask)

            photo = ImageTk.PhotoImage(card)
            self.composite_cache[cache_key] = photo
            return photo
        except Exception as e:
            print(f"Error drawing card: {e}")
            return None

    def refresh_ai_view(self):
        if not hasattr(self, 'ai_grid_frame'): return
        for widget in self.ai_grid_frame.winfo_children(): widget.destroy()

        search_q = self._parse_search_query()
        active_t, active_c, active_n = self._active_filter_values()
        row, col = 0, 0
        max_cols = self._last_cols if self._last_cols > 0 else 5
        
        is_default = not search_q and not active_t and not active_c and not active_n
        items_to_show = []
        if is_default:
            for tag in self.popular_tanks:
                if tag in self.tank_db: items_to_show.append((tag, self.tank_db[tag]))
                
            target_rows = max(1, round(20 / max_cols))
            target_count = target_rows * max_cols
            
            if len(items_to_show) > target_count:
                items_to_show = items_to_show[:target_count]
            elif len(items_to_show) < target_count:
                for tag, data in self.tank_db.items():
                    if len(items_to_show) >= target_count: break
                    if tag not in self.popular_tanks:
                        items_to_show.append((tag, data))
        else:
            for tag, data in self.tank_db.items():
                if not isinstance(data, dict):
                    continue
                data_name = str(data.get("name", "")).casefold()
                data_tag = str(tag).casefold()
                data_tier = self._normalize_tier(data.get("tier"))
                data_class = self._normalize_class(data.get("class"))
                data_nation = self._normalize_nation(data.get("nation"))

                if search_q and search_q not in data_name and search_q not in data_tag: continue
                if active_t and data_tier not in active_t: continue
                if active_c and data_class not in active_c: continue
                if active_n and data_nation not in active_n: continue
                items_to_show.append((tag, data))
            
            def _tier_sort(item):
                d = item[1] if isinstance(item[1], dict) else {}
                try:
                    return int(d.get("tier", 0) or 0)
                except Exception:
                    return 0
            items_to_show.sort(key=_tier_sort, reverse=True)
            
        for tag, data in items_to_show:
            if not isinstance(data, dict):
                continue
            card_f = tk.Frame(self.ai_grid_frame, bg="#111", width=170, height=155)
            card_f.grid(row=row, column=col, sticky="nsew", padx=0.5, pady=0.5)
            card_f.grid_propagate(False) 
            
            nation = data.get("nation", "Unknown")
            img = self.get_composite_icon(tag, nation)
            card_f.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))

            if img:
                lbl = tk.Label(card_f, image=img, bg="#111", cursor="hand2", bd=0)
                lbl.place(relx=0.5, y=0, width=170, height=120, anchor="n")
                lbl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
                
            is_prem = data.get("is_premium", False)
            accent_color = "#e09b1b" if is_prem else "#bbbbbb"

            l1_f = tk.Frame(card_f, bg="#111")
            l1_f.place(relx=0.5, y=133, anchor="s")
            
            roman_tiers = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
            try:
                tier_num = int(data.get('tier', 0) or 0)
            except Exception:
                tier_num = 0
            rt = roman_tiers[tier_num - 1] if 1 <= tier_num <= 11 else str(tier_num)
            tl = tk.Label(l1_f, text=rt, font=("Arial", 12, "bold"), fg=accent_color, bg="#111", bd=0)
            tl.pack(side="left", padx=3)
            
            s_flag = self.get_small_flag(nation)
            if s_flag:
                fl = tk.Label(l1_f, image=s_flag, bg="#111", bd=0)
                fl.pack(side="left", padx=3)
                fl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            
            xvm_classes = {"LT": chr(0x3A), "MT": chr(0x3B), "HT": chr(0x3F), "TD": chr(0x2E), "SPG": chr(0x2D)}
            sym = xvm_classes.get(str(data.get('class', '')).upper(), "?")
            cl = tk.Label(l1_f, text=sym, font=("XVMSymbol", 17), fg=accent_color, bg="#111", bd=0)
            cl.pack(side="left", padx=3)
            
            raw_name = str(data.get("name", tag)).replace("_", " ")
            sys_id = tag.split('_')[0].lower()
            
            m = re.match(r'^([a-z]+)(\d*)$', sys_id)
            if m:
                letters, digits = m.groups()
                country_codes = {"gb", "uk", "usa", "ussr", "ger", "fr", "ch", "cz", "pl", "swe", "it", "jp", "cn", "r", "a", "g", "f", "s", "j"}
                if letters in country_codes:
                    rn_low = raw_name.lower()
                    if rn_low.startswith(sys_id + " "):
                        raw_name = raw_name[len(sys_id):].strip()
                    elif digits and rn_low.startswith(f"{letters} {digits} "):
                        raw_name = raw_name[len(letters) + len(digits) + 1:].strip()
                    elif rn_low.startswith(letters + " "):
                        raw_name = raw_name[len(letters):].strip()

            name_words = raw_name.split()
            if not name_words:
                name_words = [data["name"]]

            disp_name = ""
            for w in name_words:
                if len(disp_name) + len(w) <= 22:
                    disp_name += w + " "
                else:
                    break
            disp_name = disp_name.strip() if disp_name else name_words[0][:20]

            text_color = "#e09b1b" if is_prem else "#bbbbbb"
            nl = tk.Label(card_f, text=disp_name, bg="#111", fg=text_color, font=("Arial", 9, "bold"))
            nl.place(relx=0.5, y=152, anchor="s")
            
            tl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            cl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            nl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            l1_f.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))

            col += 1
            if col >= max_cols: col = 0; row += 1

        for c in range(max_cols):
            self.ai_grid_frame.columnconfigure(c, weight=1)
        # Очищуємо попередні ваги, якщо кількість колонок зменшилась
        for c in range(max_cols, max_cols + 15):
            self.ai_grid_frame.columnconfigure(c, weight=0)
        
    def _collect_filtered_items(self):
        """Collect filtered items WITHOUT modifying UI. Returns (items_to_show, is_default)."""
        search_q = self._parse_search_query()
        active_t, active_c, active_n = self._active_filter_values()
        max_cols = self._last_cols if self._last_cols > 0 else 5
        
        is_default = not search_q and not active_t and not active_c and not active_n
        items_to_show = []
        
        if is_default:
            for tag in self.popular_tanks:
                if tag in self.tank_db: items_to_show.append((tag, self.tank_db[tag]))
            
            target_rows = max(1, round(20 / max_cols))
            target_count = target_rows * max_cols
            
            if len(items_to_show) > target_count:
                items_to_show = items_to_show[:target_count]
            elif len(items_to_show) < target_count:
                for tag, data in self.tank_db.items():
                    if len(items_to_show) >= target_count: break
                    if tag not in self.popular_tanks:
                        items_to_show.append((tag, data))
        else:
            for tag, data in self.tank_db.items():
                if not isinstance(data, dict):
                    continue
                data_name = str(data.get("name", "")).casefold()
                data_tag = str(tag).casefold()
                data_tier = self._normalize_tier(data.get("tier"))
                data_class = self._normalize_class(data.get("class"))
                data_nation = self._normalize_nation(data.get("nation"))
                
                if search_q and search_q not in data_name and search_q not in data_tag: continue
                if active_t and data_tier not in active_t: continue
                if active_c and data_class not in active_c: continue
                if active_n and data_nation not in active_n: continue
                items_to_show.append((tag, data))
            
            def _tier_sort(item):
                d = item[1] if isinstance(item[1], dict) else {}
                try:
                    return int(d.get("tier", 0) or 0)
                except Exception:
                    return 0
            items_to_show.sort(key=_tier_sort, reverse=True)
        
        return items_to_show, is_default
    
    def _finish_filter_with_items(self, items_to_show):
        """Destroy old grid and build new one from filtered items (instant)."""
        # Destroy old grid
        for widget in self.ai_grid_frame.winfo_children(): widget.destroy()
        
        row, col = 0, 0
        max_cols = self._last_cols if self._last_cols > 0 else 5
        
        for tag, data in items_to_show:
            if not isinstance(data, dict):
                continue
            card_f = tk.Frame(self.ai_grid_frame, bg="#111", width=170, height=155)
            card_f.grid(row=row, column=col, sticky="nsew", padx=0.5, pady=0.5)
            card_f.grid_propagate(False)
            
            nation = data.get("nation", "Unknown")
            img = self.get_composite_icon(tag, nation)
            card_f.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            
            if img:
                lbl = tk.Label(card_f, image=img, bg="#111", cursor="hand2", bd=0)
                lbl.place(relx=0.5, y=0, width=170, height=120, anchor="n")
                lbl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
                
            is_prem = data.get("is_premium", False)
            accent_color = "#e09b1b" if is_prem else "#bbbbbb"
            
            l1_f = tk.Frame(card_f, bg="#111")
            l1_f.place(relx=0.5, y=133, anchor="s")
            
            roman_tiers = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
            try:
                tier_num = int(data.get('tier', 0) or 0)
            except Exception:
                tier_num = 0
            rt = roman_tiers[tier_num - 1] if 1 <= tier_num <= 11 else str(tier_num)
            tl = tk.Label(l1_f, text=rt, font=("Arial", 12, "bold"), fg=accent_color, bg="#111", bd=0)
            tl.pack(side="left", padx=3)
            
            s_flag = self.get_small_flag(nation)
            if s_flag:
                fl = tk.Label(l1_f, image=s_flag, bg="#111", bd=0)
                fl.pack(side="left", padx=3)
                fl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            
            xvm_classes = {"LT": chr(0x3A), "MT": chr(0x3B), "HT": chr(0x3F), "TD": chr(0x2E), "SPG": chr(0x2D)}
            sym = xvm_classes.get(str(data.get('class', '')).upper(), "?")
            cl = tk.Label(l1_f, text=sym, font=("XVMSymbol", 17), fg=accent_color, bg="#111", bd=0)
            cl.pack(side="left", padx=3)
            
            raw_name = str(data.get("name", tag)).replace("_", " ")
            sys_id = tag.split('_')[0].lower()
            
            m = re.match(r'^([a-z]+)(\d*)$', sys_id)
            if m:
                letters, digits = m.groups()
                country_codes = {"gb", "uk", "usa", "ussr", "ger", "fr", "ch", "cz", "pl", "swe", "it", "jp", "cn", "r", "a", "g", "f", "s", "j"}
                if letters in country_codes:
                    rn_low = raw_name.lower()
                    if rn_low.startswith(sys_id + " "):
                        raw_name = raw_name[len(sys_id):].strip()
                    elif digits and rn_low.startswith(f"{letters} {digits} "):
                        raw_name = raw_name[len(letters) + len(digits) + 1:].strip()
                    elif rn_low.startswith(letters + " "):
                        raw_name = raw_name[len(letters):].strip()
            
            name_words = raw_name.split()
            if not name_words:
                name_words = [data["name"]]
            
            disp_name = ""
            for w in name_words:
                if len(disp_name) + len(w) <= 22:
                    disp_name += w + " "
                else:
                    break
            disp_name = disp_name.strip() if disp_name else name_words[0][:20]
            
            text_color = "#e09b1b" if is_prem else "#bbbbbb"
            nl = tk.Label(card_f, text=disp_name, bg="#111", fg=text_color, font=("Arial", 9, "bold"))
            nl.place(relx=0.5, y=152, anchor="s")
            
            tl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            cl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            nl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            l1_f.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
            
            col += 1
            if col >= max_cols: col = 0; row += 1
        
        for c in range(max_cols):
            self.ai_grid_frame.columnconfigure(c, weight=1)
        for c in range(max_cols, max_cols + 15):
            self.ai_grid_frame.columnconfigure(c, weight=0)
        
        # Complete progress bar and hide
        try:
            canvas_width = self.filter_progress_canvas.winfo_width()
            if canvas_width > 1:
                self.filter_progress_canvas.coords(self._progress_rect, 0, 0, canvas_width, 4)
        except Exception:
            pass
        # Hide progress bar after delay
        if self._filter_hide_job is not None:
            self.root.after_cancel(self._filter_hide_job)
        self._filter_hide_job = self.root.after(300, self._hide_filter_progress)
    
    def _animate_realtime(self, duration, callback):
        """Animate progress bar based on real time (duration in seconds)"""
        if not self._filter_active:
            return
        start_time = time.time()
        def update():
            if not self._filter_active:
                return
            elapsed = time.time() - start_time
            if elapsed >= duration:
                # Animation complete, call callback
                if callback:
                    callback()
                return
            progress = elapsed / duration
            try:
                canvas_width = self.filter_progress_canvas.info_width()
                if canvas_width > 1:
                    progress_width = int(canvas_width * progress)
                    self.filter_progress_canvas.coords(self._progress_rect, 0, 0, progress_width, 4)
            except Exception:
                pass
            self.root.after(50, update)
        update()
        update()
    
    def _hide_filter_progress(self):
        """Hide progress bar (canvas) but keep container (reserved space)"""
        self._filter_active = False
        self._filter_hide_job = None
        if hasattr(self, 'filter_progress_canvas') and self.filter_progress_canvas.winfo_exists():
            self.filter_progress_canvas.pack_forget()
        # Reset rectangle to 0 width
        try:
            self.filter_progress_canvas.coords(self._progress_rect, 0, 0, 0, 4)
        except Exception:
            pass
        
    def return_to_ai_home(self):
        self.active_tank = None
        if hasattr(self, 'ai_res_f'): self.ai_res_f.pack_forget()
        if hasattr(self, 'ai_grid_container'): self.ai_grid_container.pack(side="top", fill="both", expand=True)
        # Cancel any pending search timer
        if self._search_timer is not None:
            self.root.after_cancel(self._search_timer)
            self._search_timer = None
        # Скидаємо всі фільтри та пошук
        self.ai_search_var.set(self.search_placeholder)
        for f in self.tier_filters.values(): f["active"] = False; f["btn"].config(bg="#333333", fg="#aaaaaa")
        for f in self.class_filters.values(): f["active"] = False; f["btn"].config(bg="#333333", fg="#aaaaaa")
        for f in self.nation_filters.values(): f["active"] = False; f["btn"].config(bg="#333333")
        self.refresh_ai_view()

    def get_loadout_icon(self, category, name, size=(40, 40)):
        """Повертає PhotoImage іконки обладнання/снаряда/навички"""
        cache_key = f"{category}_{name}_{size[0]}"
        if cache_key in self.loadout_icon_cache:
            return self.loadout_icon_cache[cache_key]

        candidates = []
        if category == 'field_mods':
            # Prefer original client icons (pairModifications/80x80).
            candidates.extend([
                os.path.join(self.FIELD_MODS_ORIGINAL_DIR, f"{name}.png"),
                os.path.join(self.FIELD_MODS_ORIGINAL_DIR, f"{name.lower()}.png"),
            ])

        base_dir = os.path.join(self.LOADOUT_ICON_DIR, category)
        candidates.extend([
            os.path.join(base_dir, f"{name}.png"),
            os.path.join(base_dir, f"{name.lower()}.png"),
        ])

        icon_path = next((p for p in candidates if os.path.exists(p)), None)
        if not icon_path:
            return None
        try:
            img = Image.open(icon_path).convert("RGBA")
            # Keep native icon look: crop transparent margins and fit into square without stretching.
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            # Scale to fit both up and down while preserving aspect ratio.
            scale = min(size[0] / max(1, img.width), size[1] / max(1, img.height))
            new_w = max(1, int(round(img.width * scale)))
            new_h = max(1, int(round(img.height * scale)))
            fitted = img.resize((new_w, new_h), Image.LANCZOS)
            x = (size[0] - fitted.width) // 2
            y = (size[1] - fitted.height) // 2
            canvas.paste(fitted, (x, y), fitted)
            img = canvas
            if category == 'crew_roles':
                alpha = img.split()[-1]
                gray = Image.new("RGBA", size, (154, 154, 154, 255))
                gray.putalpha(alpha)
                img = gray
            photo = ImageTk.PhotoImage(img)
            self.loadout_icon_cache[cache_key] = photo
            return photo
        except:
            return None

    def _get_section_icon(self, section, size=(18, 18)):
        """Іконка секції з fallback на tth, якщо loadout-іконок немає."""
        candidates = {
            "ammo": [
                ("ammo", "ARMOR_PIERCING"),
                ("ammo", "ARMOR_PIERCING_CR"),
            ],
            "consumables": [
                ("artefacts", "largeRepairkit"),
                ("artefacts", "handExtinguishers"),
            ],
            "equipment": [
                ("artefacts", "rammer"),
                ("artefacts", "coatedOptics"),
                ("artefacts", "aimingStabilizer"),
            ],
            "crew": [
                ("artefacts", "commander_sixthSense"),
                ("artefacts", "gunner_sniper"),
            ],
            "field_mod": [
                ("field_mods", "firepower_on"),
                ("field_mods", "mobility_on"),
            ],
        }
        for category, name in candidates.get(section, []):
            photo = self.get_loadout_icon(category, name, size=size)
            if photo:
                return photo

        tth_fallback = {
            "ammo": "relativePower.png",
            "consumables": "relativePower.png",
            "equipment": "relativeMobility.png",
            "crew": "relativeCamouflage.png",
            "field_mod": "relativeVisibility.png",
        }
        return self.get_tth_icon(tth_fallback.get(section), size=size)

    def _make_section_header(self, parent, title, icon_photo=None):
        """Рядок-заголовок секції"""
        hf = tk.Frame(parent, bg="#111111")
        hf.pack(side="top", fill="x", pady=(10, 3))
        tk.Frame(hf, height=1, bg="#333333").pack(side="top", fill="x")
        title_row = tk.Frame(hf, bg="#111111")
        title_row.pack(side="top", fill="x", padx=5, pady=2)
        if icon_photo:
            icon_lbl = tk.Label(title_row, image=icon_photo, bg="#111111")
            icon_lbl.image = icon_photo
            icon_lbl.pack(side="left", padx=(0, 4))
        tk.Label(title_row, text=title, fg="#666666", bg="#111111",
                 font=("Arial", 11), anchor="w").pack(side="left", fill="x")
        return hf

    def _find_tth_for_tag(self, tag):
        tth = self.tank_tth.get(tag)
        if isinstance(tth, dict) and tth:
            return tth

        # Явні alias-и для спец-варіантів/локальних розбіжностей тегів.
        tth_aliases = {
            "A14_T30": "A14_T30_FL",
            "R122_T44_100": "R122_T44_100B",
        }
        alias_key = tth_aliases.get(tag)
        if alias_key:
            alias_tth = self.tank_tth.get(alias_key)
            if isinstance(alias_tth, dict) and alias_tth:
                return alias_tth

        tag_l = str(tag).lower()
        tag_n = tag_l.replace('-', '_')

        def _get_tth_by_key(candidate_key):
            v = self.tank_tth.get(candidate_key)
            if isinstance(v, dict) and v:
                return v
            return None

        def _strip_mode_suffixes(s):
            suffixes = [
                "_storymode", "_7x7", "_fallout", "_fl", "_sh",
                "_igr", "_bootcamp", "_training", "_test",
            ]
            base = s
            changed = True
            while changed:
                changed = False
                for suf in suffixes:
                    if base.endswith(suf):
                        base = base[: -len(suf)]
                        changed = True
            return base

        # 1) Прямий/нормалізований пошук
        for key, value in self.tank_tth.items():
            key_l = str(key).lower()
            key_n = key_l.replace('-', '_')
            if (key_l == tag_l or key_n == tag_n) and isinstance(value, dict) and value:
                return value

        # 2) Спроба з обрізаними суфіксами режимів
        base_tag = _strip_mode_suffixes(tag_n)
        if base_tag != tag_n:
            for key, value in self.tank_tth.items():
                key_n = str(key).lower().replace('-', '_')
                if key_n == base_tag and isinstance(value, dict) and value:
                    return value

        # 3) Спроба з корекцією story-перепрефікса: G1037_x -> G37_x
        m_story = re.match(r'^([a-z]+)(\d{4})_(.+)$', base_tag)
        if m_story:
            pref, num4, rest = m_story.groups()
            try:
                num_val = int(num4)
                if num_val >= 1000:
                    candidate = f"{pref}{num_val - 1000}_{rest}"
                    for key, value in self.tank_tth.items():
                        key_n = str(key).lower().replace('-', '_')
                        if key_n == candidate and isinstance(value, dict) and value:
                            return value
            except Exception:
                pass

        suffix = tag_n.split("_", 1)[1] if "_" in tag_n else tag_n
        for key, value in self.tank_tth.items():
            key_l = str(key).lower().replace('-', '_')
            key_suffix = key_l.split("_", 1)[1] if "_" in key_l else key_l
            if key_suffix == suffix and isinstance(value, dict) and value:
                return value

        # 4) Fallback по назві: беремо інший тег з тією ж назвою танка
        current = self.tank_db.get(tag)
        if isinstance(current, dict):
            cur_name = str(current.get("name", "")).strip().casefold()
            if cur_name:
                for other_tag, other_data in self.tank_db.items():
                    if other_tag == tag or not isinstance(other_data, dict):
                        continue
                    if str(other_data.get("name", "")).strip().casefold() != cur_name:
                        continue
                    v = _get_tth_by_key(other_tag)
                    if v:
                        return v

        return {}

    def get_tth_icon(self, icon_name, size=(16, 16)):
        cache_key = f"{icon_name}_{size[0]}x{size[1]}"
        if cache_key in self.tth_icon_cache:
            return self.tth_icon_cache[cache_key]

        if not icon_name:
            return None
        icon_path = os.path.join(self.TTH_ICON_DIR, icon_name)
        if not os.path.exists(icon_path):
            return None
        try:
            img = Image.open(icon_path).convert("RGBA").resize(size, Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.tth_icon_cache[cache_key] = photo
            return photo
        except Exception:
            return None

    def _build_icon_row(self, parent, items):
        """Рядок з іконками (items = список (photo, label, tooltip))"""
        row = tk.Frame(parent, bg="#1a1a1a", pady=5)
        row.pack(side="top", fill="x", padx=0, pady=2)
        for photo, label_text, bg_color in items:
            slot = tk.Frame(row, bg="#222222", bd=1, relief="flat")
            slot.pack(side="left", padx=3)
            if photo:
                lbl = tk.Label(slot, image=photo, bg="#222222", padx=2, pady=2)
                lbl.pack()
            else:
                lbl = tk.Label(slot, text="?", fg="#555", bg="#222222",
                               font=("Arial", 10), width=3, height=2)
                lbl.pack()
            if label_text:
                tk.Label(slot, text=label_text, fg="#aaaaaa", bg="#222222",
                         font=("Arial", 7), anchor="center").pack(pady=(0,2))
        return row

    def _ammo_type_color(self, shell_type):
        colors = {
            'ARMOR_PIERCING': '#f0e060',
            'ARMOR_PIERCING_CR': '#f0c030',
            'HIGH_EXPLOSIVE': '#e05020',
            'HOLLOW_CHARGE': '#40c8e0',
            'ARMOR_PIERCING_HE': '#c060e0',
            'HIGH_EXPLOSIVE_MODERN': '#e07030',
        }
        for k, v in colors.items():
            if k == shell_type:
                return v
        return '#ffffff'

    def _ammo_icon_name(self, shell_type):
        """Повертає ім'я файлу іконки снаряда"""
        # Знайдемо найближчий файл
        ammo_dir = os.path.join(self.LOADOUT_ICON_DIR, 'ammo')
        if not os.path.exists(ammo_dir):
            return None
        # Прямий збіг
        direct = os.path.join(ammo_dir, f'{shell_type}.png')
        if os.path.exists(direct):
            return shell_type
        # Пошук найближчого
        files = os.listdir(ammo_dir)
        for f in files:
            if shell_type in f.replace('.png', ''):
                return f.replace('.png', '')
        return None

    def _extract_field_mod_tokens(self, tag):
        """Читає клієнтський *_modifications.xml і повертає KPI-токени в порядку появи."""
        cfg_path = os.path.join(
            os.path.dirname(__file__),
            'extracted_data',
            'common',
            'post_progression',
            'veh_skill_configs',
            f'{tag}_modifications.xml',
        )
        if not os.path.exists(cfg_path):
            return []

        try:
            raw = open(cfg_path, 'rb').read().decode('latin1', errors='ignore')
        except Exception:
            return []

        kpi_keys = [
            'enginePower', 'gunDispersion', 'gunStabilizationFromTurret', 'gunStabilizationFromHull',
            'hitPoints', 'hullTraverseSpeed', 'turretTraverseSpeed', 'turretTraverse',
            'specialShellPenetration', 'standardShellVelocity', 'allShellDamage', 'shellModuleDamage',
            'additionalShellAmmoCapacity', 'aimingTime', 'gunDepression', 'viewRange',
            'ammoRackHP', 'ammoRackPenalty', 'chassisHP', 'chassisRepairSpeed',
            'crewProtection', 'enginePenalty',
        ]

        pattern = '|'.join(re.escape(k) for k in kpi_keys)
        ordered = []
        for m in re.finditer(pattern, raw):
            token = m.group(0)
            if token not in ordered:
                ordered.append(token)
        return ordered

    def _load_field_mod_pairs_by_tank(self):
        """Завантажує готову мапу пар FIELD MODS по танках, згенеровану з Orion-декодування."""
        path = os.path.join(
            os.path.dirname(__file__),
            'extracted_data',
            'common',
            'post_progression',
            'field_mod_pairs_by_tank.json',
        )
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            pairs_by_tank = payload.get('pairs_by_tank', {}) if isinstance(payload, dict) else {}
            if not isinstance(pairs_by_tank, dict):
                return {}
            return pairs_by_tank
        except Exception:
            return {}

    def _field_mod_pair_limit_for_tier(self, tag):
        """Кількість пар польової модернізації, доступних для рівня танка."""
        data = self.tank_db.get(tag, {}) if isinstance(self.tank_db, dict) else {}
        try:
            tier = int((data or {}).get('tier', 0) or 0)
        except Exception:
            tier = 0

        if tier < 6:
            return 0
        if tier <= 8:
            return 3
        if tier == 9:
            return 4
        if tier == 10:
            return 5
        return 0

    def _field_mod_lookup_tags(self, tag):
        """Повертає кандидати тегів для пошуку пар (оригінал + базовий без суфіксів режимів)."""
        candidates = []
        raw = str(tag or "").strip()
        if not raw:
            return candidates
        candidates.append(raw)

        lowered = raw.lower()
        suffixes = [
            "_storymode", "_storymodehard", "_newonboarding", "_7x7",
            "_fl", "_igr", "_training", "_test",
        ]
        base = raw
        changed = True
        while changed:
            changed = False
            low_base = base.lower()
            for suf in suffixes:
                if low_base.endswith(suf):
                    base = base[: -len(suf)]
                    changed = True
                    break
        if base and base not in candidates:
            candidates.append(base)
        return candidates

    def _field_mod_icon_from_token(self, token):
        """Мапа KPI-токена клієнта -> реальна іконка pairModifications."""
        token_map = {
            'enginePower': 'improvedEnginePower',
            'gunDispersion': 'improvedAimingHandling',
            'aimingTime': 'improvedAimingHandling',
            'gunStabilizationFromTurret': 'improvedTurretRingStability',
            'gunStabilizationFromHull': 'improvedChassisStability',
            'hitPoints': 'reinforcedStructure',
            'chassisHP': 'reinforcedStructure',
            'hullTraverseSpeed': 'betterFriction',
            'turretTraverseSpeed': 'improvedTurretTurningWheels',
            'turretTraverse': 'improvedTurretTurningWheels',
            'specialShellPenetration': 'improvedSharpnessVisor',
            'standardShellVelocity': 'improvedMuzzleBreak',
            'allShellDamage': 'improvedGunBreech',
            'shellModuleDamage': 'improvedGunBreech',
            'additionalShellAmmoCapacity': 'improvedLightFilters',
            'gunDepression': 'improvedScope',
            'viewRange': 'improvedObservationDevice',
            'ammoRackHP': 'reinforcedInteriorModules',
            'ammoRackPenalty': 'reinforcedInteriorModules',
            'chassisRepairSpeed': 'improvedSelfRepairingTracks',
            'crewProtection': 'improvedSpallingResistance',
            'enginePenalty': 'reinforcedInteriorModules',
        }
        return token_map.get(token)

    def _default_field_mod_pairs(self):
        return [
            ('improvedAimingHandling', 'improvedSharpnessVisor'),
            ('improvedEnginePower', 'betterFriction'),
            ('improvedCamouflage', 'improvedObservationDevice'),
            ('reinforcedStructure', 'reinforcedInteriorModules'),
        ]

    def _get_field_mod_pairs_for_tank(self, tag):
        """Формує пари FIELD MODS для конкретного танка з клієнтських даних."""
        if tag in self._field_mod_pairs_cache:
            cached = self._field_mod_pairs_cache[tag]
            # Якщо в кеші вже достатньо пар для поточного рівня — використовуємо.
            if isinstance(cached, list) and len(cached) >= self._field_mod_pair_limit_for_tier(tag):
                return cached

        pair_limit = self._field_mod_pair_limit_for_tier(tag)
        if pair_limit <= 0:
            self._field_mod_pairs_cache[tag] = []
            return []

        # 1) Пріоритет: прямий витяг з декодованих клієнтських post_progression даних.
        for lookup_tag in self._field_mod_lookup_tags(tag):
            tank_entry = self._field_mod_pairs_by_tank.get(lookup_tag)
            if not isinstance(tank_entry, dict):
                continue
            raw_pairs = tank_entry.get('pairs', [])
            pairs = []
            if isinstance(raw_pairs, list):
                for item in raw_pairs:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        left = str(item[0]).strip()
                        right = str(item[1]).strip()
                        if left and right:
                            pairs.append((left, right))
            if pairs:
                pairs = pairs[:pair_limit]
                self._field_mod_pairs_cache[tag] = pairs
                return pairs

        # 2) Fallback: локальна евристика з *_modifications.xml (коли мапа не згенерована).
        tokens = self._extract_field_mod_tokens(tag)
        icons = []
        for tk_name in tokens:
            icon = self._field_mod_icon_from_token(tk_name)
            if icon and icon not in icons:
                icons.append(icon)

        if len(icons) < 2:
            self._field_mod_pairs_cache[tag] = []
            return []

        pairs = []
        i = 0
        while i + 1 < len(icons):
            pairs.append((icons[i], icons[i + 1]))
            i += 2

        if not pairs:
            self._field_mod_pairs_cache[tag] = []
            return []

        pairs = pairs[:pair_limit]
        self._field_mod_pairs_cache[tag] = pairs
        return pairs

    def on_ai_tank_select(self, tag):
        self.active_tank = tag
        data = self.tank_db.get(tag, {})
        if not isinstance(data, dict):
            data = {}
        self.ai_grid_container.pack_forget()
        self.ai_res_f.pack(side="top", fill="both", expand=True)
        self.detail_canvas.yview_moveto(0)

        # ── Іконка танка ──
        img = self.get_composite_icon(tag, data.get("nation", ""), size=(196, 126))

        # ── Очищення ──
        for widget in self.ai_title_frame.winfo_children(): widget.destroy()
        for widget in self.ai_tth_frame.winfo_children(): widget.destroy()
        for widget in self.ai_equipment_frame.winfo_children(): widget.destroy()
        for widget in self.ai_consumables_frame.winfo_children(): widget.destroy()
        for widget in self.ai_ammo_frame.winfo_children(): widget.destroy()
        for widget in self.ai_equipment_frame_2.winfo_children(): widget.destroy()
        for widget in self.ai_consumables_frame_2.winfo_children(): widget.destroy()
        for widget in self.ai_ammo_frame_2.winfo_children(): widget.destroy()
        for widget in self.ai_crew_frame.winfo_children(): widget.destroy()
        for widget in self.ai_field_mod_frame.winfo_children(): widget.destroy()
        # Очищення міток з номерами
        if hasattr(self, '_loadout_num_label') and self._loadout_num_label.winfo_exists():
            self._loadout_num_label.destroy()
        if hasattr(self, '_loadout_num_label_2') and self._loadout_num_label_2.winfo_exists():
            self._loadout_num_label_2.destroy()

        is_prem = data.get("is_premium", False)
        acc = "#e09b1b" if is_prem else "#bbbbbb"

        # ── Заголовок (tier + flag + class + name) ──
        hf = tk.Frame(self.ai_title_frame, bg="#111111")
        hf.pack(side="top", anchor="center", pady=(0, 8))
        roman_tiers = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
        try:
            tier_val = int(data.get('tier', 0) or 0)
        except Exception:
            tier_val = 0
        rt = roman_tiers[tier_val - 1] if 1 <= tier_val <= 11 else str(tier_val)
        tk.Label(hf, text=rt, font=("Arial", 16, "bold"), fg=acc, bg="#111111").pack(side="left", padx=(0,4))
        s_flag = self.get_small_flag(data.get("nation", ""))
        if s_flag:
            fl = tk.Label(hf, image=s_flag, bg="#111111")
            fl.image = s_flag
            fl.pack(side="left", padx=(0,4))
        xvm_classes = {"LT": chr(0x3A), "MT": chr(0x3B), "HT": chr(0x3F), "TD": chr(0x2E), "SPG": chr(0x2D)}
        sym = xvm_classes.get(str(data.get('class', '')).upper(), "?")
        tk.Label(hf, text=sym, font=("XVMSymbol", 18), fg=acc, bg="#111111").pack(side="left", padx=(0,6))
        tk.Label(hf, text=data.get('name', tag), font=("Arial", 14, "bold"), fg=acc, bg="#111111").pack(side="left")

        # ── HP (компактний центральний блок) ──
        tth = self._find_tth_for_tag(tag)
        if not tth:
            self.reload_tth_data()
            tth = self._find_tth_for_tag(tag)

        # ── Повна ТТХ таблиця ──
        tth_rows = []
        if tth.get('hp'):
            tth_rows.append(("relativeArmor.png", "Міцність (HP):", str(tth['hp'])))
        hull = tth.get('hull_armor', {})
        if isinstance(hull, dict) and hull:
            front = hull.get('front') or hull.get('f') or hull.get(list(hull.keys())[0])
            side  = hull.get('side')  or hull.get('s')
            rear  = hull.get('rear')  or hull.get('r')
            parts = [str(v) for v in [front, side, rear] if v is not None]
            if parts:
                tth_rows.append(("relativeArmor.png", "Броня корпусу:", " / ".join(parts)))
        elif hull:
            tth_rows.append(("relativeArmor.png", "Броня корпусу:", str(hull)))
        turret = tth.get('turret_armor', {})
        if isinstance(turret, dict) and turret:
            front = turret.get('front') or turret.get('f') or turret.get(list(turret.keys())[0])
            side  = turret.get('side')  or turret.get('s')
            rear  = turret.get('rear')  or turret.get('r')
            parts = [str(v) for v in [front, side, rear] if v is not None]
            if parts:
                tth_rows.append(("relativeArmor.png", "Броня башти:", " / ".join(parts)))
        elif turret:
            tth_rows.append(("relativeArmor.png", "Броня башти:", str(turret)))
        shells = tth.get('shells', [])
        if isinstance(shells, list) and shells:
            ap = next((s for s in shells if str(s.get('type','')).upper() in ('AP','APCR','APBC','APCBC')), None)
            sh = ap or shells[0]
            dmg = sh.get('damage') or sh.get('alphaDamage')
            pen = sh.get('piercing_power') or sh.get('piercingPower') or sh.get('penetration')
            if dmg:
                tth_rows.append(("relativePower.png", "Шкода:", str(dmg)))
            if pen:
                if isinstance(pen, (list, tuple)):
                    pen = pen[0]
                tth_rows.append(("relativePower.png", "Пробиття (мм):", str(pen)))
        if tth.get('reload'):
            tth_rows.append(("relativePower.png", "Перезарядка (с):", str(tth['reload'])))
        spd = tth.get('speed_fwd') or tth.get('maxSpeed') or tth.get('speed')
        if spd:
            spd_bwd = tth.get('speed_bwd') or tth.get('maxSpeedBackward')
            spd_str = f"{spd}" + (f" / -{spd_bwd}" if spd_bwd else "")
            tth_rows.append(("relativeMobility.png", "Швидкість (км/г):", spd_str))
        if tth.get('view_range'):
            tth_rows.append(("relativeVisibility.png", "Огляд (м):", str(tth['view_range'])))

        tth_wrapper = tk.Frame(self.ai_tth_frame, bg="#1a1a1a", bd=0, relief="flat", highlightthickness=0, width=self._detail_info_fixed_width)
        tth_wrapper.pack(side="top", anchor="center", padx=0)
        tth_wrapper.pack_propagate(False)
        tth_wrapper.grid_columnconfigure(0, weight=0)
        tth_wrapper.grid_columnconfigure(1, weight=1, minsize=self._detail_tth_fixed_width)
        tth_wrapper.grid_columnconfigure(2, weight=1)

        left_img_f = tk.Frame(tth_wrapper, bg="#111111", bd=0, highlightthickness=0)
        left_img_f.grid(row=0, column=0, sticky="nsw", padx=(0, 8), pady=0)
        if img:
            left_img_l = tk.Label(left_img_f, image=img, bg="#111111", bd=0, highlightthickness=0)
            left_img_l.image = img
            left_img_l.pack(side="top", anchor="n", pady=(0, 20))

        tth_table = tk.Frame(tth_wrapper, bg="#1a1a1a", width=self._detail_tth_fixed_width)
        tth_table.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=6)
        tth_table.grid_propagate(False)
        for i, (icon_name, label_text, value_text) in enumerate(tth_rows):
            row_bg = "#1a1a1a" if i % 2 == 0 else "#1f1f1f"
            row_f = tk.Frame(tth_table, bg=row_bg)
            row_f.pack(side="top", fill="x", padx=6, pady=2)
            row_icon = self.get_tth_icon(icon_name, size=(16, 16))
            if row_icon:
                il = tk.Label(row_f, image=row_icon, bg=row_bg)
                il.image = row_icon
                il.pack(side="left", padx=(0, 5))
            tk.Label(row_f, text=label_text, fg="#9a9a9a", bg=row_bg,
                     font=("Arial", 9), width=15, anchor="w").pack(side="left")
            tk.Label(row_f, text=value_text, fg="#e6e6e6", bg=row_bg,
                     font=("Arial", 10, "bold"), anchor="e").pack(side="right", padx=(0, 4))

        # ── ОКРЕМІ СЕКЦІЇ ЗБІРОК ──
        equip_body = self._make_tiles_section(self.ai_equipment_frame, "ОБЛАДНАННЯ", "equipment")
        cons_body = self._make_tiles_section(self.ai_consumables_frame, "ВИТРАТНІ", "consumables")
        ammo_body = self._make_tiles_section(self.ai_ammo_frame, "СНАРЯДИ", "ammo")
        crew_body = self._make_tiles_section(self.ai_crew_frame, "НАВИЧКИ ЕКІПАЖУ", "crew")
        fm_body = self._make_tiles_section(self.ai_field_mod_frame, "ПОЛЬОВА МОДЕРНІЗАЦІЯ", "field_mod")

        # ── ОБЛАДНАННЯ: спеціалізоване обладнання ──
        equip_items = [
            ("rammer", self.t("rammer", "Ухиливач")),
            ("coatedOptics", self.t("coatedOptics", "Гарячі скла")),
            ("aimingStabilizer", self.t("aimingStabilizer", "Стабілізатор наведення")),
        ]
        equip_slots = []
        for name, _label in equip_items:
            photo = self.get_loadout_icon('artefacts', name, (48, 48))
            slot = tk.Frame(equip_body, bg="#111111", bd=0, relief="flat")
            icon_box = tk.Frame(slot, bg="#1d2a1a", bd=1, relief="flat", width=54, height=54)
            icon_box.pack(side="top")
            icon_box.pack_propagate(False)
            lbl = tk.Label(icon_box, bg="#1d2a1a", padx=0, pady=0)
            if photo:
                lbl.config(image=photo)
                lbl.image = photo
            else:
                lbl.config(width=4, height=2, bg="#2a3a28")
            lbl.pack(expand=True)
            equip_slots.append(slot)

        # ── ВИТРАТНІ: амуніція та готівка ──
        cons_items = [
            ("largeRepairkit", self.t("largeRepairkit", "Великий ремонтний набір")),
            ("handExtinguishers", self.t("handExtinguishers", "Вогнегасник")),
            ("hotCoffee", self.t("hotCoffee", "Міцна каву")),
        ]
        cons_slots = []
        for name, _label in cons_items:
            photo = self.get_loadout_icon('artefacts', name, (48, 48))
            slot = tk.Frame(cons_body, bg="#111111", bd=0, relief="flat")
            icon_box = tk.Frame(slot, bg="#1a1d2a", bd=1, relief="flat", width=54, height=54)
            icon_box.pack(side="top")
            icon_box.pack_propagate(False)
            lbl = tk.Label(icon_box, bg="#1a1d2a", padx=0, pady=0)
            if photo:
                lbl.config(image=photo)
                lbl.image = photo
            else:
                lbl.config(width=4, height=2, bg="#272a3a")
            lbl.pack(expand=True)
            cons_slots.append(slot)

        ammo_items = [
            "ARMOR_PIERCING",
            "ARMOR_PIERCING_CR",
            "HIGH_EXPLOSIVE",
        ]
        ammo_slots = []
        for name in ammo_items:
            photo = self.get_loadout_icon('ammo', name, (48, 48))
            slot = tk.Frame(ammo_body, bg="#111111", bd=0, relief="flat")
            icon_box = tk.Frame(slot, bg="#1a1d2a", bd=1, relief="flat", width=54, height=54)
            icon_box.pack(side="top")
            icon_box.pack_propagate(False)
            lbl = tk.Label(icon_box, bg="#1a1d2a", padx=0, pady=0)
            if photo:
                lbl.config(image=photo)
                lbl.image = photo
            else:
                lbl.config(width=4, height=2, bg="#272a3a")
            lbl.pack(expand=True)
            ammo_slots.append(slot)

        # ── РЯДОК 2: без заголовків ──
        equip_body_2 = tk.Frame(self.ai_equipment_frame_2, bg="#111111")
        equip_body_2.pack(side="top", fill="x", pady=3)
        cons_body_2 = tk.Frame(self.ai_consumables_frame_2, bg="#111111")
        cons_body_2.pack(side="top", fill="x", pady=3)
        ammo_body_2 = tk.Frame(self.ai_ammo_frame_2, bg="#111111")
        ammo_body_2.pack(side="top", fill="x", pady=3)

        # Обладнання row 2 (такі самі іконки як у рядку 1)
        equip_slots_2 = []
        for name, _label in equip_items:
            photo = self.get_loadout_icon('artefacts', name, (48, 48))
            slot = tk.Frame(equip_body_2, bg="#111111", bd=0, relief="flat")
            icon_box = tk.Frame(slot, bg="#1d2a1a", bd=1, relief="flat", width=54, height=54)
            icon_box.pack(side="top")
            icon_box.pack_propagate(False)
            lbl = tk.Label(icon_box, bg="#1d2a1a", padx=0, pady=0)
            if photo:
                lbl.config(image=photo)
                lbl.image = photo
            else:
                lbl.config(width=4, height=2, bg="#2a3a28")
            lbl.pack(expand=True)
            equip_slots_2.append(slot)

        # Витратні row 2 (такі самі іконки як у рядку 1)
        cons_slots_2 = []
        for name, _label in cons_items:
            photo = self.get_loadout_icon('artefacts', name, (48, 48))
            slot = tk.Frame(cons_body_2, bg="#111111", bd=0, relief="flat")
            icon_box = tk.Frame(slot, bg="#1a1d2a", bd=1, relief="flat", width=54, height=54)
            icon_box.pack(side="top")
            icon_box.pack_propagate(False)
            lbl = tk.Label(icon_box, bg="#1a1d2a", padx=0, pady=0)
            if photo:
                lbl.config(image=photo)
                lbl.image = photo
            else:
                lbl.config(width=4, height=2, bg="#272a3a")
            lbl.pack(expand=True)
            cons_slots_2.append(slot)

        # Снаряди row 2 (такі самі іконки як у рядку 1)
        ammo_slots_2 = []
        for name in ammo_items:
            photo = self.get_loadout_icon('ammo', name, (48, 48))
            slot = tk.Frame(ammo_body_2, bg="#111111", bd=0, relief="flat")
            icon_box = tk.Frame(slot, bg="#1a1d2a", bd=1, relief="flat", width=54, height=54)
            icon_box.pack(side="top")
            icon_box.pack_propagate(False)
            lbl = tk.Label(icon_box, bg="#1a1d2a", padx=0, pady=0)
            if photo:
                lbl.config(image=photo)
                lbl.image = photo
            else:
                lbl.config(width=4, height=2, bg="#272a3a")
            lbl.pack(expand=True)
            ammo_slots_2.append(slot)

        # Layout для рядка 2
        self._layout_tile_row(equip_body_2, equip_slots_2, gap=0)
        self._layout_tile_row(cons_body_2, cons_slots_2, gap=0)
        self._layout_tile_row(ammo_body_2, ammo_slots_2, gap=0)

        # ── НАВИЧКИ ЕКІПАЖУ: по членах екіпажу, тільки іконки ──
        crew_rows = self._get_crew_rows_for_tank(tag)
        crew_slots = []
        for member, skills in crew_rows:
            slot = tk.Frame(crew_body, bg="#111111", bd=0, relief="flat")
            row = tk.Frame(slot, bg="#111111")
            row.pack(side="top", pady=(0, 3))

            role_icon = member.get('role')
            also_roles = member.get('also') or []

            role_box = tk.Frame(row, bg="#111111", bd=0, relief="flat", width=40, height=40)
            role_box.pack(side="left", padx=(0, 3))
            role_box.pack_propagate(False)

            role_photo = self.get_loadout_icon('crew_roles', role_icon, (24, 24))
            role_lbl = tk.Label(role_box, bg="#111111")
            if role_photo:
                role_lbl.config(image=role_photo)
                role_lbl.image = role_photo
            role_lbl.pack(expand=True)

            # Secondary roles (e.g., commander+radioman) are shown as smaller icons.
            for sec_role in also_roles:
                sec_box = tk.Frame(row, bg="#111111", bd=0, relief="flat", width=40, height=40)
                sec_box.pack(side="left", padx=(0, 3))
                sec_box.pack_propagate(False)

                sec_photo = self.get_loadout_icon('crew_roles', sec_role, (24, 24))
                sec_lbl = tk.Label(sec_box, bg="#111111")
                if sec_photo:
                    sec_lbl.config(image=sec_photo)
                    sec_lbl.image = sec_photo
                sec_lbl.pack(expand=True)

            for skill_name in skills:
                skill_box = tk.Frame(row, bg="#2a1a1a", bd=1, relief="flat", width=40, height=40)
                skill_box.pack(side="left", padx=(0, 3))
                skill_box.pack_propagate(False)
                skill_photo = self.get_loadout_icon('artefacts', skill_name, (24, 24))
                skill_lbl = tk.Label(skill_box, bg="#2a1a1a")
                if skill_photo:
                    skill_lbl.config(image=skill_photo)
                    skill_lbl.image = skill_photo
                skill_lbl.pack(expand=True)
            crew_slots.append(slot)

        # ── ПОЛЬОВА МОДЕРНІЗАЦІЯ: парні модернізації, тільки іконки ──
        fm_pairs = self._get_field_mod_pairs_for_tank(tag)
        fm_slots = []
        for left_name, right_name in fm_pairs:
            slot = tk.Frame(fm_body, bg="#111111", bd=0, relief="flat")
            row = tk.Frame(slot, bg="#111111")
            row.pack(side="top")

            for name in (left_name, right_name):
                icon_box = tk.Frame(row, bg="#1a242a", bd=1, relief="flat", width=64, height=64)
                icon_box.pack(side="left", padx=0)
                icon_box.pack_propagate(False)
                photo = self.get_loadout_icon('field_mods', name, (64, 64))
                lbl = tk.Label(icon_box, bg="#1a242a", padx=0, pady=0)
                if photo:
                    lbl.config(image=photo)
                    lbl.image = photo
                else:
                    lbl.config(width=3, height=2, bg="#1e2d35")
                lbl.pack(expand=True)
            fm_slots.append(slot)

        # Адаптивна сітка всередині кожної секції.
        # min_cell малий → cols великий → всі елементи в один рядок поки ширина дозволяє.
        self._layout_tile_row(equip_body, equip_slots, gap=0)
        self._layout_tile_row(cons_body, cons_slots, gap=0)
        self._layout_tile_row(ammo_body, ammo_slots, gap=0)
        self._layout_tile_grid(crew_body, crew_slots, min_cell=9999, gap=0, stretch=False)
        self._layout_tile_row(fm_body, fm_slots, gap=0)
        equip_body.bind("<Configure>", lambda e, c=equip_body, s=equip_slots: self._layout_tile_row(c, s, gap=0))
        cons_body.bind("<Configure>", lambda e, c=cons_body, s=cons_slots: self._layout_tile_row(c, s, gap=0))
        ammo_body.bind("<Configure>", lambda e, c=ammo_body, s=ammo_slots: self._layout_tile_row(c, s, gap=0))
        crew_body.bind("<Configure>", lambda e, c=crew_body, s=crew_slots: self._layout_tile_grid(c, s, min_cell=9999, gap=0, stretch=False))
        self._layout_pair_tiles_wrap(fm_body, fm_slots, pair_gap=10, row_gap=4)
        fm_body.bind("<Configure>", lambda e, c=fm_body, s=fm_slots: self._layout_pair_tiles_wrap(c, s, pair_gap=10, row_gap=4))

        # Після побудови контенту перебудовуємо розкладку під поточну ширину.
        self._reflow_detail_layout()

    def show_ai_result(self, text):
        pass  # ШІ результати видалено — тепер відображаємо ТТХ
