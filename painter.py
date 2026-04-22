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
    def __init__(self, parent, current_mode, current_classes, default_color, tool_type):
        super().__init__(parent)
        self.tool_type = tool_type
        self.title("Параметри мітки")
        
        self.resizable(False, False)
        # Use minsize and winfo logic or just leave it to automatically wrap elements
        self.minsize(350, 100)
        
        self.attributes("-topmost", True)
        self.configure(bg="#222") 
        self.grab_set()
        
        self.result = None
        self.color = default_color
        
        self.mode_labels = {
            "Standard": "Стандарт", "Encounter": "Зустріч", 
            "Assault": "Штурм", "Onslaught": "НАТИСК"
        }
        
        self.modes = {"Standard": tk.BooleanVar(value=False),
                      "Encounter": tk.BooleanVar(value=False),
                      "Assault": tk.BooleanVar(value=False),
                      "Onslaught": tk.BooleanVar(value=False)}
                      
        self.classes = {"ЛТ": tk.BooleanVar(value=current_classes.get("ЛТ", False)),
                        "СТ": tk.BooleanVar(value=current_classes.get("СТ", False)),
                        "ТТ": tk.BooleanVar(value=current_classes.get("ТТ", False)),
                        "ПТ": tk.BooleanVar(value=current_classes.get("ПТ", False)),
                        "САУ": tk.BooleanVar(value=current_classes.get("САУ", False))}
        
        self.text_var = tk.StringVar()
        self.text_var.trace("w", self.validate_text)
        self.poi_vars = {}
        
        self.build_ui()
        
    def build_ui(self):
        style_bg = "#222"
        style_fg = "white"
        cb_style = {"bg": style_bg, "fg": style_fg, "selectcolor": "#333", "activebackground": style_bg, "activeforeground": style_fg}
        
        tk.Label(self, text="Режим бою (можна кілька):", font=("Arial", 9, "bold"), bg=style_bg, fg="#aaa").pack(anchor="w", padx=10, pady=(10,0))
        mf = tk.Frame(self, bg=style_bg)
        mf.pack(fill="x", padx=10)
        for k, v in self.modes.items():
            tk.Checkbutton(mf, text=self.mode_labels[k], variable=v, **cb_style).pack(side="left")
            
        tk.Label(self, text="Техніка (якщо пусто = Загальне):", font=("Arial", 9, "bold"), bg=style_bg, fg="#aaa").pack(anchor="w", padx=10, pady=(10,0))
        cf = tk.Frame(self, bg=style_bg)
        cf.pack(fill="x", padx=10)
        for k, v in self.classes.items():
            tk.Checkbutton(cf, text=k, variable=v, **cb_style).pack(side="left")
            
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
            for i, code in enumerate(xvm_codes):
                self.poi_vars[code] = tk.BooleanVar(value=False)
                tk.Checkbutton(pf, text=chr(code), variable=self.poi_vars[code], font=("XVMSymbol", 16), **cb_style).grid(row=i//5, column=i%5, sticky="w", padx=2, pady=2)
            
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
        tk.Button(bf, text="СКАСУВАТИ", bg="#8b0000", fg="white", bd=0, font=("Arial", 10, "bold"), pady=5, command=self.destroy).pack(side="right", expand=True, fill="x", padx=5)
        
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
        
    def pick_color(self):
        c = colorchooser.askcolor(color=self.color, parent=self)[1]
        if c: self.set_color(c)
        
    def save(self):
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
        
        self.canvas.bind("<ButtonPress-1>", self.on_press, add="+")
        self.canvas.bind("<B1-Motion>", self.on_drag, add="+")
        self.canvas.bind("<ButtonRelease-1>", self.on_release, add="+")
        self.canvas.bind("<Control-Button-1>", self.on_move_press, add="+")
        self.canvas.bind("<Control-B1-Motion>", self.on_move_drag, add="+")
        self.canvas.bind("<Control-ButtonRelease-1>", self.on_move_release, add="+")
        self.canvas.bind("<Double-Button-3>", self.on_right_double, add="+")

        self.class_icon_codes = {
            "ЛТ": 0x3A,
            "СТ": 0x3B,
            "ТТ": 0x3F,
            "ПТ": 0x42,
            "САУ": 0x45,
        }
        
    # load_data and save_data moved to DataManager
            
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

    def _get_marker_class_anchor(self, obj, cw, ch):
        icon_coords = obj.get("class_icon_coords")
        if isinstance(icon_coords, list) and len(icon_coords) >= 2:
            return icon_coords[0] * cw, icon_coords[1] * ch
        coords = obj.get("coords", [])
        if len(coords) >= 2:
            return coords[0] * cw, coords[1] * ch + 22
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
            if obj.get("type") == "marker" and obj.get("classes"):
                icon_x, icon_y = self._get_marker_class_anchor(obj, cw, ch)
                if icon_x is not None:
                    icon_dist = math.hypot((icon_x / cw) - click_px, (icon_y / ch) - click_py)
                    if icon_dist < min_dist:
                        min_dist = icon_dist
                        closest_idx = i
                        closest_kind = "class_icons"
            if obj.get("type") == "marker" and len(coords) >= 4:
                dist = min(
                    math.hypot(coords[0] - click_px, coords[1] - click_py),
                    math.hypot(coords[2] - click_px, coords[3] - click_py),
                    self._distance_to_segment(click_px, click_py, coords[0], coords[1], coords[2], coords[3]),
                )
            elif obj.get("type") == "text" and len(coords) >= 2:
                dist = math.hypot(coords[0] - click_px, coords[1] - click_py)
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

    def _draw_class_icons(self, x, y, class_list, color):
        ordered_classes = [cls for cls in ("ЛТ", "СТ", "ТТ", "ПТ", "САУ") if cls in class_list]
        if not ordered_classes:
            return

        base_sz = 29
        gap = 21
        total_w = gap * (len(ordered_classes) - 1)
        start_x = x - total_w / 2

        for idx, cls in enumerate(ordered_classes):
            code = self.class_icon_codes.get(cls)
            if not code:
                continue
            draw_x = start_x + idx * gap
            self.canvas.create_text(draw_x, y, text=chr(code), font=("XVMSymbol", base_sz), fill="black", tags=("painter_obj", "class_icon_bg"))
            self.canvas.create_text(draw_x, y, text=chr(code), font=("XVMSymbol", base_sz - 4), fill=color, tags=("painter_obj", "class_icon_fg"))
            
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
        
        self.app.dialog_open = True
        dlg = PainterDialog(self.app.root, current_mode, current_classes, self.default_color, self.active_tool)
        self.app.root.wait_window(dlg)
        self.app.dialog_open = False
        
        self.canvas.delete("temp_draw")
        self.temp_item = None
            
        if dlg.result:
            self.default_color = dlg.result["color"]
            new_obj = {
                "type": self.active_tool,
                "modes": dlg.result["modes"],
                "classes": dlg.result["classes"],
                "text": dlg.result["text"],
                "poi": dlg.result["poi"],
                "color": dlg.result["color"]
            }
            if self.active_tool == "marker":
                new_obj["coords"] = [px1, py1, px2, py2]
                if dlg.result["classes"]:
                    new_obj["class_icon_coords"] = [px1, min(max(py1 + (22 / ch), 0.0), 1.0)]
            else:
                new_obj["coords"] = [px2, py2] 
                
            map_id = self.app.current_map_eng
            if map_id not in self.drawings: self.drawings[map_id] = []
            self.drawings[map_id].append(new_obj)
            self.data_mgr.save_drawings(self.drawings)
        
        self.redraw()
        self.app.set_painter_tool(None)
            
    def on_right_double(self, event):
        if not self.app.current_map_eng or self.app.mode != "edit": return
        map_id = self.app.current_map_eng
        if map_id not in self.drawings or not self.drawings[map_id]: return
        
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        click_px, click_py = event.x / cw, event.y / ch
        
        closest_idx = -1
        min_dist = 0.05 
        
        for i, obj in enumerate(self.drawings[map_id]):
            if not self.is_visible(obj): continue
            
            coords = obj["coords"]
            if obj["type"] == "marker":
                if len(coords) < 4: continue 
                dist1 = math.hypot(coords[2]-click_px, coords[3]-click_py) 
                dist2 = math.hypot(coords[0]-click_px, coords[1]-click_py) 
                dist = min(dist1, dist2)
            else:
                if len(coords) < 2: continue 
                dist = math.hypot(coords[0]-click_px, coords[1]-click_py)
                
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
                
        if closest_idx != -1:
            del self.drawings[map_id][closest_idx]
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

    def redraw(self):
        self.canvas.delete("painter_obj")
        if not self.app.current_map_eng: return
        map_id = self.app.current_map_eng
        if map_id not in self.drawings: return
        
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: return
        
        for obj in self.drawings[map_id]:
            if not self.is_visible(obj): continue
            
            c = obj["color"]
            coords = obj["coords"]
            
            if obj["type"] == "marker":
                if len(coords) < 4: continue 
                x1, y1 = coords[0]*cw, coords[1]*ch
                x2, y2 = coords[2]*cw, coords[3]*ch
                self.canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill=c, width=3, dash=(5, 5), tags="painter_obj")
                
                self.canvas.create_oval(x1-12, y1-12, x1+12, y1+12, outline=c, width=2, tags="painter_obj")
                self.canvas.create_oval(x1-4, y1-4, x1+4, y1+4, fill="white", outline="white", tags="painter_obj")

                if obj.get("classes"):
                    icon_x, icon_y = self._get_marker_class_anchor(obj, cw, ch)
                    self._draw_class_icons(icon_x, icon_y, obj["classes"], c)
                
                if obj.get("text"):
                    mx, my = (x1+x2)/2, ((y1+y2)/2)-10
                    self.canvas.create_text(mx, my, text=obj["text"], fill=c, font=("Arial", 9, "bold"), tags="painter_obj")
                    
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
                    base_sz = 48
                    items = []
                    total_w = 0
                    # Множники кеглю для кожного знаку (1.0 = базовий розмір base_sz)
                    XVM_SCALE = {
                        0x2B: 1.4,  # + маркер
                        0x2D: 0.7,  # - риска
                        0x2E: 0.7,  # . крапка
                        0x3A: 0.7,  # : ЛТ
                        0x3B: 0.7,  # ; СТ
                        0x3F: 0.7,  # ? ТТ
                        0x42: 0.7,  # B ПТ
                        0x45: 0.7,  # E САУ
                        0x50: 0.7,  # P знак 9
                        0x52: 0.7,  # R знак 10
                        0x5C: 0.7,  # \ знак 11
                        0x6F: 1.4,  # o знак 12
                        0x2C: 0.7,  # , знак 13
                    }
                    for code in poi_data:
                        sz = int(base_sz * XVM_SCALE.get(code, 1.0))
                        
                        t = self.canvas.create_text(0, 0, text=chr(code), font=("XVMSymbol", sz), state="hidden")
                        bbox = self.canvas.bbox(t)
                        w = bbox[2] - bbox[0] + 4 if bbox else sz * 0.8
                        self.canvas.delete(t)
                        items.append({"code": code, "sz": sz, "w": w})
                        total_w += w
                        
                    curr_x = x - total_w / 2
                    for it in items:
                        cx = curr_x + it["w"] / 2
                        self.canvas.create_text(cx, y-24, text=chr(it["code"]), font=("XVMSymbol", it["sz"]), fill="black", tags=("painter_obj", "xvm_bg"))
                        self.canvas.create_text(cx, y-24, text=chr(it["code"]), font=("XVMSymbol", it["sz"]-4), fill=c, tags=("painter_obj", "xvm_fg"))
                        curr_x += it["w"]
                
                if obj.get("text"):
                    ty = y + 15 if poi_data else y
                    self.canvas.create_text(x, ty, text=obj["text"], fill=c, font=("Arial", 10, "bold"), tags="painter_obj")
