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
            self.drawings[map_id] = self._strip_duplicates(self.drawings[map_id])
        
        self.active_tool = None
        self.default_color = "#ffaa00"
        
        self.start_x = 0
        self.start_y = 0
        self.temp_item = None
        self.move_drag = None
        self.move_drag_active = False
        self._editing_idx = -1
        self._creation_history = []
        self._move_history = []
        self._deletion_history = []

        self._group_schemes = {}  # {drawing_id: {map_id, elements, group_id, updated_at, ...}}
        self._scheme_downloaded_at = {}  # {drawing_id: "2026-06-29 15:30:00"}
        self._hidden_download_schemes = set()  # {scheme_id} — схеми приховані в Download діалозі
        self._thickness = int(self.app.settings.get("draw_thickness", 3))
        self._select_all = False

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

    def _is_duplicate(self, obj, others):
        for existing in others:
            if obj["type"] != existing.get("type"):
                continue
            if obj["color"] != existing.get("color"):
                continue
            if not self._coords_match(obj["coords"], existing.get("coords", [])):
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
        for k in list(self.drawings.keys()):
            self.drawings[k] = self._strip_duplicates(self.drawings[k])
        self.data_mgr.save_drawings(self.drawings)

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
            self.redraw()

    def toggle_select_all(self):
        self._select_all = not self._select_all
        if self._select_all:
            palette = getattr(self.app, 'drawing_palette', None)
            if palette and palette.is_in_edit_mode():
                palette.exit_edit_mode()
        self.redraw()

    def select_all_active(self):
        return self._select_all

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
        ]:
            target_canvas.bind(ev, cb, add="+")

    def on_escape_deselect(self, event=None):
        palette = getattr(self.app, 'drawing_palette', None)
        if palette:
            palette.exit_edit_mode()
    
    def set_tool(self, tool):
        self.active_tool = tool
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
            self.drawings[self.app.current_map_eng] = []
            self._creation_history.clear()
            self._editing_idx = -1
            palette = getattr(self.app, 'drawing_palette', None)
            if palette:
                palette.exit_edit_mode()
            self.save_drawings()
            self.redraw()

    def ctrl_z_undo(self):
        if not self.app.current_map_eng:
            return
        palette = getattr(self.app, 'drawing_palette', None)
        if palette:
            palette.exit_edit_mode()
        map_id = self.app.current_map_eng
        if self._move_history:
            idx, original = self._move_history.pop()
            if map_id in self.drawings and 0 <= idx < len(self.drawings[map_id]):
                obj = self.drawings[map_id][idx]
                if original["coords"]:
                    obj["coords"] = original["coords"]
                if original["class_icon_coords"]:
                    obj["class_icon_coords"] = original["class_icon_coords"]
                if original["text_coords"]:
                    obj["text_coords"] = original["text_coords"]
                self.save_drawings()
                self.redraw()
            return
        if self._deletion_history:
            d_map_id, d_idx, d_obj = self._deletion_history.pop()
            if d_map_id in self.drawings:
                self.drawings[d_map_id].insert(d_idx, d_obj)
            self.save_drawings()
            self.redraw()
            return
        if not self._creation_history:
            return
        idx = self._creation_history.pop()
        if map_id in self.drawings and 0 <= idx < len(self.drawings[map_id]):
            del self.drawings[map_id][idx]
            self.save_drawings()
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
        self.redraw()

    def on_press(self, event):
        if not self.app.current_map_eng or self.app.mode != "edit": return
        if event.state & 0x0004:
            return
        if self._select_all:
            palette = getattr(self.app, 'drawing_palette', None)
            self._select_all = False
            if palette:
                palette._update_select_all_btn()
            self.redraw()
            return

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
        
        if self.active_tool in ("marker", "arrow"):
            map_id = self.app.current_map_eng
            if map_id in self.drawings:
                min_dist = 15 
                snap_x, snap_y = self.start_x, self.start_y
                for obj in self.drawings[map_id]:
                    if obj["type"] == self.active_tool and self.is_visible(obj):
                        coords = obj["coords"]
                        if len(coords) >= 4:
                            ox, oy = coords[0]*cw, coords[1]*ch
                            dist = math.hypot(ox - event.x, oy - event.y)
                            if dist < min_dist:
                                min_dist = dist
                                snap_x, snap_y = ox, oy
                self.start_x = snap_x
                self.start_y = snap_y

            self.temp_item = self.canvas.create_line(self.start_x, self.start_y, event.x, event.y, arrow=tk.LAST, fill=self.default_color, width=self._thickness, dash=(5, 5), tags="temp_draw")
            if self.active_tool == "marker":
                self.canvas.create_oval(self.start_x-12, self.start_y-12, self.start_x+12, self.start_y+12, outline=self.default_color, width=max(1, self._thickness-1), tags="temp_draw")
                self.canvas.create_oval(self.start_x-4, self.start_y-4, self.start_x+4, self.start_y+4, fill="white", outline="white", tags="temp_draw")
        elif self.active_tool == "brush":
            self._brush_points = [(event.x, event.y)]
            self.temp_item = self.canvas.create_line(event.x, event.y, event.x, event.y, fill=self.default_color, width=self._thickness, dash=(5, 5), tags="temp_draw")
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

        maker_types = ("marker", "arrow", "brush")

        for i, obj in enumerate(objects):
            if not self.is_visible(obj):
                continue
            coords = obj.get("coords", [])

            special_kind = None
            special_dist = float('inf')
            obj_best_dist = float('inf')
            obj_best_kind = "object"

            if obj.get("type") in maker_types and obj.get("text"):
                tx, ty = self._get_marker_text_pos(obj, cw, ch)
                if tx is not None:
                    d = math.hypot((tx / cw) - click_px, (ty / ch) - click_py)
                    if d < special_dist:
                        special_dist = d
                        special_kind = "marker_text"

            if obj.get("type") in ("marker", "arrow") and len(coords) >= 4:
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

            elif obj.get("type") == "brush" and len(coords) >= 4:
                poly_end_d = min(
                    math.hypot(coords[0] - click_px, coords[1] - click_py),
                    math.hypot(coords[-2] - click_px, coords[-1] - click_py),
                )
                brush_seg_dist = float('inf')
                for j in range(0, len(coords)-2, 2):
                    d = self._distance_to_segment(click_px, click_py, coords[j], coords[j+1], coords[j+2], coords[j+3])
                    brush_seg_dist = min(brush_seg_dist, d)
                general_dist = min(poly_end_d, brush_seg_dist)

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
        idx = self.move_drag["index"]
        original = {
            "coords": self.move_drag.get("original_coords", []),
            "class_icon_coords": self.move_drag.get("original_class_icon_coords", []),
            "text_coords": self.move_drag.get("original_text_coords", []),
        }
        self._move_history.append((idx, original))
        self.move_drag = None
        self.save_drawings()
        self.app.root.after(50, self._edit_object_at, idx)
        return "break"

    def on_drag(self, event):
        if not self.temp_item or self.app.mode != "edit": return
        if self.active_tool in ("marker", "arrow"):
            self.canvas.coords(self.temp_item, self.start_x, self.start_y, event.x, event.y)
        elif self.active_tool == "brush":
            last_x, last_y = self._brush_points[-1]
            if math.hypot(event.x - last_x, event.y - last_y) >= 10:
                self._brush_points.append((event.x, event.y))
                flat = [coord for p in self._brush_points for coord in p]
                self.canvas.coords(self.temp_item, *flat)
        elif self.active_tool == "text":
            self.canvas.coords(self.temp_item, event.x, event.y)
            
    def on_release(self, event):
        if not self.active_tool or not self.app.current_map_eng or self.app.mode != "edit": return
        if not self.temp_item: return
            
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: return
        
        if self.active_tool in ("marker", "arrow", "brush") and self.start_x == event.x and self.start_y == event.y:
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
            "thickness": self._thickness,
            "_source": getattr(self.app, "active_group_id", "public") or "public",
        }
        if self.active_tool == "brush":
            norm_points = [(x / cw, y / ch) for x, y in self._brush_points]
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
        self._creation_history.append(len(self.drawings[map_id]) - 1)
        self.save_drawings()
        self.redraw()
        self.canvas.delete("temp_draw")
        self.temp_item = None
        self._edit_object_at(len(self.drawings[map_id]) - 1)
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
        self._deletion_history.append((map_id, idx, copy.deepcopy(obj)))
        self._creation_history = [i - 1 if i > idx else i for i in self._creation_history if i != idx]
        del objects[idx]
        self._editing_idx = -1
        self.save_drawings()
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
        for idx in range(len(objects) - 1, -1, -1):
            self._deletion_history.append((map_id, idx, copy.deepcopy(objects[idx])))
        self.drawings[map_id] = []
        self._creation_history.clear()
        self._editing_idx = -1
        self._select_all = False
        if palette:
            palette._update_select_all_btn()
        self.save_drawings()
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
            self._deletion_history.append((map_id, idx, copy.deepcopy(obj)))
            del objects[idx]
            self._creation_history = [i - 1 if i > idx else i for i in self._creation_history if i != idx]
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

    def _render_elements(self, canvas, elements, cw, ch, offset_x=0, offset_y=0, img_w=None, img_h=None, screen_scale=1.0):
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
            coords = obj["coords"]

            if obj["type"] == "marker":
                if len(coords) < 4: continue
                x1, y1 = coords[0]*cw + offset_x, coords[1]*ch + offset_y
                x2, y2 = coords[2]*cw + offset_x, coords[3]*ch + offset_y
                canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill=c, width=lw, dash=(5, 5), tags="painter_obj")

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
                canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill=c, width=lw, dash=(5, 5), tags="painter_obj")

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
                arr = tk.NONE
                if obj.get("arrow_start") and obj.get("arrow_end"):
                    arr = tk.BOTH
                elif obj.get("arrow_start"):
                    arr = tk.FIRST
                elif obj.get("arrow_end"):
                    arr = tk.LAST
                canvas.create_line(*flat_px, arrow=arr, fill=c, width=lw, dash=(5, 5), tags="painter_obj")

                if obj.get("text"):
                    mx, my = self._get_marker_text_pos(obj, cw, ch, sc)
                    if mx is not None:
                        if offset_x or offset_y:
                            mx += offset_x
                            my += offset_y
                        canvas.create_text(mx, my, text=obj["text"], fill=c, font=("Arial", mt_sz, "bold"), tags="painter_obj")

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
                    poi_oy = int(24 * sc)
                    for it in items:
                        cx = curr_x + it["w"] / 2
                        if it.get("tree"):
                            canvas.create_text(cx, y-poi_oy, text=chr(0xF18C),
                                                font=("FontAwesome", it["sz"]), fill=c,
                                                tags="painter_obj")
                        else:
                            canvas.create_text(cx, y-poi_oy, text=chr(it["code"]), font=("XVMSymbol", it["sz"]), fill="black", tags=("painter_obj", "xvm_bg"))
                            canvas.create_text(cx, y-poi_oy, text=chr(it["code"]), font=("XVMSymbol", it["sz"]-max(2, int(4*sc))), fill=c, tags=("painter_obj", "xvm_fg"))
                        curr_x += it["w"]

                if obj.get("text"):
                    ty = y + int(15 * sc) if poi_data else y
                    canvas.create_text(x, ty, text=obj["text"], fill=c, font=("Arial", tt_sz, "bold"), tags="painter_obj")

    def redraw(self, cw=None, ch=None):
        if not self.app.current_map_eng: return
        map_id = self.app.current_map_eng

        if cw is None or ch is None:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
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
        self._render_elements(self.canvas, all_visible, cw, ch, screen_scale=screen_scale)

        if self._select_all:
            sel_sc = min(cw, ch) / 800.0
            margin = max(4, int(8 * sel_sc))
            for obj in visible:
                c = obj["coords"]
                if obj["type"] in ("marker", "arrow"):
                    if len(c) < 4: continue
                    x1 = c[0]*cw; y1 = c[1]*ch; x2 = c[2]*cw; y2 = c[3]*ch
                    l = min(x1, x2) - margin; r = max(x1, x2) + margin
                    t = min(y1, y2) - margin; b = max(y1, y2) + margin
                elif obj["type"] == "brush":
                    if len(c) < 4: continue
                    xs = [c[i]*cw for i in range(0, len(c), 2)]
                    ys = [c[i+1]*ch for i in range(0, len(c), 2)]
                    l = min(xs) - margin; r = max(xs) + margin
                    t = min(ys) - margin; b = max(ys) + margin
                elif obj["type"] == "text":
                    if len(c) < 2: continue
                    l = c[0]*cw - 30*margin; r = c[0]*cw + 30*margin
                    t = c[1]*ch - 30*margin; b = c[1]*ch + 30*margin
                else:
                    continue
                self.canvas.create_rectangle(l, t, r, b, outline="yellow", dash=(4, 4), width=max(1, int(2*sel_sc)), tags="painter_obj")

        self.app._lift_overlay()
