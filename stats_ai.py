import os
import re
import json
import tempfile
import random
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps, ImageDraw
import io
import threading
import subprocess
import sys
from datetime import datetime, timezone, date
from stats_data import EQUIP_MAP, CONS_MAP, CREW_SKILL_MAP
import config
import language_module

ENABLE_POPULAR_TANK_CACHE = True
ENABLE_AI_BUILD_CACHE = True

_CACHE_PATH = os.path.join(config.USER_DATA_DIR, "popular_tanks_cache.json")
_AI_BUILD_CACHE_PATH = os.path.join(config.USER_DATA_DIR, "ai_builds_cache.json")
_DATA_DIR = config.BASE_DIR


def _load_ai_build_cache():
    if os.path.exists(_AI_BUILD_CACHE_PATH):
        try:
            with open(_AI_BUILD_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("builds", {}), data.get("updated", {}), data.get("fail_count", 0)
        except Exception:
            pass
    return {}, {}, 0


def _save_ai_build_cache(tag, build_data, fail_count=None):
    builds, updated, cur_fc = _load_ai_build_cache()
    builds[tag] = build_data
    updated[tag] = time.strftime("%Y-%m-%dT%H:%M:%S")
    if fail_count is not None:
        cur_fc = fail_count
    try:
        with open(_AI_BUILD_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"builds": builds, "updated": updated, "fail_count": cur_fc}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _handle_ai_build_failure(tag):
    builds, updated, fc = _load_ai_build_cache()
    fc = fc + 1
    try:
        with open(_AI_BUILD_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"builds": builds, "updated": updated, "fail_count": fc}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    if fc > 0 and fc % 3 == 0:
        from service_messages import log_event
        log_event("ai_build", f"Не вдалося оновити build для {tag} після {fc} спроб поспіль.", level="warning")
    print(f"[AI Tank Build] Failure #{fc} for {tag}")


def _load_popular_tank_cache():
    """Load cached popular tanks. Returns (list_of_tags, updated_iso, fail_count)."""
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                tanks = [t.get('tag') or t.get('name', '').lower().replace(' ', '_') for t in data.get('tanks', [])]
                updated = data.get('updated')
                fail_count = data.get('fail_count', 0)
                return tanks, updated, fail_count
        except Exception:
            pass
    return [], None, 0


def _is_cache_expired(updated_iso, max_days=7):
    if not updated_iso:
        return True
    try:
        updated = datetime.fromisoformat(updated_iso)
        now = datetime.now(timezone.utc if updated.tzinfo else None)
        if updated.tzinfo is None:
            now = datetime.now()
        delta = now - updated
        return delta.days >= max_days
    except Exception:
        return True

class StatsAI:
    PLACEHOLDER_PREFIX = "Search among "

    def __init__(self, ai_frame, tank_db, popular_tanks, main_app):
        self.ai_frame = ai_frame
        self.tank_db = tank_db
        self._cache_data = None
        self._cache_fresh = False
        if ENABLE_POPULAR_TANK_CACHE:
            cached_tanks, updated, fail_count = _load_popular_tank_cache()
            if cached_tanks:
                self._cache_data = {"tanks": [{"tag": t} for t in cached_tanks], "updated": updated, "fail_count": fail_count}
                self.popular_tanks = cached_tanks
                self._cache_fresh = not _is_cache_expired(updated, max_days=30)
                if self._cache_fresh:
                    print(f"[AI Browser] Завантажено {len(cached_tanks)} танків з кешу (оновлено: {updated})")
                else:
                    print(f"[AI Browser] Завантажено {len(cached_tanks)} танків з кешу (потрібне оновлення: {updated})")
            else:
                self.popular_tanks = []
                print(f"[AI Browser] Кеш відсутній, запуск AI...")
        else:
            self.popular_tanks = []
        self.main_app = main_app  # Reference to WotAssistantHQ
        self.locale_manager = getattr(main_app, 'locale', None)  # Localization support

        
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
        self._loading_anim_active = False
        self._field_mod_pairs_by_tank = self._load_field_mod_pairs_by_tank()
        self._crew_builds = self._load_crew_builds()
        self._equipment_loadouts = self._load_equipment_loadouts()
        
        self.root = self.main_app.root
        self._search_timer = None
        self._filter_active = False
        self._filter_version = 0
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
        self._detail_image_lift_px = 10
        self._layout_debug = False
        self._sections_debug = False
        self.tank_tth = {}
        self.reload_tth_data()
        
        self.LOADOUT_ICON_DIR = os.path.join(_DATA_DIR, 'extracted_icons', 'loadout')
        self.FIELD_MODS_ORIGINAL_DIR = os.path.join(
            self.LOADOUT_ICON_DIR,
            'field_mods',
            'pairModifications',
            '80x80',
        )
        self.TTH_ICON_DIR = os.path.join(_DATA_DIR, 'extracted_icons', 'tth')
        
        self._available_icons = {}
        self._load_available_icons()

        self.search_placeholder = self.main_app.t('ui', 'search_placeholder').format(count=len(self.tank_db))
        
        self.build_ai_ui()
        self.refresh_ai_view()
        self.root.bind_all("<MouseWheel>", self._global_mousewheel, add="+")

    def _load_crew_builds(self):
        """Завантажує crew_builds.json з рекомендованими будовами екіпажу."""
        path = os.path.join(_DATA_DIR, 'crew_builds.json')
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_equipment_loadouts(self):
        """Завантажує equipment_loadouts.json з даними про обладнання."""
        path = os.path.join(_DATA_DIR, 'equipment_loadouts.json')
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

        tank_entry = tanks.get(tag) or {}
        crew_members = tank_entry.get('crew_members')
        if not isinstance(crew_members, list) or not crew_members:
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

            skills = []

            def _append_unique(seq):
                for name in seq:
                    if name and name not in skills:
                        skills.append(name)

            _append_unique(role_skill_pools.get(role) or [])
            _append_unique(default_skills.get(role) or [])
            _append_unique(fallback_common)
            primary_block = skills[:primary_perk_count]

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
        tth_path = os.path.join(_DATA_DIR, 'tank_tth.json')
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
        raw = str(nation_value).strip()
        base = raw.split('_')[0] if '_' in raw else raw
        return base.lower()

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
            if hasattr(self, 'ai_status_bar'):
                self.ai_status_bar.grid_forget()

    def _parse_search_query(self):
        raw_q = self.ai_search_var.get() or ""
        q = raw_q.strip()
        if not q:
            return ""
        if q.casefold() == self.search_placeholder.casefold():
            return ""
        return q.casefold()

    def _perform_search(self):
        self._show_grid_if_needed()
        self.root.after(10, self.refresh_ai_view)

    def update_search_placeholder(self, new_placeholder):
        old_placeholder = self.search_placeholder
        current_text = (self.ai_search_var.get() or "").strip()
        self.search_placeholder = new_placeholder

        looks_like_placeholder = (
            current_text.startswith(self.PLACEHOLDER_PREFIX) and current_text.endswith("...")
        )
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
        fb = tk.Frame(self.ai_frame, bg="#1a1a1a", pady=2)
        fb.pack(side="top", fill="x")
        
        row1 = tk.Frame(fb, bg="#1a1a1a", height=46)
        row1.pack(side="top", fill="x", pady=2)
        row1.pack_propagate(False)
        
        
        placeholder = self.search_placeholder
        
        self.btn_home = tk.Button(row1, text="⌂", bg="#2a2a2a", fg="gray", activebackground="#333", activeforeground="white", font=("Arial", 28), bd=0, relief="flat", cursor="hand2", command=self.return_to_ai_home)
        self.btn_home.pack(side="left", fill="y", padx=(5, 0))

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

        def on_key_press(e):
            if not e.char:
                return
            if se.get() == placeholder:
                se.delete(0, 'end')
                se.config(fg="white")
            if self._search_timer is not None:
                self.root.after_cancel(self._search_timer)
            self._search_timer = self.root.after(500, self._perform_search)

        se.bind("<FocusIn>", on_search_focus_in)
        se.bind("<FocusOut>", on_search_focus_out)
        se.bind("<KeyPress>", on_key_press)

        tk.Frame(fb, height=2, bg="#111").pack(side="top", fill="x")

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

        tk.Frame(fb, height=2, bg="#111").pack(side="top", fill="x")

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
        
        self.progress_container = tk.Frame(fb, height=4, bg="#0a0a0a")
        self.progress_container.pack(side="top", fill="x")
        self.progress_container.pack_propagate(False)
        
        self.filter_progress_canvas = tk.Canvas(self.progress_container, height=4, bg="#0a0a0a", highlightthickness=0)
        self._progress_rect = self.filter_progress_canvas.create_rectangle(0, 0, 0, 4, fill="#ff4500", outline="")
        
        self.ai_grid_container = tk.Frame(self.ai_frame, bg="#000")
        self.ai_grid_container.pack(side="top", fill="both", expand=True)

        self.ai_canvas = tk.Canvas(self.ai_grid_container, bg="#000", highlightthickness=0)
        self.ai_scrollbar = ttk.Scrollbar(self.ai_grid_container, orient="vertical", command=self.ai_canvas.yview, style="Dark.Vertical.TScrollbar")

        self.ai_grid_frame = tk.Frame(self.ai_canvas, bg="#000", padx=0.5, pady=0.5)
        self.ai_canvas_window = self.ai_canvas.create_window((0, 0), window=self.ai_grid_frame, anchor="nw")
        self.ai_canvas.configure(yscrollcommand=self.ai_scrollbar.set)
        
        
        def _on_canvas_resize(event):
            self.ai_canvas.coords(self.ai_canvas_window, 0, 0)
            self.ai_canvas.itemconfig(self.ai_canvas_window, width=event.width)
            if event.width < 100:
                return
            new_max_cols = max(1, event.width // 171)
            if self._last_cols != new_max_cols:
                self._last_cols = new_max_cols
                if not self.active_tank:
                    if hasattr(self, '_resize_timer') and self._resize_timer:
                        try: self.root.after_cancel(self._resize_timer)
                        except: pass
                    self._resize_timer = self.root.after(300, self.refresh_ai_view)
        self.refresh_ai_view()

        self.ai_canvas.bind("<Configure>", _on_canvas_resize)
        
        self.ai_canvas.pack(side="left", fill="both", expand=True)
        self.ai_scrollbar.pack(side="right", fill="y")
        self.ai_canvas.bind("<Enter>", lambda e: self.ai_canvas.focus_set())
        self.ai_canvas.bind("<MouseWheel>", lambda e: (self.ai_canvas.yview_scroll(int(-1*(e.delta/120)), "units"), "break")[1])
        self.ai_canvas.bind("<Button-4>", lambda e: (self.ai_canvas.yview_scroll(-1, "units"), "break")[1])
        self.ai_canvas.bind("<Button-5>", lambda e: (self.ai_canvas.yview_scroll(1, "units"), "break")[1])
        self.ai_grid_frame.bind("<Configure>", lambda e: self.ai_canvas.configure(
            scrollregion=(0, 0, e.width, e.height)))
        
        self.ai_res_f = tk.Frame(self.ai_frame, bg="#111111")
        
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
        self.detail_canvas.bind("<Enter>", lambda e: self.detail_canvas.focus_set())
        self.detail_canvas.bind("<MouseWheel>", lambda e: (self.detail_canvas.yview_scroll(int(-1*(e.delta/120)), "units"), "break")[1])
        self.detail_canvas.bind("<Button-4>", lambda e: (self.detail_canvas.yview_scroll(-1, "units"), "break")[1])
        self.detail_canvas.bind("<Button-5>", lambda e: (self.detail_canvas.yview_scroll(1, "units"), "break")[1])
        
        self.ai_title_frame = tk.Frame(self.detail_inner, bg="#111111")
        self.ai_title_frame.pack(side="top", anchor="center", pady=(2, 2))

        self.ai_image_frame = tk.Frame(self.detail_inner, bg="#111111")
        self.ai_tank_icon_lf = tk.Label(self.ai_image_frame, bg="#111111")

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
        self.ai_top_headers_row = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_equipment_header = tk.Frame(self.ai_top_headers_row, bg="#111111")
        self.ai_ammo_header = tk.Frame(self.ai_top_headers_row, bg="#111111")
        self.ai_consumables_header = tk.Frame(self.ai_top_headers_row, bg="#111111")
        self.ai_top_loadout_row = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_equipment_frame = tk.Frame(self.ai_top_loadout_row, bg="#111111")
        self.ai_ammo_frame = tk.Frame(self.ai_top_loadout_row, bg="#111111")
        self.ai_consumables_frame = tk.Frame(self.ai_top_loadout_row, bg="#111111")
        self.ai_top_loadout_row_2 = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_equipment_frame_2 = tk.Frame(self.ai_top_loadout_row_2, bg="#111111")
        self.ai_ammo_frame_2 = tk.Frame(self.ai_top_loadout_row_2, bg="#111111")
        self.ai_consumables_frame_2 = tk.Frame(self.ai_top_loadout_row_2, bg="#111111")
        self.ai_crew_frame = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_field_mod_frame = tk.Frame(self.ai_content_panel, bg="#111111")
        self.ai_status_bar = tk.Frame(self.ai_content_panel, bg="#2a2a2a", height=28)
        
        self.refresh_ai_view()
        self._status_label = None

    def _global_mousewheel(self, event):
        try:
            w = self.root.winfo_containing(event.x_root, event.y_root)
            while w:
                if w == self.ai_canvas:
                    self.ai_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                    return "break"
                if w == self.detail_canvas:
                    self.detail_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                    return "break"
                w = w.master if hasattr(w, 'master') else None
        except Exception:
            pass
        return None

    def update_status_bar(self, text="", fg="#aaaaaa"):
        pass

    def _on_detail_canvas_resize(self, event):
        self.detail_canvas.itemconfig(self.detail_canvas_win, width=event.width)
        self._reflow_detail_layout(event.width)

    def _reflow_detail_layout(self, width=None):
        if width is None and hasattr(self, 'detail_canvas'):
            width = self.detail_canvas.winfo_width()
        if width is None:
            return

        compact_w = self._detail_compact_max_width
        self.ai_content_panel.grid_columnconfigure(1, minsize=compact_w)
        
        self.ai_content_panel.grid_rowconfigure(0, weight=0)  # TTH
        self.ai_content_panel.grid_rowconfigure(1, weight=0)  # Headers row
        self.ai_content_panel.grid_rowconfigure(2, weight=0)  # Loadout 1
        self.ai_content_panel.grid_rowconfigure(3, weight=0)  # Loadout 2
        self.ai_content_panel.grid_rowconfigure(4, weight=0)  # Crew
        self.ai_content_panel.grid_rowconfigure(5, weight=0)  # Field mods
        self.ai_content_panel.grid_rowconfigure(6, weight=0)  # Field mods row 2
        self.ai_content_panel.grid_rowconfigure(7, weight=0)  # Status bar

        sections = [
            self.ai_tth_frame,
            self.ai_top_headers_row,
            self.ai_top_loadout_row,
            self.ai_top_loadout_row_2,
            self.ai_crew_frame,
            self.ai_field_mod_frame,
        ]


        for idx, sec in enumerate(sections, start=0):
            if idx == 0:
                sec.grid(row=0, column=1, sticky="nsew", padx=0, pady=(2, 2))
            elif idx == 1 or idx == 2:
                sec.grid(row=idx, column=1, sticky="nsew", padx=0, pady=(0, 0))
            else:
                sec.grid(row=idx, column=1, sticky="nsew", padx=0, pady=(0, 8))



        fixed_w = min(self._detail_info_fixed_width, compact_w)
        self.ai_tth_frame.configure(width=fixed_w)
        self.ai_top_headers_row.grid_propagate(False)
        self.ai_crew_frame.grid_propagate(False)
        self.ai_field_mod_frame.grid_propagate(False)
        
        self.ai_equipment_header.grid_forget()
        self.ai_ammo_header.grid_forget()
        self.ai_consumables_header.grid_forget()
        self.ai_top_headers_row.grid_columnconfigure(0, weight=0)
        self.ai_top_headers_row.grid_columnconfigure(1, weight=1)
        self.ai_top_headers_row.grid_columnconfigure(2, weight=1)
        self.ai_top_headers_row.grid_columnconfigure(3, weight=1)
        self.ai_equipment_header.grid(row=0, column=1, sticky="ew", padx=(0, 2))
        self.ai_ammo_header.grid(row=0, column=2, sticky="ew", padx=(1, 1))
        self.ai_consumables_header.grid(row=0, column=3, sticky="ew", padx=(2, 0))

        self.ai_equipment_frame.grid_forget()
        self.ai_ammo_frame.grid_forget()
        self.ai_consumables_frame.grid_forget()
        self.ai_top_loadout_row.grid_columnconfigure(0, weight=1)
        self.ai_top_loadout_row.grid_columnconfigure(1, weight=1)
        self.ai_top_loadout_row.grid_columnconfigure(2, weight=1)
        self.ai_equipment_frame.grid(row=0, column=0, sticky="ew")
        self.ai_ammo_frame.grid(row=0, column=1, sticky="ew", padx=(1, 1))
        self.ai_consumables_frame.grid(row=0, column=2, sticky="ew", padx=(2, 0))

        self.ai_top_loadout_row_2.configure(width=fixed_w)
        self.ai_equipment_frame_2.grid_forget()
        self.ai_ammo_frame_2.grid_forget()
        self.ai_consumables_frame_2.grid_forget()
        self.ai_top_loadout_row_2.grid_columnconfigure(0, weight=1)
        self.ai_top_loadout_row_2.grid_columnconfigure(1, weight=1)
        self.ai_top_loadout_row_2.grid_columnconfigure(2, weight=1)
        self.ai_equipment_frame_2.grid(row=0, column=0, sticky="ew")
        self.ai_ammo_frame_2.grid(row=0, column=1, sticky="ew", padx=(1, 1))
        self.ai_consumables_frame_2.grid(row=0, column=2, sticky="ew", padx=(2, 0))

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
        try:
            if not container.winfo_exists():
                return
            container.update_idletasks()
            width = max(1, container.winfo_width())
            pair_w = max((s.winfo_reqwidth() for s in slots), default=1)
        except tk.TclError:
            return
        cols = max(1, width // max(1, pair_w + pair_gap))

        for s in slots:
            try:
                s.grid_forget()
            except tk.TclError:
                pass

        for i, s in enumerate(slots):
            try:
                r = i // cols
                c = i % cols
                padx = (0, pair_gap if c < cols - 1 else 0)
                s.grid(row=r, column=c, padx=padx, pady=(0, row_gap), sticky="nw")
                container.columnconfigure(c, weight=0)
            except tk.TclError:
                pass

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
        self._filter_version = getattr(self, '_filter_version', 0) + 1
        self._filter_active = False
        was_active = self.tier_filters[t]["active"]
        for key, item in self.tier_filters.items():
            item["active"] = False
            item["btn"].config(bg="#333333", fg="#aaaaaa")
        if not was_active:
            self.tier_filters[t]["active"] = True
            self.tier_filters[t]["btn"].config(bg="#444444", fg="#ffffff")
        self.root.update_idletasks()
        self._filter_active = True
        self.filter_progress_canvas.pack(fill="both", expand=True)
        self.filter_progress_canvas.coords(self._progress_rect, 0, 0, 0, 4)
        self._animate_realtime(
            1.5,
            lambda: self._collect_filtered_items(),
            lambda result: self._finish_filter_with_items(result[0] if result else [])
        )
        
    def toggle_class_filter(self, c):
        self._show_grid_if_needed()
        self._filter_version = getattr(self, '_filter_version', 0) + 1
        self._filter_active = False
        was_active = self.class_filters[c]["active"]
        for key, item in self.class_filters.items():
            item["active"] = False
            item["btn"].config(bg="#333333", fg="#aaaaaa")
        if not was_active:
            self.class_filters[c]["active"] = True
            self.class_filters[c]["btn"].config(bg="#444444", fg="#ffffff")
        self.root.update_idletasks()
        self._filter_active = True
        self.filter_progress_canvas.pack(fill="both", expand=True)
        self.filter_progress_canvas.coords(self._progress_rect, 0, 0, 0, 4)
        self._animate_realtime(
            0.8,
            lambda: self._collect_filtered_items(),
            lambda result: self._finish_filter_with_items(result[0] if result else [])
        )
        
    def toggle_nation_filter(self, n):
        self._show_grid_if_needed()
        self._filter_version = getattr(self, '_filter_version', 0) + 1
        self._filter_active = False
        was_active = self.nation_filters[n]["active"]
        for key, item in self.nation_filters.items():
            item["active"] = False
            item["btn"].config(bg="#333333")
        if not was_active:
            self.nation_filters[n]["active"] = True
            self.nation_filters[n]["btn"].config(bg="#444444")
        self.root.update_idletasks()
        self._filter_active = True
        self.filter_progress_canvas.pack(fill="both", expand=True)
        self.filter_progress_canvas.coords(self._progress_rect, 0, 0, 0, 4)
        self._animate_realtime(
            0.8,
            lambda: self._collect_filtered_items(),
            lambda result: self._finish_filter_with_items(result[0] if result else [])
        )
        
    def show_loading_screen(self):
        self.loading_frame = tk.Frame(self.ai_grid_container, bg="black")
        self.loading_canvas = tk.Canvas(self.loading_frame, bg="black", highlightthickness=0)
        self.loading_canvas.pack(fill="both", expand=True)
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
        norm = self._normalize_nation(nation) if hasattr(self, '_normalize_nation') else str(nation).strip().lower()
        cache_key = f"small_flag_{norm}"
        if cache_key in self.composite_cache: return self.composite_cache[cache_key]
        flag_map = {"usa": "usa", "ussr": "ussr", "germany": "germany", "france": "france",
                    "uk": "uk", "china": "china", "japan": "japan", "czech": "czech",
                    "poland": "poland", "sweden": "sweden", "italy": "italy"}
        f_name = flag_map.get(norm, norm)
        base = _DATA_DIR
        flag_path = os.path.join(base, "extracted_icons", "clean_nations", f"{f_name}.png")
        if not os.path.exists(flag_path):
            flag_path = None
            for p in [f"{f_name}_160x100.png", f"{f_name}_155x31.png", f"{f_name}_131x31.png"]:
                test_p = os.path.join(base, "extracted_icons", "nations", p)
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
            card_w, card_h = size
            card = Image.new("RGBA", (card_w, card_h), (17, 17, 17, 255))
            
            std_w, std_h = 380, 304
            temp = ImageOps.contain(tank_img, (std_w, std_h), Image.LANCZOS)
            canvas = Image.new("RGBA", (std_w, std_h), (0, 0, 0, 0))
            x = (std_w - temp.width) // 2
            y = (std_h - temp.height) // 2
            canvas.paste(temp, (x, y), temp)
            tank_img = canvas
            
            work_w = int(card_w * 1.55)
            work_h = int(card_h * 1.55)
            tank_img = ImageOps.contain(tank_img, (work_w, work_h), Image.LANCZOS)
            
            y_offset = (card_h - tank_img.height) // 2 - self._detail_image_lift_px
            card.paste(tank_img, ((card_w - tank_img.width)//2, y_offset), tank_img)

            if self._layout_debug:
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

    def _show_legend_tooltip(self, event, text):
        """Показує підказку при наведенні."""
        if not hasattr(self, '_legend_tooltip') or not self._legend_tooltip.winfo_exists():
            self._legend_tooltip = tk.Toplevel(self.root)
            self._legend_tooltip.overrideredirect(True)
            self._legend_tooltip.configure(bg="#333333")
            self._legend_tooltip_label = tk.Label(self._legend_tooltip, text="", fg="white", bg="#333333", font=("Arial", 9), padx=8, pady=4)
            self._legend_tooltip_label.pack()
            self._legend_tooltip.withdraw()
        try:
            self._legend_tooltip_label.configure(text=text)
            x = event.widget.winfo_rootx() + 20
            y = event.widget.winfo_rooty() + 20
            self._legend_tooltip.geometry(f"+{x}+{y}")
            self._legend_tooltip.deiconify()
        except tk.TclError:
            pass

    def _hide_legend_tooltip(self):
        """Ховає підказку."""
        if hasattr(self, '_legend_tooltip') and self._legend_tooltip.winfo_exists():
            self._legend_tooltip.withdraw()

    def _resolve_item_name(self, item_key, category="artefacts"):
        """Resolve item key to localized name from game client .mo files."""
        msgid = f"{item_key}/name"
        wot_path = self.main_app.settings.get("wot_path", "") if hasattr(self, 'main_app') else ""
        lm = language_module.get_lang_module(wot_path)
        if lm:
            result = lm.t(msgid)
            if result and result != msgid and not result.startswith("#"):
                return result
        return item_key

    def _mo_label(self, msgid, fallback=""):
        """Look up a label from game client .mo files via msgid."""
        wot_path = self.main_app.settings.get("wot_path", "") if hasattr(self, 'main_app') else ""
        lm = language_module.get_lang_module(wot_path)
        if lm:
            result = lm.t(msgid)
            if result and result != msgid and not result.startswith("#"):
                return result
        return fallback

    def _bind_item_tooltip(self, widget, item_key, category="artefacts"):
        """Bind hover tooltip showing localized item name."""
        name = self._resolve_item_name(item_key, category)
        widget.bind("<Enter>", lambda e, n=name: self._show_legend_tooltip(e, n))
        widget.bind("<Leave>", lambda e: self._hide_legend_tooltip())

    def _build_name_to_tag_lookup(self):
        lookup = {}
        for tag, data in self.tank_db.items():
            clean = self._get_clean_tank_name(tag, data)
            if clean:
                key = clean.lower()
                if key not in lookup:
                    lookup[key] = tag
        return lookup

    def _find_tank_tag(self, name, lookup):
        key = name.strip().lower()
        if key in lookup:
            return lookup[key]
        for lk, lt in lookup.items():
            if key == lk or key in lk or lk in key:
                return lt
        words = set(key.split())
        best = None
        best_score = 0
        for lk, lt in lookup.items():
            lw = set(lk.split())
            overlap = len(words & lw)
            if overlap > best_score:
                best_score = overlap
                best = lt
        if best_score >= 2:
            return best
        return None

    def refresh_ai_view(self):
        """Оновлює грід за допомогою чанків, щоб не блокувати UI."""
        if not hasattr(self, 'ai_grid_frame'): return

        search_q = self._parse_search_query()
        active_t, active_c, active_n = self._active_filter_values()
        max_cols = self._last_cols if self._last_cols > 0 else 5

        is_default = not search_q and not active_t and not active_c and not active_n
        items_to_show = []
        if is_default:
            for tag in self.popular_tanks:
                if tag in self.tank_db:
                    data = self.tank_db[tag]
                    tier = int(data.get("tier", 0) or 0)
                    if 8 <= tier <= 11:
                        items_to_show.append((tag, data))

            if not self.popular_tanks:
                for widget in self.ai_grid_frame.winfo_children():
                    widget.destroy()
                placeholder = tk.Label(self.ai_grid_frame, text=self.main_app.t("ui", "select_tank_placeholder"),
                                       bg="#000", fg="#555", font=("Arial", 12))
                placeholder.pack(expand=True)
                return

            def _tier_sort(item):
                d = item[1] if isinstance(item[1], dict) else {}
                return int(d.get("tier", 0) or 0)
            items_to_show.sort(key=_tier_sort, reverse=True)

            target_rows = max(1, round(30 / max_cols))
            target_count = target_rows * max_cols

            if len(items_to_show) > target_count:
                items_to_show = items_to_show[:target_count]
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

        if len(items_to_show) > 60:
            items_to_show = items_to_show[:60]

        self._finish_filter_with_items(items_to_show)
        
    def _collect_filtered_items(self):
        """Collect filtered items WITHOUT modifying UI. Returns (items_to_show, is_default)."""
        search_q = self._parse_search_query()
        active_t, active_c, active_n = self._active_filter_values()
        max_cols = self._last_cols if self._last_cols > 0 else 5
        
        is_default = not search_q and not active_t and not active_c and not active_n
        items_to_show = []
        
        if is_default:
            for tag in self.popular_tanks:
                if tag in self.tank_db:
                    data = self.tank_db[tag]
                    tier = int(data.get("tier", 0) or 0)
                    if 8 <= tier <= 11:
                        items_to_show.append((tag, data))
            
            def _tier_sort(item):
                d = item[1] if isinstance(item[1], dict) else {}
                try:
                    return int(d.get("tier", 0) or 0)
                except Exception:
                    return 0
            items_to_show.sort(key=_tier_sort, reverse=True)

            target_rows = max(1, round(30 / max_cols))
            target_count = target_rows * max_cols
            
            if len(items_to_show) > target_count:
                items_to_show = items_to_show[:target_count]
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
    
    def _get_clean_tank_name(self, tag, data):
        raw_name = str(data.get("name", tag)).replace("_", " ")
        sys_id = tag.split('_')[0].lower()
        m = re.search(r'^([a-z]+)(\d*)$', sys_id)
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
        return raw_name

    def _finish_filter_with_items(self, items_to_show):
        """Build new grid in background, then swap instantly to avoid black flash."""
        fv_at_start = getattr(self, '_filter_version', 0)
        max_cols = self._last_cols if self._last_cols > 0 else 5

        new_grid = tk.Frame(self.ai_canvas, bg="#000", padx=0.5, pady=0.5)

        if not items_to_show:
            msg_text = self.t("no_tanks_found", "NO TANKS FOUND")
            msg_label = tk.Label(
                new_grid,
                text=msg_text,
                bg="#000",
                fg="#bbbbbb",
                font=("Arial", 14, "bold"),
                anchor="center",
                justify="center"
            )
            msg_label.pack(expand=True, fill="both")
        else:
            row, col = 0, 0
            for tag, data in items_to_show:
                if not isinstance(data, dict):
                    continue
                card_f = tk.Frame(new_grid, bg="#111", width=170, height=155)
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
                
                raw_name = self._get_clean_tank_name(tag, data)
                
                name_words = raw_name.split()
                if not name_words:
                    name_words = [data.get("name", tag)]
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
                
                for w in [tl, cl, nl, l1_f]:
                    w.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
                
                col += 1
                if col >= max_cols: col = 0; row += 1
            
        if getattr(self, '_filter_version', 0) != fv_at_start:
            new_grid.destroy()
            return
        
        for c in range(max_cols):
            new_grid.columnconfigure(c, weight=1)
        for c in range(max_cols, max_cols + 15):
            new_grid.columnconfigure(c, weight=0)
        
        new_grid.bind("<Configure>", lambda e: self.ai_canvas.configure(
            scrollregion=(0, 0, e.width, e.height)))
        
        self.ai_canvas.itemconfig(self.ai_canvas_window, window=new_grid)
        old_grid = self.ai_grid_frame
        self.ai_grid_frame = new_grid
        old_grid.destroy()
        
        self.root.after(50, lambda: (
            self.ai_grid_frame.update_idletasks(),
            self.ai_canvas.configure(
                scrollregion=(0, 0, self.ai_grid_frame.winfo_width(), self.ai_grid_frame.winfo_height()))
        )[-1])
        
        try:
            canvas_width = self.filter_progress_canvas.winfo_width()
            if canvas_width > 1:
                self.filter_progress_canvas.coords(self._progress_rect, 0, 0, canvas_width, 4)
        except Exception:
            pass
    def _animate_realtime(self, duration, work_func, callback):
        """Animate progress bar. work_func runs during animation; callback after both complete."""
        filter_version = self._filter_version
        if not self._filter_active:
            return
        start_time = time.time()
        result = [None]  # Mutable container for work result
        work_done = [False]
        
        def do_work():
            result[0] = work_func()
            work_done[0] = True
        
        import threading
        work_thread = threading.Thread(target=do_work, daemon=True)
        work_thread.start()
        
        def update():
            if not self._filter_active or self._filter_version != filter_version:
                return
            elapsed = time.time() - start_time
            progress = min(elapsed / duration, 1.0)
            try:
                canvas_width = self.filter_progress_canvas.winfo_width()
                if canvas_width > 1:
                    progress_width = int(canvas_width * progress)
                    self.filter_progress_canvas.coords(self._progress_rect, 0, 0, progress_width, 4)
                    self.filter_progress_canvas.update_idletasks()
            except Exception:
                pass
            
            if not work_done[0] or elapsed < duration:
                self.root.after(50, update)
            else:
                try:
                    canvas_width = self.filter_progress_canvas.winfo_width()
                    if canvas_width > 1:
                        self.filter_progress_canvas.coords(self._progress_rect, 0, 0, canvas_width, 4)
                        self.filter_progress_canvas.update_idletasks()
                except Exception:
                    pass
                if callback:
                    callback(result[0])
        
        update()
    
    def _hide_filter_progress(self):
        """Hide progress bar (canvas) but keep container (reserved space)"""
        self._filter_active = False
        self._filter_hide_job = None
        if hasattr(self, 'filter_progress_canvas') and self.filter_progress_canvas.winfo_exists():
            self.filter_progress_canvas.pack_forget()
        try:
            self.filter_progress_canvas.coords(self._progress_rect, 0, 0, 0, 4)
        except Exception:
            pass
        
    def return_to_ai_home(self):
        self.active_tank = None
        if hasattr(self, 'ai_res_f'): self.ai_res_f.pack_forget()
        if hasattr(self, 'ai_grid_container'): self.ai_grid_container.pack(side="top", fill="both", expand=True)
        if self._search_timer is not None:
            self.root.after_cancel(self._search_timer)
            self._search_timer = None
        self.ai_search_var.set(self.search_placeholder)
        for f in self.tier_filters.values(): f["active"] = False; f["btn"].config(bg="#333333", fg="#aaaaaa")
        for f in self.class_filters.values(): f["active"] = False; f["btn"].config(bg="#333333", fg="#aaaaaa")
        for f in self.nation_filters.values(): f["active"] = False; f["btn"].config(bg="#333333")
        self.refresh_ai_view()

    def get_loadout_icon(self, category, name, size=(40, 40), disabled=False):
        """Повертає PhotoImage іконки обладнання/снаряда/навички"""
        cache_key = f"{category}_{name}_{size[0]}_{disabled}"
        if cache_key in self.loadout_icon_cache:
            return self.loadout_icon_cache[cache_key]

        candidates = []
        if category == 'field_mods':
            base_field = os.path.join(self.LOADOUT_ICON_DIR, 'field_mods', 'pairModifications')
            for sub in ['120x120', '100x100', '80x80', '24x24']:
                candidates.append(os.path.join(base_field, sub, f"{name}.png"))
                candidates.append(os.path.join(base_field, sub, f"{name.lower()}.png"))

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
            if disabled:
                from PIL import ImageEnhance
                img = ImageEnhance.Brightness(img).enhance(0.3)
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            if category == 'crew_roles':
                scale_w = size[0] / max(1, img.width)
                scale_h = size[1] / max(1, img.height)
            else:
                max_upscale = 4.0
                scale_w = min(size[0] / max(1, img.width), max_upscale)
                scale_h = min(size[1] / max(1, img.height), max_upscale)
            scale = min(scale_w, scale_h)
            new_w = max(1, int(round(img.width * scale)))
            new_h = max(1, int(round(img.height * scale)))
            if category == 'crew_roles':
                resample = Image.LANCZOS
            else:
                resample = Image.NEAREST if img.width < 48 or img.height < 48 else Image.LANCZOS
            fitted = img.resize((new_w, new_h), resample)
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
                ("field_mods", "improvedEnginePower"),
                ("field_mods", "improvedAimingHandling"),
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

        for key, value in self.tank_tth.items():
            key_l = str(key).lower()
            key_n = key_l.replace('-', '_')
            if (key_l == tag_l or key_n == tag_n) and isinstance(value, dict) and value:
                return value

        base_tag = _strip_mode_suffixes(tag_n)
        if base_tag != tag_n:
            for key, value in self.tank_tth.items():
                key_n = str(key).lower().replace('-', '_')
                if key_n == base_tag and isinstance(value, dict) and value:
                    return value

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

        # Reverse: TTH keys with StoryMode 4-digit prefix -> target tag
        for key, value in self.tank_tth.items():
            key_n = str(key).lower().replace('-', '_')
            base_key = _strip_mode_suffixes(key_n)
            if base_key != key_n:
                m = re.match(r'^([a-z]+)(\d{4})_(.+)$', base_key)
                if m:
                    try:
                        pref, num4, rest = m.groups()
                        num_val = int(num4)
                        if num_val >= 1000:
                            candidate = f"{pref}{num_val - 1000}_{rest}"
                            if candidate == base_tag and isinstance(value, dict) and value:
                                return value
                    except Exception:
                        pass

        suffix = tag_n.split("_", 1)[1] if "_" in tag_n else tag_n
        for key, value in self.tank_tth.items():
            key_l = str(key).lower().replace('-', '_')
            key_suffix = key_l.split("_", 1)[1] if "_" in key_l else key_l
            if key_suffix == suffix and isinstance(value, dict) and value:
                return value

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
            img = Image.open(icon_path).convert("RGBA")
            if disabled:
                from PIL import ImageEnhance
                img = ImageEnhance.Brightness(img).enhance(0.3).resize(size, Image.LANCZOS)
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
        ammo_dir = os.path.join(self.LOADOUT_ICON_DIR, 'ammo')
        if not os.path.exists(ammo_dir):
            return None
        direct = os.path.join(ammo_dir, f'{shell_type}.png')
        if os.path.exists(direct):
            return shell_type
        files = os.listdir(ammo_dir)
        for f in files:
            if shell_type in f.replace('.png', ''):
                return f.replace('.png', '')
        return None

    def _extract_field_mod_tokens(self, tag):
        """Читає клієнтський *_modifications.xml і повертає KPI-токени в порядку появи."""
        cfg_path = os.path.join(
            _DATA_DIR,
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
        """Завантажує готову мапу пар FIELD MODS по танках, згенеровану з декодування XML."""
        path = os.path.join(
            _DATA_DIR,
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
        if tier == 11:
            return 0  # Tier 11 не мають польової модернізації
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
            if isinstance(cached, list) and len(cached) >= self._field_mod_pair_limit_for_tier(tag):
                return cached

        pair_limit = self._field_mod_pair_limit_for_tier(tag)
        if pair_limit <= 0:
            self._field_mod_pairs_cache[tag] = []
            return []

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

        tokens = self._extract_field_mod_tokens(tag)
        icons = []
        for tk_name in tokens:
            icon = self._field_mod_icon_from_token(tk_name)
            if icon and icon not in icons:
                icons.append(icon)

        if len(icons) >= 2:
            pairs = []
            i = 0
            while i + 1 < len(icons):
                pairs.append((icons[i], icons[i + 1]))
                i += 2
            if pairs:
                pairs = pairs[:pair_limit]
                self._field_mod_pairs_cache[tag] = pairs
                return pairs

        tank_info = self.tank_db.get(tag, {}) if isinstance(self.tank_db, dict) else {}
        tank_class = str((tank_info or {}).get('class', '')).upper()

        class_role_priority = {
            'HT':  ['role_HT_universal', 'role_HT_break', 'role_HT_assault'],
            'MT':  ['role_MT_universal', 'role_MT_sniper', 'role_MT_assault'],
            'LT':  ['role_LT_universal'],
            'TD':  ['role_ATSPG_universal', 'role_ATSPG_sniper', 'role_ATSPG_assault'],
            'SPG': ['role_ATSPG_universal', 'role_ATSPG_assault', 'role_ATSPG_sniper'],
        }
        role_pairs_map = {}
        for _, entry in self._field_mod_pairs_by_tank.items():
            if not isinstance(entry, dict):
                continue
            role = entry.get('role_normalized') or entry.get('role_raw', '')
            raw = entry.get('pairs', [])
            if role and raw and role not in role_pairs_map:
                parsed = []
                for item in raw:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        l, r = str(item[0]).strip(), str(item[1]).strip()
                        if l and r:
                            parsed.append((l, r))
                if parsed:
                    role_pairs_map[role] = parsed

        roles_to_try = class_role_priority.get(tank_class, [])
        for role in roles_to_try:
            if role in role_pairs_map:
                pairs = role_pairs_map[role][:pair_limit]
                self._field_mod_pairs_cache[tag] = pairs
                return pairs

        pairs = self._default_field_mod_pairs()[:pair_limit]
        self._field_mod_pairs_cache[tag] = pairs
        return pairs


    def on_ai_tank_select(self, tag):
        self.active_tank = tag
        
        self.detail_canvas.yview_moveto(0)
        
        def background_collect():
            tank_info = self._collect_tank_data(tag)
            if self.ai_equipment_frame.winfo_exists():
                self.ai_equipment_frame.after(0, lambda: self._finish_tank_detail_with_loading(tank_info))
        
        import threading
        threading.Thread(target=background_collect, daemon=True).start()


    def _finish_tank_detail_with_loading(self, tank_info):
        """Build tank detail UI without touching visibility (swap happens at end)."""
        if not tank_info:
            return
        self._finish_tank_detail(tank_info)


    def _collect_tank_data(self, tag):
        """Collect tank data without modifying UI. Returns dict with prepared data."""
        data = self.tank_db.get(tag, {})
        if not isinstance(data, dict):
            data = {}
        
        img = self.get_composite_icon(tag, data.get("nation", ""), size=(196, 126))
        
        tth = self._find_tth_for_tag(tag)
        if not tth:
            self.reload_tth_data()
            tth = self._find_tth_for_tag(tag)
        
        crew_rows = self._get_crew_rows_for_tank(tag)
        
        fm_pairs = self._get_field_mod_pairs_for_tank(tag)
        
        return {
            'tag': tag,
            'data': data,
            'img': img,
            'tth': tth or {},
            'crew_rows': crew_rows,
            'fm_pairs': fm_pairs,
        }

    def _finish_tank_detail(self, tank_info):
        """Build tank detail UI after animation completes."""
        if not tank_info:
            return
        
        tag = tank_info['tag']
        data = tank_info['data']
        img = tank_info['img']
        tth = tank_info['tth']
        crew_rows = tank_info['crew_rows']
        fm_pairs = tank_info['fm_pairs']
        
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
        if hasattr(self, '_loadout_num_label') and self._loadout_num_label.winfo_exists():
            self._loadout_num_label.destroy()
        if hasattr(self, '_loadout_num_label_2') and self._loadout_num_label_2.winfo_exists():
            self._loadout_num_label_2.destroy()
        
        is_prem = data.get("is_premium", False)
        acc = "#e09b1b" if is_prem else "#bbbbbb"
        
        hf = tk.Frame(self.ai_title_frame, bg="#111111")
        hf.pack(side="top", anchor="center", pady=(0, 8))
        roman_tiers = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
        try:
            tier_val = int(data.get('tier', 0) or 0)
        except Exception:
            tier_val = 0
        rt = roman_tiers[tier_val - 1] if 1 <= tier_val <= 11 else str(tier_val)
        tk.Label(hf, text=rt, font=("Arial", 16, "bold"), fg=acc, bg="#111111").pack(side="left", padx=(0, 4))
        s_flag = self.get_small_flag(data.get("nation", ""))
        if s_flag:
            fl = tk.Label(hf, image=s_flag, bg="#111111")
            fl.image = s_flag
            fl.pack(side="left", padx=(0, 4))
        xvm_classes = {"LT": chr(0x3A), "MT": chr(0x3B), "HT": chr(0x3F), "TD": chr(0x2E), "SPG": chr(0x2D)}
        sym = xvm_classes.get(str(data.get('class', '')).upper(), "?")
        tk.Label(hf, text=sym, font=("XVMSymbol", 18), fg=acc, bg="#111111").pack(side="left", padx=(0, 6))
        tk.Label(hf, text=data.get('name', tag), font=("Arial", 14, "bold"), fg=acc, bg="#111111").pack(side="left")
        
        tth_rows = []
        if tth.get('hp'):
            tth_rows.append(("relativeArmor.png", self._mo_label("vehicleInfo/params/maxHealth", "HP"), str(tth['hp'])))
        hull = tth.get('hull_armor', {})
        if isinstance(hull, dict) and hull:
            front = hull.get('front') or hull.get('f') or hull.get(list(hull.keys())[0])
            side = hull.get('side') or hull.get('s')
            rear = hull.get('rear') or hull.get('r')
            parts = [str(v) for v in [front, side, rear] if v is not None]
            if parts:
                tth_rows.append(("relativeArmor.png", self._mo_label("vehicleParams/hullArmor", "Hull armor"), " / ".join(parts)))
        elif hull:
            tth_rows.append(("relativeArmor.png", self._mo_label("vehicleParams/hullArmor", "Hull armor"), str(hull)))
        turret = tth.get('turret_armor', {})
        if isinstance(turret, dict) and turret:
            front = turret.get('front') or turret.get('f') or turret.get(list(turret.keys())[0])
            side = turret.get('side') or turret.get('s')
            rear = turret.get('rear') or turret.get('r')
            parts = [str(v) for v in [front, side, rear] if v is not None]
            if parts:
                tth_rows.append(("relativeArmor.png", self._mo_label("vehicleParams/turretArmor", "Turret armor"), " / ".join(parts)))
        elif turret:
            tth_rows.append(("relativeArmor.png", self._mo_label("vehicleParams/turretArmor", "Turret armor"), str(turret)))
        shells = tth.get('shells', [])
        if isinstance(shells, list) and shells:
            ap = next((s for s in shells if str(s.get('type', '')).upper() in ('AP', 'APCR', 'APBC', 'APCBC')), None)
            sh = ap or shells[0]
            dmg = sh.get('damage') or sh.get('alphaDamage')
            pen = sh.get('piercing_power') or sh.get('piercingPower') or sh.get('penetration')
            if dmg:
                tth_rows.append(("relativePower.png", self._mo_label("vehicleParams/damage", "Damage"), str(dmg)))
            if pen:
                if isinstance(pen, (list, tuple)):
                    pen = pen[0]
                tth_rows.append(("relativePower.png", self._mo_label("vehicleParams/piercingPower", "Penetration"), str(pen)))
        if tth.get('reload'):
            tth_rows.append(("relativePower.png", self._mo_label("vehicleInfo/params/reloadTimeSecs", "Reload"), str(tth['reload'])))
        spd = tth.get('speed_fwd') or tth.get('maxSpeed') or tth.get('speed')
        if spd:
            spd_bwd = tth.get('speed_bwd') or tth.get('maxSpeedBackward')
            spd_str = f"{spd}" + (f" / -{spd_bwd}" if spd_bwd else "")
            tth_rows.append(("relativeMobility.png", self._mo_label("vehicleParams/speedLimits", "Speed"), spd_str))
        if tth.get('view_range'):
            tth_rows.append(("relativeVisibility.png", self._mo_label("vehicleInfo/params/circularVisionRadius", "View range"), str(tth['view_range'])))
        
        tth_wrapper = tk.Frame(self.ai_tth_frame, bg="#1a1a1a", bd=0, relief="flat", highlightthickness=0, width=self._detail_info_fixed_width)
        tth_wrapper.pack(side="top", anchor="center", padx=0)
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
        for i, (icon_name, label_text, value_text) in enumerate(tth_rows):
            row_bg = "#1a1a1a" if i % 2 == 0 else "#1f1f1f"
            row_f = tk.Frame(tth_table, bg=row_bg)
            row_f.pack(side="top", fill="x", padx=6, pady=2)
            row_icon = self.get_tth_icon(icon_name, size=(16, 16))
            if row_icon:
                il = tk.Label(row_f, image=row_icon, bg=row_bg)
                il.image = row_icon
                il.pack(side="left", padx=(0, 5))
            tk.Label(row_f, text=label_text, fg="#9a9a9a", bg=row_bg, font=("Arial", 9), width=15, anchor="w").pack(side="left")
            tk.Label(row_f, text=value_text, fg="#e6e6e6", bg=row_bg, font=("Arial", 10, "bold"), anchor="e").pack(side="right", padx=(0, 4))
        
        equip_body = self._make_tiles_section(self.ai_equipment_frame, self._mo_label("easyTankEquipView/optDevices/title", "EQUIPMENT"), "equipment")
        cons_body = self._make_tiles_section(self.ai_consumables_frame, self._mo_label("easyTankEquipView/consumables/title", "CONSUMABLES"), "consumables")
        ammo_body = self._make_tiles_section(self.ai_ammo_frame, self._mo_label("easyTankEquipView/shells/title", "AMMUNITION"), "ammo")
        crew_body = self._make_tiles_section(self.ai_crew_frame, self._mo_label("easyTankEquipView/crew/title", "CREW"), "crew")

        fm_body = self._make_tiles_section(self.ai_field_mod_frame, self._mo_label("postProgressionIntro/title", "FIELD MODIFICATION"), "field_mod")
        

        equip_body_2 = tk.Frame(self.ai_equipment_frame_2, bg="#111111")
        equip_body_2.pack(side="top", fill="x", pady=3)
        cons_body_2 = tk.Frame(self.ai_consumables_frame_2, bg="#111111")
        cons_body_2.pack(side="top", fill="x", pady=3)
        ammo_body_2 = tk.Frame(self.ai_ammo_frame_2, bg="#111111")
        ammo_body_2.pack(side="top", fill="x", pady=3)
        
        loading_labels = []
        
        # Load AI build cache data for first render
        _ai_cache_build = {}
        if ENABLE_AI_BUILD_CACHE:
            try:
                _builds, _, _ = _load_ai_build_cache()
                if tag in _builds:
                    _ai_cache_build = _builds[tag]
            except Exception:
                pass
        
        def map_equip(name):
            return EQUIP_MAP.get(name, name.lower().replace(" ", "").replace("-", ""))
        def map_cons(name):
            return CONS_MAP.get(name, name.lower().replace(" ", "").replace("-", ""))
        def map_skill(name):
            return CREW_SKILL_MAP.get(name, name.lower().replace(" ", "").replace("-", ""))
        
        def _build_data(cached_data, tank_tth=None):
            if cached_data is None:
                cached_data = {}
            
            def _map_shell_type(raw_type):
                """Map game-internal shell type to canonical icon filename."""
                canon = {
                    "ARMOR_PIERCING": "ARMOR_PIERCING",
                    "AP": "ARMOR_PIERCING",
                    "ARMOR_PIERCING_CR": "ARMOR_PIERCING_CR",
                    "APCR": "ARMOR_PIERCING_CR",
                    "ARMOR_PIERCING_HE": "ARMOR_PIERCING_HE",
                    "APHE": "ARMOR_PIERCING_HE",
                    "HOLLOW_CHARGE": "HOLLOW_CHARGE",
                    "HEAT": "HOLLOW_CHARGE",
                    "HIGH_EXPLOSIVE": "HIGH_EXPLOSIVE",
                    "HE": "HIGH_EXPLOSIVE",
                    "HIGH_EXPLOSIVE_MODERN": "HIGH_EXPLOSIVE_MODERN",
                    "HIGH_EXPLOSIVE_SPG": "HIGH_EXPLOSIVE_SPG",
                }
                raw = raw_type.upper().replace('_', '').replace('-', '').replace(' ', '')
                for k, v in canon.items():
                    if k.replace('_', '') in raw or raw in k.replace('_', ''):
                        return v
                return None

            def _default_ammo_for_tank(tier, tank_class):
                """Return default shell types (max 3) based on tier and class."""
                if tank_class == "SPG":
                    base = ["HIGH_EXPLOSIVE_SPG", "HIGH_EXPLOSIVE", "HIGH_EXPLOSIVE_PREMIUM"]
                    return base[:3]
                base = ["ARMOR_PIERCING", "ARMOR_PIERCING_CR", "HIGH_EXPLOSIVE"]
                return base[:3]

            equipment_1 = []
            equipment_2 = []
            consumables_1 = []
            consumables_2 = []
            consumables = []
            crew_skills = []
            field_mods = []
            ammo = []
            
            if False:
                # tomato_data path removed - using cached_data only
                pass
            
            if not equipment_1:
                equipment_1 = cached_data.get("equipment_1", [])
            if not equipment_2:
                equipment_2 = cached_data.get("equipment_2", [])
            if not consumables_1:
                consumables_1 = cached_data.get("consumables_1", [])
            if not consumables_2:
                consumables_2 = cached_data.get("consumables_2", [])
            if not consumables_1 and not consumables_2:
                old_cons = cached_data.get("consumables", [])
                if old_cons:
                    consumables_1 = old_cons[:3]
                    consumables_2 = old_cons[:3]
            if not crew_skills:
                crew_skills = cached_data.get("crew", [])
            if not field_mods:
                field_mods = cached_data.get("field_mods", [])
            
            if not crew_skills:
                crew_skills = []
            if not field_mods:
                field_mods = []
            
            if tank_tth and tank_tth.get('shells'):
                shells = tank_tth['shells']
                for shell in shells:
                    shell_type = shell.get('type', '')
                    if shell_type:
                        mapped = _map_shell_type(shell_type)
                        if mapped:
                            ammo.append(mapped)
            if not ammo:
                cls = data.get('class', 'MT') if isinstance(data, dict) else 'MT'
                ammo = _default_ammo_for_tank(data.get('tier', 8) if isinstance(data, dict) else 8, cls)
            
            return {
                "equipment_1": equipment_1,
                "equipment_2": equipment_2,
                "consumables_1": consumables_1,
                "consumables_2": consumables_2,
                "ammo": ammo,  # Тепер типи снарядів з tank_tth, а не жорстко закодовані числа
                "crew": crew_skills,
                "field_mods": field_mods
            }

        build_data = _build_data(_ai_cache_build, tank_tth=tth)

        # Prewarm loadout icons from cached build data
        for k, cat, sz in [('equipment_1','artefacts',(48,48)),('equipment_2','artefacts',(48,48)),
                            ('consumables_1','artefacts',(48,48)),('consumables_2','artefacts',(48,48))]:
            for item in build_data.get(k, []):
                if item: self.get_loadout_icon(cat, item, sz)
        for sk_list in build_data.get('crew', []):
            if isinstance(sk_list, tuple) and len(sk_list) == 2:
                for sk in sk_list[1]:
                    if sk: self.get_loadout_icon('artefacts', sk, (24, 24))
        for a in build_data.get('ammo', []):
            n = a[0] if isinstance(a, tuple) else a
            if n: self.get_loadout_icon('ammo', n, (48, 48))

        self._update_ai_setup_ui(build_data, equip_body, cons_body, ammo_body, crew_body, fm_body,
                                   equip_body_2, cons_body_2, ammo_body_2, loading_labels, data, crew_rows, fm_pairs)

        self.root.update_idletasks()

        # Swap: hide grid first, then pack rendered detail at the top (no jump)
        self.ai_grid_container.pack_forget()
        self.ai_res_f.pack(side="top", fill="both", expand=True)
        self.root.update_idletasks()

        self._current_build_data = build_data
        self._current_bodies = (equip_body, cons_body, ammo_body, crew_body, fm_body,
                                equip_body_2, cons_body_2, ammo_body_2, loading_labels, data, crew_rows, fm_pairs)

        tank_name = data.get('name', tag)
        tag_copy = tag
        name_copy = tank_name
        self.root.after(100, lambda t=tag_copy, n=name_copy: self._launch_ai_tank_build(t, n))

    def _find_equip_key(self, tag, data):
        """Знаходить ключ у equipment_loadouts для заданого танка."""
        if not self._equipment_loadouts:
            return None
        if tag in self._equipment_loadouts:
            return tag
        name = (data.get('name', '') if isinstance(data, dict) else '').strip()
        parts = tag.split('_', 1)
        nation_code = parts[0] if parts else ''
        short_name = parts[1] if len(parts) > 1 else tag
        nation_code_alpha = re.sub(r'\d+$', '', nation_code)
        nation_map = {'A': 'usa', 'Ch': 'china', 'Cz': 'czech',
                      'Env': 'germany', 'F': 'france', 'G': 'germany',
                      'GB': 'uk', 'It': 'italy', 'J': 'japan',
                      'Pl': 'poland', 'R': 'ussr', 'S': 'sweden'}
        nation_str = nation_map.get(nation_code_alpha, '')
        exact = []
        name_match = []
        fuzzy = []
        for ek in self._equipment_loadouts:
            suffix = ek.split(':')[-1]
            if suffix == short_name:
                exact.append(ek)
            if nation_str and ek.startswith(nation_str + ':') and short_name in ek:
                fuzzy.append(ek)
            if name:
                name_key = name.lower().replace(' ', '_').replace('-', '_')
                if name_key and name_key in ek.lower():
                    name_match.append(ek)
        if exact: return exact[0]
        if name_match: return name_match[0]
        if fuzzy: return fuzzy[0]
        return None

    def _map_ai_fm_text_to_icon(self, text):
        t = text.lower()
        if "terrain" in t or "grouser" in t: return "additionalGrousers"
        if "lightweight" in t or "friction" in t: return "betterFriction"
        if "durability" in t or "chassis durability" in t: return "improvedChassisDurability"
        if "stability" in t and "chassis" in t: return "improvedChassisStability"
        if "aiming" in t or "parallax" in t or "gears" in t or "valve" in t: return "improvedAimingHandling"
        if "camouflage" in t or "concealment" in t: return "improvedCamouflage"
        if "engine" in t or "power" in t: return "improvedEnginePower"
        if "breech" in t: return "improvedGunBreech"
        if "filter" in t or "shielding" in t or "isolation" in t: return "improvedLightFilters"
        if "muzzle" in t: return "improvedMuzzleBreak"
        if "observation" in t or "right-angle" in t: return "improvedObservationDevice"
        if "reflex" in t: return "improvedReflexScopes"
        if "scope" in t or "powder" in t: return "improvedScope"
        if "tracks" in t or "self-repairing tracks" in t: return "improvedSelfRepairingTracks"
        if "wheels" in t and "repairing" in t: return "improvedSelfRepairingWheels"
        if "sharpness" in t or "visor" in t: return "improvedSharpnessVisor"
        if "sound" in t or "insulation" in t or "spalling" in t or "lenses" in t or "reflective" in t or "headlight" in t: return "improvedSpallingResistance"
        if "backwards" in t or "reverse" in t: return "improvedSpeedIndicatorBackwards"
        if "speed" in t or "forward" in t: return "improvedSpeedIndicator"
        if "ring" in t: return "improvedTurretRingStability"
        if "tuning" in t or "turret turning" in t or "suspension" in t: return "improvedTurretTurningWheels"
        if "sensitivity" in t or "optics" in t: return "increasedSensitivityOptics"
        if "thickness" in t or "armor" in t: return "increasedThickness"
        if "interior" in t or "modules" in t: return "reinforcedInteriorModules"
        if "structure" in t: return "reinforcedStructure"
        return "glow"

    def _update_ai_setup_ui(self, build_data, equip_body, cons_body, ammo_body, crew_body, fm_body, equip_body_2, cons_body_2, ammo_body_2, loading_labels, data, crew_rows, fm_pairs):
        try:
            if not equip_body.winfo_exists():
                return
        except:
            return
        
        for lbl in loading_labels:
            try:
                if lbl.winfo_exists(): lbl.destroy()
            except: pass
            
        for body in [equip_body, cons_body, ammo_body, crew_body, fm_body, equip_body_2, cons_body_2, ammo_body_2]:
            if body is None:
                continue
            try:
                if body.winfo_exists():
                    for w in body.winfo_children(): 
                        try: w.destroy()
                        except: pass
            except: pass
            
        def render_items(parent, items, category, size=(48, 48)):
            slots = []
            for name in items:
                if not name:
                    continue
                photo = self.get_loadout_icon(category, name, size)
                slot = tk.Frame(parent, bg="#111111", bd=0, relief="flat")
                icon_box = tk.Frame(slot, bg="#1d2a1a" if category == "artefacts" else "#1a1d2a", bd=1, relief="flat", width=size[0]+6, height=size[1]+6)
                icon_box.pack(side="top")
                icon_box.pack_propagate(False)
                lbl = tk.Label(icon_box, bg="#1d2a1a" if category == "artefacts" else "#1a1d2a", padx=0, pady=0)
                if photo:
                    lbl.config(image=photo)
                    lbl.image = photo
                else:
                    lbl.config(width=4, height=2, bg="#2a3a28" if category == "artefacts" else "#272a3a")
                lbl.pack(expand=True, fill="both")
                self._bind_item_tooltip(slot, name, category)
                slots.append(slot)
            self._layout_tile_row(parent, slots, gap=3)
            return slots

        def render_ammo_items(parent, items, category="ammo", size=(48, 48)):
            slots = []
            for item in items:
                if isinstance(item, tuple) and len(item) == 2:
                    name, count = item
                else:
                    name, count = item, 0
                photo = self.get_loadout_icon(category, name, size)
                slot = tk.Frame(parent, bg="#111111", bd=0, relief="flat")
                icon_box = tk.Frame(slot, bg="#1a1d2a", bd=1, relief="flat", width=size[0]+6, height=size[1]+6)
                icon_box.pack(side="top")
                icon_box.pack_propagate(False)
                lbl = tk.Label(icon_box, bg="#1a1d2a", padx=0, pady=0)
                if photo:
                    lbl.config(image=photo)
                    lbl.image = photo
                else:
                    lbl.config(width=4, height=2, bg="#272a3a")
                lbl.pack(expand=True, fill="both")
                if count > 0:
                    t_lbl = tk.Label(icon_box, text=str(count), fg="#ffffff", bg="#0a0b12", font=("Arial", 8, "bold"), padx=2, pady=0)
                    t_lbl.place(relx=1.0, rely=1.0, anchor="se")
                self._bind_item_tooltip(slot, name, category)
                slots.append(slot)
            self._layout_tile_row(parent, slots, gap=0)
            return slots

        ration_map = {
            "ussr": "ration", "usa": "cocacola", "germany": "chocolate", "uk": "ration_uk",
            "france": "hotCoffee", "china": "ration_china", "poland": "ration_poland",
            "czech": "ration_czech", "japan": "ration_japan", "italy": "ration_italy", "sweden": "ration_sweden"
        }
        nation = data.get("nation", "").split('_')[0]
        correct_ration = ration_map.get(nation.lower())
        loadout_num_label_1 = tk.Label(equip_body, text="1", font=("Arial", 10, "bold"), fg="#888888", bg="#111111", width=3, cursor="hand2")
        loadout_num_label_1.pack(side="left", padx=(0, 2))
        loadout_num_label_1.bind("<Enter>", lambda e: self._show_legend_tooltip(e, self.main_app.t("ui", "loadout_main")))
        loadout_num_label_1.bind("<Leave>", lambda e: self._hide_legend_tooltip())
        
        equip_grid_frame_1 = tk.Frame(equip_body, bg="#111111")
        equip_grid_frame_1.pack(side="left", fill="none", expand=False)
        render_items(equip_grid_frame_1, build_data.get("equipment_1", []), "artefacts")
        
        loadout_num_label_2 = tk.Label(equip_body_2, text="2", font=("Arial", 10, "bold"), fg="#888888", bg="#111111", width=3, cursor="hand2")
        loadout_num_label_2.pack(side="left", padx=(0, 2))
        loadout_num_label_2.bind("<Enter>", lambda e: self._show_legend_tooltip(e, self.main_app.t("ui", "loadout_alt")))
        loadout_num_label_2.bind("<Leave>", lambda e: self._hide_legend_tooltip())
        
        equip_grid_frame_2 = tk.Frame(equip_body_2, bg="#111111")
        equip_grid_frame_2.pack(side="left", fill="none", expand=False)
        render_items(equip_grid_frame_2, build_data.get("equipment_2", []), "artefacts")
        render_items(cons_body, build_data.get("consumables_1", build_data.get("consumables", [])), "artefacts")
        render_items(cons_body_2, build_data.get("consumables_2", build_data.get("consumables", [])), "artefacts")
        render_ammo_items(ammo_body, build_data.get("ammo", []), "ammo")
        render_ammo_items(ammo_body_2, build_data.get("ammo", []), "ammo")
        
        ai_crew = {}
        ai_crew_also = {}  # Secondary role skills
        
        crew_member_count = len(crew_rows)
        
        for role, skills in build_data.get("crew", []):
            r_lower = role.lower()
            
            if role == "loader_radio":
                if "loader" not in ai_crew:
                    ai_crew["loader"] = []
                ai_crew["loader"].append(skills[:6])
                
                if "loader" not in ai_crew_also:
                    ai_crew_also["loader"] = []
                ai_crew_also["loader"].append(skills[6:10])
            elif role == "loader_2" and len(skills) > 6:
                if "loader" not in ai_crew_also:
                    ai_crew_also["loader"] = []
                ai_crew_also["loader"].append(skills[6:])
                if "loader" not in ai_crew:
                    ai_crew["loader"] = []
                ai_crew["loader"].append(skills[:6])
            elif role == "loader_1" or role == "loader_2":
                r_lower = "loader"
                if r_lower not in ai_crew:
                    ai_crew[r_lower] = []
                ai_crew[r_lower].append(skills[:6] if len(skills) > 6 else skills)
            else:
                import re as _re
                r_lower = _re.sub(r'_\d+$', '', r_lower)
                if "radio" in r_lower or "radioman" in r_lower: r_lower = "radioman"
                elif "loader" in r_lower: r_lower = "loader"
                elif "gunner" in r_lower: r_lower = "gunner"
                elif "driver" in r_lower: r_lower = "driver"
                elif "commander" in r_lower: r_lower = "commander"
                if r_lower not in ai_crew:
                    ai_crew[r_lower] = []
                ai_crew[r_lower].append(skills)
            
        crew_slots = []
        for i, (member, _) in enumerate(crew_rows):
            slot = tk.Frame(crew_body, bg="#111111", bd=0, relief="flat")
            row = tk.Frame(slot, bg="#111111")
            row.pack(side="top", pady=(0, 3))
            
            role_str = member.get("role", "commander")
            primary_r_icon = role_str.lower()
            if "loader_radio" in primary_r_icon:
                primary_r_icon = "loader"
            elif "radio" in primary_r_icon or "radioman" in primary_r_icon:
                primary_r_icon = "radioman"
            elif "loader" in primary_r_icon:
                primary_r_icon = "loader"
            elif "gunner" in primary_r_icon:
                primary_r_icon = "gunner"
            elif "driver" in primary_r_icon:
                primary_r_icon = "driver"
            elif "commander" in primary_r_icon:
                primary_r_icon = "commander"
            
            also_roles = member.get("also") or []
            
            role_box = tk.Frame(row, bg="#111111", bd=0, relief="flat", width=40, height=40)
            role_box.pack(side="left", padx=(0, 3))
            role_box.pack_propagate(False)
            role_photo = self.get_loadout_icon("crew_roles", primary_r_icon + "_plus", (24, 24))
            role_lbl = tk.Label(role_box, bg="#111111")
            if role_photo:
                role_lbl.config(image=role_photo)
                role_lbl.image = role_photo
            role_lbl.pack(expand=True)
            
            for sec_role in also_roles:
                sec_icon = sec_role.lower()
                if "loader" in sec_icon: sec_icon = "loader"
                if "radio" in sec_icon or "radioman" in sec_icon: sec_icon = "radioman"
                if "gunner" in sec_icon: sec_icon = "gunner"
                if "driver" in sec_icon: sec_icon = "driver"
                if "commander" in sec_icon: sec_icon = "commander"
                
                sec_box = tk.Frame(row, bg="#111111", bd=0, relief="flat", width=40, height=40)
                sec_box.pack(side="left", padx=(0, 3))
                sec_box.pack_propagate(False)
                sec_photo = self.get_loadout_icon("crew_roles", sec_icon + "_plus", (24, 24))
                sec_lbl = tk.Label(sec_box, bg="#111111")
                if sec_photo:
                    sec_lbl.config(image=sec_photo)
                    sec_lbl.image = sec_photo
                sec_lbl.pack(expand=True)
                
            primary_skills = []
            secondary_skills = []
            original_role = member.get("role", "").lower()
            
            roles_to_check = [primary_r_icon] + [sr.lower() for sr in also_roles]
            for idx, r in enumerate(roles_to_check):
                is_primary = (idx == 0)
                if "loader_radio" in original_role:
                    if ai_crew.get("loader") and ai_crew["loader"]:
                        primary_skills = ai_crew["loader"].pop(0)
                    if ai_crew_also.get("loader") and ai_crew_also["loader"]:
                        secondary_skills = ai_crew_also["loader"].pop(0)
                else:
                    if "radio" in r or "radioman" in r: r = "radioman"
                    elif "loader" in r: r = "loader"
                    elif "gunner" in r: r = "gunner"
                    elif "driver" in r: r = "driver"
                    elif "commander" in r: r = "commander"
                    
                    target = primary_skills if is_primary else secondary_skills
                    if r in ai_crew and ai_crew[r]:
                        target.extend(ai_crew[r].pop(0))
                    if r in ai_crew_also and ai_crew_also[r]:
                        secondary_skills.extend(ai_crew_also[r].pop(0))
            
            seen_p = set()
            clean_primary = []
            for sk in primary_skills:
                if sk not in seen_p:
                    seen_p.add(sk)
                    clean_primary.append(sk)
            seen_s = set()
            clean_secondary = []
            for sk in secondary_skills:
                if sk not in seen_s:
                    seen_s.add(sk)
                    clean_secondary.append(sk)
            
            for sk in clean_primary:
                sk_box = tk.Frame(row, bg="#2a1a1a", bd=1, relief="flat", width=40, height=40)
                sk_box.pack(side="left", padx=(0, 3))
                sk_box.pack_propagate(False)
                self._bind_item_tooltip(sk_box, sk, "crew_perks")
                sk_photo = self.get_loadout_icon("artefacts", sk, (24, 24))
                sk_lbl = tk.Label(sk_box, bg="#2a1a1a")
                if sk_photo:
                    sk_lbl.config(image=sk_photo)
                    sk_lbl.image = sk_photo
                sk_lbl.pack(expand=True)
            
            if clean_secondary:
                spacer = tk.Frame(row, bg="#111111", width=16)
                spacer.pack(side="left")
                for sk in clean_secondary:
                    sk_box = tk.Frame(row, bg="#2a1a1a", bd=1, relief="flat", width=40, height=40)
                    sk_box.pack(side="left", padx=(0, 3))
                    sk_box.pack_propagate(False)
                    self._bind_item_tooltip(sk_box, sk, "crew_perks")
                    sk_photo = self.get_loadout_icon("artefacts", sk, (24, 24))
                    sk_lbl = tk.Label(sk_box, bg="#2a1a1a")
                    if sk_photo:
                        sk_lbl.config(image=sk_photo)
                        sk_lbl.image = sk_photo
                    sk_lbl.pack(expand=True)
            crew_slots.append(slot)

        self._layout_tile_grid(crew_body, crew_slots, min_cell=9999, gap=0, stretch=False)

        fm_raw = build_data.get("field_mods", [])
        
        fm_data = []
        if isinstance(fm_raw, list):
            for item in fm_raw:
                if isinstance(item, str):
                    fm_data.append(item)
                elif isinstance(item, dict):
                    fm_data.extend(item.keys())
        elif isinstance(fm_raw, dict):
            mods = fm_raw.get("mods", [])
            if isinstance(mods, list):
                for item in mods:
                    if isinstance(item, dict):
                        fm_data.extend(item.keys())
        
        fm_slots = []
        ai_fm_icons = []
        for text in fm_data:
            if isinstance(text, str):
                try:
                    icon = self._map_ai_fm_text_to_icon(text)
                    if icon:
                        ai_fm_icons.append(icon)
                except:
                    pass
        
        for pair in fm_pairs:
            if len(pair) != 2:
                continue
            mod_left, mod_right = pair[0], pair[1]
            is_left  = mod_left  in ai_fm_icons
            is_right = mod_right in ai_fm_icons
            if not is_left and not is_right:
                is_left = True
            
            pair_frame = tk.Frame(fm_body, bg="#111111", bd=0, relief="flat")
            
            for mod_id, is_selected in ((mod_left, is_left), (mod_right, is_right)):
                bg_sel   = "#1a2e1a"
                bg_dim   = "#0d1215"
                bd_color = "#3a6a3a" if is_selected else "#222222"
                
                icon_outer = tk.Frame(pair_frame, bg=bd_color, bd=0, relief="flat")
                icon_outer.pack(side="left", padx=2, pady=2)
                
                icon_box = tk.Frame(icon_outer, bg=bg_sel if is_selected else bg_dim,
                                    bd=0, relief="flat", width=62, height=62)
                icon_box.pack(padx=1, pady=1)
                icon_box.pack_propagate(False)
                
                photo = self.get_loadout_icon('field_mods', mod_id, (56, 56), disabled=not is_selected)
                lbl = tk.Label(icon_box, bg=bg_sel if is_selected else bg_dim, padx=0, pady=0)
                if photo:
                    lbl.config(image=photo)
                    lbl.image = photo
                else:
                    lbl.config(width=3, height=2, bg="#1e3020" if is_selected else "#0f161a")
                lbl.pack(expand=True)
            
            div = tk.Label(pair_frame, text="/", fg="#555555", bg="#111111", font=("Arial", 9))
            div.place(relx=0.5, rely=0.5, anchor="center")

            fm_slots.append(pair_frame)
        
        self._layout_pair_tiles_wrap(fm_body, fm_slots, pair_gap=6, row_gap=6)
        fm_body.bind("<Configure>", lambda e, c=fm_body, s=fm_slots: self._layout_pair_tiles_wrap(c, s, pair_gap=6, row_gap=6))
        
        self._reflow_detail_layout()
        
        tank_name = data.get('name', 'Unknown')
        
        self.detail_canvas.yview_moveto(0)
        
        self._hide_filter_progress()

        self.root.update_idletasks()

    def show_ai_result(self, text):
        pass  # ШІ результати видалено — тепер відображаємо ТТХ
    
    def schedule_browser(self):
        """Більше не використовується — AI запускається з splash в main.py"""
        pass

    def needs_ai_refresh(self):
        """Returns True if AI needs to run — only when cache is expired or missing."""
        if not ENABLE_POPULAR_TANK_CACHE:
            return True
        return not self._cache_fresh

    def _parse_ai_tank_build(self, text):
        """Parse AI response for a tank build. Returns updated build_data dict.
        Strips prompt echo — finds the last "Build Generated:" and parses from there."""
        import re as _re
        idx = text.rfind('Build Generated:')
        if idx >= 0:
            text = text[idx:]
        build_data = {}
        lines = text.split('\n')
        current_section = None
        loadout1_eq = []
        loadout2_eq = []
        loadout1_cons = []
        loadout2_cons = []
        ammo1 = []
        ammo2 = []
        crew = []
        field_mods = []

        def _clean_item(name):
            n = name.strip().strip('*').strip()
            nl = n.lower()
            for eq_key, eq_val in EQUIP_MAP.items():
                if nl == eq_key.lower():
                    return eq_val
            for cs_key, cs_val in CONS_MAP.items():
                if nl == cs_key.lower():
                    return cs_val
            best_val = None
            best_len = 0
            for eq_key, eq_val in EQUIP_MAP.items():
                ekl = eq_key.lower()
                if ekl in nl or nl in ekl:
                    if len(eq_key) > best_len:
                        best_val = eq_val
                        best_len = len(eq_key)
            if best_val:
                return best_val
            for cs_key, cs_val in CONS_MAP.items():
                csl = cs_key.lower()
                if csl in nl or nl in csl:
                    if len(cs_key) > best_len:
                        best_val = cs_val
                        best_len = len(cs_key)
            if best_val:
                return best_val
            return n.lower().replace(' ', '').replace('-', '')

        for line in lines:
            line = line.strip()
            if not line:
                continue
            ll = line.lower()
            if 'slot' not in ll:
                if ('equipment' in ll and ('loadout' in ll or ':' in ll)):
                    current_section = 'equipment'
                    continue
                elif 'ammo' in ll and ('loadout' in ll or ':' in ll):
                    current_section = 'ammo'
                    continue
                elif 'consumables' in ll and ('loadout' in ll or ':' in ll):
                    current_section = 'consumables'
                    continue
                elif ('crew' in ll and 'perks' in ll) or ('perks' in ll and ('commander' in ll or ':' in ll)):
                    current_section = 'crew'
                    continue
                elif ('field' in ll and ('mod' in ll or 'modification' in ll)) or 'level' in ll:
                    current_section = 'field_mods'

            if current_section == 'equipment':
                if 'loadout 1' in ll or 'main' in ll:
                    slots = _re.findall(r'Slot\s+\d+:\s*([^|]+)', line)
                    if slots:
                        loadout1_eq = [_clean_item(s) for s in slots[:3]]
                elif 'loadout 2' in ll or 'advanced' in ll:
                    slots = _re.findall(r'Slot\s+\d+:\s*([^|]+)', line)
                    if slots:
                        loadout2_eq = [_clean_item(s) for s in slots[:3]]
            elif current_section == 'ammo':
                if 'loadout 1' in ll or 'main' in ll:
                    types = _re.findall(r'([A-Z_]+)\s*:', line)
                    if types:
                        ammo1 = types[:3]
                elif 'loadout 2' in ll or 'advanced' in ll:
                    types = _re.findall(r'([A-Z_]+)\s*:', line)
                    if types:
                        ammo2 = types[:3]
            elif current_section == 'consumables':
                if 'loadout 1' in ll or 'main' in ll:
                    slots = _re.findall(r'Slot\s+\d+:\s*([^|]+)', line)
                    if slots:
                        loadout1_cons = [_clean_item(s) for s in slots[:3]]
                elif 'loadout 2' in ll or 'advanced' in ll:
                    slots = _re.findall(r'Slot\s+\d+:\s*([^|]+)', line)
                    if slots:
                        loadout2_cons = [_clean_item(s) for s in slots[:3]]
            elif current_section == 'crew':
                match = _re.match(r'\s*(?:\*|[─└├│\->]+\s*)?\s*([\w\-]+(?:\s*-\s*\w+)?)(?:\s*\([^)]*\))?\s*:\s*(.+)', line)
                if match:
                    role = match.group(1).strip().lower().replace(' ', '_').replace('-', '_')
                    if role == 'loader_radioman': role = 'loader_radio'
                    skills_text = match.group(2)
                    skills_text = _re.sub(r'^\s*\((?:primary|secondary)[^)]*\)\s*:\s*', '', skills_text)
                    skills_text = _re.sub(r'\s*\(choose\s+\d+\)\s*$', '', skills_text)
                    skills_text = skills_text.strip('[]')
                    skills_list = [s.strip() for s in skills_text.split(',') if s.strip()]
                    mapped = []
                    for s in skills_list:
                        found = False
                        sl = s.lower()
                        for sk_key, sk_val in CREW_SKILL_MAP.items():
                            if sl == sk_key.lower():
                                mapped.append(sk_val)
                                found = True
                                break
                        if found:
                            continue
                        best_val = None
                        best_len = 0
                        for sk_key, sk_val in CREW_SKILL_MAP.items():
                            skl = sk_key.lower()
                            if skl in sl or sl in skl:
                                if len(sk_key) > best_len:
                                    best_val = sk_val
                                    best_len = len(sk_key)
                        if best_val:
                            mapped.append(best_val)
                        else:
                            mapped.append(s.lower().replace(' ', '').replace('-', ''))
                    crew.append((role, mapped[:6]))
            elif current_section == 'field_mods':
                if 'level' in ll:
                    parts = line.split('|')
                    for part in parts:
                        if ':' in part:
                            choice = part.split(':')[1].strip()
                            field_mods.append(choice.lower().replace(' ', ''))

        build_data['equipment_1'] = loadout1_eq
        build_data['equipment_2'] = loadout2_eq
        build_data['consumables_1'] = loadout1_cons
        build_data['consumables_2'] = loadout2_cons
        build_data['ammo'] = ammo1 or ammo2
        build_data['crew'] = crew if crew else None
        build_data['field_mods'] = field_mods
        return build_data

    def _generate_tank_build_prompt(self, tag, tank_name):
        """Generate a concise prompt for the AI to create a competitive build."""
        import importlib
        import generate_prompt_v2
        importlib.reload(generate_prompt_v2)
        from generate_prompt_v2 import generate_prompt
        return generate_prompt(tag, tank_name)

    def _launch_ai_tank_build(self, tag, tank_name):
        """Запускає AI браузер для отримання build для конкретного танка.
        Якщо є свіжий кеш — використовує його, AI не запускає.
        Якщо попередній запит ще виконується — завершує його."""
        if ENABLE_AI_BUILD_CACHE:
            builds, updated, _ = _load_ai_build_cache()
            if tag in builds:
                if tag in updated and not _is_cache_expired(updated[tag], max_days=30):
                    print(f"[AI Tank Build] Свіжий кеш для {tag} — скіп, вже відрендерено")
                    return
                # Stale cache: show stale data while AI updates
                self.root.after(0, lambda bd=builds[tag]: self._update_ai_setup_ui(
                    bd, *self._current_bodies
                ) if hasattr(self, '_current_bodies') else None)
                print(f"[AI Tank Build] Кеш для {tag} прострочений, запускаю AI оновлення")
            else:
                print(f"[AI Tank Build] Немає кешу для {tag}, запускаю AI")

        if hasattr(self, '_ai_build_proc') and self._ai_build_proc and self._ai_build_proc.poll() is None:
            try:
                self._ai_build_proc.terminate()
                self._ai_build_proc.wait(timeout=3)
            except Exception:
                try: self._ai_build_proc.kill()
                except: pass
            self._ai_build_proc = None
            print(f"[AI Tank Build] terminated previous request")

        self._current_build_tag = tag
        prompt = self._generate_tank_build_prompt(tag, tank_name)
        prompt_bytes = prompt.encode('utf-8', errors='replace')
        tag_bytes = str(tag).encode('utf-8', errors='replace')
        sys.stdout.buffer.write(b"[AI Tank Build] PROMPT FOR " + tag_bytes + b":\n")
        sys.stdout.buffer.write(prompt_bytes)
        sys.stdout.buffer.write(b"\n[AI Tank Build] END PROMPT\n")
        sys.stdout.buffer.flush()

        def run_build_process():
            proc = None
            try:
                if getattr(sys, 'frozen', False):
                    cmd = [sys.executable, "--ai-webview", "--prompt", prompt]
                else:
                    script = os.path.join(_DATA_DIR, "main.py")
                    cmd = [sys.executable, script, "--ai-webview", "--prompt", prompt]
                print(f"[AI Tank Build] running for {tag}")
                proc = subprocess.Popen(
                    cmd,
                    cwd=_DATA_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8', errors='replace',
                )
                self._ai_build_proc = proc
                out = ""
                try:
                    out, _ = proc.communicate(timeout=120)
                except subprocess.TimeoutExpired:
                    print(f"[AI Tank Build] TIMEOUT (120s) for {tag} — killing subprocess", flush=True)
                    proc.kill()
                    out, _ = proc.communicate()

                lines = []
                for line in out.split('\n'):
                    line = line.strip()
                    if 'RESPONSE_READY' in line:
                        break
                    if line and not line.startswith('[AI Browser]'):
                        lines.append(line)

                if lines and len(lines) >= 3:
                    combined = '\n'.join(lines)
                    print(f"[AI Tank Build] response for {tag} ({len(lines)} lines):")
                    print(combined)
                    if self._current_build_tag == tag:
                        build_data = self._parse_ai_tank_build(combined)
                        if build_data and hasattr(self, 'ai_equipment_frame') and self.ai_equipment_frame.winfo_exists():
                            self.root.after(0, lambda bd=build_data: self._apply_ai_build(bd))
                else:
                    print(f"[AI Tank Build] insufficient response for {tag} ({len(lines)} lines)")
                    _handle_ai_build_failure(tag)

            except Exception as e:
                print(f"[AI Tank Build] ERROR for {tag}: {e}")
                try:
                    _handle_ai_build_failure(tag)
                except: pass
            finally:
                if proc and proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except Exception:
                        try: proc.kill()
                        except: pass
                if self._ai_build_proc is proc:
                    self._ai_build_proc = None

        threading.Thread(target=run_build_process, daemon=True).start()

    def _apply_ai_build(self, build_data):
        """Apply AI build data to the current tank detail UI."""
        if not hasattr(self, 'ai_equipment_frame') or not self.ai_equipment_frame.winfo_exists():
            return
        if not hasattr(self, '_current_bodies'):
            return
        bd = self._current_build_data
        if bd is None:
            return
        for k in ['equipment_1', 'equipment_2', 'consumables_1', 'consumables_2', 'ammo']:
            if k in build_data and build_data[k]:
                bd[k] = build_data[k]
        if build_data.get('crew'):
            bd['crew'] = build_data['crew']
        if build_data.get('field_mods'):
            bd['field_mods'] = build_data['field_mods']
        bodies = self._current_bodies
        self._update_ai_setup_ui(bd, *bodies)
        if ENABLE_AI_BUILD_CACHE:
            tag = self._current_build_tag if hasattr(self, '_current_build_tag') else None
            if tag:
                _save_ai_build_cache(tag, build_data, fail_count=0)

    def _handle_ai_failure(self):
        """Called on main thread when AI fetch failed. Increments fail_count and logs on 3rd failure."""
        fc = 0
        if self._cache_data:
            fc = self._cache_data.get('fail_count', 0) + 1
            self._cache_data['fail_count'] = fc
            try:
                with open(_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cur = json.load(f)
                cur['fail_count'] = fc
                with open(_CACHE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(cur, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        if not self.popular_tanks and self._cache_data and self._cache_data.get('tanks'):
            cached_tanks = [t['tag'] for t in self._cache_data['tanks'] if t.get('tag') in self.tank_db]
            if cached_tanks:
                self.popular_tanks = cached_tanks
                self.refresh_ai_view()
                print(f"[AVISO] Завантажено з кешу (спроба {fc})")
        if fc > 0 and fc % 3 == 0:
                    from service_messages import log_event
                    log_event(
                        "popular_tanks",
                        f"Не вдалося оновити популярні танки після {fc} спроб поспіль.",
                        level="warning"
                    )

    def stop_browser(self):
        """Зупиняє процес браузера при виході з програми."""
        proc = getattr(self, '_ai_browser_process', None)
        if proc and proc.poll() is None:
            print("[AI Browser] stopping browser process")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()

    def launch_ai_browser(self, prompt=None, progress_cb=None, done_cb=None):
        """Запускає AI браузер (ai_webview_gui.py) для отримання популярних танків"""
        print("[AI Browser] launch_ai_browser called")
        if not hasattr(self, '_ai_fetch_in_progress'):
            self._ai_fetch_in_progress = False
        if self._ai_fetch_in_progress:
            print("[AI Browser] fetch in progress, returning")
            return
        self._ai_fetch_in_progress = True

        if prompt:
            ai_prompt = prompt
        else:
            today_str = date.today().strftime("%Y-%m-%d")
            ai_prompt = f"{today_str}. In World of Tanks, compile a list of the 50 most popular tanks for tiers 8-11, using the exact tank names as they appear in the game client. List only the tank names, one per line."

        def run_browser_process():
            try:
                if getattr(sys, 'frozen', False):
                    cmd = [sys.executable, "--ai-webview", "--prompt", ai_prompt]
                else:
                    script = os.path.join(_DATA_DIR, "main.py")
                    cmd = [sys.executable, script, "--ai-webview", "--prompt", ai_prompt]
                print(f"[AI Browser] running: {' '.join(cmd)}")
                if progress_cb:
                    progress_cb(10, self.locale_manager.t_ui('data_updating'))
                self._ai_browser_process = subprocess.Popen(
                    cmd,
                    cwd=_DATA_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8', errors='replace',
                )
                proc = self._ai_browser_process
                if progress_cb:
                    progress_cb(25, self.locale_manager.t_ui('fetching_info'))

                out = ""
                try:
                    out, _ = proc.communicate(timeout=45)
                except subprocess.TimeoutExpired:
                    print("[AI Browser] TIMEOUT (45s) — killing subprocess", flush=True)
                    proc.kill()
                    out, _ = proc.communicate()

                resp_file = os.path.join(tempfile.gettempdir(), "wot_ai_response.txt")
                if os.path.exists(resp_file):
                    with open(resp_file, 'r', encoding='utf-8') as f:
                        file_out = f.read()
                    try:
                        os.remove(resp_file)
                    except Exception:
                        pass
                    if file_out:
                        out = file_out

                tank_lines = []
                for line in out.split('\n'):
                    line = line.strip()
                    if 'RESPONSE_READY' in line:
                        break
                    if line and not line.startswith('[AI Browser]') and not line.startswith('ERROR:'):
                        tank_lines.append(line)

                if tank_lines:
                    combined = '\n'.join(tank_lines)
                    if progress_cb:
                        progress_cb(70, self.locale_manager.t_ui('processing'))
                    parse_event = threading.Event()
                    self.root.after(0, lambda t=combined, ev=parse_event: [
                        self.process_ai_response(t),
                        ev.set()
                    ])
                    parse_event.wait(timeout=30)
                    if progress_cb:
                        progress_cb(95, self.locale_manager.t_ui('ready'))
                else:
                    pass

                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    pass

            except Exception as e:
                print(f"[AI Browser] ERROR: {e}")
            finally:
                proc = getattr(self, '_ai_browser_process', None)
                if proc:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                self._ai_browser_process = None
                self.root.after(0, self._re_enable_ui)
                self.root.after(0, self._handle_ai_failure)
                if done_cb:
                    done_cb()

        threading.Thread(target=run_browser_process, daemon=True).start()

    def _re_enable_ui(self):
        self._ai_fetch_in_progress = False

    def process_ai_response(self, response_text):
        """Обробляє відповідь від AI і оновлює популярні танки"""
        try:
            tank_names = []
            lines = response_text.split('\n')
            print(f"[AI Response] Received {len(lines)} lines")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                clean = re.sub(r'^[\d\*\-•]+\s*[\.\)\-\s]*\s*', '', line).strip()
                clean = clean.replace('**', '').replace('*', '').replace('__', '')
                clean = re.sub(r'\s*\(.*?\)\s*$', '', clean).strip()
                low = clean.lower()

                skip_words = [
                    'перейти', 'справка', 'оставить', 'войти', 'режим ии',
                    'результаты поиска', 'все', 'картинки', 'видео', 'новости',
                    'google', 'форум', 'account', 'поиск', 'настройки',
                    'list the most popular', 'output only', 'sorted by',
                    'here are', 'here is', 'as of', 'based on', 'these are',
                    'the most', 'popular tanks', 'tiers 6', 'tier 6', 'tier 7',
                    'tier 8', 'tier 9', 'tier 10', 'tier 11',
                    'note:', 'please note', 'disclaimer',
                    'i hope', 'let me', 'do you', 'would you', 'could you',
                    'reddit', 'www.', '.com', '.org', 'sign in', 'sign up',
                    'world of tanks', 'worldoftanks',
                ]
                blocked = False
                for sw in skip_words:
                    if sw in low:
                        blocked = True
                        break
                if blocked:
                    continue
                if len(clean) < 3 or len(clean) > 60:
                    continue
                if re.match(r'^[\w\s\'\-\.\/\,\:\(\)\&]+$', clean):
                    tank_names.append(clean)

            print(f"[AI Response] After filtering: {len(tank_names)} tank candidates")
            if tank_names:
                name_to_tag = self._build_name_to_tag_lookup()
                raw_tanks = []
                seen = set()
                for n in tank_names:
                    tag = self._find_tank_tag(n, name_to_tag)
                    if tag is None:
                        tag = n.lower().replace(' ', '_').replace("'", "").replace(".", "").replace("/", "_").replace(",", "")
                    if tag not in seen:
                        seen.add(tag)
                        raw_tanks.append({"name": n, "tag": tag})
                raw_tanks = raw_tanks[:50]
                valid_tanks = [t for t in raw_tanks if t['tag'] in self.tank_db]
                print(f"[AI Response] {len(raw_tanks)} raw, {len(valid_tanks)} valid (found in DB)")
                tanks = valid_tanks[:30]
                for t in tanks:
                    t_tag = t.get('tag')
                    t['tier'] = self.tank_db.get(t_tag, {}).get('tier', 0)
                tanks.sort(key=lambda x: x.get('tier', 0), reverse=True)
                for t in tanks:
                    t.pop('tier', None)
                cache_data = {"tanks": tanks, "updated": time.strftime("%Y-%m-%dT%H:%M:%S"), "fail_count": 0}
                if ENABLE_POPULAR_TANK_CACHE:
                    with open(_CACHE_PATH, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, ensure_ascii=False, indent=2)
                self.popular_tanks = [t['tag'] for t in tanks]
                self.refresh_ai_view()
                pass
            else:
                pass
            self._re_enable_ui()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._re_enable_ui()
