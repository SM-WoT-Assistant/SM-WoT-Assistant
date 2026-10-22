# painter.py (відновлено з ARC/painter_1_06.py)
import os, json, math, copy
import tkinter as tk
import config
import ctypes
import dialog_utils

font_path = os.path.join(config.BASE_DIR, "xvmsymbol.ttf")
if os.path.exists(font_path):
    FR_PRIVATE = 0x10
    ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)

fa_path = os.path.join(config.BASE_DIR, "fontawesome-webfont.ttf")
if os.path.exists(fa_path):
    FR_PRIVATE = 0x10
    ctypes.windll.gdi32.AddFontResourceExW(fa_path, FR_PRIVATE, 0)

class MapPainter:
    def __init__(self, canvas, app, data_mgr):
        self.canvas = canvas
        self.app = app
        self.data_mgr = data_mgr
        self.drawings = self.data_mgr.load_drawings()
        for map_id in list(self.drawings.keys()):
            self.drawings[map_id] = self._normalize_coords(self.drawings[map_id])
            self.drawings[map_id] = self._strip_duplicates(self.drawings[map_id])
        
        self.active_tool = None
        self.default_color = "#ffaa00"
        
        self.start_x = 0
        self.start_y = 0
        self.temp_item = None
        self.move_drag = None
        self.move_drag_active = False
        self._editing_idx = -1
        # Єдиний хронологічний undo-стек (фікс 27.09.2026): раніше були ТРИ
        # незалежні стеки (creation/move/deletion) з фіксованим пріоритетом
        # у ctrl_z_undo — Ctrl+Z відкочував НЕ останню дію (створив A →
        # видалив B → Ctrl+Z відновлював B), move/deletion переживали зміну
        # мапи (idx з чужої мапи застосовувався до поточної), а хак-корекція
        # індексів creation ламала LIFO-порядок.
        # Операції: ("create", map_id, obj) — видалення за ідентичністю (`is`);
        # ("delete", map_id, idx, obj) — вставка на idx (LIFO → idx валідний);
        # ("delete_all", map_id, [(idx, obj), ...]) — відновлення за зростанням;
        # ("move", map_id, idx, original) — відкат coords;
        # ("update", map_id, idx, snapshot) — відкат мутації на місці (resize).
        # Об'єкти в операціях — САМІ живі dict (без deepcopy): видалений з
        # списку об'єкт ніхто не мутує, тож `is`-пошук create лишається
        # коректним після послідовності delete→undo→undo.
        self._undo_stack = []

        self._group_schemes = {}  # {drawing_id: {map_id, elements, group_id, updated_at, ...}}
        self._scheme_downloaded_at = {}  # {drawing_id: "2026-06-29 15:30:00"}
        self._hidden_download_schemes = set()  # {scheme_id} — схеми приховані в Download діалозі
        self._thickness = int(self.app.settings.get("draw_thickness", 3))
        self._select_all = False
        # Shift-множинне виділення: індекси drawings[map_id]. Операції
        # (рух/делет) застосовуються до всієї множини одним undo-записом.
        # Індикатор — підсвітка кнопок типів у палітрі + рядок стану (#A).
        self._multi_sel = set()
        self._clipboard_obj = None
        self._press_candidate = None
        self._press_moved = False
        self._alt_active = False
        # Ctrl+C/V через <Control-KeyPress> + keycode (VK 67/86) — працює в
        # будь-якій розкладці. Keysym-імена (cyrillic_es/ve) Windows Tk
        # відкидає прямо в bind() — крах старту (інцидент 26.08.2026).
        self.app.root.bind("<Control-KeyPress>", self._on_clipboard_key)
        # V (VK 86) → select tool + Alt spring-loaded move (Етапи 4-5),
        # Del → видалення виділеного (Етап 6) — на root, доки фокус не в Entry.
        self.app.root.bind("<KeyPress>", self._on_tool_hotkey, add="+")
        self.app.root.bind("<Delete>", self._on_delete_key, add="+")
        self.app.root.bind("<KeyPress-Alt_L>", self._on_alt_press, add="+")
        self.app.root.bind("<KeyPress-Alt_R>", self._on_alt_press, add="+")
        self.app.root.bind("<KeyRelease-Alt_L>", self._on_alt_release, add="+")
        self.app.root.bind("<KeyRelease-Alt_R>", self._on_alt_release, add="+")
        self.app.root.bind("<FocusOut>", self._on_focus_out, add="+")

    def apply_thickness_to_all(self, value):
        """Apply thickness to ALL existing drawings on current map."""
        map_id = getattr(self.app, "current_map_eng", None)
        if not map_id or map_id not in self.drawings:
            return
        changed = 0
        for obj in self.drawings[map_id]:
            if obj.get("type") in ("marker", "arrow", "brush"):
                old = obj.get("thickness", 3)
                if old != value:
                    obj["thickness"] = value
                    changed += 1
        if changed:
            self.save_drawings()
            self.redraw()

    def _coords_match(self, c1, c2):
        if len(c1) != len(c2):
            return False
        for a, b in zip(c1, c2):
            if abs(a - b) >= 0.001:
                return False
        return True

    def _normalize_coords(self, items):
        for obj in items:
            if "coords" not in obj and ("x1" in obj or "y1" in obj):
                x1 = obj.get("x1", 0)
                y1 = obj.get("y1", 0)
                x2 = obj.get("x2", x1)
                y2 = obj.get("y2", y1)
                obj["coords"] = [x1, y1, x2, y2]
        return items

    def _is_duplicate(self, obj, others):
        for existing in others:
            if obj["type"] != existing.get("type"):
                continue
            if obj["color"] != existing.get("color"):
                continue
            if not self._coords_match(obj.get("coords", []), existing.get("coords", [])):
                continue
            if obj.get("text", "") != existing.get("text", ""):
                continue
            if sorted(obj.get("classes", [])) != sorted(existing.get("classes", [])):
                continue
            if sorted(obj.get("modes", [])) != sorted(existing.get("modes", [])):
                continue
            if sorted(obj.get("poi", [])) != sorted(existing.get("poi", [])):
                continue
            if obj.get("scale", 1.0) != existing.get("scale", 1.0):
                continue
            if obj.get("arrow_start") != existing.get("arrow_start"):
                continue
            if obj.get("arrow_end") != existing.get("arrow_end"):
                continue
            return True
        return False

    def _strip_duplicates(self, items):
        seen = []
        result = []
        for obj in items:
            if not self._is_duplicate(obj, seen):
                seen.append(obj)
                result.append(obj)
        return result

    def save_drawings(self):
        self.data_mgr.save_drawings(self.drawings)

    def _autosave_active_scheme(self):
        """Після commit-зміни малюнка — автосейв поточної активної схеми."""
        palette = getattr(self.app, 'drawing_palette', None)
        if palette:
            palette._autosave_current_scheme()

    def apply_scale_to_all(self, value):
        map_id = getattr(self.app, "current_map_eng", None)
        if not map_id or map_id not in self.drawings:
            return
        changed = 0
        for obj in self.drawings[map_id]:
            old = obj.get("scale", 1.0)
            if abs(old - value) > 0.01:
                obj["scale"] = value
                changed += 1
        if changed:
            self.save_drawings()
            # Scale must reach saved_schemes (the mod reads the scheme at
            # battle start, not the canvas) - otherwise the minimap keeps
            # the old size (user report 03.10.2026).
            self._autosave_active_scheme()
            self.redraw()

    def toggle_select_all(self):
        self._select_all = not self._select_all
        if self._select_all:
            # ALL = повний вибір множини; Shift-множина стає зайвою —
            # прибираємо, щоб два виділення не конфліктували в палітрі.
            self._clear_multi_sel(silent=True)
            palette = getattr(self.app, 'drawing_palette', None)
            if palette and palette.is_in_edit_mode():
                palette.exit_edit_mode()
        self.redraw()

    def select_all_active(self):
        return self._select_all

    # ------------------------------------------------------------------
    # Shift-множинне виділення + груповий рух (12.10.2026, варіант A)
    # ------------------------------------------------------------------
    def multi_sel_active(self):
        return bool(self._multi_sel)

    def _notify_multi_changed(self):
        palette = getattr(self.app, 'drawing_palette', None)
        if palette and hasattr(palette, "update_multi_selection"):
            palette.update_multi_selection()

    def _toggle_multi_sel(self, idx):
        """Shift+клік: додати/прибрати елемент з множини."""
        if idx in self._multi_sel:
            self._multi_sel.discard(idx)
        else:
            self._multi_sel.add(idx)
        # Множинне виділення і одиночне — різні режими: входячи в множину,
        # знімаємо одиночне, щоб палітра не показувала суперечливий стан.
        if self._multi_sel:
            palette = getattr(self.app, 'drawing_palette', None)
            if palette and palette.is_in_edit_mode():
                palette.exit_edit_mode()
        self._notify_multi_changed()
        self.redraw()

    def _clear_multi_sel(self, silent=False):
        if not self._multi_sel:
            return
        self._multi_sel = set()
        if not silent:
            self._notify_multi_changed()
        self.redraw()

    def _start_group_move(self, event, indices):
        """Старт групового перетягування елементів за списком індексів."""
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        group = []
        for i in indices:
            if 0 <= i < len(objects):
                o = objects[i]
                group.append((i, {
                    "coords": list(o.get("coords", [])),
                    "class_icon_coords": list(o.get("class_icon_coords", [])),
                    "text_coords": list(o.get("text_coords", [])) if o.get("text_coords") else [],
                    "had_norm": o.get("norm"),
                }))
        if not group:
            return
        self._press_candidate = {
            "index": group[0][0],
            "target_kind": "object",
            "start_event": (event.x, event.y),
            "group": group,
        }
        self._press_moved = False

    def _clipboard_focus_in_field(self):
        """Ctrl+C/V не перехоплюємо, коли фокус у текстовому віджеті — там
        має працювати звичайне копіювання тексту. Працює для Entry/Text
        в будь-якому вікні: палітра, діалоги, налаштування."""
        try:
            w = self.app.root.focus_get()
        except Exception:
            return False
        if w is None:
            return False
        return getattr(w, "widgetName", "") in ("entry", "text", "spinbox", "combobox")

    def _on_clipboard_key(self, event=None):
        """Ctrl+C/V через keycode (VK 67/86) — розкладконезалежно.
        Повертає "break" для C/V (стоп поширення bindtags — без подвійного
        спрацювання canvas+root), None для решти клавіш."""
        try:
            state = int(getattr(event, "state", 0) or 0)
            code = int(getattr(event, "keycode", 0) or 0)
        except Exception:
            return None
        if not (state & 0x4):  # Control не затиснуто
            return None
        # УВАГА: біт 0x8 (який я вважав Alt) на реальних системах супроводжує
        # звичайний Ctrl (state=12 на Ctrl+C з доказів [CLIP] 28.08.2026) —
        # гард на 0x8 блокував би ВСІ Ctrl+C/V. Alt не перехоплюємо окремо.
        if code == 67:
            return self.on_clipboard_copy(event)
        if code == 86:
            return self.on_clipboard_paste(event)
        return None

    def copy_selected(self):
        """Копіює вибраний локальний елемент у буфер (Ctrl+C)."""
        map_id = self.app.current_map_eng
        if not map_id or self.app.mode != "edit":
            return False
        idx = getattr(self, "_editing_idx", -1)
        objects = self.drawings.get(map_id, [])
        if idx < 0 or idx >= len(objects):
            return False
        self._clipboard_obj = copy.deepcopy(objects[idx])
        self._paste_count = 0
        return True

    def paste_clipboard(self):
        """Вставляє копію на ту саму позицію; теги modes/classes беруться з
        поточних чекбоксів палітри (паста = новий елемент)."""
        if self._clipboard_obj is None:
            return False
        map_id = self.app.current_map_eng
        if not map_id or self.app.mode != "edit":
            return False
        new_obj = copy.deepcopy(self._clipboard_obj)
        # Копія зі зсувом +20px — інакше вона лягає РІВНО на оригінал і паста
        # виглядає «непрацюючою» (28.08.2026); повторні пасти каскадуються
        # (кожна наступна +20px від попередньої).
        try:
            _, _, cw, ch = self._img_rect()
            cw = max(int(cw), 1)
            ch = max(int(ch), 1)
            off = getattr(self, "_paste_count", 0) + 1
            self._paste_count = off
            dx = 20.0 * off / max(cw, 1)
            dy = 20.0 * off / max(ch, 1)
            for key in ("coords", "text_coords"):
                c = new_obj.get(key)
                if isinstance(c, list) and len(c) >= 2:
                    new_obj[key] = [min(max(c[i] + (dx if i % 2 == 0 else dy), 0.0), 1.0)
                                    for i in range(len(c))]
        except Exception:
            pass
        palette = getattr(self.app, 'drawing_palette', None)
        if palette:
            # Копія: modes = поточний режим (видна в цьому режимі),
            # класи з поточних чекбоксів палітри.
            new_obj["modes"] = [self.app.selected_battle_mode.get()]
            new_obj["classes"] = [k for k, v in palette.class_vars.items() if v.get()]
        if map_id not in self.drawings:
            self.drawings[map_id] = []
        self.drawings[map_id].append(new_obj)
        self._undo_stack.append(("create", map_id, new_obj))
        # Паста — свідоме дублювання: зберігаємо БЕЗ _strip_duplicates,
        # інакше копія, тотожна оригіналу (типові порожні теги), мовчазно
        # зрізалась і «паста не вставляла на поточну мапу» (28.08.2026).
        self.data_mgr.save_drawings(self.drawings)
        self.redraw()
        self._edit_object_at(len(self.drawings[map_id]) - 1)
        return True

    def on_clipboard_copy(self, event=None):
        if self._clipboard_focus_in_field():
            return "break"
        palette = getattr(self.app, 'drawing_palette', None)
        if self.copy_selected():
            if palette:
                palette.set_status(self.app.t('ui', 'element_copied'))
        else:
            if palette:
                palette.set_status(self.app.t('ui', 'element_copy_none'))
        return "break"

    def on_clipboard_paste(self, event=None):
        if self._clipboard_focus_in_field():
            return "break"
        palette = getattr(self.app, 'drawing_palette', None)
        if self.paste_clipboard():
            if palette:
                palette.set_status(self.app.t('ui', 'element_pasted'))
        else:
            if palette:
                palette.set_status(self.app.t('ui', 'element_paste_none'))
        return "break"

    def bind_events_to(self, target_canvas):
        """Прив'язка подій малювання до конкретного канвасу."""
        for ev, cb in [
            ("<ButtonPress-1>", self.on_press),
            ("<B1-Motion>", self.on_drag),
            ("<ButtonRelease-1>", self.on_release),
            ("<Control-Button-1>", self.on_move_press),
            ("<Control-B1-Motion>", self.on_move_drag),
            ("<Control-ButtonRelease-1>", self.on_move_release),
            ("<Button-3>", self.on_right_click),
            ("<Escape>", self.on_escape_deselect),
            ("<Delete>", self._on_delete_key),
            ("<KeyPress>", self._on_tool_hotkey),
            ("<KeyPress-Alt_L>", self._on_alt_press),
            ("<KeyPress-Alt_R>", self._on_alt_press),
            ("<KeyRelease-Alt_L>", self._on_alt_release),
            ("<KeyRelease-Alt_R>", self._on_alt_release),
            ("<Control-KeyPress>", self._on_clipboard_key),
        ]:
            target_canvas.bind(ev, cb, add="+")

    def on_escape_deselect(self, event=None):
        # Esc (Етап 6): пріоритети — (1) скасувати активний рух/прев'ю з
        # відновленням оригіналів, (2) select-all → off, (3) зняти виділення.
        # Інструмент при цьому НЕ вимикається (сталість, Етап 3).
        drag = None
        if self._press_candidate is not None:
            drag = self._press_candidate
        elif self.move_drag_active and self.move_drag:
            drag = self.move_drag
        if drag is not None:
            if self._press_moved or self.move_drag_active:
                idx = drag.get("index", -1)
                map_id = self.app.current_map_eng
                objects = self.drawings.get(map_id, []) if map_id else []
                if drag.get("group"):
                    # Груповий рух: відкочуємо координати КОЖНОГО учасника
                    # (без history — точне відновлення, як одиночний cancel).
                    for g_idx, g_orig in drag["group"]:
                        if not (0 <= g_idx < len(objects)):
                            continue
                        g_obj = objects[g_idx]
                        if g_orig["coords"]:
                            g_obj["coords"] = list(g_orig["coords"])
                        if g_orig["class_icon_coords"]:
                            g_obj["class_icon_coords"] = list(g_orig["class_icon_coords"])
                        if g_orig["text_coords"]:
                            g_obj["text_coords"] = list(g_orig["text_coords"])
                elif 0 <= idx < len(objects):
                    obj = objects[idx]
                    if drag.get("original_coords"):
                        obj["coords"] = list(drag["original_coords"])
                    if drag.get("original_class_icon_coords"):
                        obj["class_icon_coords"] = list(drag["original_class_icon_coords"])
                    if drag.get("original_text_coords"):
                        obj["text_coords"] = list(drag["original_text_coords"])
                self.save_drawings()
            self._press_candidate = None
            self._press_moved = False
            self.move_drag = None
            self.move_drag_active = False
            try:
                self.redraw()
            except Exception:
                pass
            return
        if self.temp_item is not None:
            # Скасування в процесі малювання прев'ю (інструмент лишається)
            self.canvas.delete("temp_draw")
            self.temp_item = None
            self._brush_points = []
            return
        if self._select_all:
            self.toggle_select_all()
            return
        if self._multi_sel:
            # Пріоритет Esc (#2012): cancel-drag → select-all → МНОЖИНА →
            # exit_edit_mode. Інструмент не вимикається.
            self._clear_multi_sel()
            return
        palette = getattr(self.app, 'drawing_palette', None)
        if palette:
            palette.exit_edit_mode()

    def _on_tool_hotkey(self, event=None):
        """V (VK 86, keycode-dispatch #1671) → select tool (Етап 4)."""
        if event is None or event.keycode != 86:
            return None
        if event.state & 0x0004:
            return None  # Ctrl+V = паста. Біт 0x8 НЕ є Alt на цій системі
        # (звичайна V приходить з state=8, замір 26.09.2026) — не гартуємо.
        if self._clipboard_focus_in_field():
            return None  # фокус у Entry/Text — V друкується текстом
        palette = getattr(self.app, 'drawing_palette', None)
        if not palette or palette.state() == 'withdrawn':
            return None
        if self.app.mode != "edit" or not self.app.current_map_eng:
            return None
        palette._set_tool_from_code("select")
        return "break"

    def _on_delete_key(self, event=None):
        """Del (Етап 6): видалити виділений елемент (select-all → всі виділені)."""
        if self._clipboard_focus_in_field():
            return None
        palette = getattr(self.app, 'drawing_palette', None)
        if not palette or palette.state() == 'withdrawn':
            return None
        if not palette.is_in_edit_mode() and not self._select_all and not self._multi_sel:
            return None
        palette._delete_selected()
        return "break"

    def _on_alt_press(self, event=None):
        """Alt утримання (Етап 5): тимчасовий move — курсор fleur.
        Флаг `_alt_active` — головне джерело правди для on_press (state-біти
        на цій системі ненадійні, див. коментар про біт 0x8 у _on_clipboard_key)."""
        palette = getattr(self.app, 'drawing_palette', None)
        if not palette or palette.state() == 'withdrawn' or self.app.mode != "edit":
            return None
        if self._alt_active:
            return None
        self._alt_active = True
        try:
            self.canvas.config(cursor="fleur")
        except Exception:
            pass
        return None

    def _on_alt_release(self, event=None):
        """Відпустили Alt (Етап 5): повернення до попереднього інструменту."""
        if not self._alt_active:
            return None
        self._alt_active = False
        try:
            self.canvas.config(cursor="fleur" if self.active_tool == "move" else "")
        except Exception:
            pass
        return None

    def _on_focus_out(self, event=None):
        # Втрата фокусу під час утримання Alt → скид spring-loaded стану:
        # KeyRelease може загубитись (фокус пішов з вікна) і флаг застрягне би.
        if self._alt_active:
            self._alt_active = False
            try:
                self.canvas.config(cursor="fleur" if self.active_tool == "move" else "")
            except Exception:
                pass
    
    def set_tool(self, tool):
        self.active_tool = tool
        try:
            # Візуальний фідбек: move та Alt-тимчасовий рух — курсор-рух (fleur).
            self.canvas.config(cursor="fleur" if tool == "move" else "")
        except Exception:
            pass
        palette = getattr(self.app, 'drawing_palette', None)
        if not palette or not palette.is_in_edit_mode():
            pass
        
    def clear_all(self):
        if not self.app.current_map_eng: return
        map_id = self.app.current_map_eng
        if map_id in self.drawings and self.drawings[map_id]:
            self.app.ask_clear_confirm(self.app.translate_map_name(map_id), self._do_clear)

    def _do_clear(self, confirmed):
        if confirmed and self.app.current_map_eng:
            map_id = self.app.current_map_eng
            old = self.drawings.get(map_id, [])
            if old:
                # Один запис delete_all — Ctrl+Z відновлює все одразу.
                self._undo_stack.append(
                    ("delete_all", map_id, [(i, o) for i, o in enumerate(old)]))
            self.drawings[map_id] = []
            self._editing_idx = -1
            self._multi_sel = set()
            palette = getattr(self.app, 'drawing_palette', None)
            if palette:
                palette.exit_edit_mode()
                if hasattr(palette, "update_multi_selection"):
                    palette.update_multi_selection()
            self.save_drawings()
            self.redraw()

    def ctrl_z_undo(self):
        """Відкат ОСТАННЬОЇ дії (справжній LIFO за єдиним стеком)."""
        if not self.app.current_map_eng:
            return
        palette = getattr(self.app, 'drawing_palette', None)
        if palette:
            palette.exit_edit_mode()
        if not self._undo_stack:
            return
        op = self._undo_stack.pop()
        kind = op[0]
        try:
            if kind == "move":
                _, map_id, idx, original = op
                objs = self.drawings.get(map_id, [])
                if 0 <= idx < len(objs):
                    obj = objs[idx]
                    if original["coords"]:
                        obj["coords"] = original["coords"]
                    if original["class_icon_coords"]:
                        obj["class_icon_coords"] = original["class_icon_coords"]
                    if original["text_coords"]:
                        obj["text_coords"] = original["text_coords"]
                    if "had_norm" in original:
                        if original["had_norm"]:
                            obj["norm"] = original["had_norm"]
                        else:
                            obj.pop("norm", None)
            elif kind == "move_group":
                # Один запис на всю групу: відкочуємо координати + norm кожного.
                _, map_id, entries = op
                objs = self.drawings.get(map_id, [])
                for g_idx, g_orig in entries:
                    if not (0 <= g_idx < len(objs)):
                        continue
                    g_obj = objs[g_idx]
                    if g_orig["coords"]:
                        g_obj["coords"] = g_orig["coords"]
                    if g_orig["class_icon_coords"]:
                        g_obj["class_icon_coords"] = g_orig["class_icon_coords"]
                    if g_orig["text_coords"]:
                        g_obj["text_coords"] = g_orig["text_coords"]
                    if "had_norm" in g_orig:
                        if g_orig["had_norm"]:
                            g_obj["norm"] = g_orig["had_norm"]
                        else:
                            g_obj.pop("norm", None)
            elif kind == "update":
                _, map_id, idx, snapshot = op
                objs = self.drawings.get(map_id, [])
                if 0 <= idx < len(objs):
                    obj = objs[idx]
                    for key, val in snapshot.items():
                        obj[key] = copy.deepcopy(val)
            elif kind == "delete":
                _, map_id, idx, obj = op
                objs = self.drawings.setdefault(map_id, [])
                objs.insert(max(0, min(idx, len(objs))), obj)
            elif kind == "delete_all":
                _, map_id, entries = op
                objs = self.drawings.setdefault(map_id, [])
                # Зростаючий idx: відновлюємо зліва направо — позиції валідні.
                for e_idx, e_obj in sorted(entries, key=lambda e: e[0]):
                    objs.insert(max(0, min(e_idx, len(objs))), e_obj)
            elif kind == "delete_multi":
                # Видалення Shift-множини: відновлення зростаючим idx.
                _, map_id, entries = op
                objs = self.drawings.setdefault(map_id, [])
                for e_idx, e_obj in sorted(entries, key=lambda e: e[0]):
                    objs.insert(max(0, min(e_idx, len(objs))), e_obj)
            elif kind == "create":
                _, map_id, obj = op
                objs = self.drawings.get(map_id, [])
                # Ідентичність (`is`), а не індекс: після серії вставок/
                # видалень індекс міг зміститись, об'єкт — ні.
                for j, o in enumerate(objs):
                    if o is obj:
                        del objs[j]
                        break
        except Exception as e:
            print(f"[UNDO] failed ({kind}): {e}")
            return
        self.save_drawings()
        self._autosave_active_scheme()
        self.redraw()

    def resize_selected(self, direction):
        """Resize the edited element. direction: 1 = bigger, -1 = smaller."""
        if not self.app.current_map_eng or self._editing_idx < 0:
            return
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        if self._editing_idx >= len(objects):
            return
        obj = objects[self._editing_idx]
        scale = obj.get("scale", 1.0)
        step = 0.1
        new_scale = scale + direction * step
        new_scale = max(0.3, min(3.0, new_scale))
        if new_scale == scale:
            return
        # Snapshot ДО мутації — Ctrl+Z відкочує resize (фікс 27.09.2026:
        # раніше resize мутував coords/scale без запису в історію, тож Ctrl+Z
        # після resize відкочував сторонню дію).
        snapshot = {k: copy.deepcopy(v) for k, v in obj.items()
                    if k in ("scale", "coords", "class_icon_coords", "text_coords")}
        self._undo_stack.append(("update", map_id, self._editing_idx, snapshot))
        obj["scale"] = new_scale
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if obj.get("type") == "brush":
            pass
        elif obj.get("type") in ("marker", "arrow") and len(obj.get("coords", [])) >= 4:
            coords = obj["coords"]
            mx, my = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
            dx = coords[2] - mx
            dy = coords[3] - my
            coords[2] = mx + dx * (new_scale / scale)
            coords[3] = my + dy * (new_scale / scale)
        self.save_drawings()
        # Ctrl+resize must reach saved_schemes too: the mod reads the scheme
        # at battle start (not the canvas) - without this the minimap kept
        # the old element size (user report 03.10.2026).
        self._autosave_active_scheme()
        self.redraw()

    def on_press(self, event):
        if not self.app.current_map_eng or self.app.mode != "edit": return
        if event.state & 0x0004:
            return
        palette = getattr(self.app, 'drawing_palette', None)
        palette_visible = palette and palette.state() != 'withdrawn'
        # Shift = 0x0001 (надійний біт на відміну від Alt 0x8, #2010).
        shift_held = bool(event.state & 0x0001)

        if self._select_all:
            # ALL активний: клік по ЕЛЕМЕНТІ = груповий рух усіх видимих;
            # клік по порожньому / при інструменті малювання = вимкнення ALL
            # (як раніше, фікс 01.10.2026 не змінюється).
            if palette_visible and self.active_tool not in ("marker", "arrow", "brush", "text"):
                idx, _ = self._find_object_index_at(event.x, event.y)
                if idx >= 0:
                    map_id = self.app.current_map_eng
                    objects = self.drawings.get(map_id, [])
                    indices = [i for i, o in enumerate(objects) if self.is_visible(o)]
                    self._start_group_move(event, indices)
                    return
            self._select_all = False
            if palette:
                palette._update_select_all_btn()
            self.redraw()
            return

        # Alt = spring-loaded move (Етап 5): флаг від keysym-біндів
        # (<KeyPress-Alt_L>), НЕ від state-бітів — біт 0x8 на цій системі
        # ненадійний (супроводжує звичайний Ctrl, [CLIP] 28.08.2026).
        # Елемент під курсором рухається з автовибором (PS Ctrl+Move),
        # доки Alt утримується. Порожнє поле при Alt — нічого
        # (малювання не стартує).
        if palette_visible and self._alt_active:
            idx, target_kind = self._find_object_index_at(event.x, event.y)
            if idx >= 0:
                map_id = self.app.current_map_eng
                obj = self.drawings[map_id][idx]
                self._press_candidate = {
                    "index": idx,
                    "target_kind": target_kind,
                    "start_event": (event.x, event.y),
                    "original_coords": list(obj.get("coords", [])),
                    "original_class_icon_coords": list(obj.get("class_icon_coords", [])),
                    "original_text_coords": list(obj.get("text_coords", [])) if obj.get("text_coords") else [],
                    "via_alt": True,
                }
                self._press_moved = False
                self._edit_object_at(idx)
            return

        if palette_visible:
            idx, target_kind = self._find_object_index_at(event.x, event.y)
            # Етап 4 (27.09.2026): клік по існуючому елементу = ВИДІЛЕННЯ —
            # але ТІЛЬКИ при select/move/без інструмента. При активному
            # інструменті малювання (27.09.2026, фікс «неможливо намалювати
            # два елемента близько») прес біля/на елементі йде в малювання:
            # клік-без-руху все одно виділяє (on_release → _select_at),
            # потяг створює елемент навіть поверх існуючого. Рух елемента при
            # активному малюванні — через V/select або Alt (спек #2011/#2012).
            if idx >= 0 and self.active_tool not in ("marker", "arrow", "brush", "text"):
                if shift_held:
                    # Shift+клік = toggle у множині (варіант A: без рамок —
                    # індикатор у палітрі). Одиночне виділення не чіпаємо.
                    self._toggle_multi_sel(idx)
                    return
                if self._multi_sel and idx in self._multi_sel:
                    # Клік по елементу з множини = груповий рух усієї множини.
                    self._start_group_move(event, sorted(self._multi_sel))
                    return
                if self._multi_sel:
                    # Клік по елементу ПОЗА множиною = одиночне виділення,
                    # множина скидається.
                    self._clear_multi_sel()
                map_id = self.app.current_map_eng
                obj = self.drawings[map_id][idx]
                self._press_candidate = {
                    "index": idx,
                    "target_kind": target_kind,
                    "start_event": (event.x, event.y),
                    "original_coords": list(obj.get("coords", [])),
                    "original_class_icon_coords": list(obj.get("class_icon_coords", [])),
                    "original_text_coords": list(obj.get("text_coords", [])) if obj.get("text_coords") else [],
                }
                self._press_moved = False
                self._edit_object_at(idx)
                return
            if self.active_tool == "move":
                # move: клік по порожньому — нічого (виділення лишається,
                # доки не вибрано інший елемент / не знято).
                return
            if not self.active_tool or self.active_tool == "select":
                if self._multi_sel:
                    # Клік по порожньому = зняти НЕ лише одиночне, а й
                    # Shift-множину (спека: звичайний клік без Шіфту).
                    self._clear_multi_sel()
                    if palette.is_in_edit_mode():
                        palette.exit_edit_mode()
                    return
                if palette.is_in_edit_mode():
                    # select (AI) та режим без інструмента: клік по порожньому = зняти виділення
                    palette.exit_edit_mode()
                    return
            # активний інструмент малювання → малюємо нижче (по порожньому
            # ПОЛЮ і по/біля елемента — див. умову вище)

        if not self.active_tool or not palette_visible:
            # Оборонний гард (27.09.2026): при ЗАКРИТІЙ палітрі жодних
            # елементів/виділень — малювання можливе лише після активації
            # кнопкою DRAW (стан інструмента міг пережити закриття раніше).
            return
        
        org_x, org_y, cw, ch = self._img_rect()
        if cw < 10 or ch < 10: return

        self.start_x = event.x
        self.start_y = event.y
        # Сира точка пресу ДО snap: on_release скасовує бід-лінію за відстанню
        # від неї (фікс 27.09.2026). Раніше compare був start==event після
        # snap (радіус 15px) → чистий клік біля існуючого marker/arrow
        # СТВОРЮВАВ елемент ("незрозумілі елементи, яких я не ставив").
        self._raw_press = (event.x, event.y)
        # Захист від stale-кандидата: сюди доходимо лише з диспетчера
        # малювання — будь-який кандидат тут уже з попередньої взаємодії.
        self._press_candidate = None
        self._press_moved = False
        
        if self.active_tool in ("marker", "arrow"):
            map_id = self.app.current_map_eng
            if map_id in self.drawings:
                min_dist = 15 
                snap_x, snap_y = self.start_x, self.start_y
                for obj in self.drawings[map_id]:
                    if obj["type"] == self.active_tool and self.is_visible(obj):
                        coords = obj["coords"]
                        if len(coords) >= 4:
                            # image-space px -> canvas px (letterbox origin)
                            ox, oy = org_x + coords[0]*cw, org_y + coords[1]*ch
                            dist = math.hypot(ox - event.x, oy - event.y)
                            if dist < min_dist:
                                min_dist = dist
                                snap_x, snap_y = ox, oy
                self.start_x = snap_x
                self.start_y = snap_y

            self._draw_temp_line([self.start_x, self.start_y, event.x, event.y], arrow=True)
            if self.active_tool == "marker":
                self.canvas.create_oval(self.start_x-12, self.start_y-12, self.start_x+12, self.start_y+12, outline=self.default_color, width=max(1, self._thickness-1), tags="temp_draw")
                self.canvas.create_oval(self.start_x-4, self.start_y-4, self.start_x+4, self.start_y+4, fill="white", outline="white", tags="temp_draw")
        elif self.active_tool == "brush":
            self._brush_points = [(event.x, event.y)]
            self._draw_temp_line([event.x, event.y, event.x, event.y], arrow=False)
        elif self.active_tool == "text":
            self.temp_item = self.canvas.create_text(event.x, event.y, text="📍", fill=self.default_color, font=("Arial", 16), tags="temp_draw")

    def _distance_to_segment(self, px, py, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / float(dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def _get_marker_text_pos(self, obj, cw, ch, sc=1.0):
        text_coords = obj.get("text_coords")
        if isinstance(text_coords, list) and len(text_coords) >= 2:
            return text_coords[0] * cw, text_coords[1] * ch
        coords = obj.get("coords", [])
        if obj.get("type") == "brush" and len(coords) >= 4:
            n = len(coords) // 2
            mx = sum(coords[i*2] for i in range(n)) / n * cw
            my = sum(coords[i*2+1] for i in range(n)) / n * ch - int(10 * sc)
            return mx, my
        if len(coords) >= 4:
            mx = (coords[0] + coords[2]) / 2 * cw
            my = (coords[1] + coords[3]) / 2 * ch - int(10 * sc)
            return mx, my
        return None, None

    def _find_object_index_at(self, event_x, event_y):
        if not self.app.current_map_eng:
            return -1, "object"
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        if not objects:
            return -1, "object"

        org_x, org_y, cw, ch = self._img_rect()
        if cw < 10 or ch < 10:
            return -1, "object"

        # Усі відстані нижче рахуються у ПІКСЕЛЯХ (фікс 27.09.2026): раніше
        # поріг був глобальним 18px у НОРМАЛІЗОВАНИХ координатах, ділився на
        # min(cw,ch) — на асиметричному канвасі горизонтальний радіус
        # виростав до 18*cw/ch (~24px), тож «поле вибору» було набагато
        # більшим за сам елемент і сусідні елементи не можна було розділити.
        # Клік переводиться у ПРОСТІР ЗОБРАЖЕННЯ (letterbox rect) — там живуть
        # координати елементів (фікс 01.10.2026).
        TH_MARKER = 14   # marker: коло r≈12px
        TH_SEGMENT = 8   # arrow/brush: лінія/сегмент
        TH_TEXT = 10     # text/POI-іконка
        TH_TIP = 10      # marker_tip / marker_text (пріоритетний хіт)

        click_x, click_y = float(event_x) - org_x, float(event_y) - org_y
        closest_idx = -1
        closest_kind = "object"
        min_dist = float('inf')

        maker_types = ("marker", "arrow", "brush")

        for i, obj in enumerate(objects):
            if not self.is_visible(obj):
                continue
            coords = obj.get("coords", [])

            special_kind = None
            special_dist = float('inf')
            obj_best_dist = float('inf')
            obj_best_kind = "object"
            obj_threshold = TH_MARKER

            if obj.get("type") in maker_types and obj.get("text"):
                tx, ty = self._get_marker_text_pos(obj, cw, ch)
                if tx is not None:
                    d = math.hypot(tx - click_x, ty - click_y)
                    if d < special_dist:
                        special_dist = d
                        special_kind = "marker_text"

            if obj.get("type") in ("marker", "arrow") and len(coords) >= 4:
                obj_threshold = TH_SEGMENT
                c0x, c0y = coords[0] * cw, coords[1] * ch
                c1x, c1y = coords[2] * cw, coords[3] * ch
                d = math.hypot(c1x - click_x, c1y - click_y)
                if d < special_dist:
                    special_dist = d
                    special_kind = "marker_tip"

                general_dist = min(
                    math.hypot(c0x - click_x, c0y - click_y),
                    math.hypot(c1x - click_x, c1y - click_y),
                    self._distance_to_segment(click_x, click_y, c0x, c0y, c1x, c1y),
                )
                # marker: голова стрілки/коло біля початку — більший поріг
                if obj.get("type") == "marker":
                    obj_threshold = TH_MARKER

                if special_kind is not None and special_dist < TH_TIP:
                    obj_best_kind = special_kind
                    obj_best_dist = special_dist
                else:
                    obj_best_kind = "object"
                    obj_best_dist = general_dist

            elif obj.get("type") == "brush" and len(coords) >= 4:
                obj_threshold = TH_SEGMENT
                c0x, c0y = coords[0] * cw, coords[1] * ch
                clx, cly = coords[-2] * cw, coords[-1] * ch
                poly_end_d = min(
                    math.hypot(c0x - click_x, c0y - click_y),
                    math.hypot(clx - click_x, cly - click_y),
                )
                brush_seg_dist = float('inf')
                for j in range(0, len(coords)-2, 2):
                    sx, sy = coords[j] * cw, coords[j+1] * ch
                    ex, ey = coords[j+2] * cw, coords[j+3] * ch
                    d = self._distance_to_segment(click_x, click_y, sx, sy, ex, ey)
                    brush_seg_dist = min(brush_seg_dist, d)
                general_dist = min(poly_end_d, brush_seg_dist)

                if special_kind is not None and special_dist < TH_TIP:
                    obj_best_kind = special_kind
                    obj_best_dist = special_dist
                else:
                    obj_best_kind = "object"
                    obj_best_dist = general_dist

            elif obj.get("type") == "text" and len(coords) >= 2:
                obj_threshold = TH_TEXT
                tx = coords[0] * cw
                ty = coords[1] * ch
                obj_best_dist = math.hypot(tx - click_x, ty - click_y)
                obj_best_kind = "object"
                poi = obj.get("poi", [])
                txt = obj.get("text", "")
                if poi:
                    d = math.hypot(tx - click_x, ty - 24 - click_y)
                    if d < obj_best_dist:
                        obj_best_dist = d
                if txt:
                    ofs = 15 if poi else 0
                    d = math.hypot(tx - click_x, ty + ofs - click_y)
                    if d < obj_best_dist:
                        obj_best_dist = d
            else:
                continue

            # Пер-типовий поріг: кожен елемент «магнітиться» лише у межах
            # свого радіуса — сусідні елементи не перехоплюють клік.
            if obj_best_dist < obj_threshold and obj_best_dist < min_dist:
                min_dist = obj_best_dist
                closest_idx = i
                closest_kind = obj_best_kind

        return closest_idx, closest_kind

    def on_move_press(self, event):
        if self.app.mode != "edit" or not self.app.current_map_eng:
            return
        idx, target_kind = self._find_object_index_at(event.x, event.y)
        if idx == -1:
            self.move_drag = None
            self.move_drag_active = False
            return

        map_id = self.app.current_map_eng
        obj = self.drawings[map_id][idx]
        self.move_drag = {
            "index": idx,
            "target_kind": target_kind,
            "start_event": (event.x, event.y),
            "original_coords": list(obj.get("coords", [])),
            "original_class_icon_coords": list(obj.get("class_icon_coords", [])),
            "original_text_coords": list(obj.get("text_coords", [])) if obj.get("text_coords") else [],
        }
        self.move_drag_active = True
        return "break"

    def on_move_drag(self, event):
        if self.app.mode != "edit" or not self.move_drag or not self.app.current_map_eng:
            return

        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        idx = self.move_drag["index"]
        if idx >= len(objects):
            self.move_drag = None
            self.move_drag_active = False
            return

        org_x, org_y, cw, ch = self._img_rect()
        if cw < 10 or ch < 10:
            return

        # delta normalized over the IMAGE (stored coords are image fractions)
        dx = (event.x - self.move_drag["start_event"][0]) / cw
        dy = (event.y - self.move_drag["start_event"][1]) / ch

        # Груповий рух (ALL або Shift-множина): однакова дельта до кожного
        # елемента; marker_tip/marker_text суб-цілі не застосовуються.
        group = self.move_drag.get("group")
        if group:
            for g_idx, g_orig in group:
                if not (0 <= g_idx < len(objects)):
                    continue
                g_obj = objects[g_idx]
                g_coords = g_orig["coords"]
                if g_obj.get("type") in ("marker", "arrow") and len(g_coords) >= 4:
                    g_obj["coords"] = [
                        min(max(g_coords[0] + dx, 0.0), 1.0),
                        min(max(g_coords[1] + dy, 0.0), 1.0),
                        min(max(g_coords[2] + dx, 0.0), 1.0),
                        min(max(g_coords[3] + dy, 0.0), 1.0),
                    ]
                elif g_obj.get("type") == "brush" and len(g_coords) >= 4:
                    g_new = []
                    for j in range(0, len(g_coords), 2):
                        g_new.append(min(max(g_coords[j] + dx, 0.0), 1.0))
                        g_new.append(min(max(g_coords[j + 1] + dy, 0.0), 1.0))
                    g_obj["coords"] = g_new
                elif g_obj.get("type") == "text" and len(g_coords) >= 2:
                    g_obj["coords"] = [
                        min(max(g_coords[0] + dx, 0.0), 1.0),
                        min(max(g_coords[1] + dy, 0.0), 1.0),
                    ]
                g_tc = g_orig.get("text_coords", [])
                if g_tc and len(g_tc) >= 2:
                    g_obj["text_coords"] = [
                        min(max(g_tc[0] + dx, 0.0), 1.0),
                        min(max(g_tc[1] + dy, 0.0), 1.0),
                    ]
            self.redraw()
            return "break"

        obj = objects[idx]
        original = self.move_drag["original_coords"]
        target_kind = self.move_drag.get("target_kind", "object")

        if target_kind == "marker_tip" and obj.get("type") in ("marker", "arrow"):
            original = self.move_drag["original_coords"]
            obj["coords"] = [
                original[0], original[1],
                min(max(original[2] + dx, 0.0), 1.0),
                min(max(original[3] + dy, 0.0), 1.0),
            ]
            self.redraw()
            return "break"

        if target_kind == "marker_text" and obj.get("type") in ("marker", "arrow"):
            orig_tc = self.move_drag.get("original_text_coords", [])
            if not orig_tc or len(orig_tc) < 2:
                tx, ty = self._get_marker_text_pos(obj, cw, ch)
                if tx is None or ty is None:
                    tx, ty = 0.0, 0.0
                orig_tc = [tx / cw, ty / ch]
            obj["text_coords"] = [
                min(max(orig_tc[0] + dx, 0.0), 1.0),
                min(max(orig_tc[1] + dy, 0.0), 1.0),
            ]
            self.redraw()
            return "break"

            self.redraw()
            return "break"

        if obj.get("type") in ("marker", "arrow") and len(original) >= 4:
            new_coords = [
                min(max(original[0] + dx, 0.0), 1.0),
                min(max(original[1] + dy, 0.0), 1.0),
                min(max(original[2] + dx, 0.0), 1.0),
                min(max(original[3] + dy, 0.0), 1.0),
            ]
        elif obj.get("type") == "brush" and len(original) >= 4:
            new_coords = []
            for j in range(0, len(original), 2):
                new_coords.append(min(max(original[j] + dx, 0.0), 1.0))
                new_coords.append(min(max(original[j+1] + dy, 0.0), 1.0))
        elif obj.get("type") == "text" and len(original) >= 2:
            new_coords = [
                min(max(original[0] + dx, 0.0), 1.0),
                min(max(original[1] + dy, 0.0), 1.0),
            ]
        else:
            return

        obj["coords"] = new_coords
        self.redraw()
        return "break"

    def on_move_release(self, event):
        if not self.move_drag_active:
            return
        self.move_drag_active = False
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])

        # Груповий рух: ОДИН undo-запис на всю групу + norm:"img" кожному
        # елементу (після руху координати однозначно образ-просторові).
        group = self.move_drag.get("group")
        if group:
            entries = []
            for g_idx, g_orig in group:
                if 0 <= g_idx < len(objects):
                    objects[g_idx]["norm"] = "img"
                    entries.append((g_idx, g_orig))
            if entries:
                self._undo_stack.append(("move_group", map_id, entries))
            self.move_drag = None
            self.save_drawings()
            self._autosave_active_scheme()
            return "break"

        idx = self.move_drag["index"]
        # norm ще НЕ змінений (ставимо нижче) — це попереднє значення.
        prev_norm = objects[idx].get("norm") if 0 <= idx < len(objects) else None
        if 0 <= idx < len(objects):
            # Рух = калібрування: після перетягування координати елемента
            # відповідають його екранній позиції в поточному (образ-)
            # просторі — фіксуємо маркером, щоб надалі не здвинувся.
            objects[idx]["norm"] = "img"
        original = {
            "coords": self.move_drag.get("original_coords", []),
            "class_icon_coords": self.move_drag.get("original_class_icon_coords", []),
            "text_coords": self.move_drag.get("original_text_coords", []),
            # norm теж відкочуємо: legacy-елемент після Ctrl+Z має лишитись
            # legacy (canvas-простір), а не стати "img".
            "had_norm": prev_norm,
        }
        self._undo_stack.append(("move", map_id, idx, original))
        self.move_drag = None
        self.save_drawings()
        self._autosave_active_scheme()
        self.app.root.after(50, self._edit_object_at, idx)
        return "break"

    def on_drag(self, event):
        # _press_candidate виставляється ТІЛЬКИ при попаданні на елемент
        # (Етап 4) або Alt — тож активний інструмент малювання не заважає:
        # потяг виділеного = рух, малювання стартує лише з порожнього поля.
        if self._press_candidate is not None and self.app.mode == "edit":
            if not self._press_moved:
                sx, sy = self._press_candidate["start_event"]
                if math.hypot(event.x - sx, event.y - sy) < 5:
                    return
                self._press_moved = True
                self.move_drag = self._press_candidate
                self.move_drag_active = True
            self.on_move_drag(event)
            return
        if not self.temp_item or self.app.mode != "edit": return
        if self.active_tool in ("marker", "arrow"):
            self._draw_temp_line([self.start_x, self.start_y, event.x, event.y], arrow=True)
        elif self.active_tool == "brush":
            last_x, last_y = self._brush_points[-1]
            if math.hypot(event.x - last_x, event.y - last_y) >= 10:
                self._brush_points.append((event.x, event.y))
                flat = [coord for p in self._brush_points for coord in p]
                self._draw_temp_line(flat, arrow=False)
        elif self.active_tool == "text":
            self.canvas.coords(self.temp_item, event.x, event.y)
            
    def on_release(self, event):
        # Кандидат (Етап 4 / Alt) обробляється ЗАВЖДДИ — незалежно від
        # активного інструмента; інакше кандидат «застрягав» і наступний
        # клік малював зі станим start-пунктом.
        if self._press_candidate is not None:
            if self._press_moved:
                self.on_move_release(event)
            self._press_candidate = None
            self._press_moved = False
            return
        if not self.active_tool or not self.app.current_map_eng or self.app.mode != "edit": return
        if not self.temp_item: return
            
        org_x, org_y, cw, ch = self._img_rect()
        if cw < 10 or ch < 10: return
        
        rx, ry = getattr(self, "_raw_press", (self.start_x, self.start_y))
        raw_dist = math.hypot(event.x - rx, event.y - ry)

        if self.active_tool in ("marker", "arrow", "brush") and raw_dist < 4:
            # Сталість інструментів (Етап 3): скасування прев'ю НЕ вимикає
            # інструмент — доки не вимкнено кнопкою тулбара / не перемкнено.
            self.canvas.delete("temp_draw")
            self.temp_item = None
            # Етап 4 (27.09.2026): клік по існуючому елементу при активному
            # інструменті = ВИДІЛЕННЯ (малюємо тільки по порожньому/потягом).
            self._select_at(rx, ry)
            return
        if self.active_tool == "text" and raw_dist < 4:
            # POI/текст: клік по елементу = виділення; по порожньому = створення.
            if self._select_at(rx, ry):
                self.canvas.delete("temp_draw")
                self.temp_item = None
                return
        
        # canvas px -> image-space normalized (letterbox origin + image size)
        px1, py1 = (self.start_x - org_x) / cw, (self.start_y - org_y) / ch
        px2, py2 = (event.x - org_x) / cw, (event.y - org_y) / ch

        new_obj = {
            "type": self.active_tool,
            "modes": [self.app.selected_battle_mode.get()],
            "classes": [],
            "text": "",
            "poi": [],
            "color": "#00ff00" if self.active_tool == "text" else self.default_color,
            "thickness": self._thickness,
            "_source": getattr(self.app, "active_group_id", "public") or "public",
            # Створення = образ-простір (letterbox-фікс 02.10.2026) — маркер
            # щоб конверсії/аудити знали простір координат елемента.
            "norm": "img",
        }
        if self.active_tool == "brush":
            norm_points = [((x - org_x) / cw, (y - org_y) / ch)
                            for x, y in self._brush_points]
            flat = [coord for p in norm_points for coord in p]
            new_obj["coords"] = flat
            new_obj["arrow_start"] = False
            new_obj["arrow_end"] = False
        elif self.active_tool in ("marker", "arrow"):
            new_obj["coords"] = [px1, py1, px2, py2]
        else:
            new_obj["coords"] = [px2, py2]

        map_id = self.app.current_map_eng
        if map_id not in self.drawings: self.drawings[map_id] = []
        if self._is_duplicate(new_obj, self.drawings[map_id]):
            self.canvas.delete("temp_draw")
            self.temp_item = None
            return
        self.drawings[map_id].append(new_obj)

        palette = getattr(self.app, 'drawing_palette', None)
        if not palette:
            self.canvas.delete("temp_draw")
            self.temp_item = None
            return

        palette.exit_edit_mode()
        palette.apply_to_new_object(new_obj, cw, ch)
        self.default_color = new_obj["color"]
        self._undo_stack.append(("create", map_id, new_obj))
        self.save_drawings()
        self._autosave_active_scheme()
        self.redraw()
        self.canvas.delete("temp_draw")
        self.temp_item = None
        self._edit_object_at(len(self.drawings[map_id]) - 1)
        # Сталість інструментів (Етап 3): після створення елемента інструмент
        # лишається активним — наступний ЛКМ малює наступний елемент, доки
        # інструмент не вимкнено (тап по кнопці) і не перемкнено на інший.
        self.app.root.after(10, palette._lift_self)
            
    def on_right_click(self, event):
        if self.app.mode != "edit" or not self.app.current_map_eng:
            return
        idx, _ = self._find_object_index_at(event.x, event.y)
        if idx < 0:
            return

        menu = tk.Menu(self.canvas, tearoff=0, bg="#333", fg="white",
                       activebackground="#555", activeforeground="white",
                       font=("Arial", 10))
        menu.add_command(label=self.app.t('ui', 'edit_btn'), command=lambda: self.app.root.after(50, self._edit_object_at, idx))
        menu.add_separator(background="#555")
        menu.add_command(label=self.app.t('ui', 'delete_btn'), command=lambda: self.app.root.after(50, self._delete_object_at, idx))
        menu.post(event.x_root, event.y_root)

    def _select_at(self, x, y):
        """Виділення елемента під точкою (Етап 4): клік при активному
        інструменті малювання вибирає елемент замість створення нового.
        Повертає True, якщо елемент знайдено."""
        palette = getattr(self.app, 'drawing_palette', None)
        if not palette or palette.state() == 'withdrawn':
            return False
        idx, _ = self._find_object_index_at(x, y)
        if idx < 0:
            return False
        self._edit_object_at(idx)
        return True

    def _edit_object_at(self, idx):
        if not self.app.current_map_eng:
            return
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        if idx < 0 or idx >= len(objects):
            return
        obj = objects[idx]
        palette = getattr(self.app, 'drawing_palette', None)
        if not palette:
            return
        needs_show = palette.state() == 'withdrawn'
        palette.exit_edit_mode()
        self._editing_idx = idx
        if obj["type"] == "brush":
            label = self.app.t('ui', 'brush_type')
        elif obj["type"] == "arrow":
            label = self.app.t('ui', 'arrow_type')
        elif obj["type"] == "marker":
            label = self.app.t('ui', 'marker_type')
        else:
            label = self.app.t('ui', 'text_type')
        palette.load_object(obj)
        palette._lift_self()
        if needs_show:
            palette.show()
            if hasattr(self.app, 'draw_btn'):
                self.app.draw_btn.config(bg="#ffaa00", fg="black")
        self.redraw()

    def _delete_edited_object(self):
        if self._editing_idx < 0 or not self.app.current_map_eng:
            return
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        if self._editing_idx < 0 or self._editing_idx >= len(objects):
            return
        idx = self._editing_idx
        obj = objects[idx]
        type_labels = {"brush": "brush_type", "arrow": "arrow_type", "marker": "marker_type"}
        label = self.app.t('ui', type_labels.get(obj.get("type", ""), "text_type"))
        if not self._confirm_delete(label):
            return
        # Живий obj (не deepcopy): він виходить зі списку, ніхто його не мутує,
        # тож ідентичність зберігається для зворотного зв'язку з create-op.
        self._undo_stack.append(("delete", map_id, idx, obj))
        del objects[idx]
        self._editing_idx = -1
        self.save_drawings()
        self._autosave_active_scheme()
        self.redraw()

    def _delete_all_selected(self):
        if not self.app.current_map_eng:
            return
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        if not objects:
            return
        if not self._confirm_delete(self.app.t('ui', 'select_all')):
            return
        palette = getattr(self.app, 'drawing_palette', None)
        self._undo_stack.append(
            ("delete_all", map_id, [(i, o) for i, o in enumerate(objects)]))
        self.drawings[map_id] = []
        self._editing_idx = -1
        self._select_all = False
        self._multi_sel = set()
        if palette:
            palette._update_select_all_btn()
            if hasattr(palette, "update_multi_selection"):
                palette.update_multi_selection()
        self.save_drawings()
        self._autosave_active_scheme()
        self.redraw()

    def _delete_multi_sel(self):
        """Видалити всі елементи Shift-множини: одне підтвердження,
        один undo-запис."""
        if not self.app.current_map_eng or not self._multi_sel:
            return
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        valid = sorted(i for i in self._multi_sel if 0 <= i < len(objects))
        if not valid:
            self._clear_multi_sel()
            return
        palette = getattr(self.app, 'drawing_palette', None)
        n = len(valid)
        if not self._confirm_delete(
                f"{self.app.t('ui', 'select_all')} ({n})"):
            return
        self._undo_stack.append(
            ("delete_multi", map_id, [(i, objects[i]) for i in valid]))
        # Видалення у зворотному порядку, щоб попередні індекси не змістились.
        for i in reversed(valid):
            del objects[i]
        # _editing_idx може вказувати на видалений/зміщений елемент.
        if self._editing_idx in valid:
            self._editing_idx = -1
            if palette:
                palette.exit_edit_mode()
        elif self._editing_idx > valid[0]:
            self._editing_idx -= sum(1 for i in valid if i < self._editing_idx)
        self._multi_sel = set()
        if palette and hasattr(palette, "update_multi_selection"):
            palette.update_multi_selection()
        self.save_drawings()
        self._autosave_active_scheme()
        self.redraw()

    def _confirm_delete(self, label):
        dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, self.app.t('ui', 'confirm_title'))
        dialog_utils._DragHelper(dlg, hdr)
        dlg.grab_set()

        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - 150
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - 60
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text=self.app.t('ui', 'confirm_delete_msg').format(label=label), font=("Arial", 10),
                 bg="#222", fg="#cccccc", wraplength=360).pack(padx=20, pady=(20, 15))

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(0, 15))
        result = {"ok": False}
        def on_yes(): result["ok"] = True; dlg.destroy()
        def on_no(): dlg.destroy()

        tk.Button(bf, text=self.app.t('ui', 'btn_yes'), bg="#555", fg="white", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_yes).pack(side="left", padx=10)
        tk.Button(bf, text=self.app.t('ui', 'btn_no'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_no).pack(side="left", padx=10)

        self.app.root.wait_window(dlg)
        return result["ok"]

    def _delete_object_at(self, idx):
        if not self.app.current_map_eng:
            return
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        if idx < 0 or idx >= len(objects):
            return
        obj = objects[idx]
        if obj["type"] == "brush":
            label = self.app.t('ui', 'brush_type')
        elif obj["type"] == "arrow":
            label = self.app.t('ui', 'arrow_type')
        elif obj["type"] == "marker":
            label = self.app.t('ui', 'marker_type')
        else:
            label = self.app.t('ui', 'text_type')
        ok = self._confirm_delete(label)
        if ok:
            self._undo_stack.append(("delete", map_id, idx, obj))
            del objects[idx]
            if self._editing_idx == idx:
                self._editing_idx = -1
                palette = getattr(self.app, 'drawing_palette', None)
                if palette:
                    palette.exit_edit_mode()
            elif self._editing_idx > idx:
                self._editing_idx -= 1
            self.save_drawings()
            self.redraw()

    _UKR_TO_EN = {"ЛТ": "LT", "СТ": "MT", "ТТ": "HT", "ПТ": "TD", "САУ": "SPG"}

    def is_visible(self, obj):
        current_mode = self.app.selected_battle_mode.get()
        active_classes = [k for k, v in self.app.selected_classes.items() if v.get()]
        
        if obj.get("modes") and current_mode not in obj["modes"]:
            return False
            
        req_classes = obj.get("classes", [])
        if req_classes:
            req_en = [self._UKR_TO_EN.get(c, c) for c in req_classes]
            if not any(cls in active_classes for cls in req_en):
                return False
                
        return True

    @staticmethod
    def _dash_runs(points, on, off):
        """Розбити ламану (flat [x0,y0,...]) на видимі (ON) відрізки пунктиру.

        Tk -dash на цій платформі ненадійний: значення off ігнорується, а
        відступ малюється рівним товщині лінії (заміри 26.09.2026: (5,5)/(12,6)/(6,30)
        дають однаковий результат, зв'язок on->довжина штриха нелінійний).
        Тому пунктир малюється явними сегментами: штрих = 2.6*lw,
        відступ = 1.5*lw — детерміновано на будь-якій товщині/DPI
        (відступ ×1.5 від товщини з 28.09.2026 за запитом користувача).
        """
        if len(points) < 4:
            return []
        runs = []
        cur = None
        px, py = points[0], points[1]
        need = float(on)
        on_phase = True
        i = 2
        while i + 1 < len(points):
            qx, qy = points[i], points[i + 1]
            seg = math.hypot(qx - px, qy - py)
            travelled = 0.0
            while seg - travelled > 1e-9:
                step = min(need, seg - travelled)
                sx = px + (qx - px) * travelled / seg
                sy = py + (qy - py) * travelled / seg
                travelled += step
                nx = px + (qx - px) * travelled / seg
                ny = py + (qy - py) * travelled / seg
                if on_phase:
                    if cur is None:
                        cur = [sx, sy]
                    cur.extend((nx, ny))
                need -= step
                if need <= 1e-9:
                    if on_phase:
                        runs.append(cur)
                        cur = None
                        on_phase = False
                        need = float(off)
                    else:
                        on_phase = True
                        need = float(on)
                        cur = [nx, ny]
            px, py = qx, qy
            i += 2
        if on_phase and cur is not None and len(cur) >= 4:
            runs.append(cur)
        return runs

    @staticmethod
    def _arrow_shape(lw):
        """Стрілка Tk = (довжина, ширина, надріз); дефолт "8 10 3".

        Робимо її ×2 від дефолту і прив'язуємо до товщини лінії (lw вже
        містить sc_eff → масштабується з DPI/масштабом об'єкта).

        01.10.2026: прибрано floor max(1.0, lw/3) — він тримав k=1 при
        lw<3, тож голова лишалась фіксованою 16×20 і НЕ зменшувалась
        разом з елементом (скриншот 380: лінія 2px при масштабі 0.8,
        голова — 16px). Без floor форма строго лінійна від lw."""
        k = lw / 3.0
        return "%.1f %.1f %.1f" % (16.0 * k, 20.0 * k, 6.0 * k)

    def _draw_temp_line(self, flat, arrow=False):
        """Прев'ю лінії при малюванні з явним пунктиром (див. _dash_runs)."""
        self.canvas.delete("temp_line")
        lw = self._thickness
        for run in self._dash_runs(flat, 2.6 * lw, 1.5 * lw):
            self.canvas.create_line(*run, fill=self.default_color, width=lw,
                                    tags=("temp_draw", "temp_line"))
        if arrow and len(flat) >= 4:
            x1, y1, x2, y2 = flat[0], flat[1], flat[-2], flat[-1]
            d = math.hypot(x2 - x1, y2 - y1)
            # Стрілка: суцільний «хвіст» = її довжина (накриває проміжок
            # пунктиру під збільшеною стрілкою, див. _arrow_shape)
            _ash = self._arrow_shape(lw)
            _alen = float(_ash.split()[0])
            if d > _alen:
                self.canvas.create_line(x2 - (x2 - x1) / d * _alen, y2 - (y2 - y1) / d * _alen,
                                        x2, y2, arrow=tk.LAST, arrowshape=_ash,
                                        fill=self.default_color,
                                        width=lw, tags=("temp_draw", "temp_line"))
            elif d > 0:
                self.canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, arrowshape=_ash,
                                        fill=self.default_color,
                                        width=lw, tags=("temp_draw", "temp_line"))
        self.temp_item = "temp_line"

    def _render_elements(self, canvas, elements, cw, ch, offset_x=0.0, offset_y=0.0, img_w=None, img_h=None, screen_scale=1.0):
        """Render elements on a given canvas. No visibility filtering — renders all.
        offset_x/offset_y: image offset within canvas (for preview).
        img_w/img_h: if set, use as reference dimensions instead of cw/ch."""
        canvas.delete("painter_obj")
        if not elements:
            return
        if img_w is not None and img_h is not None:
            cw, ch = img_w, img_h
        sc = min(cw, ch) / 800.0 * screen_scale

        for obj in elements:
            obj_sc = obj.get("scale", 1.0)
            sc_eff = sc * obj_sc
            r12 = max(3, int(12 * sc_eff))
            r4 = max(2, int(4 * sc_eff))
            lw = max(1, int(obj.get("thickness", 3) * sc_eff))
            mt_sz = max(6, int(9 * sc_eff))
            poi_base = max(12, int(48 * sc_eff))
            tt_sz = max(6, int(10 * sc_eff))

            c = obj["color"]
            coords = obj.get("coords", [])
            if not coords and "x1" in obj:
                coords = [obj.get("x1", 0), obj.get("y1", 0),
                          obj.get("x2", obj.get("x1", 0)), obj.get("y2", obj.get("y1", 0))]

            if obj["type"] == "marker":
                if len(coords) < 4: continue
                x1, y1 = coords[0]*cw + offset_x, coords[1]*ch + offset_y
                x2, y2 = coords[2]*cw + offset_x, coords[3]*ch + offset_y
                for _run in self._dash_runs([x1, y1, x2, y2], 2.6 * lw, 1.5 * lw):
                    canvas.create_line(*_run, fill=c, width=lw, tags="painter_obj")
                _d = math.hypot(x2 - x1, y2 - y1)
                _ash = self._arrow_shape(lw)
                _alen = float(_ash.split()[0])
                if _d > _alen:
                    canvas.create_line(x2 - (x2 - x1) / _d * _alen, y2 - (y2 - y1) / _d * _alen, x2, y2, arrow=tk.LAST, arrowshape=_ash, fill=c, width=lw, tags="painter_obj")
                elif _d > 0:
                    canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, arrowshape=_ash, fill=c, width=lw, tags="painter_obj")

                canvas.create_oval(x1-r12, y1-r12, x1+r12, y1+r12, outline=c, width=max(1, lw-1), tags="painter_obj")
                canvas.create_oval(x1-r4, y1-r4, x1+r4, y1+r4, fill="white", outline="white", tags="painter_obj")

                if obj.get("text"):
                    mx, my = self._get_marker_text_pos(obj, cw, ch, sc)
                    if mx is not None:
                        if offset_x or offset_y:
                            mx += offset_x
                            my += offset_y
                        canvas.create_text(mx, my, text=obj["text"], fill=c, font=("Arial", mt_sz, "bold"), tags="painter_obj")

            elif obj["type"] == "arrow":
                if len(coords) < 4: continue
                x1, y1 = coords[0]*cw + offset_x, coords[1]*ch + offset_y
                x2, y2 = coords[2]*cw + offset_x, coords[3]*ch + offset_y
                for _run in self._dash_runs([x1, y1, x2, y2], 2.6 * lw, 1.5 * lw):
                    canvas.create_line(*_run, fill=c, width=lw, tags="painter_obj")
                _d = math.hypot(x2 - x1, y2 - y1)
                _ash = self._arrow_shape(lw)
                _alen = float(_ash.split()[0])
                if _d > _alen:
                    canvas.create_line(x2 - (x2 - x1) / _d * _alen, y2 - (y2 - y1) / _d * _alen, x2, y2, arrow=tk.LAST, arrowshape=_ash, fill=c, width=lw, tags="painter_obj")
                elif _d > 0:
                    canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, arrowshape=_ash, fill=c, width=lw, tags="painter_obj")

                if obj.get("text"):
                    mx, my = self._get_marker_text_pos(obj, cw, ch, sc)
                    if mx is not None:
                        if offset_x or offset_y:
                            mx += offset_x
                            my += offset_y
                        canvas.create_text(mx, my, text=obj["text"], fill=c, font=("Arial", mt_sz, "bold"), tags="painter_obj")

            elif obj["type"] == "brush":
                if len(coords) < 4: continue
                flat_px = [(coords[i]*cw + offset_x) if i%2==0 else (coords[i]*ch + offset_y) for i in range(len(coords))]
                for _run in self._dash_runs(flat_px, 2.6 * lw, 1.5 * lw):
                    canvas.create_line(*_run, fill=c, width=lw, tags="painter_obj")
                if obj.get("arrow_start") and len(flat_px) >= 4:
                    _ax0, _ay0 = flat_px[0], flat_px[1]
                    _ax1, _ay1 = flat_px[2], flat_px[3]
                    _da = math.hypot(_ax1 - _ax0, _ay1 - _ay0)
                    if _da > 0:
                        _ash = self._arrow_shape(lw)
                        _alen = float(_ash.split()[0])
                        _tl = min(_alen, _da)
                        canvas.create_line(_ax0, _ay0, _ax0 + (_ax1 - _ax0) / _da * _tl, _ay0 + (_ay1 - _ay0) / _da * _tl, arrow=tk.FIRST, arrowshape=_ash, fill=c, width=lw, tags="painter_obj")
                if obj.get("arrow_end") and len(flat_px) >= 4:
                    _bx0, _by0 = flat_px[-4], flat_px[-3]
                    _bx1, _by1 = flat_px[-2], flat_px[-1]
                    _db = math.hypot(_bx1 - _bx0, _by1 - _by0)
                    if _db > 0:
                        _ash = self._arrow_shape(lw)
                        _alen = float(_ash.split()[0])
                        _tl = min(_alen, _db)
                        canvas.create_line(_bx1 - (_bx1 - _bx0) / _db * _tl, _by1 - (_by1 - _by0) / _db * _tl, _bx1, _by1, arrow=tk.LAST, arrowshape=_ash, fill=c, width=lw, tags="painter_obj")

                if obj.get("text"):
                    mx, my = self._get_marker_text_pos(obj, cw, ch, sc)
                    if mx is not None:
                        if offset_x or offset_y:
                            mx += offset_x
                            my += offset_y
                        canvas.create_text(mx, my, text=obj["text"], fill=c, font=("Arial", mt_sz, "bold"), tags="painter_obj")

            elif obj["type"] == "dot":
                if len(coords) < 2: continue
                x, y = coords[0]*cw + offset_x, coords[1]*ch + offset_y
                dsz = max(2, int(obj.get("size", 3) * sc_eff))
                canvas.create_rectangle(x-dsz, y-dsz, x+dsz, y+dsz, fill=c, outline="", tags="painter_obj")

            elif obj["type"] == "zone":
                if len(coords) < 6: continue
                flat_px = [(coords[i]*cw + offset_x) if i%2==0 else (coords[i]*ch + offset_y) for i in range(len(coords))]
                wz = max(1, lw - 1)
                for _run in self._dash_runs(flat_px + flat_px[:2], 2.6 * wz, 1.5 * wz):
                    canvas.create_line(*_run, fill=c, width=wz, tags="painter_obj")

            elif obj["type"] == "text":
                if len(coords) < 2: continue
                x, y = coords[0]*cw + offset_x, coords[1]*ch + offset_y

                poi_data = obj.get("poi", [])
                if isinstance(poi_data, str):
                    if poi_data.startswith("xvm_"):
                        poi_data = [int(poi_data.split("_")[1], 16)]
                    else:
                        poi_data = []

                if poi_data:
                    base_sz = poi_base
                    items = []
                    total_w = 0
                    XVM_SCALE = {
                        0x2B: 0.7,
                        0x2D: 0.7,
                        0x2E: 0.7,
                        0x3A: 0.7,
                        0x3B: 0.7,
                        0x3F: 0.7,
                        0x42: 0.7,
                        0x45: 0.7,
                        0x50: 0.7,
                        0x52: 0.7,
                        0x5C: 0.7,
                        0x6F: 0.7,
                        0x2C: 0.7,
                    }
                    for code in poi_data:
                        if code == "tree":
                            sz = int(poi_base * 0.5)
                            items.append({"tree": True, "sz": sz, "w": sz + int(4 * sc)})
                            total_w += sz + int(4 * sc)
                            continue
                        sz = int(base_sz * XVM_SCALE.get(code, 1.0))

                        t = canvas.create_text(0, 0, text=chr(code), font=("XVMSymbol", sz), state="hidden")
                        bbox = canvas.bbox(t)
                        w = bbox[2] - bbox[0] + int(4 * sc) if bbox else sz * 0.8
                        canvas.delete(t)
                        items.append({"code": code, "sz": sz, "w": w})
                        total_w += w

                    curr_x = x - total_w / 2
                    for it in items:
                        cx = curr_x + it["w"] / 2
                        if it.get("tree"):
                            canvas.create_text(cx, y, text=chr(0xF18C),
                                                font=("FontAwesome", it["sz"]), fill=c,
                                                tags="painter_obj")
                        else:
                            canvas.create_text(cx, y, text=chr(it["code"]), font=("XVMSymbol", it["sz"]), fill="black", tags=("painter_obj", "xvm_bg"))
                            canvas.create_text(cx, y, text=chr(it["code"]), font=("XVMSymbol", it["sz"]-max(2, int(4*sc))), fill=c, tags=("painter_obj", "xvm_fg"))
                        curr_x += it["w"]

                if obj.get("text"):
                    ty = y + int(15 * sc) if poi_data else y
                    canvas.create_text(x, ty, text=obj["text"], fill=c, font=("Arial", tt_sz, "bold"), tags="painter_obj")

    def migrate_legacy_coords(self):
        """One-time conversion of pre-02.10 canvas-fraction drawings into the
        image-rect space (commit 8085639). Idempotent via the norm marker.
        Caller must ensure app._map_img_rect is valid (first render done).
        Returns the number of converted elements across all maps."""
        org_x, org_y, img_w, img_h = self._img_rect()
        # _map_img_rect is in MAIN-canvas coords; prefer app.canvas, fall back
        # to the painter canvas (overlay mirrors main size via _sync_po_pos).
        src = getattr(self.app, "canvas", None) or self.canvas
        if src is None or not src.winfo_exists():
            return 0
        cw = float(src.winfo_width())
        ch = float(src.winfo_height())
        if img_w < 10 or img_h < 10 or cw < 50 or ch < 50:
            return 0
        import tactics_manager
        n = 0
        for items in self.drawings.values():
            if isinstance(items, list):
                n += tactics_manager.migrate_legacy_elements(
                    items, cw, ch, org_x, org_y, img_w, img_h)
        if n:
            # Rollback point before the first rewrite of the drawings file.
            import shutil
            bak = config.DRAWINGS_FILE + ".bak_pre_norm"
            try:
                if os.path.isfile(config.DRAWINGS_FILE) and not os.path.isfile(bak):
                    shutil.copy2(config.DRAWINGS_FILE, bak)
            except Exception as e:
                print(f"[NORM] drawings backup failed ({e}) — NOT saving")
                return 0
            self.save_drawings()
        return n

    def _img_rect(self):
        """(org_x, org_y, iw, ih) - the map image rect in canvas coords.

        map_renderer may letterbox the image inside a non-square canvas
        (show_main_splash stores app._map_img_rect). Schemes are normalized
        over the IMAGE, so both render and click->coords math must use this
        rect - not the raw canvas (01.10.2026: elements leaked into the
        black letterbox margins)."""
        r = getattr(self.app, "_map_img_rect", None)
        if r is None:
            src = getattr(self.app, "canvas", None)
            if src is None or not src.winfo_exists():
                src = self.canvas
            return 0.0, 0.0, float(src.winfo_width()), float(src.winfo_height())
        return r

    def redraw(self, cw=None, ch=None):
        if not self.app.current_map_eng: return
        # Взаємовиключність мод/оверлей діє ТІЛЬКИ в бойовому контексті
        # (режим norm поверх гри, поки бій триває) — там мод малює натомість.
        # У редакторі (mode == "edit") та в hangar схеми малюються ЗАВЖДИ:
        # раніше гейт вимикав показ скрізь при use_mod і схеми зникали з
        # мапи редактора саме в момент перемикання чекбокса (скарга 30.09.2026).
        if (getattr(self.app, '_use_mod_var', None) and self.app._use_mod_var.get()
                and getattr(self.app, 'battle_map_data_id', None)
                and getattr(self.app, 'mode', 'edit') == "norm"):
            self.canvas.delete("painter_obj")
            return
        map_id = self.app.current_map_eng

        # Scheme space = the map image rect (map_renderer may letterbox the
        # image inside a non-square canvas); caller dims are informational.
        org_x, org_y, cw, ch = self._img_rect()
        if cw < 10 or ch < 10: return

        self.canvas.delete("painter_obj")

        group_scheme_els = []
        active_group_id = getattr(self.app, "active_group_id", None)
        for gs in self._group_schemes.values():
            if gs.get("map_id") == map_id and isinstance(gs.get("elements"), list):
                if active_group_id and active_group_id != "public" and gs.get("group_id") != active_group_id:
                    continue
                for el in gs["elements"]:
                    if self.is_visible(el):
                        group_scheme_els.append(el)

        local_els = self.drawings.get(map_id, [])
        if active_group_id and active_group_id != "public":
            local_els = [obj for obj in local_els if obj.get("_source") == active_group_id]
        else:
            local_els = [obj for obj in local_els if not obj.get("_source") or obj.get("_source") == "public"]
        visible = [obj for obj in local_els if self.is_visible(obj)]
        all_visible = visible + group_scheme_els

        if not all_visible:
            self.app._lift_overlay()
            return

        screen_scale = getattr(self.app, '_get_drawing_scale', lambda: 1.0)()
        self._render_elements(self.canvas, all_visible, cw, ch,
                              offset_x=org_x, offset_y=org_y,
                              img_w=cw, img_h=ch, screen_scale=screen_scale)

        if self._select_all:
            sel_sc = min(cw, ch) / 800.0
            margin = max(4, int(8 * sel_sc))
            for obj in visible:
                c = obj.get("coords", [])
                if not c and "x1" in obj:
                    c = [obj.get("x1", 0), obj.get("y1", 0),
                         obj.get("x2", obj.get("x1", 0)), obj.get("y2", obj.get("y1", 0))]
                if obj["type"] in ("marker", "arrow"):
                    if len(c) < 4: continue
                    x1 = c[0]*cw + org_x; y1 = c[1]*ch + org_y; x2 = c[2]*cw + org_x; y2 = c[3]*ch + org_y
                    l = min(x1, x2) - margin; r = max(x1, x2) + margin
                    t = min(y1, y2) - margin; b = max(y1, y2) + margin
                elif obj["type"] == "brush":
                    if len(c) < 4: continue
                    xs = [c[i]*cw + org_x for i in range(0, len(c), 2)]
                    ys = [c[i+1]*ch + org_y for i in range(0, len(c), 2)]
                    l = min(xs) - margin; r = max(xs) + margin
                    t = min(ys) - margin; b = max(ys) + margin
                elif obj["type"] == "text":
                    if len(c) < 2: continue
                    l = c[0]*cw + org_x - 30*margin; r = c[0]*cw + org_x + 30*margin
                    t = c[1]*ch + org_y - 30*margin; b = c[1]*ch + org_y + 30*margin
                else:
                    continue
                self.canvas.create_rectangle(l, t, r, b, outline="yellow", dash=(4, 4), width=max(1, int(2*sel_sc)), tags="painter_obj")

        self.app._lift_overlay()
