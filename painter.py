# painter.py (відновлено з ARC/painter_1_06.py)
import os, json, math
import tkinter as tk
import config
import ctypes

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
        
        self.active_tool = None
        self.default_color = "#ffaa00"
        
        self.start_x = 0
        self.start_y = 0
        self.temp_item = None
        self.move_drag = None
        self.move_drag_active = False
        
        self._creation_history = []
        self._editing_idx = -1

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
    
    def set_tool(self, tool):
        self.active_tool = tool
        palette = getattr(self.app, 'drawing_palette', None)
        if not palette or not palette.is_in_edit_mode():
            self.app.status_label.config(text=f"ІНСТРУМЕНТ: {tool.upper() if tool else 'ВИМКНЕНО'}")
        
    def clear_all(self):
        if not self.app.current_map_eng: return
        map_id = self.app.current_map_eng
        if map_id in self.drawings and self.drawings[map_id]:
            self.app.ask_clear_confirm(self.app.translate_map_name(map_id), self._do_clear)

    def _do_clear(self, confirmed):
        if confirmed and self.app.current_map_eng:
            self.drawings[self.app.current_map_eng] = []
            self._creation_history.clear()
            self._editing_idx = -1
            palette = getattr(self.app, 'drawing_palette', None)
            if palette:
                palette.exit_edit_mode()
            self.data_mgr.save_drawings(self.drawings)
            self.redraw()

    def ctrl_z_undo(self):
        if not self._creation_history or not self.app.current_map_eng:
            return
        palette = getattr(self.app, 'drawing_palette', None)
        if palette:
            palette.exit_edit_mode()
        idx = self._creation_history.pop()
        map_id = self.app.current_map_eng
        if map_id in self.drawings and 0 <= idx < len(self.drawings[map_id]):
            del self.drawings[map_id][idx]
            self.data_mgr.save_drawings(self.drawings)
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
        obj["scale"] = new_scale
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if obj.get("type") == "marker" and len(obj.get("coords", [])) >= 4:
            coords = obj["coords"]
            mx, my = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
            dx = coords[2] - mx
            dy = coords[3] - my
            coords[2] = mx + dx * (new_scale / scale)
            coords[3] = my + dy * (new_scale / scale)
        self.data_mgr.save_drawings(self.drawings)
        self.redraw()

    def on_press(self, event):
        if not self.app.current_map_eng or self.app.mode != "edit": return

        palette = getattr(self.app, 'drawing_palette', None)
        palette_visible = palette and palette.state() != 'withdrawn'

        if palette_visible and not self.active_tool:
            idx, _ = self._find_object_index_at(event.x, event.y)
            if idx >= 0:
                self._edit_object_at(idx)
                return
            elif palette.is_in_edit_mode():
                palette.exit_edit_mode()
                return

        if not self.active_tool:
            return
        
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

            special_kind = None
            special_dist = float('inf')

            if obj.get("type") == "marker" and obj.get("text"):
                tx, ty = self._get_marker_text_pos(obj, cw, ch)
                if tx is not None:
                    d = math.hypot((tx / cw) - click_px, (ty / ch) - click_py)
                    if d < special_dist:
                        special_dist = d
                        special_kind = "marker_text"

            if obj.get("type") == "marker" and obj.get("classes"):
                icon_x, icon_y = self._get_marker_class_anchor(obj, cw, ch)
                if icon_x is not None:
                    d = math.hypot((icon_x / cw) - click_px, (icon_y / ch) - click_py)
                    if d < special_dist:
                        special_dist = d
                        special_kind = "class_icons"

            if obj.get("type") == "marker" and len(coords) >= 4:
                d = math.hypot(coords[2] - click_px, coords[3] - click_py)
                if d < special_dist:
                    special_dist = d
                    special_kind = "marker_tip"

                general_dist = min(
                    math.hypot(coords[0] - click_px, coords[1] - click_py),
                    math.hypot(coords[2] - click_px, coords[3] - click_py),
                    self._distance_to_segment(click_px, click_py, coords[0], coords[1], coords[2], coords[3]),
                )

                if special_kind is not None and special_dist < threshold_norm:
                    obj_best_kind = special_kind
                    obj_best_dist = special_dist
                else:
                    obj_best_kind = "object"
                    obj_best_dist = general_dist

            elif obj.get("type") == "text" and len(coords) >= 2:
                tx_norm, ty_norm = coords[0], coords[1]
                obj_best_dist = math.hypot(tx_norm - click_px, ty_norm - click_py)
                obj_best_kind = "object"
                poi = obj.get("poi", [])
                txt = obj.get("text", "")
                if poi:
                    d = math.hypot(tx_norm - click_px, ty_norm - 24/ch - click_py)
                    if d < obj_best_dist:
                        obj_best_dist = d
                if txt:
                    ofs = 15/ch if poi else 0
                    d = math.hypot(tx_norm - click_px, ty_norm + ofs - click_py)
                    if d < obj_best_dist:
                        obj_best_dist = d
            else:
                continue

            if obj_best_dist < min_dist:
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
        active_classes = [k for k, v in self.app.selected_classes.items() if v.get()]
        ordered_classes = [cls for cls in ("ЛТ", "СТ", "ТТ", "ПТ", "САУ")
                           if cls in class_list and cls in active_classes]
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
        
        if self.active_tool == "marker" and self.start_x == event.x and self.start_y == event.y:
            self.canvas.delete("temp_draw")
            self.temp_item = None
            palette = getattr(self.app, 'drawing_palette', None)
            if palette:
                palette._deactivate_tool()
            self.active_tool = None
            return
        
        px1, py1 = self.start_x / cw, self.start_y / ch
        px2, py2 = event.x / cw, event.y / ch

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

        palette = getattr(self.app, 'drawing_palette', None)
        if not palette:
            self.canvas.delete("temp_draw")
            self.temp_item = None
            return

        needs_show = palette.state() == 'withdrawn'
        palette.exit_edit_mode()
        palette.apply_to_new_object(new_obj, cw, ch)
        self.default_color = new_obj["color"]
        self._creation_history.append(len(self.drawings[map_id]) - 1)
        self.data_mgr.save_drawings(self.drawings)
        self.redraw()
        self.canvas.delete("temp_draw")
        self.temp_item = None
        palette._deactivate_tool()
        if needs_show:
            palette.show()
            if hasattr(self.app, 'draw_btn'):
                self.app.draw_btn.config(bg="#ffaa00", fg="black")
        self.active_tool = None
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
        label = self.app.t('ui', 'marker_type') if obj["type"] == "marker" else self.app.t('ui', 'text_type')
        self.app.status_label.config(text=self.app.t('ui', 'editing_label').format(label=label), fg="#ffff00")
        palette.load_object(obj)
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
        del objects[idx]
        self._creation_history = [i - 1 if i > idx else i for i in self._creation_history if i != idx]
        self._editing_idx = -1
        if hasattr(self.app, 'status_label'):
            self.app.status_label.config(text="")
        palette = getattr(self.app, 'drawing_palette', None)
        if palette:
            palette._edit_obj = None
        self.data_mgr.save_drawings(self.drawings)
        self.redraw()

    def _confirm_delete(self, label):
        dlg = tk.Toplevel(self.app.root)
        dlg.title(self.app.t('ui', 'confirm_title'))
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        dlg.minsize(300, 120)
        dlg.attributes("-topmost", True)
        dlg.grab_set()

        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - 150
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - 60
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text=self.app.t('ui', 'confirm_delete_msg').format(label=label), font=("Arial", 10),
                 bg="#2a2a2a", fg="#cccccc").pack(pady=(20, 15))

        bf = tk.Frame(dlg, bg="#2a2a2a")
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
        label = self.app.t('ui', 'marker_type') if obj["type"] == "marker" else self.app.t('ui', 'text_type')
        ok = self._confirm_delete(label)
        if ok:
            del objects[idx]
            self._creation_history = [i - 1 if i > idx else i for i in self._creation_history if i != idx]
            if self._editing_idx == idx:
                self._editing_idx = -1
                palette = getattr(self.app, 'drawing_palette', None)
                if palette:
                    palette.exit_edit_mode()
            elif self._editing_idx > idx:
                self._editing_idx -= 1
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
        if not self.app.current_map_eng: return
        map_id = self.app.current_map_eng
        
        if cw is None or ch is None:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: return

        self.canvas.delete("painter_obj")
        if map_id not in self.drawings: return
        sc = min(cw, ch) / 800.0
        
        for obj in self.drawings[map_id]:
            if not self.is_visible(obj): continue

            obj_sc = obj.get("scale", 1.0)
            sc_eff = sc * obj_sc
            r12 = max(3, int(12 * sc_eff))
            r4 = max(2, int(4 * sc_eff))
            lw = max(1, int(3 * sc_eff))
            mt_sz = max(6, int(9 * sc_eff))
            poi_base = max(12, int(48 * sc_eff))
            tt_sz = max(6, int(10 * sc_eff))
            
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
                            self.canvas.create_text(cx, y-poi_oy, text=chr(0xF18C),
                                                    font=("FontAwesome", it["sz"]), fill=c,
                                                    tags="painter_obj")
                        else:
                            self.canvas.create_text(cx, y-poi_oy, text=chr(it["code"]), font=("XVMSymbol", it["sz"]), fill="black", tags=("painter_obj", "xvm_bg"))
                            self.canvas.create_text(cx, y-poi_oy, text=chr(it["code"]), font=("XVMSymbol", it["sz"]-max(2, int(4*sc))), fill=c, tags=("painter_obj", "xvm_fg"))
                        curr_x += it["w"]
                
                if obj.get("text"):
                    ty = y + int(15 * sc) if poi_data else y
                    self.canvas.create_text(x, ty, text=obj["text"], fill=c, font=("Arial", tt_sz, "bold"), tags="painter_obj")
