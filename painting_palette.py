import tkinter as tk
from tkinter import ttk
import os
import language_module
import dialog_utils
import firebase_identity
import firebase_drawings

FONT_AWE = "FontAwesome"

class DrawingPalette(tk.Toplevel):
    def __init__(self, root, painter, app):
        super().__init__(root)
        self.painter = painter
        self.app = app

        self.overrideredirect(True)
        self.configure(bg="#222")
        self.resizable(False, False)

        self._edit_obj = None
        self._drag_data = {"x": 0, "y": 0}
        self._saved_pos = None

        self.current_color = "#ffaa00"
        self._default_colors = [
            "#ff0000", "#ff5500", "#ffaa00", "#ffff00",
            "#aaff00", "#00ff00", "#00ffaa", "#00ffff",
            "#0088ff", "#0000ff", "#8800ff", "#ff00ff",
            "#888888",
        ]
        self._color_buttons = []

        self._active_tool_code = None

        self.mode_vars = {
            "Standard": tk.BooleanVar(value=False),
            "Encounter": tk.BooleanVar(value=False),
            "Assault": tk.BooleanVar(value=False),
            "Onslaught": tk.BooleanVar(value=False),
        }
        self.mode_labels = {
            "Standard": "Standard",
            "Encounter": "Encounter",
            "Assault": "Assault",
            "Onslaught": "Onslaught",
        }

        self.class_vars = {
            "LT": tk.BooleanVar(value=False),
            "MT": tk.BooleanVar(value=False),
            "HT": tk.BooleanVar(value=False),
            "TD": tk.BooleanVar(value=False),
            "SPG": tk.BooleanVar(value=False),
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
        tk.Label(hdr, text=self.app.t('ui', 'palette_title'), bg="#2a2a2a", fg="white",
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
            (0x3A, chr(0x3A), "XVMSymbol"),
            (0x3B, chr(0x3B), "XVMSymbol"),
            (0x3F, chr(0x3F), "XVMSymbol"),
            (0x2E, chr(0x2E), "XVMSymbol"),
            (0x2D, chr(0x2D), "XVMSymbol"),
            ("tree", chr(0xF18C), FONT_AWE),
            (0x2B, chr(0x2B), "XVMSymbol"),
            (0x42, chr(0x42), "XVMSymbol"),
            (0x45, chr(0x45), "XVMSymbol"),
            (0x50, chr(0x50), "XVMSymbol"),
            (0x52, chr(0x52), "XVMSymbol"),
            (0x5C, chr(0x5C), "XVMSymbol"),
            (0x6F, chr(0x6F), "XVMSymbol"),
            (0x2C, chr(0x2C), "XVMSymbol"),
        ]

        mid = 6
        rows = [all_tools[:mid], all_tools[mid:]]

        for row_items in rows:
            r = tk.Frame(tb, bg="#1a1a1a")
            r.pack(side="top", fill="x", pady=1)
            for code, text, font_name in row_items:
                btn_frame = tk.Frame(r, bg="#1a1a1a", width=38, height=38)
                btn_frame.pack(side="left", padx=1)
                btn_frame.pack_propagate(False)
                btn = tk.Button(btn_frame, text=text, font=(font_name, 16), bg="#333", fg="#aaa",
                                bd=0, command=lambda c=code: self._on_toolbar_click(c))
                btn.pack(expand=True, fill="both")
                self._toolbar_buttons[code] = btn

        self._tb_marker = self._toolbar_buttons.get("marker")

        sep = tk.Frame(self, bg="#333", height=1)
        sep.pack(fill="x", padx=6, pady=3)

        tk.Label(self, text=self.app.t('ui', 'battle_mode'), font=("Arial", 8, "bold"),
                 bg=bg, fg="#aaa").pack(anchor="w", padx=8, pady=(2, 0))
        mf = tk.Frame(self, bg=bg)
        mf.pack(fill="x", padx=8)
        _mode_mo_keys = {
            "Standard": "type/ctf/name",
            "Encounter": "type/domination/name",
            "Assault": "type/assault/name",
            "Onslaught": "type/comp7/name",
        }
        lm = language_module.get_lang_module()
        for k, v in self.mode_vars.items():
            mo_key = _mode_mo_keys.get(k)
            txt = lm.t(mo_key) if mo_key else None
            if not txt:
                txt = self.app.t('ui', 'mode_' + k.lower())
            cb = tk.Checkbutton(mf, text=txt, variable=v, command=self._on_any_change,
                                **cb_style, font=("Arial", 8))
            cb.pack(side="left", padx=1)

        sep2 = tk.Frame(self, bg="#333", height=1)
        sep2.pack(fill="x", padx=6, pady=2)

        tk.Label(self, text=self.app.t('ui', 'vehicle_class'), font=("Arial", 8, "bold"),
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
        tk.Label(self._text_frame, text=self.app.t('ui', 'text_label'), font=("Arial", 8, "bold"),
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
        self._del_btn = tk.Button(self._del_frame, text=self.app.t('ui', 'delete_btn').upper(), bg="#cc3333",
                                  fg="white", bd=0, font=("Arial", 8), command=self._delete_selected)
        self._del_btn.pack(fill="x", padx=8, pady=4)
        self._del_frame.pack(fill="x")
        self._del_frame.pack_forget()

        sep4 = tk.Frame(self, bg="#333", height=1)
        sep4.pack(fill="x", padx=6, pady=2)

        tk.Label(self, text=self.app.t('ui', 'color_label'), font=("Arial", 8, "bold"),
                 bg=bg, fg="#aaa").pack(anchor="w", padx=8, pady=(2, 0))
        clf = tk.Frame(self, bg=bg)
        clf.pack(fill="x", padx=8)
        for i, hex_code in enumerate(self._default_colors):
            btn = tk.Button(clf, bg=hex_code, width=2, bd=1, relief="raised",
                            command=lambda c=hex_code: self._set_color(c))
            btn.pack(side="left", padx=1, pady=3)
            self._color_buttons.append(btn)
        self._color_preview = tk.Label(clf, text=" \u25a0 ", bg=bg, fg=self.current_color, font=("Arial", 14))
        self._color_preview.pack(side="left", padx=3)

        sep5 = tk.Frame(self, bg="#333", height=1)
        sep5.pack(fill="x", padx=6, pady=2)

        cf = tk.Frame(self, bg=bg)
        cf.pack(fill="x", padx=8, pady=(2, 2))
        tk.Button(cf, text=self.app.t('ui', 'clear').upper(), bg="#444", fg="white", bd=0,
                  font=("Arial", 8), command=self._clear_all).pack(fill="x", expand=True, padx=1)

        sep6 = tk.Frame(self, bg="#333", height=1)
        sep6.pack(fill="x", padx=6, pady=2)

        bf = tk.Frame(self, bg=bg)
        bf.pack(fill="x", padx=8, pady=(2, 6))
        tk.Button(bf, text=self.app.t('ui', 'publish_map').upper(), bg="#446644", fg="#cfc", bd=0,
                  font=("Arial", 8, "bold"), command=self._choose_publish_action).pack(side="left", fill="x", expand=True, padx=1)
        tk.Button(bf, text=self.app.t('ui', 'save_btn').upper(), bg="#444", fg="white", bd=0,
                  font=("Arial", 8, "bold"), command=self._choose_save_action).pack(side="left", fill="x", expand=True, padx=1)
        tk.Button(bf, text=self.app.t('ui', 'load_btn').upper(), bg="#444", fg="white", bd=0,
                   font=("Arial", 8, "bold"), command=self._import_unified).pack(side="left", fill="x", expand=True, padx=1)
        tk.Button(bf, text=self.app.t('ui', 'download_btn').upper(), bg="#446688", fg="white", bd=0,
                   font=("Arial", 8, "bold"), command=self._show_download_dialog).pack(side="left", fill="x", expand=True, padx=1)

        self._choice_frame = tk.Frame(self, bg="#333")
        tk.Label(self._choice_frame, text="", font=("Arial", 8), bg="#333", fg="#ccc",
                 height=1).pack(fill="x", padx=6, pady=(4, 2))
        self._choice_frame.pack(fill="x", padx=6, pady=4)
        self._choice_frame.pack_forget()

        self._status_lbl = tk.Label(self, text="", font=("Arial", 8), bg=bg, fg="#ffaa00",
                                     height=1, anchor="w")
        self._status_lbl.pack(fill="x", padx=8, pady=(2, 2))

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
        self.current_color = "#ffaa00" if code == "marker" else "#00ff00"
        self._color_preview.config(fg=self.current_color)
        self._update_color_buttons()

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
            self.lift(aboveThis=self.master)
        except:
            pass

    def _on_any_change(self, *args):
        if getattr(self, '_loading_obj', False):
            return
        self._lift_self()
        if self._edit_obj:
            self._write_to_object(self._edit_obj)
            self.painter.redraw()
            self.painter.data_mgr.save_drawings(self.painter.drawings)

    def _set_color(self, c):
        self.current_color = c
        self._color_preview.config(fg=c)
        self._update_color_buttons()
        self._on_any_change()

    def _update_color_buttons(self):
        for i, btn in enumerate(self._color_buttons):
            if i < len(self._default_colors):
                bg = self._default_colors[i]
                is_active = (bg == self.current_color)
                btn.config(bg=bg,
                           bd=2 if is_active else 1,
                           relief="sunken" if is_active else "raised")

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

    def _export_all(self):
        self._lift_self()
        self.app.export_all_tactics()

    def _import_unified(self):
        self._lift_self()
        self.app.import_tactic_unified()

    def _choose_publish_action(self):
        self._lift_self()
        if not firebase_identity.is_registered():
            self._show_custom_message(
                self.app.t('ui', 'publish_map'),
                self.app.t('ui', 'publish_register_first'))
            return
        import config
        map_name = config.MAP_NAMES_EN.get(self.app.current_map_eng, self.app.current_map_eng)
        def on_map():
            self._hide_choice_inline()
            self._publish()
        def on_all():
            self._hide_choice_inline()
            self._publish_all()
        self._show_choice_inline(
            self.app.t('ui', 'publish_what'),
            map_name, on_map,
            self.app.t('ui', 'publish_all'), on_all)

    def _choose_save_action(self):
        self._lift_self()
        import config
        map_name = config.MAP_NAMES_EN.get(self.app.current_map_eng, self.app.current_map_eng)
        def on_map():
            self._hide_choice_inline()
            self._export()
        def on_all():
            self._hide_choice_inline()
            self._export_all()
        self._show_choice_inline(
            self.app.t('ui', 'save_what'),
            map_name, on_map,
            self.app.t('ui', 'all_maps'), on_all)

    def _show_choice_inline(self, title, btn1_text, btn1_cmd, btn2_text, btn2_cmd):
        for w in self._choice_frame.winfo_children():
            w.destroy()
        tk.Label(self._choice_frame, text=title, bg="#333", fg="#ccc",
                 font=("Arial", 8)).pack(fill="x", padx=6, pady=(4, 2))
        bf = tk.Frame(self._choice_frame, bg="#333")
        bf.pack(pady=(0, 4))
        tk.Button(bf, text=btn1_text, bg="#446644", fg="#cfc", bd=0,
                  font=("Arial", 8, "bold"), padx=10, pady=3, command=btn1_cmd).pack(side="left", padx=2)
        tk.Button(bf, text=btn2_text, bg="#446644", fg="#cfc", bd=0,
                  font=("Arial", 8, "bold"), padx=10, pady=3, command=btn2_cmd).pack(side="left", padx=2)
        tk.Button(bf, text="✕", bg="#333", fg="#888", bd=0,
                  font=("Arial", 8), command=self._hide_choice_inline).pack(side="left", padx=6)
        self._choice_frame.pack(fill="x", padx=6, pady=4, before=self._status_lbl)

    def _hide_choice_inline(self):
        self._choice_frame.pack_forget()

    def _fetch_existing_comments(self, map_ids):
        try:
            import firebase_reporter
            import requests
            url = firebase_reporter._rtdb_url("schemes.json")
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return set()
            data = r.json()
            if not data or not isinstance(data, dict):
                return set()
            existing = set()
            for item in data.values():
                if not isinstance(item, dict):
                    continue
                mid = item.get("map_id", "")
                com = item.get("comment", "")
                if mid in map_ids:
                    existing.add((mid, com))
            return existing
        except Exception:
            return set()

    def _publish(self):
        self._lift_self()
        if not firebase_identity.is_registered():
            self._show_custom_message(
                self.app.t('ui', 'publish_map'),
                self.app.t('ui', 'publish_register_first'))
            return
        if not self.app.current_map_eng:
            return
        drawings = self.painter.drawings.get(self.app.current_map_eng, [])
        if not drawings:
            self._show_custom_message(
                self.app.t('ui', 'publish_map'),
                self.app.t('ui', 'publish_no_drawings'))
            return

        import config
        map_name = config.MAP_NAMES_EN.get(self.app.current_map_eng, self.app.current_map_eng)
        existing = self._fetch_existing_comments({self.app.current_map_eng})
        desc = self._ask_publish_description(
            map_name, existing_comments=existing,
            map_id=self.app.current_map_eng)
        if desc is None:
            return
        desc_en = self._translate_to_english(desc)

        def on_done(ok, msg):
            if ok:
                self.after(0, lambda: self._show_custom_message(
                    self.app.t('ui', 'publish_map'),
                    self.app.t('ui', 'publish_done')))
            else:
                self.after(0, lambda: self._show_custom_message(
                    self.app.t('ui', 'publish_map'),
                    self.app.t('ui', 'publish_error').format(msg=msg),
                    is_error=True))

        firebase_drawings.publish_drawing(
            map_name=map_name, map_id=self.app.current_map_eng,
            elements_data=drawings, title=map_name,
            comment=desc_en, on_done=on_done)

    def _publish_all(self):
        import config
        self._lift_self()
        if not firebase_identity.is_registered():
            self._show_custom_message(
                self.app.t('ui', 'publish_all'),
                self.app.t('ui', 'publish_register_first'))
            return

        maps_with = {k: v for k, v in self.painter.drawings.items()
                     if isinstance(v, list) and len(v) > 0}
        if not maps_with:
            self._show_custom_message(
                self.app.t('ui', 'publish_all'),
                self.app.t('ui', 'publish_no_drawings_all'))
            return

        existing = self._fetch_existing_comments({"all_maps"})
        desc = self._ask_publish_description(
            "All Maps", count=len(maps_with),
            existing_comments=existing, map_ids={"all_maps"})
        if desc is None:
            return
        desc_en = self._translate_to_english(desc)

        bundle = {
            "type": "all_maps",
            "drawings": {k: v for k, v in maps_with.items()},
            "map_names": {k: config.MAP_NAMES_EN.get(k, k) for k in maps_with},
            "version": config.load_version(),
            "total_maps": len(maps_with),
            "total_elements": sum(len(v) for v in maps_with.values()),
        }

        def on_done(ok, msg):
            self.after(0, lambda: self._show_publish_all_result(
                {"ok": 1 if ok else 0, "errors": 0 if ok else 1, "total": 1}))

        firebase_drawings.publish_drawing(
            map_name="All Maps", map_id="all_maps",
            elements_data=bundle, title="All Maps",
            comment=desc_en, on_done=on_done)

    def _ask_publish_description(self, name, count=0, existing_comments=None,
                                  map_id=None, map_ids=None):
        dlg = tk.Toplevel(self.app.root)
        dlg.title(self.app.t('ui', 'publish_map') if count == 0 else self.app.t('ui', 'publish_all'))
        dlg.configure(bg="#222")
        dlg.resizable(False, False)
        dlg.transient(self.app.root)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()

        if count:
            lbl_text = self.app.t('ui', 'publish_publishing_all').format(count=count)
        else:
            lbl_text = self.app.t('ui', 'publish_publishing').format(name=name)
        tk.Label(dlg, text=lbl_text, bg="#222", fg="#ffaa00",
                 font=("Arial", 9, "bold")).pack(padx=16, pady=(12, 6))

        tk.Label(dlg, text=self.app.t('ui', 'publish_desc_hint'),
                 bg="#222", fg="#888", font=("Arial", 8),
                 anchor="w").pack(fill="x", padx=16)

        err_lbl = tk.Label(dlg, text="", bg="#222", fg="#ff6666",
                           font=("Arial", 8), anchor="w", wraplength=360)
        err_lbl.pack(fill="x", padx=16)
        err_lbl.pack_forget()

        text_w = tk.Text(dlg, height=3, width=40, bg="#111", fg="white",
                          insertbackground="white", bd=1, relief="solid",
                          wrap="word", font=("Arial", 9))
        text_w.pack(padx=16, pady=(2, 8))

        def clear_error():
            text_w.config(bg="#111")
            err_lbl.pack_forget()

        text_w.bind("<KeyRelease>", lambda e: clear_error())

        result = [None]

        def on_ok():
            desc = text_w.get("1.0", "end-1c").strip()
            if not desc:
                text_w.config(bg="#331111")
                err_lbl.config(text=self.app.t('ui', 'publish_desc_required'))
                err_lbl.pack(fill="x", padx=16)
                return
            desc_en = self._translate_to_english(desc)

            if existing_comments is not None:
                check_ids = [map_id] if map_id else (map_ids or set())
                for mid in check_ids:
                    if (mid, desc_en) in existing_comments:
                        text_w.config(bg="#331111")
                        err_lbl.config(text="Same map with this description already exists. Change description to publish.")
                        err_lbl.pack(fill="x", padx=16)
                        return

            result[0] = desc
            dlg.destroy()

        def on_cancel():
            result[0] = None
            dlg.destroy()

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(0, 12))
        tk.Button(bf, text=self.app.t('ui', 'publish_cancel'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=12, pady=4, command=on_cancel).pack(side="left", padx=4)
        tk.Button(bf, text=self.app.t('ui', 'publish_confirm'), bg="#446644", fg="#cfc", bd=0,
                  font=("Arial", 9, "bold"), padx=12, pady=4, command=on_ok).pack(side="left", padx=4)

        self._center_on_root(dlg)
        self.wait_window(dlg)
        return result[0]

    def _translate_to_english(self, text):
        if not text:
            return ""
        try:
            from deep_translator import GoogleTranslator
            return GoogleTranslator(source='auto', target='en').translate(text)
        except Exception:
            return text

    def _center_on_root(self, dlg):
        self.app.root.update_idletasks()
        rx = self.app.root.winfo_x()
        ry = self.app.root.winfo_y()
        rw = self.app.root.winfo_width()
        rh = self.app.root.winfo_height()
        dlg.update_idletasks()
        dw = dlg.winfo_reqwidth()
        dh = dlg.winfo_reqheight()
        x = rx + max(0, (rw - dw) // 2)
        y = ry + max(0, (rh - dh) // 2)
        dlg.geometry(f"+{x}+{y}")

    def _show_custom_message(self, title, message, is_error=False):
        dlg = tk.Toplevel(self.app.root)
        dlg.title(title)
        dlg.configure(bg="#222")
        dlg.resizable(False, False)
        dlg.transient(self.app.root)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()
        tk.Label(dlg, text=title, bg="#222", fg="#ffaa00",
                 font=("Arial", 10, "bold")).pack(padx=20, pady=(14, 6))
        tk.Label(dlg, text=message, bg="#222",
                 fg="#ff6666" if is_error else "#cccccc",
                 font=("Arial", 9), wraplength=360, justify="left").pack(padx=20, pady=(4, 12))
        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(0, 12))
        result = [False]
        def on_ok():
            result[0] = True
            dlg.destroy()
        tk.Button(bf, text="OK", bg="#446644" if not is_error else "#664444",
                  fg="#cfc" if not is_error else "#fcc", bd=0,
                  font=("Arial", 9, "bold"), padx=20, pady=4, command=on_ok).pack()
        self._center_on_root(dlg)
        self.wait_window(dlg)
        return result[0]

    def _show_publish_all_result(self, results):
        msg = self.app.t('ui', 'publish_all_result').format(
            ok=results["ok"], errors=results["errors"])
        self._show_custom_message(
            self.app.t('ui', 'publish_all'), msg,
            is_error=results["errors"] > 0)

    def _close(self):
        self.exit_edit_mode()
        self.withdraw()
        self._saved_pos = self.geometry()
        self._save_position()

    def show(self):
        self.deiconify()
        self.lift(aboveThis=self.app.root)
        self.transient(self.app.root)
        self.focus_force()
        self.update_idletasks()
        if self._saved_pos:
            self.geometry(self._saved_pos)
        self._sync_tool_state()
        self.after(100, self._lift_self)

    def _sync_tool_state(self):
        active = self.painter.active_tool
        if not active:
            self._active_tool_code = None
        elif active == "marker":
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
            self.geometry(f"500x480+{px}+{py}")
            self._saved_pos = f"500x480+{px}+{py}"
        except Exception:
            self.geometry("+100+100")

    # --- Public API ---

    _UKR_TO_EN_CLASS = {"ЛТ": "LT", "СТ": "MT", "ТТ": "HT", "ПТ": "TD", "САУ": "SPG"}

    def load_object(self, obj):
        self._loading_obj = True
        try:
            self._edit_obj = obj
            for k, v in self.mode_vars.items():
                v.set(k in obj.get("modes", []))
            raw_classes = obj.get("classes", [])
            en_classes = {self._UKR_TO_EN_CLASS.get(c, c) for c in raw_classes}
            for k, v in self.class_vars.items():
                v.set(k in en_classes)
            self.text_var.set(obj.get("text", ""))
            self.current_color = obj.get("color", "#ffaa00")
            self._color_preview.config(fg=self.current_color)
            self._update_color_buttons()

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
            label = self.app.t('ui', 'status_editing_marker') if obj["type"] == "marker" else self.app.t('ui', 'status_editing_text')
            self._status_lbl.config(text=f"{label}")
        finally:
            self._loading_obj = False

    def exit_edit_mode(self):
        if self._edit_obj is None:
            return
        self._write_to_object(self._edit_obj)
        self.painter.redraw()
        self.painter.data_mgr.save_drawings(self.painter.drawings)
        self._edit_obj = None
        self.painter._editing_idx = -1
        self._active_tool_code = None
        self._update_toolbar_buttons()
        self.painter.set_tool(None)
        self._del_frame.pack_forget()
        self._status_lbl.config(text="")

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

    # --- Download Community Schemes ---

    def _show_download_dialog(self):
        self._lift_self()
        dlg = tk.Toplevel(self.app.root)
        dlg.overrideredirect(True)
        dlg.configure(bg="#222")
        dlg.attributes("-topmost", True)
        dlg.grab_set()
        dlg.focus_force()
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        hdr_bg = "#2a2a2a"
        hdr = tk.Frame(dlg, bg=hdr_bg, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  {self.app.t('ui', 'download_title')}", bg=hdr_bg, fg="#ffaa00",
                 font=("Arial", 9, "bold")).pack(side="left")
        tk.Button(hdr, text="✕", bg=hdr_bg, fg="#aaa", bd=0,
                  font=("Arial", 8), command=dlg.destroy).pack(side="right", padx=4)
        _drag = {"x": 0, "y": 0}
        def drag_start(e):
            _drag["x"] = e.x
            _drag["y"] = e.y
        def drag_move(e):
            dlg.geometry(f"+{dlg.winfo_x() + e.x - _drag['x']}+{dlg.winfo_y() + e.y - _drag['y']}")
        hdr.bind("<Button-1>", drag_start)
        hdr.bind("<B1-Motion>", drag_move)
        hdr.bind("<Enter>", lambda e: hdr.config(cursor="fleur"))

        bg = "#222"

        status_lbl = tk.Label(dlg, text=self.app.t('ui', 'download_loading'),
                              bg=bg, fg="#888", font=("Arial", 9))
        status_lbl.pack(padx=10, pady=10)

        def _populate():
            try:
                schemes = firebase_drawings.get_all_schemes()
            except Exception:
                schemes = {}
            self.after(0, lambda: _build_dialog(schemes))

        def _build_dialog(schemes):
            for w in dlg.winfo_children():
                w.destroy()

            if not schemes:
                status_lbl = tk.Label(dlg, text=self.app.t('ui', 'download_no_schemes'),
                                      bg=bg, fg="#ff6666", font=("Arial", 9))
                status_lbl.pack(padx=20, pady=20)
                tk.Button(dlg, text="OK", bg="#444", fg="white", bd=0,
                          font=("Arial", 9), command=dlg.destroy).pack(pady=(0, 12))
                return

            # Build data list
            items = []
            for sid, data in schemes.items():
                map_id = data.get("map_id", "")
                map_name = data.get("map_name", "")
                author = data.get("author_nickname", "")
                created = (data.get("created_at") or "")[:10]
                el_count = data.get("element_count", 0)
                comment = (data.get("comment") or "")[:40]
                items.append({
                    "scheme_id": sid,
                    "map_id": map_id,
                    "map_name": map_name,
                    "author": author,
                    "created": created,
                    "comment": comment,
                    "el_count": el_count,
                    "elements": data.get("elements", []),
                })

            items.sort(key=lambda x: x.get("created", ""), reverse=True)

            # Collect unique map names and authors for filters
            unique_maps = sorted(set(it["map_name"] for it in items if it["map_name"]))
            unique_authors = sorted(set(it["author"] for it in items if it["author"]))

            # Dark ttk theme
            style = ttk.Style()
            style.theme_use("default")
            style.configure("Treeview", background="#1a1a1a", foreground="#cccccc",
                            fieldbackground="#1a1a1a", bordercolor="#333", arrowcolor="#888")
            style.configure("Treeview.Heading", background="#333", foreground="#aaa",
                            fieldbackground="#333")
            style.map("Treeview", background=[("selected", "#444")],
                      foreground=[("selected", "white")])
            style.configure("TCombobox", background="#1a1a1a", foreground="#cccccc",
                            fieldbackground="#1a1a1a", arrowcolor="#888")
            style.map("TCombobox", fieldbackground=[("readonly", "#1a1a1a")],
                      foreground=[("readonly", "#cccccc")])
            style.configure("Vertical.TScrollbar", background="#444", troughcolor="#222",
                            gripcount=0, arrowsize=12, relief="flat", borderwidth=0)
            style.map("Vertical.TScrollbar", background=[("active", "#555")])

            all_label = self.app.t('ui', 'download_filter_all')

            # Filter frame
            ff = tk.Frame(dlg, bg=bg)
            ff.pack(fill="x", padx=8, pady=(6, 2))

            tk.Label(ff, text="Map:", bg=bg, fg="#aaa", font=("Arial", 8, "bold")).pack(side="left", padx=(0, 2))
            map_filter_var = tk.StringVar(value=all_label)
            map_filter_cb = tk.ttk.Combobox(ff, textvariable=map_filter_var,
                                             values=[all_label] + unique_maps,
                                             state="readonly", width=18, font=("Arial", 8))
            map_filter_cb.pack(side="left", padx=4)

            tk.Label(ff, text="Author:", bg=bg, fg="#aaa", font=("Arial", 8, "bold")).pack(side="left", padx=(8, 2))
            author_filter_var = tk.StringVar(value=all_label)
            author_filter_cb = tk.ttk.Combobox(ff, textvariable=author_filter_var,
                                                 values=[all_label] + unique_authors,
                                                 state="readonly", width=14, font=("Arial", 8))
            author_filter_cb.pack(side="left", padx=4)

            # Tree frame
            tf = tk.Frame(dlg, bg=bg)
            tf.pack(fill="both", expand=True, padx=8, pady=4)

            columns = ("map", "comment", "author", "date", "preview")
            tree = tk.ttk.Treeview(tf, columns=columns, show="headings",
                                    height=12, selectmode="browse")
            tree.heading("map", text="Map Name")
            tree.heading("comment", text="Description")
            tree.heading("author", text="Author")
            tree.heading("date", text="Date")
            tree.heading("preview", text="")
            tree.column("map", width=120)
            tree.column("comment", width=150)
            tree.column("author", width=90)
            tree.column("date", width=75)
            tree.column("preview", width=50, anchor="center")

            vsb = tk.ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")

            # Preview button for each row
            def make_preview_cmd(scheme_item):
                return lambda: self._preview_scheme(scheme_item, dlg)

            def _do_filter(*args):
                mf = map_filter_var.get()
                af = author_filter_var.get()
                tree.delete(*tree.get_children())
                for it in items:
                    if mf != all_label and it["map_name"] != mf:
                        continue
                    if af != all_label and it["author"] != af:
                        continue
                    has_preview = it["map_id"] != "all_maps"
                    tree.insert("", "end",
                                values=(it["map_name"], it["comment"], it["author"], it["created"],
                                        "Preview" if has_preview else ""),
                                iid=it["scheme_id"])

            map_filter_cb.bind("<<ComboboxSelected>>", _do_filter)
            author_filter_cb.bind("<<ComboboxSelected>>", _do_filter)

            # Click on tree item for preview
            def on_tree_click(event):
                region = tree.identify_region(event.x, event.y)
                if region == "cell":
                    col = tree.identify_column(event.x)
                    if col == "#5":
                        sel = tree.selection()
                        if sel:
                            sid = sel[0]
                            for it in items:
                                if it["scheme_id"] == sid and it["map_id"] != "all_maps":
                                    self._preview_scheme(it, dlg)
                                    return

            tree.bind("<ButtonRelease-1>", on_tree_click)

            # Bottom buttons
            bf = tk.Frame(dlg, bg=bg)
            bf.pack(fill="x", padx=8, pady=(0, 8))

            def on_download():
                sel = tree.selection()
                if not sel:
                    return
                sid = sel[0]
                for it in items:
                    if it["scheme_id"] == sid:
                        self._download_result = it
                        dlg.destroy()
                        return

            def on_cancel():
                self._download_result = None
                dlg.destroy()

            tk.Button(bf, text="Cancel", bg="#444", fg="#aaa", bd=0,
                      font=("Arial", 9), padx=12, pady=4, command=on_cancel).pack(side="right", padx=2)
            tk.Button(bf, text="Download", bg="#446688", fg="white", bd=0,
                      font=("Arial", 9, "bold"), padx=12, pady=4, command=on_download).pack(side="right", padx=2)

            # Populate tree initially
            _do_filter()
            dlg.update_idletasks()

        dlg.geometry("600x380")
        self._center_on_root(dlg)

        import threading
        self._download_result = None
        t = threading.Thread(target=_populate, daemon=True)
        t.start()
        self.wait_window(dlg)

        if self._download_result is not None:
            self._handle_download_result(self._download_result)

    def _handle_download_result(self, item):
        """Called when user selects a scheme to download. Shows choice dialog."""
        painter = self.painter
        map_id = item["map_id"]
        elements = item["elements"]
        if not isinstance(elements, list):
            elements = []

        import config
        is_all_maps = (map_id == "all_maps")
        if is_all_maps and isinstance(elements, dict):
            map_name = "All Maps"
        else:
            map_name = config.MAP_NAMES_EN.get(map_id, item.get("map_name", map_id))

        choice = self._choose_download_action(map_name, is_all_maps)
        if choice is None:
            return

        if choice == "replace":
            if is_all_maps and isinstance(elements, dict):
                drawings = elements.get("drawings", {})
                for kid, kdrawings in drawings.items():
                    if isinstance(kdrawings, list):
                        painter.drawings[kid] = kdrawings
            else:
                painter.drawings[map_id] = elements
            painter._creation_history.clear()
            painter._editing_idx = -1
            self.exit_edit_mode()

        elif choice == "add":
            if is_all_maps and isinstance(elements, dict):
                drawings = elements.get("drawings", {})
                for kid, kdrawings in drawings.items():
                    if not isinstance(kdrawings, list):
                        continue
                    existing = painter.drawings.get(kid, [])
                    painter.drawings[kid] = existing + kdrawings
            else:
                existing = painter.drawings.get(map_id, [])
                painter.drawings[map_id] = existing + elements

        elif choice == "save_pc":
            import json
            from tkinter import filedialog
            default_name = f"{map_name}_scheme.json"
            fp = filedialog.asksaveasfilename(
                parent=self,
                title=self.app.t('ui', 'download_save_pc'),
                defaultextension=".json",
                initialfile=default_name,
                filetypes=[("JSON", "*.json")],
            )
            if fp:
                data = item.get("elements", []) if not is_all_maps else item.get("elements", {})
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            return

        painter.data_mgr.save_drawings(painter.drawings)
        painter.redraw()

    def _choose_download_action(self, map_name, is_all_maps):
        """Show choice dialog for download action. Returns 'replace', 'add', 'save_pc' or None."""
        dlg = tk.Toplevel(self.app.root)
        dlg.title(self.app.t('ui', 'download_confirm_title'))
        dlg.configure(bg="#222")
        dlg.resizable(False, False)
        dlg.transient(self.app.root)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()

        tk.Label(dlg, text=self.app.t('ui', 'download_confirm_title'),
                 bg="#222", fg="#ffaa00", font=("Arial", 10, "bold")).pack(padx=20, pady=(14, 6))
        tk.Label(dlg, text=f" {map_name}",
                 bg="#222", fg="#cccccc", font=("Arial", 9)).pack(padx=20, pady=(0, 4))
        tk.Label(dlg, text=" ", bg="#222", fg="#888", font=("Arial", 8)).pack(padx=20, pady=(0, 4))

        result = [None]

        def on_replace():
            result[0] = "replace"
            dlg.destroy()

        def on_add():
            result[0] = "add"
            dlg.destroy()

        def on_save():
            result[0] = "save_pc"
            dlg.destroy()

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(0, 12))
        tk.Button(bf, text=self.app.t('ui', 'download_replace'), bg="#556677", fg="white", bd=0,
                  font=("Arial", 9), padx=12, pady=4, command=on_replace).pack(side="left", padx=4)
        tk.Button(bf, text=self.app.t('ui', 'download_add'), bg="#446644", fg="#cfc", bd=0,
                  font=("Arial", 9), padx=12, pady=4, command=on_add).pack(side="left", padx=4)
        tk.Button(bf, text=self.app.t('ui', 'download_save_pc'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=12, pady=4, command=on_save).pack(side="left", padx=4)

        self._center_on_root(dlg)
        self.wait_window(dlg)
        return result[0]

    def _preview_scheme(self, item, parent_dlg):
        if item["map_id"] == "all_maps":
            return
        map_id = item["map_id"]
        elements = item["elements"]
        if not elements:
            return

        # Find map image
        import config
        img_path = os.path.join(config.BASE_DIR, "extracted_maps", f"{map_id}.png")
        if not os.path.exists(img_path):
            img_path = os.path.join(config.BASE_DIR, "maps", map_id.replace(" ", "_"), "map.webp")
            if not os.path.exists(img_path):
                dialog_utils.dark_messagebox(
                    parent_dlg,
                    self.app.t('ui', 'download_preview'),
                    self.app.t('ui', 'download_preview_no_image'))
                return

        from PIL import Image, ImageTk

        pw, ph = 600, 500
        pv = tk.Toplevel(parent_dlg)
        pv.title(f"Preview: {item['map_name']}")
        pv.configure(bg="#111")
        pv.resizable(False, False)
        pv.transient(parent_dlg)
        pv.attributes("-topmost", True)
        pv.lift()
        pv.focus_force()
        pv.update_idletasks()
        dialog_utils._set_dark_title_bar(pv)

        canvas = tk.Canvas(pv, width=pw, height=ph, bg="#111", highlightthickness=0)
        canvas.pack()

        try:
            img = Image.open(img_path)
            img_w, img_h = img.size
            scale = min(pw / img_w, ph / img_h, 1.0)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            if scale < 1.0:
                img = img.resize((new_w, new_h), Image.LANCZOS)
            pv._photo = ImageTk.PhotoImage(img)
            cx, cy = (pw - new_w) // 2, (ph - new_h) // 2
            canvas.create_image(cx, cy, anchor="nw", image=pv._photo)
            canvas.image = pv._photo
        except Exception:
            dialog_utils.dark_messagebox(pv, "Preview Error", "Could not load map image")
            pv.destroy()
            return

        # Render elements on preview canvas
        if isinstance(elements, list):
            map_id_cur = self.app.current_map_eng
            painter = self.app.painter
            if painter:
                painter._render_elements(canvas, elements, pw, ph)

        tk.Button(pv, text="Close", bg="#444", fg="white", bd=0,
                  font=("Arial", 9), command=pv.destroy).pack(pady=4)

        self._center_on_root(pv)

    def is_in_edit_mode(self):
        return self._edit_obj is not None

    def has_any_tool_active(self):
        return self._active_tool_code is not None
