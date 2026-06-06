import tkinter as tk
from tkinter import colorchooser

FONT_AWE = "FontAwesome"

class DrawingPalette(tk.Toplevel):
    def __init__(self, root, painter, app):
        super().__init__(root)
        self.painter = painter
        self.app = app

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#222")
        self.resizable(False, False)

        self._edit_obj = None
        self._drag_data = {"x": 0, "y": 0}
        self._saved_pos = None

        self.current_color = "#ffaa00"

        self._active_tool_code = None

        self.mode_vars = {
            "Standard": tk.BooleanVar(value=False),
            "Encounter": tk.BooleanVar(value=False),
            "Assault": tk.BooleanVar(value=False),
            "Onslaught": tk.BooleanVar(value=False),
        }
        self.mode_labels = {
            "Standard": "\u0421\u0442\u0430\u043d\u0434\u0430\u0440\u0442",
            "Encounter": "\u0417\u0443\u0441\u0442\u0440\u0456\u0447",
            "Assault": "\u0428\u0442\u0443\u0440\u043c",
            "Onslaught": "\u041d\u0410\u0422\u0418\u0421\u041a",
        }

        self.class_vars = {
            "\u041b\u0422": tk.BooleanVar(value=False),
            "\u0421\u0422": tk.BooleanVar(value=False),
            "\u0422\u0422": tk.BooleanVar(value=False),
            "\u041f\u0422": tk.BooleanVar(value=False),
            "\u0421\u0410\u0423": tk.BooleanVar(value=False),
        }

        self.text_var = tk.StringVar(value="")
        self.text_var.trace("w", self._validate_text)
        self.text_var.trace("w", self._on_any_change)

        self._toolbar_buttons = {}
        self._build_ui()
        self._restore_position()

    def _build_ui(self):
        bg = "#222"
        cb_style = {"bg": bg, "fg": "white", "selectcolor": "#333", "activebackground": bg, "activeforeground": "white"}

        hdr = tk.Frame(self, bg="#2a2a2a", height=26)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="\u041c\u0430\u043b\u044e\u0432\u0430\u043d\u043d\u044f", bg="#2a2a2a", fg="white",
                 font=("Arial", 9, "bold")).pack(side="left", padx=8)
        tk.Button(hdr, text="\u2715", bg="#2a2a2a", fg="#aaa", bd=0,
                  font=("Arial", 8), command=self._close).pack(side="right", padx=4)

        hdr.bind("<Button-1>", self._drag_start)
        hdr.bind("<B1-Motion>", self._drag_move)
        hdr.bind("<ButtonRelease-1>", self._drag_stop)
        hdr.bind("<Enter>", lambda e: hdr.config(cursor="fleur"))

        tb = tk.Frame(self, bg="#1a1a1a")
        tb.pack(fill="x", padx=4, pady=(4, 2))

        all_tools = [
            ("marker", chr(0xF01B), FONT_AWE),
            (0x2B, chr(0x2B), "XVMSymbol"),
            (0x42, chr(0x42), "XVMSymbol"),
            (0x45, chr(0x45), "XVMSymbol"),
            (0x50, chr(0x50), "XVMSymbol"),
            (0x52, chr(0x52), "XVMSymbol"),
            (0x5C, chr(0x5C), "XVMSymbol"),
            (0x6F, chr(0x6F), "XVMSymbol"),
            (0x2C, chr(0x2C), "XVMSymbol"),
            ("tree", chr(0xF18C), FONT_AWE),
            (0x3A, chr(0x3A), "XVMSymbol"),
            (0x3B, chr(0x3B), "XVMSymbol"),
            (0x3F, chr(0x3F), "XVMSymbol"),
            (0x2E, chr(0x2E), "XVMSymbol"),
            (0x2D, chr(0x2D), "XVMSymbol"),
        ]

        mid = (len(all_tools) + 1) // 2
        rows = [all_tools[:mid], all_tools[mid:]]

        for row_items in rows:
            r = tk.Frame(tb, bg="#1a1a1a")
            r.pack(side="top", fill="x")
            for code, text, font_name in row_items:
                btn = tk.Button(r, text=text, font=(font_name, 16), bg="#333", fg="#aaa",
                                bd=0, width=2, command=lambda c=code: self._on_toolbar_click(c))
                btn.pack(side="left", padx=1)
                self._toolbar_buttons[code] = btn

        self._tb_marker = self._toolbar_buttons.get("marker")

        sep = tk.Frame(self, bg="#333", height=1)
        sep.pack(fill="x", padx=6, pady=3)

        tk.Label(self, text="\u0420\u0435\u0436\u0438\u043c \u0431\u043e\u044e:", font=("Arial", 8, "bold"),
                 bg=bg, fg="#aaa").pack(anchor="w", padx=8, pady=(2, 0))
        mf = tk.Frame(self, bg=bg)
        mf.pack(fill="x", padx=8)
        for k, v in self.mode_vars.items():
            cb = tk.Checkbutton(mf, text=self.mode_labels[k], variable=v, command=self._on_any_change,
                                **cb_style, font=("Arial", 8))
            cb.pack(side="left", padx=1)

        sep2 = tk.Frame(self, bg="#333", height=1)
        sep2.pack(fill="x", padx=6, pady=2)

        tk.Label(self, text="\u0422\u0435\u0445\u043d\u0456\u043a\u0430:", font=("Arial", 8, "bold"),
                 bg=bg, fg="#aaa").pack(anchor="w", padx=8, pady=(2, 0))
        cf = tk.Frame(self, bg=bg)
        cf.pack(fill="x", padx=8)
        for k, v in self.class_vars.items():
            cb = tk.Checkbutton(cf, text=k, variable=v, command=self._on_any_change,
                                **cb_style, font=("Arial", 8))
            cb.pack(side="left", padx=1)

        sep3 = tk.Frame(self, bg="#333", height=1)
        sep3.pack(fill="x", padx=6, pady=2)

        self._text_frame = tk.Frame(self, bg=bg)
        tk.Label(self._text_frame, text="\u0422\u0435\u043a\u0441\u0442:", font=("Arial", 8, "bold"),
                 bg=bg, fg="#aaa").pack(anchor="w")
        tef = tk.Frame(self._text_frame, bg=bg)
        tef.pack(fill="x")
        self._entry = tk.Entry(tef, textvariable=self.text_var, width=28, bg="#111", fg="white",
                                insertbackground="white", bd=1, relief="solid")
        self._entry.pack(side="left", pady=2)
        self._count_lbl = tk.Label(tef, text="0/30", bg=bg, fg="gray", font=("Arial", 8))
        self._count_lbl.pack(side="left", padx=4)
        self._text_frame.pack(fill="x", padx=8)

        self._del_frame = tk.Frame(self, bg=bg)
        self._del_btn = tk.Button(self._del_frame, text="\u0412\u0438\u0434\u0430\u043b\u0438\u0442\u0438", bg="#cc3333",
                                  fg="white", bd=0, font=("Arial", 8), command=self._delete_selected)
        self._del_btn.pack(fill="x", padx=8, pady=4)
        self._del_frame.pack(fill="x")
        self._del_frame.pack_forget()

        sep4 = tk.Frame(self, bg="#333", height=1)
        sep4.pack(fill="x", padx=6, pady=2)

        tk.Label(self, text="\u041a\u043e\u043b\u0456\u0440:", font=("Arial", 8, "bold"),
                 bg=bg, fg="#aaa").pack(anchor="w", padx=8, pady=(2, 0))
        clf = tk.Frame(self, bg=bg)
        clf.pack(fill="x", padx=8)
        colors = [("#ff0000", "\u0427\u0435\u0440\u0432\u043e\u043d\u0438\u0439"), ("#00ff00", "\u0417\u0435\u043b\u0435\u043d\u0438\u0439"),
                  ("#00bbff", "\u0421\u0438\u043d\u0456\u0439"), ("#ffff00", "\u0416\u043e\u0432\u0442\u0438\u0439"),
                  ("#ffaa00", "\u041f\u043e\u043c\u0430\u0440\u0430\u043d\u0447\u0435\u0432\u0438\u0439")]
        for hex_code, name in colors:
            btn = tk.Button(clf, bg=hex_code, width=2, bd=0, command=lambda c=hex_code: self._set_color(c))
            btn.pack(side="left", padx=1, pady=3)
        tk.Button(clf, text="\u0406\u043d\u0448\u0438\u0439...", bg="#444", fg="white", bd=0,
                  font=("Arial", 8), command=self._pick_color).pack(side="left", padx=4)
        self._color_preview = tk.Label(clf, text=" \u25a0 ", bg=bg, fg=self.current_color, font=("Arial", 14))
        self._color_preview.pack(side="left", padx=3)

        sep5 = tk.Frame(self, bg="#333", height=1)
        sep5.pack(fill="x", padx=6, pady=2)

        bf = tk.Frame(self, bg=bg)
        bf.pack(fill="x", padx=8, pady=(2, 6))
        tk.Button(bf, text=self.app.t('ui', 'clear'), bg="#444", fg="white", bd=0,
                  font=("Arial", 8), command=self._clear_all).pack(side="left", fill="x", expand=True, padx=1)
        tk.Button(bf, text="\u0415\u043a\u0441\u043f\u043e\u0440\u0442 (.json)", bg="#444", fg="white", bd=0,
                  font=("Arial", 8), command=self._export).pack(side="left", fill="x", expand=True, padx=1)
        tk.Button(bf, text="\u0406\u043c\u043f\u043e\u0440\u0442 (.json)", bg="#444", fg="white", bd=0,
                  font=("Arial", 8), command=self._import).pack(side="left", fill="x", expand=True, padx=1)

    def _on_toolbar_click(self, code):
        self._lift_self()
        if self._edit_obj:
            self.exit_edit_mode()

        if self._active_tool_code == code:
            self._deactivate_tool()
            return

        self._set_tool_from_code(code)

    def _set_tool_from_code(self, code):
        self._active_tool_code = code
        self._update_toolbar_buttons()
        self.painter.set_tool("marker" if code == "marker" else "text")

    def _deactivate_tool(self):
        self._active_tool_code = None
        self._update_toolbar_buttons()
        self.painter.set_tool(None)

    def _highlight_toolbar_button(self, code):
        self._active_tool_code = code
        self._update_toolbar_buttons()

    def _update_toolbar_buttons(self):
        active_bg = "#ffaa00"
        active_fg = "black"
        inactive_bg = "#333"
        inactive_fg = "#aaa"
        for code, btn in self._toolbar_buttons.items():
            is_active = (code == self._active_tool_code)
            btn.config(bg=active_bg if is_active else inactive_bg,
                       fg=active_fg if is_active else inactive_fg)

    def _validate_text(self, *args):
        t = self.text_var.get()
        if len(t) > 30:
            self.text_var.set(t[:30])
            self._entry.config(bg="#550000")
        else:
            self._entry.config(bg="#111")
        self._count_lbl.config(text=f"{len(self.text_var.get())}/30")

    def _lift_self(self):
        try:
            self.lift()
            self.attributes("-topmost", True)
        except:
            pass

    def _on_any_change(self, *args):
        self._lift_self()
        if self._edit_obj:
            self._write_to_object(self._edit_obj)
            self.painter.redraw()
            self.painter.data_mgr.save_drawings(self.painter.drawings)

    def _set_color(self, c):
        self.current_color = c
        self._color_preview.config(fg=c)
        self._on_any_change()

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.current_color, parent=self)[1]
        if c:
            self._set_color(c)

    def _delete_selected(self):
        if self._edit_obj is not None:
            self.app.painter._delete_edited_object()
            self.exit_edit_mode()

    def _clear_all(self):
        self._lift_self()
        if not self.app.current_map_eng:
            return
        self.app.ask_clear_confirm(
            self.app.translate_map_name(self.app.current_map_eng),
            self.painter._do_clear,
        )

    def _export(self):
        self._lift_self()
        self.app.export_current_tactic()

    def _import(self):
        self._lift_self()
        self.app.import_external_tactic()

    def _close(self):
        self.withdraw()
        self._saved_pos = self.geometry()
        self._save_position()

    def show(self):
        self.attributes("-topmost", True)
        self.transient(self.master)
        self.deiconify()
        self.update_idletasks()
        if self._saved_pos:
            self.geometry(self._saved_pos)
        self.lift()
        self.focus_force()
        self._sync_tool_state()
        self.after(100, self._lift_self)

    def _sync_tool_state(self):
        if self._active_tool_code is None:
            active = self.painter.active_tool
            if active == "marker":
                self._active_tool_code = "marker"
            elif active == "text":
                self._active_tool_code = 0x2B
        self._update_toolbar_buttons()

    def _drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _drag_move(self, event):
        x = self.winfo_x() + event.x - self._drag_data["x"]
        y = self.winfo_y() + event.y - self._drag_data["y"]
        self.geometry(f"+{x}+{y}")

    def _drag_stop(self, event):
        self._saved_pos = self.geometry()
        self._save_position()

    def _save_position(self):
        try:
            geo = self.geometry()
            import re
            m = re.match(r'(\d+)x(\d+)[+](-?\d+)[+](-?\d+)', geo)
            if m:
                px, py = int(m.group(3)), int(m.group(4))
                self.app.settings["palette_x"] = px
                self.app.settings["palette_y"] = py
                self.app.save_settings()
        except Exception:
            pass

    def _restore_position(self):
        try:
            px = self.app.settings.get("palette_x", 100)
            py = self.app.settings.get("palette_y", 100)
            self.geometry(f"500x420+{px}+{py}")
            self._saved_pos = f"500x420+{px}+{py}"
        except Exception:
            self.geometry("+100+100")

    # --- Public API ---

    def load_object(self, obj):
        self._edit_obj = obj
        for k, v in self.mode_vars.items():
            v.set(k in obj.get("modes", []))
        for k, v in self.class_vars.items():
            v.set(k in obj.get("classes", []))
        self.text_var.set(obj.get("text", ""))
        self.current_color = obj.get("color", "#ffaa00")
        self._color_preview.config(fg=self.current_color)

        if obj["type"] == "text":
            poi_data = obj.get("poi", [])
            if isinstance(poi_data, str):
                if poi_data.startswith("xvm_"):
                    poi_data = [int(poi_data.split("_")[1], 16)]
                else:
                    poi_data = []
            if "tree" in poi_data:
                self._highlight_toolbar_button("tree")
            elif poi_data:
                code = poi_data[0] if isinstance(poi_data[0], int) else 0x2B
                self._highlight_toolbar_button(code)
            else:
                self._highlight_toolbar_button(0x2B)
        else:
            self._highlight_toolbar_button("marker")
        self.painter.set_tool(None)
        self._del_frame.pack(fill="x")

    def exit_edit_mode(self):
        if self._edit_obj:
            self._write_to_object(self._edit_obj)
            self.painter.redraw()
            self.painter.data_mgr.save_drawings(self.painter.drawings)
        self._edit_obj = None
        self.painter._editing_idx = -1
        self._del_frame.pack_forget()

    def _write_to_object(self, obj):
        obj["modes"] = [k for k, v in self.mode_vars.items() if v.get()]
        obj["classes"] = [k for k, v in self.class_vars.items() if v.get()]
        obj["text"] = self.text_var.get()
        obj["color"] = self.current_color
        if obj.get("type") == "text":
            if self._active_tool_code == "tree":
                obj["poi"] = ["tree"]
            elif isinstance(self._active_tool_code, int):
                obj["poi"] = [self._active_tool_code]
            else:
                obj["poi"] = []
        elif obj.get("type") == "marker":
            coords = obj.get("coords", [])
            cw = self.painter.canvas.winfo_width()
            ch = self.painter.canvas.winfo_height()
            sc = min(cw, ch) / 800.0 if cw >= 10 and ch >= 10 else 1.0
            if obj.get("classes") and not obj.get("class_icon_coords") and len(coords) >= 2:
                obj["class_icon_coords"] = [
                    coords[0],
                    min(max(coords[1] + (int(22 * sc) / max(ch, 1)), 0.0), 1.0),
                ]
            if obj.get("text") and not obj.get("text_coords") and len(coords) >= 4:
                obj["text_coords"] = [
                    (coords[0] + coords[2]) / 2,
                    (coords[1] + coords[3]) / 2 - int(10 * sc) / max(ch, 1),
                ]

    def apply_to_new_object(self, obj, cw, ch):
        self._write_to_object(obj)
        if obj.get("type") == "marker":
            sc = min(cw, ch) / 800.0 if cw >= 10 and ch >= 10 else 1.0
            coords = obj.get("coords", [])
            if obj.get("classes") and not obj.get("class_icon_coords") and len(coords) >= 2:
                obj["class_icon_coords"] = [
                    coords[0],
                    min(max(coords[1] + (int(22 * sc) / max(ch, 1)), 0.0), 1.0),
                ]
            if obj.get("text") and not obj.get("text_coords") and len(coords) >= 4:
                obj["text_coords"] = [
                    (coords[0] + coords[2]) / 2,
                    (coords[1] + coords[3]) / 2 - int(10 * sc) / max(ch, 1),
                ]

    def is_in_edit_mode(self):
        return self._edit_obj is not None

    def has_any_tool_active(self):
        return self._active_tool_code is not None
