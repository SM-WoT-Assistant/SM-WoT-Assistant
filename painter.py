# painter.py (відновлено з ARC/painter_1_06.py)
import os, json, math
import tkinter as tk
from tkinter import colorchooser
import config
import ctypes

font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xvmsymbol.ttf")
if os.path.exists(font_path):
    FR_PRIVATE = 0x10
    ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)


class PainterDialog(tk.Toplevel):
    def __init__(self, parent, current_mode, current_classes, default_color, tool_type, painter, edit_data=None, cancel_callback=None):
        super().__init__(parent)
        self.tool_type = tool_type
        self.edit_data = edit_data
        self.painter = painter
        self.cancel_callback = cancel_callback
        is_editing = edit_data is not None
        self.title("Редагування мітки" if is_editing else "Параметри мітки")

        self.resizable(False, False)
        self.minsize(350, 100)

        self.attributes("-topmost", True)
        self.configure(bg="#222")
        self.grab_set()

        self.result = None
        self.color = (edit_data or {}).get("color", default_color)

        self.mode_labels = {
            "Standard": "Стандарт", "Encounter": "Зустріч",
            "Assault": "Штурм", "Onslaught": "НАТИСК"
        }

        existing_modes = (edit_data or {}).get("modes", [])
        self.modes = {"Standard": tk.BooleanVar(value="Standard" in existing_modes if edit_data is not None else current_mode == "Standard"),
                      "Encounter": tk.BooleanVar(value="Encounter" in existing_modes if edit_data is not None else current_mode == "Encounter"),
                      "Assault": tk.BooleanVar(value="Assault" in existing_modes if edit_data is not None else current_mode == "Assault"),
                      "Onslaught": tk.BooleanVar(value="Onslaught" in existing_modes if edit_data is not None else current_mode == "Onslaught")}

        existing_classes = (edit_data or {}).get("classes", [])
        self.classes = {"ЛТ": tk.BooleanVar(value="ЛТ" in existing_classes if edit_data is not None else current_classes.get("ЛТ", False)),
                        "СТ": tk.BooleanVar(value="СТ" in existing_classes if edit_data is not None else current_classes.get("СТ", False)),
                        "ТТ": tk.BooleanVar(value="ТТ" in existing_classes if edit_data is not None else current_classes.get("ТТ", False)),
                        "ПТ": tk.BooleanVar(value="ПТ" in existing_classes if edit_data is not None else current_classes.get("ПТ", False)),
                        "САУ": tk.BooleanVar(value="САУ" in existing_classes if edit_data is not None else current_classes.get("САУ", False))}

        existing_text = (edit_data or {}).get("text", "")
        self.text_var = tk.StringVar(value=existing_text)
        self.text_var.trace("w", self.validate_text)
        self.text_var.trace("w", self._on_change)
        self.poi_vars = {}

        self.build_ui()
        self._sync_obj()

    def _sync_obj(self):
        if not self.edit_data:
            return
        obj = self.edit_data
        obj["modes"] = [k for k, v in self.modes.items() if v.get()]
        obj["classes"] = [k for k, v in self.classes.items() if v.get()]
        obj["text"] = self.text_var.get()
        if obj["type"] == "text":
            obj["poi"] = [code for code, var in self.poi_vars.items() if var.get()]
        obj["color"] = self.color
        if obj["type"] == "marker":
            coords = obj.get("coords", [])
            if obj.get("classes") and not obj.get("class_icon_coords") and len(coords) >= 2:
                cw = self.painter.canvas.winfo_width()
                ch = self.painter.canvas.winfo_height()
                sc = min(cw, ch) / 800.0 if cw >= 10 and ch >= 10 else 1.0
                obj["class_icon_coords"] = [coords[0], min(max(coords[1] + (int(22 * sc) / max(ch, 1)), 0.0), 1.0)]
            if obj.get("text") and not obj.get("text_coords") and len(coords) >= 4:
                cw = self.painter.canvas.winfo_width()
                ch = self.painter.canvas.winfo_height()
                sc = min(cw, ch) / 800.0 if cw >= 10 and ch >= 10 else 1.0
                obj["text_coords"] = [(coords[0]+coords[2])/2, (coords[1]+coords[3])/2 - int(10 * sc)/max(ch, 1)]
        self.painter.redraw()

    def _on_change(self, *args):
        self._sync_obj()
        
    def build_ui(self):
        style_bg = "#222"
        style_fg = "white"
        cb_style = {"bg": style_bg, "fg": style_fg, "selectcolor": "#333", "activebackground": style_bg, "activeforeground": style_fg}
        
        tk.Label(self, text="Режим бою (можна кілька):", font=("Arial", 9, "bold"), bg=style_bg, fg="#aaa").pack(anchor="w", padx=10, pady=(10,0))
        mf = tk.Frame(self, bg=style_bg)
        mf.pack(fill="x", padx=10)
        for k, v in self.modes.items():
            cb = tk.Checkbutton(mf, text=self.mode_labels[k], variable=v, command=self._on_change, **cb_style)
            cb.pack(side="left")
            
        tk.Label(self, text="Техніка (якщо пусто = Загальне):", font=("Arial", 9, "bold"), bg=style_bg, fg="#aaa").pack(anchor="w", padx=10, pady=(10,0))
        cf = tk.Frame(self, bg=style_bg)
        cf.pack(fill="x", padx=10)
        for k, v in self.classes.items():
            cb = tk.Checkbutton(cf, text=k, variable=v, command=self._on_change, **cb_style)
            cb.pack(side="left")
            
        tk.Label(self, text="Текст (опціонально):", font=("Arial", 9, "bold"), bg=style_bg, fg="#aaa").pack(anchor="w", padx=10, pady=(10,0))
        tf = tk.Frame(self, bg=style_bg)
        tf.pack(fill="x", padx=10)
        self.entry = tk.Entry(tf, textvariable=self.text_var, width=30, bg="#111", fg="white", insertbackground="white", bd=1, relief="solid")
        self.entry.pack(side="left", pady=5)
        self.count_lbl = tk.Label(tf, text="0/30", bg=style_bg, fg="gray")
        self.count_lbl.pack(side="left", padx=5)
        
        if self.tool_type == "text":
            tk.Label(self, text="Знак (можна кілька):", font=("Arial", 9, "bold"), bg=style_bg, fg="#aaa").pack(anchor="w", padx=10, pady=(10,0))
            pf = tk.Frame(self, bg=style_bg)
            pf.pack(fill="x", padx=10)
            
            xvm_codes = [0x2B, 0x2D, 0x2E, 0x3A, 0x3B, 0x3F, 0x42, 0x45, 0x50, 0x52, 0x5C, 0x6F, 0x2C]
            existing_poi = (self.edit_data or {}).get("poi", [])
            if isinstance(existing_poi, str):
                if existing_poi.startswith("xvm_"):
                    existing_poi = [int(existing_poi.split("_")[1], 16)]
                else:
                    existing_poi = []
            for i, code in enumerate(xvm_codes):
                self.poi_vars[code] = tk.BooleanVar(value=code in existing_poi)
                cb = tk.Checkbutton(pf, text=chr(code), variable=self.poi_vars[code], font=("XVMSymbol", 16), command=self._on_change, **cb_style)
                cb.grid(row=i//5, column=i%5, sticky="w", padx=2, pady=2)
            tree_var = tk.BooleanVar(value="tree" in existing_poi)
            self.poi_vars["tree"] = tree_var
            tf = tk.Frame(pf, bg=style_bg)
            tf.grid(row=(len(xvm_codes)+4)//5, column=0, columnspan=5, sticky="w", padx=2, pady=4)
            tree_img = self.painter._render_tree(24, "#00ff00") if hasattr(self.painter, '_render_tree') else None
            if tree_img:
                tree_cb = tk.Checkbutton(tf, image=tree_img, variable=tree_var, command=self._on_change, bg=style_bg, activebackground=style_bg, bd=0)
                tree_cb.image = tree_img
                tree_cb.pack(side="left")
            else:
                tree_cb = tk.Checkbutton(tf, text="T", variable=tree_var, command=self._on_change, **cb_style)
                tree_cb.pack(side="left")
            tk.Label(tf, text=self.painter.app.t('ui', 'broken_tree'), bg=style_bg, fg="#aaa", font=("Arial", 9)).pack(side="left", padx=5)
            
        tk.Label(self, text="Колір:", font=("Arial", 9, "bold"), bg=style_bg, fg="#aaa").pack(anchor="w", padx=10, pady=(10,0))
        clf = tk.Frame(self, bg=style_bg)
        clf.pack(fill="x", padx=10)
        colors = [("#ff0000", "Червоний"), ("#00ff00", "Зелений"), ("#00bbff", "Синій"), 
                  ("#ffff00", "Жовтий"), ("#ffaa00", "Помаранчевий")]
        for hex_code, name in colors:
            btn = tk.Button(clf, bg=hex_code, width=2, bd=0, command=lambda c=hex_code: self.set_color(c))
            btn.pack(side="left", padx=2, pady=5)
        tk.Button(clf, text="Інший...", bg="#444", fg="white", bd=0, command=self.pick_color).pack(side="left", padx=5)
        self.color_preview = tk.Label(clf, text=" ■ ", bg=style_bg, fg=self.color, font=("Arial", 16))
        self.color_preview.pack(side="left", padx=5)
        
        bf = tk.Frame(self, bg=style_bg)
        bf.pack(fill="x", padx=10, pady=20)
        tk.Button(bf, text="ЗБЕРЕГТИ", bg="#006400", fg="white", bd=0, font=("Arial", 10, "bold"), pady=5, command=self.save).pack(side="left", expand=True, fill="x", padx=5)
        tk.Button(bf, text="СКАСУВАТИ", bg="#8b0000", fg="white", bd=0, font=("Arial", 10, "bold"), pady=5, command=self.cancel).pack(side="right", expand=True, fill="x", padx=5)
        
    def validate_text(self, *args):
        t = self.text_var.get()
        if len(t) > 30:
            self.text_var.set(t[:30])
            self.entry.config(bg="#550000")
        else:
            self.entry.config(bg="#111")
        self.count_lbl.config(text=f"{len(self.text_var.get())}/30")
        
    def set_color(self, c):
        self.color = c
        self.color_preview.config(fg=self.color)
        self._sync_obj()
        
    def pick_color(self):
        c = colorchooser.askcolor(color=self.color, parent=self)[1]
        if c: self.set_color(c)

    def cancel(self):
        if self.cancel_callback:
            self.cancel_callback()
        self.destroy()
        
    def save(self):
        self._sync_obj()
        selected_modes = [k for k, v in self.modes.items() if v.get()]
        selected_classes = [k for k, v in self.classes.items() if v.get()]
        
        poi_res = []
        if self.tool_type == "text":
            poi_res = [code for code, var in self.poi_vars.items() if var.get()]
            
        self.result = {
            "modes": selected_modes,
            "classes": selected_classes,
            "text": self.text_var.get(),
            "poi": poi_res,
            "color": self.color
        }
        self.destroy()

class MapPainter:
    def __init__(self, canvas, app, data_mgr):
        self.canvas = canvas
        self.app = app
        self.data_mgr = data_mgr
        self.drawings = self.data_mgr.load_drawings()
        
        self.active_tool = None
        self.default_color = "#ffaa00"
        
        self.start_x = 0
        self.start_y = 0
        self.temp_item = None
        self.move_drag = None
        self.move_drag_active = False
        
        self._load_tree_icon()
        self.class_icon_codes = {
            "ЛТ": 0x3A,
            "СТ": 0x3B,
            "ТТ": 0x3F,
            "ПТ": 0x2E,
            "САУ": 0x2D,
        }
    
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
        ]:
            target_canvas.bind(ev, cb, add="+")
    
    def _load_tree_icon(self):
        try:
            tree_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon", "Broken_tree.svg")
            if not os.path.exists(tree_path):
                return
            with open(tree_path, 'rb') as f:
                self._tree_svg_data = f.read()
        except Exception as e:
            print(f"[PAINTER] Не вдалося завантажити іконку дерева: {e}")

    def _render_tree(self, size, color):
        try:
            if not hasattr(self, '_tree_svg_data'):
                return None
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtCore import QByteArray, QRectF
            from PyQt6.QtGui import QImage, QPainter
            from PIL import ImageQt, ImageTk
            key = (size, color)
            if not hasattr(self, '_tree_render_cache'):
                self._tree_render_cache = {}
            if key not in self._tree_render_cache:
                svg_text = self._tree_svg_data.decode('utf-8')
                svg_text = svg_text.replace('.st0{fill:#FFFFFF;}', '.st0{fill:%s;}' % color)
                svg_text = svg_text.replace('.st0{fill:#ffffff;}', '.st0{fill:%s;}' % color)
                qimg = QImage(size, size, QImage.Format.Format_ARGB32)
                qimg.fill(0x00000000)
                painter = QPainter(qimg)
                renderer = QSvgRenderer(QByteArray(svg_text.encode('utf-8')))
                renderer.render(painter, QRectF(0, 0, size, size))
                painter.end()
                self._tree_render_cache[key] = ImageTk.PhotoImage(ImageQt.fromqimage(qimg))
            return self._tree_render_cache[key]
        except Exception as e:
            print(f"[PAINTER] render_tree error: {e}")
            return None

    def set_tool(self, tool):
        self.active_tool = tool
        self.app.status_label.config(text=f"ІНСТРУМЕНТ: {tool.upper() if tool else 'ВИМКНЕНО'}")
        
    def clear_all(self):
        if not self.app.current_map_eng: return
        map_id = self.app.current_map_eng
        if map_id in self.drawings and self.drawings[map_id]:
            self.app.ask_clear_confirm(self.app.translate_map_name(map_id), self._do_clear)

    def _do_clear(self, confirmed):
        if confirmed and self.app.current_map_eng:
            self.drawings[self.app.current_map_eng] = []
            self.data_mgr.save_drawings(self.drawings)
            self.redraw()

    def on_press(self, event):
        if not self.active_tool or not self.app.current_map_eng or self.app.mode != "edit": return
        
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: return

        self.start_x = event.x
        self.start_y = event.y
        
        if self.active_tool == "marker":
            map_id = self.app.current_map_eng
            if map_id in self.drawings:
                min_dist = 15 
                snap_x, snap_y = self.start_x, self.start_y
                for obj in self.drawings[map_id]:
                    if obj["type"] == "marker" and self.is_visible(obj):
                        coords = obj["coords"]
                        if len(coords) >= 4:
                            ox, oy = coords[0]*cw, coords[1]*ch
                            dist = math.hypot(ox - event.x, oy - event.y)
                            if dist < min_dist:
                                min_dist = dist
                                snap_x, snap_y = ox, oy
                self.start_x = snap_x
                self.start_y = snap_y

            self.temp_item = self.canvas.create_line(self.start_x, self.start_y, event.x, event.y, arrow=tk.LAST, fill=self.default_color, width=3, dash=(5, 5), tags="temp_draw")
            self.canvas.create_oval(self.start_x-12, self.start_y-12, self.start_x+12, self.start_y+12, outline=self.default_color, width=2, tags="temp_draw")
            self.canvas.create_oval(self.start_x-4, self.start_y-4, self.start_x+4, self.start_y+4, fill="white", outline="white", tags="temp_draw")
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

    def _get_marker_class_anchor(self, obj, cw, ch, sc=1.0):
        icon_coords = obj.get("class_icon_coords")
        if isinstance(icon_coords, list) and len(icon_coords) >= 2:
            return icon_coords[0] * cw, icon_coords[1] * ch
        coords = obj.get("coords", [])
        if len(coords) >= 2:
            return coords[0] * cw, coords[1] * ch + int(22 * sc)
        return None, None

    def _get_marker_text_pos(self, obj, cw, ch, sc=1.0):
        text_coords = obj.get("text_coords")
        if isinstance(text_coords, list) and len(text_coords) >= 2:
            return text_coords[0] * cw, text_coords[1] * ch
        coords = obj.get("coords", [])
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

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return -1, "object"

        click_px, click_py = event_x / cw, event_y / ch
        threshold_px = 18
        threshold_norm = threshold_px / max(1, min(cw, ch))
        closest_idx = -1
        closest_kind = "object"
        min_dist = threshold_norm

        for i, obj in enumerate(objects):
            if not self.is_visible(obj):
                continue
            coords = obj.get("coords", [])

            found_special = False

            if obj.get("type") == "marker" and obj.get("text"):
                tx, ty = self._get_marker_text_pos(obj, cw, ch)
                if tx is not None:
                    text_dist = math.hypot((tx / cw) - click_px, (ty / ch) - click_py)
                    if text_dist < min_dist:
                        min_dist = text_dist
                        closest_idx = i
                        closest_kind = "marker_text"
                        found_special = True

            if obj.get("type") == "marker" and obj.get("classes"):
                icon_x, icon_y = self._get_marker_class_anchor(obj, cw, ch)
                if icon_x is not None:
                    icon_dist = math.hypot((icon_x / cw) - click_px, (icon_y / ch) - click_py)
                    if icon_dist < min_dist:
                        min_dist = icon_dist
                        closest_idx = i
                        closest_kind = "class_icons"
                        found_special = True

            if obj.get("type") == "marker" and len(coords) >= 4:
                tip_dist = math.hypot(coords[2] - click_px, coords[3] - click_py)
                if tip_dist < min_dist:
                    min_dist = tip_dist
                    closest_idx = i
                    closest_kind = "marker_tip"
                    found_special = True

            if found_special:
                continue

            if obj.get("type") == "marker" and len(coords) >= 4:
                dist = min(
                    math.hypot(coords[0] - click_px, coords[1] - click_py),
                    math.hypot(coords[2] - click_px, coords[3] - click_py),
                    self._distance_to_segment(click_px, click_py, coords[0], coords[1], coords[2], coords[3]),
                )
            elif obj.get("type") == "text" and len(coords) >= 2:
                tx_norm, ty_norm = coords[0], coords[1]
                dist = math.hypot(tx_norm - click_px, ty_norm - click_py)
                poi = obj.get("poi", [])
                txt = obj.get("text", "")
                if poi:
                    d = math.hypot(tx_norm - click_px, ty_norm - 24/ch - click_py)
                    if d < dist:
                        dist = d
                if txt:
                    ofs = 15/ch if poi else 0
                    d = math.hypot(tx_norm - click_px, ty_norm + ofs - click_py)
                    if d < dist:
                        dist = d
            else:
                continue
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
                closest_kind = "object"
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

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        dx = (event.x - self.move_drag["start_event"][0]) / cw
        dy = (event.y - self.move_drag["start_event"][1]) / ch
        obj = objects[idx]
        original = self.move_drag["original_coords"]
        target_kind = self.move_drag.get("target_kind", "object")

        if target_kind == "marker_tip" and obj.get("type") == "marker":
            original = self.move_drag["original_coords"]
            obj["coords"] = [
                original[0], original[1],
                min(max(original[2] + dx, 0.0), 1.0),
                min(max(original[3] + dy, 0.0), 1.0),
            ]
            self.redraw()
            return "break"

        if target_kind == "marker_text" and obj.get("type") == "marker":
            orig_tc = self.move_drag.get("original_text_coords", [])
            if not orig_tc or len(orig_tc) < 2:
                tx, ty = self._get_marker_text_pos(obj, cw, ch)
                orig_tc = [tx / cw, ty / ch]
            obj["text_coords"] = [
                min(max(orig_tc[0] + dx, 0.0), 1.0),
                min(max(orig_tc[1] + dy, 0.0), 1.0),
            ]
            self.redraw()
            return "break"

        if target_kind == "class_icons" and obj.get("type") == "marker":
            class_anchor = self.move_drag.get("original_class_icon_coords")
            if not class_anchor or len(class_anchor) < 2:
                icon_x, icon_y = self._get_marker_class_anchor(obj, cw, ch)
                class_anchor = [icon_x / cw, icon_y / ch]
            obj["class_icon_coords"] = [
                min(max(class_anchor[0] + dx, 0.0), 1.0),
                min(max(class_anchor[1] + dy, 0.0), 1.0),
            ]
            self.redraw()
            return "break"

        if obj.get("type") == "marker" and len(original) >= 4:
            new_coords = [
                min(max(original[0] + dx, 0.0), 1.0),
                min(max(original[1] + dy, 0.0), 1.0),
                min(max(original[2] + dx, 0.0), 1.0),
                min(max(original[3] + dy, 0.0), 1.0),
            ]
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
        self.move_drag = None
        self.data_mgr.save_drawings(self.drawings)
        return "break"

    def _draw_class_icons(self, x, y, class_list, color, sc=1.0):
        ordered_classes = [cls for cls in ("ЛТ", "СТ", "ТТ", "ПТ", "САУ") if cls in class_list]
        if not ordered_classes:
            return

        base_sz = max(10, int(29 * sc))
        gap = max(5, int(21 * sc))
        class_scale = {"ЛТ": 1.2, "СТ": 1.3, "ПТ": 1.3, "САУ": 1.3}
        sizes = [base_sz * class_scale.get(cls, 1.0) for cls in ordered_classes]
        gaps = [gap * class_scale.get(cls, 1.0) for cls in ordered_classes]
        total_w = sum(gaps) - gaps[-1] if gaps else 0
        start_x = x - total_w / 2

        curr_x = start_x
        for idx, cls in enumerate(ordered_classes):
            code = self.class_icon_codes.get(cls)
            if not code:
                continue
            sz = int(sizes[idx])
            g = int(gaps[idx])
            self.canvas.create_text(curr_x, y, text=chr(code), font=("XVMSymbol", sz), fill="black", tags=("painter_obj", "class_icon_bg"))
            self.canvas.create_text(curr_x, y, text=chr(code), font=("XVMSymbol", sz - 4), fill=color, tags=("painter_obj", "class_icon_fg"))
            curr_x += g
            
    def on_drag(self, event):
        if not self.temp_item or self.app.mode != "edit": return
        if self.active_tool == "marker":
            self.canvas.coords(self.temp_item, self.start_x, self.start_y, event.x, event.y)
        elif self.active_tool == "text":
            self.canvas.coords(self.temp_item, event.x, event.y)
            
    def on_release(self, event):
        if not self.active_tool or not self.app.current_map_eng or self.app.mode != "edit": return
        if not self.temp_item: return
            
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: return
        
        px1, py1 = self.start_x / cw, self.start_y / ch
        px2, py2 = event.x / cw, event.y / ch
        
        current_classes = {k: v.get() for k, v in self.app.selected_classes.items()}
        current_mode = self.app.selected_battle_mode.get()

        new_obj = {
            "type": self.active_tool,
            "modes": [],
            "classes": [],
            "text": "",
            "poi": [],
            "color": "#00ff00" if self.active_tool == "text" else self.default_color,
        }
        if self.active_tool == "marker":
            new_obj["coords"] = [px1, py1, px2, py2]
        else:
            new_obj["coords"] = [px2, py2]

        map_id = self.app.current_map_eng
        if map_id not in self.drawings: self.drawings[map_id] = []
        self.drawings[map_id].append(new_obj)

        def _cancel_remove():
            if map_id in self.drawings and new_obj in self.drawings[map_id]:
                self.drawings[map_id].remove(new_obj)
            self.redraw()

        self.app.dialog_open = True
        dlg = PainterDialog(self.app.root, current_mode, current_classes, self.default_color, self.active_tool, self, edit_data=new_obj, cancel_callback=_cancel_remove)
        self.app.root.wait_window(dlg)
        self.app.dialog_open = False
        
        self.canvas.delete("temp_draw")
        self.temp_item = None
            
        if dlg.result:
            self.default_color = dlg.result["color"]
            self.data_mgr.save_drawings(self.drawings)
            self.redraw()
        else:
            _cancel_remove()
        self.app.set_painter_tool(None)
            
    def on_right_click(self, event):
        if self.app.mode != "edit" or not self.app.current_map_eng:
            return
        idx, _ = self._find_object_index_at(event.x, event.y)
        if idx < 0:
            return

        menu = tk.Menu(self.canvas, tearoff=0, bg="#333", fg="white",
                       activebackground="#555", activeforeground="white",
                       font=("Arial", 10))
        menu.add_command(label="Редагувати", command=lambda: self.app.root.after(50, self._edit_object_at, idx))
        menu.add_separator(background="#555")
        menu.add_command(label="Видалити", command=lambda: self.app.root.after(50, self._delete_object_at, idx))
        menu.post(event.x_root, event.y_root)

    def _edit_object_at(self, idx):
        if not self.app.current_map_eng:
            return
        map_id = self.app.current_map_eng
        objects = self.drawings.get(map_id, [])
        if idx < 0 or idx >= len(objects):
            return
        obj = objects[idx]
        obj_backup = {
            "modes": list(obj.get("modes", [])),
            "classes": list(obj.get("classes", [])),
            "text": obj.get("text", ""),
            "color": obj.get("color", self.default_color),
            "poi": list(obj.get("poi", [])),
        }
        self.app.dialog_open = True
        dlg = PainterDialog(self.app.root, None, None, obj.get("color", self.default_color), obj["type"], self, edit_data=obj)
        self.app.root.wait_window(dlg)
        self.app.dialog_open = False
        if dlg.result:
            self.data_mgr.save_drawings(self.drawings)
            self.redraw()
        else:
            obj["modes"] = obj_backup["modes"]
            obj["classes"] = obj_backup["classes"]
            obj["text"] = obj_backup["text"]
            obj["color"] = obj_backup["color"]
            if obj["type"] == "text":
                obj["poi"] = obj_backup["poi"]
            self.redraw()

    def _confirm_delete(self, label):
        dlg = tk.Toplevel(self.app.root)
        dlg.title("Підтвердження")
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        dlg.minsize(300, 120)
        dlg.attributes("-topmost", True)
        dlg.grab_set()

        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - 150
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - 60
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text=f"Видалити {label}?", font=("Arial", 10),
                 bg="#2a2a2a", fg="#cccccc").pack(pady=(20, 15))

        bf = tk.Frame(dlg, bg="#2a2a2a")
        bf.pack(pady=(0, 15))
        result = {"ok": False}
        def on_yes(): result["ok"] = True; dlg.destroy()
        def on_no(): dlg.destroy()

        tk.Button(bf, text="  Так  ", bg="#555", fg="white", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_yes).pack(side="left", padx=10)
        tk.Button(bf, text="  Ні  ", bg="#444", fg="#aaa", bd=0,
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
        label = "Маркер" if obj["type"] == "marker" else "Текст/Знак"
        ok = self._confirm_delete(label)
        if ok:
            del objects[idx]
            self.data_mgr.save_drawings(self.drawings)
            self.redraw()

    def is_visible(self, obj):
        current_mode = self.app.selected_battle_mode.get()
        active_classes = [k for k, v in self.app.selected_classes.items() if v.get()]
        
        if obj.get("modes") and current_mode not in obj["modes"]:
            return False
            
        req_classes = obj.get("classes", [])
        if req_classes:
            if not any(cls in active_classes for cls in req_classes):
                return False
                
        return True

    def redraw(self, cw=None, ch=None):
        self.canvas.delete("painter_obj")
        if not self.app.current_map_eng: return
        map_id = self.app.current_map_eng
        if map_id not in self.drawings: return
        
        if cw is None or ch is None:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: return

        sc = min(cw, ch) / 800.0
        r12 = max(3, int(12 * sc))
        r4 = max(2, int(4 * sc))
        lw = max(1, int(3 * sc))
        mt_sz = max(6, int(9 * sc))
        poi_base = max(12, int(48 * sc))
        tt_sz = max(6, int(10 * sc))
        
        for obj in self.drawings[map_id]:
            if not self.is_visible(obj): continue
            
            c = obj["color"]
            coords = obj["coords"]
            
            if obj["type"] == "marker":
                if len(coords) < 4: continue 
                x1, y1 = coords[0]*cw, coords[1]*ch
                x2, y2 = coords[2]*cw, coords[3]*ch
                self.canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill=c, width=lw, dash=(5, 5), tags="painter_obj")
                
                self.canvas.create_oval(x1-r12, y1-r12, x1+r12, y1+r12, outline=c, width=max(1, lw-1), tags="painter_obj")
                self.canvas.create_oval(x1-r4, y1-r4, x1+r4, y1+r4, fill="white", outline="white", tags="painter_obj")

                if obj.get("classes"):
                    icon_x, icon_y = self._get_marker_class_anchor(obj, cw, ch, sc)
                    self._draw_class_icons(icon_x, icon_y, obj["classes"], c, sc)
                
                if obj.get("text"):
                    mx, my = self._get_marker_text_pos(obj, cw, ch, sc)
                    if mx is not None:
                        self.canvas.create_text(mx, my, text=obj["text"], fill=c, font=("Arial", mt_sz, "bold"), tags="painter_obj")
                    
            elif obj["type"] == "text":
                if len(coords) < 2: continue 
                x, y = coords[0]*cw, coords[1]*ch
                
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
                        0x2B: 1.4,
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
                        0x6F: 1.4,
                        0x2C: 0.7,
                    }
                    for code in poi_data:
                        if code == "tree":
                            sz = int(poi_base * 1.0)
                            items.append({"tree": True, "sz": sz, "color": c, "w": sz + int(4 * sc)})
                            total_w += sz + int(4 * sc)
                            continue
                        sz = int(base_sz * XVM_SCALE.get(code, 1.0))
                        
                        t = self.canvas.create_text(0, 0, text=chr(code), font=("XVMSymbol", sz), state="hidden")
                        bbox = self.canvas.bbox(t)
                        w = bbox[2] - bbox[0] + int(4 * sc) if bbox else sz * 0.8
                        self.canvas.delete(t)
                        items.append({"code": code, "sz": sz, "w": w})
                        total_w += w
                        
                    curr_x = x - total_w / 2
                    poi_oy = int(24 * sc)
                    for it in items:
                        cx = curr_x + it["w"] / 2
                        if it.get("tree"):
                            tree_img = self._render_tree(it["sz"], it["color"]) if hasattr(self, '_render_tree') else None
                            if tree_img:
                                self.canvas.create_image(cx, y-poi_oy, image=tree_img, tags="painter_obj")
                        else:
                            self.canvas.create_text(cx, y-poi_oy, text=chr(it["code"]), font=("XVMSymbol", it["sz"]), fill="black", tags=("painter_obj", "xvm_bg"))
                            self.canvas.create_text(cx, y-poi_oy, text=chr(it["code"]), font=("XVMSymbol", it["sz"]-max(2, int(4*sc))), fill=c, tags=("painter_obj", "xvm_fg"))
                        curr_x += it["w"]
                
                if obj.get("text"):
                    ty = y + int(15 * sc) if poi_data else y
                    self.canvas.create_text(x, ty, text=obj["text"], fill=c, font=("Arial", tt_sz, "bold"), tags="painter_obj")
