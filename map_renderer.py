import os
import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance
import config

class MapRenderer:
    def __init__(self, app):
        self.app = app
        self.grid_cols = 10
        self.grid_rows = 10
        self.grid_border = 20

    def load_and_resize_map(self, cw, ch, use_border=False):
        if not self.app.current_map_eng: return None
        
        paths = []
        if self.app.btn_mode_maps_2.cget("bg") == "#ff4500":
            paths.append(os.path.join(config.BASE_DIR, "extracted_maps", f"{self.app.current_map_eng}.png"))
        else:
            map_nice = config.MAP_NAMES_EN.get(self.app.current_map_eng, self.app.current_map_eng)
            eng_name = self.app.map_mgr._resolve_tactic_folder(map_nice)
            safe_folder = eng_name.replace('?', '').replace(':', '').replace('|', '').replace("'", "").replace(' - ', '_').replace(' ', '_')
            paths = [os.path.join(config.MAPS_DIR, safe_folder, "map.webp"), 
                     os.path.join(config.MAPS_DIR, f"{eng_name}.jpg"),
                     os.path.join(config.MAPS_DIR, f"{eng_name}.png")]
                     
        for p in paths:
            if os.path.exists(p):
                try:
                    img = Image.open(p).convert("RGB")
                    border_raw = self.grid_border if use_border else 0
                    if use_border and cw > 10 and ch > 10:
                        border_raw = max(5, int(border_raw * min(cw, ch) / 800))
                    s = max(1, min(cw, ch) - 2 * border_raw)
                    img = img.resize((s, s), Image.Resampling.LANCZOS)
                    
                    if hasattr(self.app, 'contrast') and self.app.contrast != 1.0:
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(self.app.contrast)
                    
                    return ImageTk.PhotoImage(img)
                except: pass
        return None

    def draw_frame(self, cw, ch):
        sc = min(cw, ch) / 800.0
        border = max(5, int(self.grid_border * sc))
        size = min(cw, ch) - 2 * border
        if size <= 10: return
        map_x = border
        map_y = border
        if cw > ch:
            map_x = border + (cw - 2 * border - size) / 2
        fc = "#333333"
        self.app.canvas.create_rectangle(0, map_y - border, cw, map_y, fill=fc, outline="", tags=("map", "frame"))
        self.app.canvas.create_rectangle(0, map_y + size, cw, map_y + size + border, fill=fc, outline="", tags=("map", "frame"))
        self.app.canvas.create_rectangle(map_x - border, map_y, map_x, map_y + size, fill=fc, outline="", tags=("map", "frame"))
        self.app.canvas.create_rectangle(map_x + size, map_y, map_x + size + border, map_y + size, fill=fc, outline="", tags=("map", "frame"))

    def _report_fallback_async(self, context, text):
        try:
            import threading
            import firebase_reporter
            threading.Thread(target=firebase_reporter.report_fallback, args=(
                "map_renderer", context, text, "warning"
            ), daemon=True).start()
        except Exception:
            pass

    def draw_arena_bases(self, cw, ch):
        app = self.app
        if not app.map_data or app.current_map_eng not in app.map_data: return
        data = app.map_data[app.current_map_eng]
        bbox = data.get("boundingBox", {})
        bl = bbox.get("bottomLeft", [-500.0, -500.0])
        ur = bbox.get("upperRight", [500.0, 500.0])
        
        if not isinstance(bl, list) or len(bl) < 2: bl = [-500.0, -500.0]
        if not isinstance(ur, list) or len(ur) < 2: ur = [500.0, 500.0]
        if bbox and ("bottomLeft" not in bbox or "upperRight" not in bbox):
            self._report_fallback_async("boundingBox",
                f"Missing boundingBox in map_data for {app.current_map_eng}")
        
        minX, minZ = bl[0], bl[1]
        maxX, maxZ = ur[0], ur[1]
        width_game = maxX - minX
        height_game = maxZ - minZ

        if width_game <= 0 or height_game <= 0: return

        border = self.grid_border
        size = min(cw, ch) - 2 * border
        if size <= 10: return
        map_x = border
        map_y = border
        if cw > ch:
            map_x = border + (cw - 2 * border - size) / 2
        map_w = size
        map_h = size

        def to_map(gx, gz):
            px = map_x + (gx - minX) / width_game * map_w
            py = map_y + (maxZ - gz) / height_game * map_h
            return px, py

        ui_mode = app.selected_battle_mode.get()
        mode_mapping = {
            "Standard": "ctf",
            "Encounter": "domination",
            "Storm": "assault",
            "Onslaught": "comp7",
            "OnslaughtLight": "comp7",
        }
        internal_mode = mode_mapping.get(ui_mode, "ctf")
        
        gameplay_types = data.get("gameplayTypes", {})
        if internal_mode not in gameplay_types:
            if internal_mode == "assault" and "assault2" in gameplay_types:
                internal_mode = "assault2"
            else:
                return

        mode_data = gameplay_types[internal_mode]

        bases = mode_data.get("bases", [])
        processed_bases = []
        for coords in bases:
            if len(coords) >= 2:
                processed_bases.append(to_map(coords[0], coords[1]))
        
        if not processed_bases: return
        
        scale = min(cw, ch) / 800.0
        base_font = max(10, int(60 * scale))
        spawn_font = max(8, int(30 * scale))
        rightmost_x = max(cx for cx, cy in processed_bases) if len(processed_bases) > 1 else None
        
        for cx, cy in processed_bases:
            angle = 180 if (rightmost_x is not None and cx == rightmost_x) else 0
            app.canvas.create_text(cx, cy, text=chr(0x73), font=("XVMSymbol", base_font), fill="#cccccc", angle=angle, tags="map")
                
        spawns = mode_data.get("spawns", [])
        for coords in spawns:
            if len(coords) >= 2:
                cx, cy = to_map(coords[0], coords[1])
                app.canvas.create_text(cx, cy, text=chr(0x44), font=("XVMSymbol", spawn_font), fill="#cccccc", tags="map")

    def draw_grid(self, cw, ch):
        app = self.app
        if not app.map_data or app.current_map_eng not in app.map_data: return
        data = app.map_data[app.current_map_eng]
        bbox = data.get("boundingBox", {})
        bl = bbox.get("bottomLeft", [-500.0, -500.0])
        ur = bbox.get("upperRight", [500.0, 500.0])
        if not isinstance(bl, list) or len(bl) < 2: bl = [-500.0, -500.0]
        if not isinstance(ur, list) or len(ur) < 2: ur = [500.0, 500.0]
        if bbox and ("bottomLeft" not in bbox or "upperRight" not in bbox):
            self._report_fallback_async("boundingBox",
                f"Missing boundingBox in draw_grid for {app.current_map_eng}")
        minX, minZ = bl[0], bl[1]
        maxX, maxZ = ur[0], ur[1]
        width_game = maxX - minX
        height_game = maxZ - minZ
        if width_game <= 0 or height_game <= 0: return

        sc = min(cw, ch) / 800.0
        border = max(5, int(self.grid_border * sc))
        b2 = border // 2
        size = min(cw, ch) - 2 * border
        if size <= 10: return
        map_x = border
        map_y = border
        if cw > ch:
            map_x = border + (cw - 2 * border - size) / 2
        map_w = size
        map_h = size

        def to_map(gx, gz):
            px = map_x + (gx - minX) / width_game * map_w
            py = map_y + (maxZ - gz) / height_game * map_h
            return px, py

        fc = "#333333"
        app.canvas.create_rectangle(0, map_y - border, cw, map_y, fill=fc, outline="", tags="map")
        app.canvas.create_rectangle(0, map_y + map_h, cw, map_y + map_h + border, fill=fc, outline="", tags="map")
        app.canvas.create_rectangle(map_x - border, map_y, map_x, map_y + map_h, fill=fc, outline="", tags="map")
        app.canvas.create_rectangle(map_x + map_w, map_y, map_x + map_w + border, map_y + map_h, fill=fc, outline="", tags="map")

        cols, rows = self.grid_cols, self.grid_rows
        cell_w = width_game / cols
        cell_h = height_game / rows
        gc = "#777777"

        for col in range(cols + 1):
            gx = minX + cell_w * col
            px, _ = to_map(gx, 0)
            if map_x <= px <= map_x + map_w:
                app.canvas.create_line(px, map_y, px, map_y + map_h, fill=gc, width=1, tags="map")

        for row in range(rows + 1):
            gz = maxZ - cell_h * row
            _, py = to_map(0, gz)
            if map_y <= py <= map_y + map_h:
                app.canvas.create_line(map_x, py, map_x + map_w, py, fill=gc, width=1, tags="map")

        row_letters = ['A','B','C','D','E','F','G','H','I','K']

        for col in range(cols):
            gx = minX + cell_w * (col + 0.5)
            px, _ = to_map(gx, 0)
            app.canvas.create_text(px, map_y - b2, text=str((col + 1) % 10),
                fill=gc, font=("Arial", 9), anchor="center", tags="map")
            app.canvas.create_text(px, map_y + map_h + b2, text=str((col + 1) % 10),
                fill=gc, font=("Arial", 9), anchor="center", tags="map")

        for row in range(rows):
            gz = maxZ - cell_h * (row + 0.5)
            _, py = to_map(0, gz)
            app.canvas.create_text(map_x - b2, py, text=row_letters[row],
                fill=gc, font=("Arial", 9), anchor="center", tags="map")
            app.canvas.create_text(map_x + map_w + b2, py, text=row_letters[row],
                fill=gc, font=("Arial", 9), anchor="center", tags="map")

    def show_main_splash(self, message=None):
        app = self.app
        app.canvas.delete("map")
        app.root.update_idletasks()
        cw, ch = app.canvas.winfo_width(), app.canvas.winfo_height()
        if cw < 10:
            extra = app.get_edit_extra_height() if app.mode == "edit" else 18
            cw, ch = app.w, app.h - extra
        app.canvas.create_rectangle(0, 0, cw, ch, fill="black", tags="map")
        
        map_drawn = False
        if app.current_map_eng:
            use_border = True
            app.current_tk_map = self.load_and_resize_map(cw, ch, use_border)
            if app.current_tk_map:
                if use_border:
                    sc = min(cw, ch) / 800.0
                    border = max(5, int(self.grid_border * sc))
                    size = min(cw, ch) - 2 * border
                    if size > 10:
                        map_x = border
                        map_y = border
                        if cw > ch:
                            map_x = border + (cw - 2 * border - size) / 2
                        app.canvas.create_image(map_x + size // 2, map_y + size // 2, image=app.current_tk_map, tags="map")
                    else:
                        app.canvas.create_image(cw // 2, ch // 2, image=app.current_tk_map, tags="map")
                else:
                    app.canvas.create_image(cw // 2, ch // 2, image=app.current_tk_map, tags="map")
                map_drawn = True
                
                self.draw_frame(cw, ch)
                if app.btn_mode_maps_2.cget("bg") == "#ff4500":
                    self.draw_grid(cw, ch)
                    self.draw_arena_bases(cw, ch)
            else:
                is_tactic = app.btn_mode_maps_1.cget("bg") == "#ff4500"
                if is_tactic:
                    msg = f"{app.t('ui', 'tactic_maps_source')} wotmapsbyyaya.com/maps\n{app.t('ui', 'tactic_no_map')}"
                    app.canvas.create_text(cw//2, ch//2, text=msg, fill="#888888", font=("Arial", 10), justify="center", tags="map")
                else:
                    msg = app.t('ui', 'map_not_found_msg').format(app.t('maps', app.current_map_eng))
                    app.canvas.create_text(cw//2, ch//2, text=msg, fill="red", font=("Arial", 10), tags="map")
                map_drawn = True 

                
        if not map_drawn:
            if message:
                app.canvas.create_text(cw//2, ch//2, text=message, fill="#888888", font=("Arial", 18), tags="map")
            elif app.mode == "edit":
                version = config.load_version()
                app.canvas.create_text(cw//2, ch - 20, text=f"SM WoT Assistant {version}", fill="#ff4500", font=("Arial", 9, "bold"), tags="map")
                line1 = f"LMB: {app.t('ui', 'help_ctrl_lmb')}"
                line2 = f"\u2195: {app.t('ui', 'help_ctrl_updown')} | \u2194: {app.t('ui', 'help_ctrl_leftright')}"
                line3 = f"Shift+\u2195: {app.t('ui', 'help_ctrlshift_updown')}"
                app.canvas.create_text(cw//2, ch - 90, text=line1, fill="#aaaaaa", font=("Arial", 9), tags="map")
                app.canvas.create_text(cw//2, ch - 70, text=line2, fill="#aaaaaa", font=("Arial", 9), tags="map")
                app.canvas.create_text(cw//2, ch - 50, text=line3, fill="#aaaaaa", font=("Arial", 9), tags="map")
                h2_frame = tk.Frame(app.canvas, bg="black")
                tk.Label(h2_frame, text=chr(0xF023), font=("FontAwesome", 11), bg="black", fg="white").pack(side="left")
                tk.Label(h2_frame, text=chr(0xF09C), font=("FontAwesome", 11), bg="black", fg="white").pack(side="left")
                tk.Label(h2_frame, text="  " + app.t('ui', 'h2'), font=("Arial", 11, "bold"), bg="black", fg="white").pack(side="left")
                app.canvas.create_window(cw//2, ch - 115, window=h2_frame, tags="map")
            if app.logo_image_object:
                    try:
                        mw, mh = int(cw * 0.55), ch - 110
                        ratio = app.logo_image_object.height / app.logo_image_object.width
                        lw, lh = mw, int(mw * ratio)
                        if lh > mh: lh = mh; lw = int(lh / ratio)
                        app.logo_img = ImageTk.PhotoImage(app.logo_image_object.resize((lw, lh), Image.Resampling.LANCZOS))
                        app.canvas.create_image(cw//2, 10 + mh//2, image=app.logo_img, tags="map")
                    except: pass
            else: 
                app.canvas.create_text(cw//2, ch//2, text=f"{app.t('ui', 'battle_mode')}\n{app.t('ui', 'press_e_to_exit')}", fill="#555", font=("Arial", 12, "bold"), justify="center", tags="map")
            app.canvas.create_text(cw//2, ch - 140, text=app.t('ui', 'h1'), fill="white", font=("Arial", 11, "bold"), tags="map")
            app.canvas.create_text(cw//2, ch - 250, text=app.t('ui', 'tactic_maps_source'),
                fill="#888888", font=("Arial", 12), tags="map")
            app.canvas.create_text(cw//2, ch - 232, text="wotmapsbyyaya.com/maps",
                fill="#888888", font=("Arial", 10), tags="map")
            app.canvas.create_text(cw//2, ch - 165, text=app.t('ui', 'borderless_warning'),
                fill="red", font=("Arial", 10), tags="map")
            
        if hasattr(app, 'painter'):
            app.painter.redraw(cw, ch)
