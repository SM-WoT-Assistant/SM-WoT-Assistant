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
            paths.append(os.path.join("extracted_maps", f"{self.app.current_map_eng}.png"))
        else:
            safe_folder = self.app.current_map_eng.replace('?', '').replace(':', '').replace('|', '').replace(' - ', '_').replace(' ', '_')
            paths = [os.path.join(config.MAPS_DIR, safe_folder, "map.webp"), 
                     os.path.join(config.MAPS_DIR, f"{self.app.current_map_eng}.jpg"),
                     os.path.join(config.MAPS_DIR, f"{self.app.current_map_eng}.png")]
                     
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

    def draw_arena_bases(self, cw, ch):
        app = self.app
        if not app.map_data or app.current_map_eng not in app.map_data: return
        data = app.map_data[app.current_map_eng]
        bbox = data.get("boundingBox", {})
        bl = bbox.get("bottomLeft", [-500.0, -500.0])
        ur = bbox.get("upperRight", [500.0, 500.0])
        
        if not isinstance(bl, list) or len(bl) < 2: bl = [-500.0, -500.0]
        if not isinstance(ur, list) or len(ur) < 2: ur = [500.0, 500.0]
        
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
            "Assault": "assault",
            "Onslaught": "comp7"
        }
        internal_mode = mode_mapping.get(ui_mode, "ctf")
        
        gameplay_types = data.get("gameplayTypes", {})
        if internal_mode not in gameplay_types:
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
            app.canvas.create_text(cx, cy, text=chr(0x73), font=("XVMSymbol", base_font), fill="#cccccc", angle=angle)
                
        spawns = mode_data.get("spawns", [])
        for coords in spawns:
            if len(coords) >= 2:
                cx, cy = to_map(coords[0], coords[1])
                app.canvas.create_text(cx, cy, text=chr(0x44), font=("XVMSymbol", spawn_font), fill="#cccccc")

    def draw_grid(self, cw, ch):
        app = self.app
        if not app.map_data or app.current_map_eng not in app.map_data: return
        data = app.map_data[app.current_map_eng]
        bbox = data.get("boundingBox", {})
        bl = bbox.get("bottomLeft", [-500.0, -500.0])
        ur = bbox.get("upperRight", [500.0, 500.0])
        if not isinstance(bl, list) or len(bl) < 2: bl = [-500.0, -500.0]
        if not isinstance(ur, list) or len(ur) < 2: ur = [500.0, 500.0]
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
        app.canvas.create_rectangle(0, map_y - border, cw, map_y, fill=fc, outline="")
        app.canvas.create_rectangle(0, map_y + map_h, cw, map_y + map_h + border, fill=fc, outline="")
        app.canvas.create_rectangle(map_x - border, map_y, map_x, map_y + map_h, fill=fc, outline="")
        app.canvas.create_rectangle(map_x + map_w, map_y, map_x + map_w + border, map_y + map_h, fill=fc, outline="")

        cols, rows = self.grid_cols, self.grid_rows
        cell_w = width_game / cols
        cell_h = height_game / rows
        gc = "#777777"

        for col in range(cols + 1):
            gx = minX + cell_w * col
            px, _ = to_map(gx, 0)
            if map_x <= px <= map_x + map_w:
                app.canvas.create_line(px, map_y, px, map_y + map_h, fill=gc, width=1)

        for row in range(rows + 1):
            gz = maxZ - cell_h * row
            _, py = to_map(0, gz)
            if map_y <= py <= map_y + map_h:
                app.canvas.create_line(map_x, py, map_x + map_w, py, fill=gc, width=1)

        row_letters = [chr(ord('A') + i) for i in range(rows)]

        for col in range(cols):
            gx = minX + cell_w * (col + 0.5)
            px, _ = to_map(gx, 0)
            app.canvas.create_text(px, map_y - b2, text=str((col + 1) % 10),
                fill=gc, font=("Arial", 9), anchor="center")
            app.canvas.create_text(px, map_y + map_h + b2, text=str((col + 1) % 10),
                fill=gc, font=("Arial", 9), anchor="center")

        for row in range(rows):
            gz = maxZ - cell_h * (row + 0.5)
            _, py = to_map(0, gz)
            app.canvas.create_text(map_x - b2, py, text=row_letters[row],
                fill=gc, font=("Arial", 9), anchor="center")
            app.canvas.create_text(map_x + map_w + b2, py, text=row_letters[row],
                fill=gc, font=("Arial", 9), anchor="center")

    def show_main_splash(self):
        app = self.app
        app.canvas.delete("all")
        app.root.update_idletasks()
        cw, ch = app.canvas.winfo_width(), app.canvas.winfo_height()
        if cw < 10:
            extra = app.get_edit_extra_height() if app.mode == "edit" else 18
            cw, ch = app.w, app.h - extra
        app.canvas.create_rectangle(0, 0, cw, ch, fill="black")
        
        map_drawn = False
        if app.current_map_eng:
            use_border = app.btn_mode_maps_2.cget("bg") == "#ff4500"
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
                        app.canvas.create_image(map_x + size // 2, map_y + size // 2, image=app.current_tk_map)
                    else:
                        app.canvas.create_image(cw // 2, ch // 2, image=app.current_tk_map)
                else:
                    app.canvas.create_image(cw // 2, ch // 2, image=app.current_tk_map)
                map_drawn = True
                app.status_label.config(text=f"КАРТА: {app.translate_map_name(app.current_map_eng)}", fg="lime")
                
                if app.btn_mode_maps_2.cget("bg") == "#ff4500":
                    self.draw_grid(cw, ch)
                    self.draw_arena_bases(cw, ch)
            else:
                app.canvas.create_text(cw//2, ch//2, text=app.t('ui', 'map_not_found_msg').format(app.t('maps', app.current_map_eng)), fill="red", font=("Arial", 10))
                map_drawn = True 
                app.status_label.config(text=app.t('ui', 'map_not_found'), fg="red")
                
        if not map_drawn:
            if app.mode == "edit":
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
                app.canvas.create_text(cw//2, ch - 20, text=f"SETUP & MAPS WoT Assistant {version}", fill="#ff4500", font=("Arial", 9, "bold"))
                app.canvas.create_text(cw//2, ch - 55, text=app.t('ui', 'editor_help'), fill="gray", font=("Arial", 9))
                app.canvas.create_text(cw//2, ch - 80, text=app.t('ui', 'h2'), fill="white", font=("Arial", 11, "bold"))
                app.canvas.create_text(cw//2, ch - 105, text=app.t('ui', 'h1'), fill="white", font=("Arial", 11, "bold"))
                if app.logo_image_object:
                    try:
                        mw, mh = int(cw * 0.55), ch - 110
                        ratio = app.logo_image_object.height / app.logo_image_object.width
                        lw, lh = mw, int(mw * ratio)
                        if lh > mh: lh = mh; lw = int(lh / ratio)
                        app.logo_img = ImageTk.PhotoImage(app.logo_image_object.resize((lw, lh), Image.Resampling.LANCZOS))
                        app.canvas.create_image(cw//2, 10 + mh//2, image=app.logo_img)
                    except: pass
            else: 
                app.canvas.create_text(cw//2, ch//2, text=f"{app.t('ui', 'battle_mode')}\n{app.t('ui', 'press_e_to_exit')}", fill="#555", font=("Arial", 12, "bold"), justify="center")
            
        if hasattr(app, 'painter'):
            app.painter.redraw(cw, ch)
