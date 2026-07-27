import tkinter as tk
from tkinter import ttk
import os
import language_module
import dialog_utils
import firebase_identity
import firebase_drawings
import firebase_groups

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
            "#ffffff",
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
        self._thickness_var = tk.IntVar(value=3)
        self._apply_all_var = tk.BooleanVar(value=False)
        self._thickness_var.trace_add("write", self._on_thickness_change)

        self.text_var = tk.StringVar(value="")
        self.text_var.trace("w", self._validate_text)
        self.text_var.trace("w", self._on_any_change)

        self._toolbar_buttons = {}
        self._build_ui()
        self._restore_position()
        self.after(0, self._refresh_linked_schemes_list)

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
            ("arrow", chr(0xF062), FONT_AWE),
            ("brush", chr(0xF040), FONT_AWE),
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

        mid = 8
        rows = [all_tools[:mid], all_tools[mid:]]

        for row_items in rows:
            r = tk.Frame(tb, bg="#1a1a1a")
            r.pack(side="top", fill="x", pady=1)
            for code, text, font_name in row_items:
                btn_frame = tk.Frame(r, bg="#1a1a1a", width=38, height=38)
                btn_frame.pack(side="left", padx=1)
                btn_frame.pack_propagate(False)
                fs = 11 if code == "arrow" else 13 if code == "brush" else 16
                btn = tk.Button(btn_frame, text=text, font=(font_name, fs), bg="#333", fg="#aaa",
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

        self._brush_frame = tk.Frame(self, bg=bg)
        self._arrow_start_var = tk.BooleanVar(value=False)
        self._arrow_end_var = tk.BooleanVar(value=False)
        tk.Label(self._brush_frame, text="Arrow:", bg=bg, fg="#aaa",
                 font=("Arial", 8, "bold")).pack(anchor="w", padx=8, pady=(2, 0))
        af = tk.Frame(self._brush_frame, bg=bg)
        af.pack(fill="x", padx=8)
        tk.Checkbutton(af, text=self.app.t('ui', 'arrow_start'), variable=self._arrow_start_var,
                       command=self._on_any_change, **cb_style, font=("Arial", 8)).pack(side="left", padx=1)
        tk.Checkbutton(af, text=self.app.t('ui', 'arrow_end'), variable=self._arrow_end_var,
                       command=self._on_any_change, **cb_style, font=("Arial", 8)).pack(side="left", padx=1)
        self._brush_frame.pack(fill="x")
        self._brush_frame.pack_forget()

        # Thickness control
        thf = tk.Frame(self, bg=bg)
        tk.Label(thf, text=self.app.t('ui', 'thickness_label'), font=("Arial", 8, "bold"),
                 bg=bg, fg="#aaa").pack(side="left", padx=(8, 4))
        tk.Scale(thf, from_=1, to=10, orient="horizontal", variable=self._thickness_var,
                 showvalue=True, bg=bg, fg="#cccccc", troughcolor="#333333", bd=0,
                 highlightthickness=0, sliderlength=16, width=10,
                 length=120).pack(side="left", padx=(0, 6))
        tk.Label(thf, textvariable=self._thickness_var, font=("Arial", 9, "bold"),
                 bg=bg, fg="#ffaa00", width=2).pack(side="left")
        self._apply_all_cb = tk.Checkbutton(thf, text=self.app.t('ui', 'apply_all'),
                                            variable=self._apply_all_var, bg=bg, fg="#cccccc",
                                            selectcolor="#333333", font=("Arial", 8))
        self._apply_all_cb.pack(side="left", padx=(4, 0))
        thf.pack(fill="x", padx=4, pady=(2, 0))

        self._sep4 = tk.Frame(self, bg="#333", height=1)
        self._sep4.pack(fill="x", padx=6, pady=2)

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

        action_frame = tk.Frame(self, bg=bg)
        action_frame.pack(fill="x", padx=8, pady=(2, 2))
        self._del_btn = tk.Button(action_frame, text=self.app.t('ui', 'delete_btn').upper(),
                                  bg="#555555", fg="#888888", bd=0, font=("Arial", 8),
                                  state="disabled", command=self._delete_selected)
        self._del_btn.pack(side="left", fill="x", expand=True, padx=1)
        tk.Button(action_frame, text=self.app.t('ui', 'clear').upper(), bg="#444", fg="white",
                  bd=0, font=("Arial", 8), command=self._clear_all).pack(side="left", fill="x", expand=True, padx=1)

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

        self._download_frame = tk.Frame(self, bg="#222")

        self._status_lbl = tk.Label(self, text="", font=("Arial", 8), bg=bg, fg="#ffaa00",
                                     height=1, anchor="w")
        self._status_lbl.pack(fill="x", padx=8, pady=(2, 2))

        self._group_mgmt_frame = tk.Frame(self, bg="#1a1a1a")
        self._group_mgmt_frame.pack(fill="x", padx=6, pady=(0, 4))
        tk.Label(self._group_mgmt_frame, text=self.app.t('ui', 'group_schemes'), bg="#1a1a1a", fg="#888",
                 font=("Arial", 8, "bold")).pack(anchor="w", padx=4, pady=(2, 0))
        mgf = tk.Frame(self._group_mgmt_frame, bg="#1a1a1a")
        mgf.pack(fill="x", padx=4, pady=2)
        tk.Button(mgf, text=self.app.t('ui', 'group_create'), bg="#446644", fg="#99cc99",
                  bd=0, font=("Arial", 8), command=self._show_create_group_dialog
                  ).pack(side="left", fill="x", expand=True, padx=1)
        tk.Button(mgf, text=self.app.t('ui', 'group_join'), bg="#334455", fg="#99ccff",
                  bd=0, font=("Arial", 8), command=self._show_join_group_dialog
                  ).pack(side="left", fill="x", expand=True, padx=1)
        tk.Button(mgf, text=self.app.t('ui', 'group_manage'), bg="#444", fg="#ccc",
                  bd=0, font=("Arial", 8), command=self._show_manage_group_dialog
                  ).pack(side="left", fill="x", expand=True, padx=1)

        # Linked schemes list (populated by _refresh_linked_schemes_list)
        sep_linked = tk.Frame(self._group_mgmt_frame, bg="#333", height=1)
        sep_linked.pack(fill="x", padx=4, pady=(0, 2))
        self._linked_schemes_frame = tk.Frame(self._group_mgmt_frame, bg="#1a1a1a")
        self._linked_schemes_frame.pack(fill="x", padx=2, pady=(0, 2))

    def _refresh_linked_schemes_list(self):
        """Перебудовує список linked-схем у _group_mgmt_frame."""
        for w in self._linked_schemes_frame.winfo_children():
            w.destroy()
        painter = self.painter
        if not hasattr(painter, '_group_schemes') or not painter._group_schemes:
            self._adapt_palette_height()
            return
        active_group = getattr(self.app, "active_group_id", None)
        hidden = painter._hidden_download_schemes
        import config
        for drawing_id, scheme in list(painter._group_schemes.items()):
            if active_group and scheme.get("group_id") != active_group:
                continue
            map_id = scheme.get("map_id", "")
            map_name = config.MAP_NAMES_EN.get(map_id, map_id)
            updated = (scheme.get("updated_at") or "")[:10]
            sid = f"{scheme.get('group_id', '')}__{drawing_id}"
            is_hidden = sid in hidden

            row = tk.Frame(self._linked_schemes_frame, bg="#1a1a1a")
            row.pack(fill="x", pady=1)

            # Checkbox (show/hide)
            hide_var = tk.BooleanVar(value=not is_hidden)
            def toggle_hide_cb(s=sid, v=hide_var):
                if v.get():
                    hidden.discard(s)
                else:
                    hidden.add(s)
                self.app._save_group_schemes_to_cache()
            tk.Checkbutton(row, variable=hide_var, command=toggle_hide_cb,
                           bg="#1a1a1a", fg="white", selectcolor="#333",
                           activebackground="#1a1a1a").pack(side="left", padx=(4, 2))

            # Info
            label_text = f"{map_name}  {updated}"
            if is_hidden:
                label_text += " " + self.app.t('ui', 'hidden_scheme_label')
            tk.Label(row, text=label_text, bg="#1a1a1a", fg="#888" if is_hidden else "#aaa",
                     font=("Arial", 7), anchor="w").pack(side="left", padx=2, fill="x", expand=True)

        self._adapt_palette_height()

    def _adapt_palette_height(self):
        """Підганяє висоту палітри під поточний вміст."""
        self.update_idletasks()
        g = self.geometry()
        import re
        m = re.match(r'^(\d+)x(\d+)(.*)', g)
        if not m:
            return
        w, rest = m.group(1), m.group(3)
        target_h = self.winfo_reqheight()
        current_h = int(m.group(2))
        if abs(target_h - current_h) > 10:
            self.geometry(f"{w}x{target_h}{rest}")

    def _make_dark_header(self, parent, title):
        hdr = tk.Frame(parent, bg="#2a2a2a", height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=title, bg="#2a2a2a", fg="white",
                 font=("Arial", 9, "bold")).pack(side="left", padx=8)
        tk.Button(hdr, text="\u2715", bg="#2a2a2a", fg="#aaa", bd=0,
                  font=("Arial", 10), activebackground="#c33", activeforeground="white",
                  command=parent.destroy).pack(side="right", padx=4)
        return hdr

    def _show_create_group_dialog(self):
        if not firebase_identity.is_registered():
            dialog_utils.dark_messagebox(self.app.root, "Groups",
                                         "Please register first to create groups.")
            return
        import firebase_groups
        dlg = tk.Toplevel(self.app.root)
        dlg.configure(bg="#222")
        dlg.overrideredirect(True)
        dlg.resizable(False, False)
        dlg.transient(self.app.root)
        dlg.attributes("-topmost", True)
        dlg.lift()
        dlg.focus_force()

        hdr = self._make_dark_header(dlg, self.app.t('ui', 'group_create_header'))
        hdr.bind("<Button-1>", lambda e: None)
        dialog_utils._DragHelper(dlg, hdr)

        f = tk.Frame(dlg, bg="#222")
        f.pack(padx=24, pady=10)
        tk.Label(f, text=self.app.t('ui', 'group_create_name_label'), bg="#222", fg="#ccc", font=("Arial", 9),
                 anchor="e", width=10).grid(row=0, column=0, padx=(0, 8), pady=4, sticky="e")
        name_var = tk.StringVar()
        tk.Entry(f, textvariable=name_var, bg="#333", fg="white",
                 insertbackground="white", width=24, font=("Arial", 10)).grid(row=0, column=1, pady=4)
        tk.Label(f, text=self.app.t('ui', 'group_create_desc_label'), bg="#222", fg="#ccc", font=("Arial", 9),
                 anchor="e", width=10).grid(row=1, column=0, padx=(0, 8), pady=4, sticky="ne")
        desc_text = tk.Text(f, height=3, width=24, bg="#333", fg="white",
                            insertbackground="white", font=("Arial", 9), wrap="word")
        desc_text.grid(row=1, column=1, pady=4)

        status_var = tk.StringVar()
        tk.Label(dlg, textvariable=status_var, bg="#222", fg="#ff6666",
                 font=("Arial", 9), wraplength=300).pack(pady=(4, 0))

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(10, 14))

        def do_create():
            name = name_var.get().strip()
            desc = desc_text.get("1.0", "end-1c").strip()
            if not name:
                status_var.set(self.app.t('ui', 'group_name_required'))
                return
            gid, code = firebase_groups.create_group(name, desc)
            if gid:
                dlg.destroy()
                if hasattr(self.app, 'ui_mgr'):
                    self.app.ui_mgr._refresh_group_selector()
                self._refresh_linked_schemes_list()
                dialog_utils.dark_messagebox(self.app.root,
                    self.app.t('ui', 'group_created_title'),
                    self.app.t('ui', 'group_created_msg').format(name=name, code=code))
            else:
                status_var.set(code or self.app.t('ui', 'group_create_error'))

        tk.Button(bf, text=self.app.t('ui', 'btn_create'), bg="#446644", fg="#cfc", bd=0,
                  font=("Arial", 10, "bold"), padx=16, pady=4, command=do_create).pack(side="left", padx=6)
        tk.Button(bf, text=self.app.t('ui', 'btn_cancel'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 10), padx=16, pady=4, command=dlg.destroy).pack(side="left", padx=6)

        dialog_utils._center_on_root(dlg, self.app.root)
        dlg.grab_set()
        self.app.root.wait_window(dlg)

    def _show_join_group_dialog(self):
        if not firebase_identity.is_registered():
            dialog_utils.dark_messagebox(self.app.root,
                self.app.t('ui', 'group_placeholder_title'),
                self.app.t('ui', 'group_not_registered_msg'))
            return
        import firebase_groups
        dlg = tk.Toplevel(self.app.root)
        dlg.configure(bg="#222")
        dlg.overrideredirect(True)
        dlg.resizable(False, False)
        dlg.transient(self.app.root)
        dlg.attributes("-topmost", True)
        dlg.lift()
        dlg.focus_force()

        hdr = self._make_dark_header(dlg, self.app.t('ui', 'group_join_header'))
        dialog_utils._DragHelper(dlg, hdr)

        tk.Label(dlg, text=self.app.t('ui', 'group_join_code_label'), bg="#222", fg="#ccc",
                 font=("Arial", 9)).pack(padx=24, pady=(14, 4))

        code_var = tk.StringVar()
        code_entry = tk.Entry(dlg, textvariable=code_var, bg="#333", fg="white",
                              insertbackground="white", width=12, font=("Arial", 14, "bold"),
                              justify="center")
        code_entry.pack(padx=24, pady=6)
        code_entry.focus_set()

        status_var = tk.StringVar()
        tk.Label(dlg, textvariable=status_var, bg="#222", fg="#ff6666",
                 font=("Arial", 9), wraplength=300).pack(pady=(4, 0))

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(10, 14))

        def do_join():
            code = code_var.get().strip().upper()
            if len(code) < 3:
                status_var.set("Enter a valid invite code")
                return
            gid, name = firebase_groups.join_group(code)
            if gid:
                dlg.destroy()
                if hasattr(self.app, 'ui_mgr'):
                    self.app.ui_mgr._refresh_group_selector()
                self._refresh_linked_schemes_list()
                dialog_utils.dark_messagebox(self.app.root,
                    self.app.t('ui', 'group_joined_title'),
                    self.app.t('ui', 'group_joined_msg').format(name=name))
            else:
                status_var.set(name or self.app.t('ui', 'group_invalid_code_msg'))

        tk.Button(bf, text=self.app.t('ui', 'btn_join'), bg="#446688", fg="white", bd=0,
                  font=("Arial", 10, "bold"), padx=16, pady=4, command=do_join).pack(side="left", padx=6)
        tk.Button(bf, text=self.app.t('ui', 'btn_cancel'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 10), padx=16, pady=4, command=dlg.destroy).pack(side="left", padx=6)

        code_entry.bind("<Return>", lambda e: do_join())
        dialog_utils._center_on_root(dlg, self.app.root)
        dlg.grab_set()
        self.app.root.wait_window(dlg)

    def _show_manage_group_dialog(self):
        import firebase_groups
        if not firebase_identity.is_registered():
            return
        identity = firebase_identity.get_identity()
        if not identity:
            return
        uid = identity.get("user_id", "")

        active_id = getattr(self.app, "active_group_id", None)
        if not active_id or active_id == firebase_groups.PUBLIC_GROUP_ID:
            dialog_utils.dark_messagebox(self.app.root,
                self.app.t('ui', 'group_placeholder_title'),
                self.app.t('ui', 'group_manage_closed_msg'))
            return

        groups = getattr(self.app, "_cached_groups", {})
        ginfo = groups.get(active_id, {})
        my_role = ginfo.get("role", "") if isinstance(ginfo, dict) else ""
        if my_role != "officer":
            dialog_utils.dark_messagebox(self.app.root,
                self.app.t('ui', 'group_placeholder_title'),
                self.app.t('ui', 'group_manage_officer_msg'))
            return

        group_data = firebase_groups.get_group_info(active_id)
        if not group_data:
            dialog_utils.dark_messagebox(self.app.root,
                self.app.t('ui', 'group_placeholder_title'),
                self.app.t('ui', 'group_manage_no_info_msg'))
            return

        import copy
        members = copy.deepcopy(group_data.get("members", {}))
        invite_code = group_data.get("invite_code", "N/A")
        group_name = group_data.get("name", "?")
        group_desc = group_data.get("description", "")

        dlg = tk.Toplevel(self.app.root)
        dlg.configure(bg="#222")
        dlg.overrideredirect(True)
        dlg.resizable(False, False)
        dlg.transient(self.app.root)
        dlg.attributes("-topmost", True)
        dlg.lift()
        dlg.focus_force()

        hdr = self._make_dark_header(dlg, self.app.t('ui', 'group_manage_header').format(name=group_name))
        dialog_utils._DragHelper(dlg, hdr)

        if group_desc:
            tk.Label(dlg, text=group_desc, bg="#222", fg="#888",
                     font=("Arial", 8)).pack(pady=(2, 4))

        icf = tk.Frame(dlg, bg="#222")
        icf.pack(pady=(2, 4))
        invite_lbl = tk.Label(icf, text=f"{self.app.t('ui', 'group_invite_code_label')} {invite_code}", bg="#222", fg="#ffaa00",
                 font=("Arial", 10, "bold"), cursor="hand2")
        invite_lbl.pack(side="left", padx=(0, 8))
        def _copy_invite(event=None):
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(invite_code)
            popup = tk.Toplevel(self.app.root)
            popup.overrideredirect(True)
            popup.configure(bg="#222")
            popup.attributes("-topmost", True)
            tk.Label(popup, text=self.app.t('ui', 'copied_to_clipboard'), bg="#222", fg="#4c4",
                     font=("Arial", 9, "bold")).pack(padx=16, pady=8)
            popup.update_idletasks()
            px = invite_lbl.winfo_rootx() + invite_lbl.winfo_width()//2 - popup.winfo_reqwidth()//2
            py = invite_lbl.winfo_rooty() + invite_lbl.winfo_height()//2 - popup.winfo_reqheight()//2
            popup.geometry(f"+{px}+{py}")
            popup.lift()
            popup.grab_set()
            self.after(2000, lambda: (popup.grab_release(), popup.destroy()))
        invite_lbl.bind("<Button-1>", _copy_invite)

        tk.Label(dlg, text=self.app.t('ui', 'group_members_label'), bg="#222", fg="#ccc",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=(8, 2))

        mf = tk.Frame(dlg, bg="#222")
        mf.pack(padx=20, fill="x")

        for muid, minfo in members.items():
            if not isinstance(minfo, dict):
                continue
            mname = minfo.get("nickname", "?")
            mrole = minfo.get("role", "member")
            is_creator = (muid == uid)
            row = tk.Frame(mf, bg="#1a1a1a")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=mname, bg="#1a1a1a", fg="white",
                     font=("Arial", 9)).pack(side="left", padx=8, pady=3)
            role_lbl = self.app.t('ui', 'group_officer_label') if mrole == "officer" else ""
            if role_lbl:
                tk.Label(row, text=role_lbl, bg="#1a1a1a", fg="#ffaa00",
                         font=("Arial", 8, "bold")).pack(side="left", padx=4)

            if not is_creator:
                def on_kick(muid=muid):
                    firebase_groups.leave_group(active_id, muid)
                    row.destroy()
                tk.Button(row, text=self.app.t('ui', 'btn_remove'), bg="#553333", fg="#cc9999",
                          bd=0, font=("Arial", 7), padx=6,
                          command=on_kick).pack(side="right", padx=4, pady=2)

        # ═══ Group Schemes section ═══
        tk.Label(dlg, text=self.app.t('ui', 'group_schemes_section_label'),
                 bg="#222", fg="#ccc", font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=(10, 2))

        sf = tk.Frame(dlg, bg="#222")
        sf.pack(padx=20, fill="x")

        group_schemes = firebase_groups.get_group_schemes(active_id)
        if group_schemes:
            for sid, sdata in sorted(group_schemes.items(),
                                     key=lambda x: x[1].get("updated_at", ""), reverse=True):
                if not isinstance(sdata, dict):
                    continue
                row = tk.Frame(sf, bg="#1a1a1a")
                row.pack(fill="x", pady=1)
                mid = sdata.get("map_id", "?")
                mname = sdata.get("map_name", "")
                comment = (sdata.get("comment") or "")[:30]
                updated = (sdata.get("updated_at") or "")[:10]
                info = f"{mname or mid}  |  {updated}"
                if comment:
                    info += f"  —  {comment}"
                tk.Label(row, text=info, bg="#1a1a1a", fg="#aaa",
                         font=("Arial", 8), anchor="w").pack(side="left", padx=8, pady=3, fill="x", expand=True)

                def on_delete_scheme(sid=sid):
                    yes = dialog_utils.dark_confirmbox(dlg,
                        self.app.t('ui', 'group_scheme_delete_confirm'),
                        f"{mname or mid}: {sdata.get('comment', '')[:40] or '?'}")
                    if yes:
                        firebase_groups.delete_group_scheme(active_id, sid)
                        firebase_groups.invalidate_group_schemes_cache(active_id)
                        row.destroy()
                        if not any(c.winfo_children() for c in (sf,)):
                            no_schemes_lbl = tk.Label(sf, text="—", bg="#222", fg="#555",
                                                       font=("Arial", 8))
                            no_schemes_lbl.pack(pady=2)

                tk.Button(row, text=self.app.t('ui', 'btn_remove'), bg="#553333", fg="#cc9999",
                          bd=0, font=("Arial", 7), padx=6,
                          command=on_delete_scheme).pack(side="right", padx=4, pady=2)
        else:
            tk.Label(sf, text="—", bg="#222", fg="#555",
                     font=("Arial", 8)).pack(pady=2)

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(12, 14))

        def _delete_group():
            yes = dialog_utils.dark_confirmbox(dlg,
                self.app.t('ui', 'group_delete_confirm_title'),
                self.app.t('ui', 'group_delete_confirm_msg').format(name=group_name))
            if not yes:
                return
            firebase_groups.delete_group(active_id)
            dlg.destroy()
            if hasattr(self.app, 'ui_mgr'):
                self.app.ui_mgr._refresh_group_selector()
            self._refresh_linked_schemes_list()
            self.app._stop_group_sync()
            self.app.active_group_id = firebase_groups.PUBLIC_GROUP_ID
            self.app.ui_mgr._on_group_select()

        tk.Button(bf, text=self.app.t('ui', 'btn_delete_group'), bg="#553333", fg="#cc9999",
                  bd=0, font=("Arial", 9), padx=10, pady=3,
                  command=_delete_group).pack(side="left", padx=4)
        tk.Button(bf, text=self.app.t('ui', 'btn_close'), bg="#444", fg="#aaa",
                  bd=0, font=("Arial", 9), padx=10, pady=3,
                  command=dlg.destroy).pack(side="left", padx=4)

        dialog_utils._center_on_root(dlg, self.app.root)
        dlg.grab_set()
        self.app.root.wait_window(dlg)

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
        if code in ("arrow", "brush"):
            self.painter.set_tool(code)
        elif code == "marker":
            self.painter.set_tool("marker")
        else:
            self.painter.set_tool("text")
        maker_like = ("marker", "arrow", "brush")
        self.current_color = "#ffaa00" if code in maker_like else "#00ff00"
        self._color_preview.config(fg=self.current_color)
        self._update_color_buttons()
        if code == "brush":
            self._brush_frame.pack(fill="x", before=self._sep4)
        else:
            self._brush_frame.pack_forget()

    def _deactivate_tool(self):
        self._active_tool_code = None
        self._update_toolbar_buttons()
        self.painter.set_tool(None)
        self._brush_frame.pack_forget()

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
            po = self.app._po_win if hasattr(self.app, '_po_win') else self.app.root
            self.lift(aboveThis=po)
        except:
            pass

    def _on_thickness_change(self, *args):
        self.painter._thickness = self._thickness_var.get()
        if self._apply_all_var.get():
            self.painter.apply_thickness_to_all(self._thickness_var.get())
        elif self._edit_obj:
            self._on_any_change()

    def _on_any_change(self, *args):
        if getattr(self, '_loading_obj', False):
            return
        self._lift_self()
        if self._edit_obj:
            self._write_to_object(self._edit_obj)
            self.painter.redraw()
            self.painter.save_drawings()

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
        active_group = getattr(self.app, 'active_group_id', firebase_groups.PUBLIC_GROUP_ID)
        groups = getattr(self.app, '_cached_groups', {})
        ginfo = groups.get(active_group, {})
        group_name = ginfo.get("name", "Public") if isinstance(ginfo, dict) else "Public"

        if active_group == firebase_groups.PUBLIC_GROUP_ID:
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
        else:
            my_role = ginfo.get("role", "") if isinstance(ginfo, dict) else ""
            if my_role != "officer":
                self._show_custom_message(
                    self.app.t('ui', 'publish_map'),
                    "Only officer can publish to this group.")
                return
            map_name = config.MAP_NAMES_EN.get(self.app.current_map_eng, self.app.current_map_eng)
            def on_map_group():
                self._hide_choice_inline()
                self._publish_to_group()
            def on_all_group():
                self._hide_choice_inline()
                self._publish_all_to_group()
            self._show_choice_inline(
                f"Publish to group \"{group_name}\":",
                map_name, on_map_group,
                self.app.t('ui', 'publish_all'), on_all_group)

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
        title = self.app.t('ui', 'publish_map') if count == 0 else self.app.t('ui', 'publish_all')
        dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, title)
        dialog_utils._DragHelper(dlg, hdr)
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
                        err_lbl.config(text=self.app.t('ui', 'publish_duplicate_error'))
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

    def _publish_to_group(self):
        """Публікує поточну мапу в активну групу (upsert — якщо схема для цієї мапи вже є, оновлює)."""
        self._lift_self()
        if not firebase_identity.is_registered():
            self._show_custom_message(
                self.app.t('ui', 'publish_map'),
                self.app.t('ui', 'publish_register_first'))
            return
        active_group = getattr(self.app, 'active_group_id', None)
        if not active_group or active_group == firebase_groups.PUBLIC_GROUP_ID:
            self._show_custom_message("Publish", "Select a closed group in the group bar first.")
            return
        if not self.app.current_map_eng:
            return
        drawings = self.painter.drawings.get(self.app.current_map_eng, [])
        if not drawings:
            self._show_custom_message(
                self.app.t('ui', 'publish_map'),
                self.app.t('ui', 'publish_no_drawings'))
            return

        groups = getattr(self.app, '_cached_groups', {})
        ginfo = groups.get(active_group, {})
        group_name = ginfo.get("name", "?") if isinstance(ginfo, dict) else "?"

        # Role check (safety guard)
        my_role = ginfo.get("role", "") if isinstance(ginfo, dict) else ""
        if my_role != "officer":
            self._show_custom_message(
                self.app.t('ui', 'publish_map'),
                "Only officer can publish.")
            return

        import config
        map_name = config.MAP_NAMES_EN.get(self.app.current_map_eng, self.app.current_map_eng)

        # Upsert: check if a scheme for this map already exists in the group
        group_schemes = firebase_groups.get_group_schemes(active_group)
        existing_drawing_id = None
        for sid, sdata in group_schemes.items():
            if sdata.get("map_id") == self.app.current_map_eng:
                existing_drawing_id = sid
                break

        import time
        if existing_drawing_id:
            ok, msg = firebase_groups.update_group_scheme(
                active_group, existing_drawing_id, elements_data=drawings, comment="")
            if ok:
                self.painter._group_schemes[existing_drawing_id] = {
                    "drawing_id": existing_drawing_id,
                    "group_id": active_group,
                    "map_id": self.app.current_map_eng,
                    "map_name": map_name,
                    "elements": list(drawings),
                    "comment": "",
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "_synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.app._save_group_schemes_to_cache()
                self._refresh_linked_schemes_list()
                self.after(0, lambda: self._show_custom_message(
                    "Publish", f"Updated scheme for \"{group_name}\"!"))
            else:
                self.after(0, lambda: self._show_custom_message(
                    "Publish Error", msg, is_error=True))
        else:
            drawing_id, ok, msg = firebase_groups.publish_to_group(
                group_id=active_group,
                map_id=self.app.current_map_eng,
                map_name=map_name,
                elements_data=drawings,
                comment="",
            )
            if ok and drawing_id:
                self.painter._group_schemes[drawing_id] = {
                    "drawing_id": drawing_id,
                    "group_id": active_group,
                    "map_id": self.app.current_map_eng,
                    "map_name": map_name,
                    "elements": list(drawings),
                    "comment": "",
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "_synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.app._save_group_schemes_to_cache()
                self._refresh_linked_schemes_list()
                self.after(0, lambda: self._show_custom_message(
                    "Publish", f"Published to \"{group_name}\"!"))
            else:
                self.after(0, lambda: self._show_custom_message(
                    "Publish Error", msg, is_error=True))

    def _publish_all_to_group(self):
        """Публікує всі мапи з малюнками в активну групу (upsert per map)."""
        self._lift_self()
        if not firebase_identity.is_registered():
            self._show_custom_message(
                self.app.t('ui', 'publish_all'),
                self.app.t('ui', 'publish_register_first'))
            return
        active_group = getattr(self.app, 'active_group_id', None)
        if not active_group or active_group == firebase_groups.PUBLIC_GROUP_ID:
            self._show_custom_message("Publish", "Select a closed group first.")
            return

        maps_with = {k: v for k, v in self.painter.drawings.items()
                     if isinstance(v, list) and len(v) > 0}
        if not maps_with:
            self._show_custom_message(
                self.app.t('ui', 'publish_all'),
                self.app.t('ui', 'publish_no_drawings_all'))
            return

        groups = getattr(self.app, '_cached_groups', {})
        ginfo = groups.get(active_group, {})
        # Role check (safety guard)
        my_role = ginfo.get("role", "") if isinstance(ginfo, dict) else ""
        if my_role != "officer":
            self._show_custom_message(
                self.app.t('ui', 'publish_all'),
                "Only officer can publish.")
            return

        group_name = ginfo.get("name", "?") if isinstance(ginfo, dict) else "?"

        import config
        ok_count = 0
        err_count = 0
        import time

        # Fetch existing schemes once for upsert
        existing_group_schemes = firebase_groups.get_group_schemes(active_group)
        scheme_by_map = {}
        for sid, sdata in existing_group_schemes.items():
            scheme_by_map[sdata.get("map_id")] = sid

        for map_id, elements in maps_with.items():
            map_name = config.MAP_NAMES_EN.get(map_id, map_id)
            existing_id = scheme_by_map.get(map_id)
            if existing_id:
                ok, _ = firebase_groups.update_group_scheme(
                    active_group, existing_id, elements_data=elements, comment="")
                if ok:
                    ok_count += 1
                    self.painter._group_schemes[existing_id] = {
                        "drawing_id": existing_id,
                        "group_id": active_group,
                        "map_id": map_id,
                        "map_name": map_name,
                        "elements": list(elements),
                        "comment": "",
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "_synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                else:
                    err_count += 1
            else:
                drawing_id, ok, _ = firebase_groups.publish_to_group(
                    group_id=active_group,
                    map_id=map_id,
                    map_name=map_name,
                    elements_data=elements,
                    comment="",
                )
                if ok:
                    ok_count += 1
                    if drawing_id:
                        self.painter._group_schemes[drawing_id] = {
                            "drawing_id": drawing_id,
                            "group_id": active_group,
                            "map_id": map_id,
                            "map_name": map_name,
                            "elements": list(elements),
                            "comment": "",
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "_synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                else:
                    err_count += 1

        if ok_count > 0:
            self.app._save_group_schemes_to_cache()
            self._refresh_linked_schemes_list()

        self._show_publish_all_result({
            "ok": ok_count,
            "errors": err_count,
            "total": len(maps_with),
        })

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
        dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, title)
        dialog_utils._DragHelper(dlg, hdr)
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
        po = self.app._po_win if hasattr(self.app, '_po_win') else self.app.root
        self.lift(aboveThis=po)
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
            self._palette_compact_geo = None
        elif active == "marker":
            self._active_tool_code = "marker"
        elif active == "arrow":
            self._active_tool_code = "arrow"
        elif active == "brush":
            self._active_tool_code = "brush"
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
            self.geometry(f"580x520+{px}+{py}")
            self._saved_pos = f"580x520+{px}+{py}"
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
            self._thickness_var.set(obj.get("thickness", 3))
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
            elif obj["type"] == "arrow":
                self._highlight_toolbar_button("arrow")
            elif obj["type"] == "brush":
                self._highlight_toolbar_button("brush")
            else:
                self._highlight_toolbar_button("marker")
            self.painter.set_tool(None)
            self._del_btn.config(state="normal", bg="#cc3333", fg="white")
            if obj["type"] == "marker":
                label = self.app.t('ui', 'status_editing_marker')
            elif obj["type"] == "arrow":
                label = self.app.t('ui', 'status_editing_arrow')
            elif obj["type"] == "brush":
                label = self.app.t('ui', 'status_editing_brush')
                self._arrow_start_var.set(obj.get("arrow_start", False))
                self._arrow_end_var.set(obj.get("arrow_end", False))
                self._brush_frame.pack(fill="x", before=self._sep4)
            else:
                label = self.app.t('ui', 'status_editing_text')
            self._status_lbl.config(text=f"{label}")
        finally:
            self._loading_obj = False

    def exit_edit_mode(self):
        if self._edit_obj is None:
            return
        self._write_to_object(self._edit_obj)
        self.painter.redraw()
        self.painter.save_drawings()
        self._edit_obj = None
        self.painter._editing_idx = -1
        self._active_tool_code = None
        self._update_toolbar_buttons()
        self.painter.set_tool(None)
        self._del_btn.config(state="disabled", bg="#555555", fg="#888888")
        self._brush_frame.pack_forget()
        self._status_lbl.config(text="")

    def _write_to_object(self, obj):
        obj["modes"] = [k for k, v in self.mode_vars.items() if v.get()]
        obj["classes"] = [k for k, v in self.class_vars.items() if v.get()]
        obj["text"] = self.text_var.get()
        obj["color"] = self.current_color
        obj["thickness"] = self._thickness_var.get()
        if obj.get("type") == "text":
            if self._active_tool_code == "tree":
                obj["poi"] = ["tree"]
            elif isinstance(self._active_tool_code, int):
                obj["poi"] = [self._active_tool_code]
            else:
                obj["poi"] = []
        elif obj.get("type") == "brush":
            obj["arrow_start"] = self._arrow_start_var.get()
            obj["arrow_end"] = self._arrow_end_var.get()
        elif obj.get("type") in ("marker", "arrow"):
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
        if obj.get("type") == "brush":
            pass
        elif obj.get("type") in ("marker", "arrow"):
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
        self._hide_choice_inline()
        self._download_result = None
        for w in self._download_frame.winfo_children():
            w.destroy()
        self._download_frame.pack(fill="both", expand=True, padx=6, pady=4, before=self._status_lbl)
        try:
            self._palette_compact_geo = self.geometry()
        except Exception:
            self._palette_compact_geo = None
        self.geometry("580x780")
        bg = "#222"
        tk.Label(self._download_frame, text=self.app.t('ui', 'download_loading'),
                 bg=bg, fg="#888", font=("Arial", 9)).pack(padx=10, pady=10)
        import threading
        t = threading.Thread(target=self._download_populate, daemon=True)
        t.start()

    def _hide_download_inline(self):
        self._download_frame.pack_forget()
        if self._palette_compact_geo:
            try:
                self.geometry(self._palette_compact_geo)
            except Exception:
                pass

    def _download_populate(self):
        try:
            schemes = {}
            public = firebase_drawings.get_all_schemes()
            for sid, sdata in public.items():
                sdata["_source"] = "public"
                schemes[sid] = sdata

            user_groups = firebase_groups.get_user_groups()
            for gid in user_groups:
                if gid == firebase_groups.PUBLIC_GROUP_ID:
                    continue
                group_schemes = firebase_groups.get_group_schemes(gid)
                for sid, sdata in group_schemes.items():
                    sdata["_source"] = gid
                    schemes[f"{gid}__{sid}"] = sdata
        except Exception as e:
            print(f"[PALETTE] Download populate error: {e}")
            schemes = {}
        self.after(0, lambda: self._build_download_ui(schemes))

    def _build_download_ui(self, schemes):
        bg = "#222"
        for w in self._download_frame.winfo_children():
            w.destroy()

        if not schemes:
            tk.Label(self._download_frame, text=self.app.t('ui', 'download_no_schemes'),
                     bg=bg, fg="#ff6666", font=("Arial", 9)).pack(padx=20, pady=20)
            tk.Button(self._download_frame, text="OK", bg="#444", fg="white", bd=0,
                      font=("Arial", 9), command=self._hide_download_inline).pack(pady=(0, 12))
            return

        groups = getattr(self.app, '_cached_groups', {})
        group_names = {firebase_groups.PUBLIC_GROUP_ID: "Public"}
        for gid, ginfo in groups.items():
            if isinstance(ginfo, dict):
                group_names[gid] = ginfo.get("name", gid)
            else:
                group_names[gid] = gid

        items = []
        for sid, data in schemes.items():
            map_id = data.get("map_id", "")
            map_name = data.get("map_name", "")
            author = data.get("author_nickname", "")
            created = (data.get("created_at") or "")[:10]
            el_count = data.get("element_count", 0)
            comment = (data.get("comment") or "")[:40]
            source = data.get("_source", "public")
            source_name = group_names.get(source, source)
            items.append({
                "scheme_id": sid,
                "map_id": map_id,
                "map_name": map_name,
                "author": author,
                "created": created,
                "comment": comment,
                "el_count": el_count,
                "elements": data.get("elements", []),
                "source": source,
                "source_name": source_name,
                "author_user_id": data.get("author_id", ""),
            })

        items.sort(key=lambda x: x.get("created", ""), reverse=True)

        unique_maps = sorted(set(it["map_name"] for it in items if it["map_name"]))
        unique_authors = sorted(set(it["author"] for it in items if it["author"]))
        unique_sources = sorted(set(it["source_name"] for it in items if it["source_name"]))
        pub_label = group_names.get(firebase_groups.PUBLIC_GROUP_ID, "Public")
        if pub_label not in unique_sources:
            unique_sources.insert(0, pub_label)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1a1a1a", foreground="#cccccc",
                        fieldbackground="#1a1a1a", bordercolor="#333", arrowcolor="#888")
        style.configure("Treeview.Heading", background="#1a1a1a", foreground="#aaa",
                        fieldbackground="#1a1a1a", borderwidth=1, relief="solid",
                        bordercolor="#000", lightcolor="#000", darkcolor="#000",
                        padding=(4, 2))
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

        ff = tk.Frame(self._download_frame, bg=bg)
        ff.pack(fill="x", padx=8, pady=(6, 2))

        t_ = self.app.t

        tk.Label(ff, text=t_('ui', 'download_filter_map') + ":", bg=bg, fg="#aaa", font=("Arial", 8, "bold")).pack(side="left", padx=(0, 2))
        map_filter_var = tk.StringVar(value=all_label)
        map_filter_cb = tk.ttk.Combobox(ff, textvariable=map_filter_var,
                                         values=[all_label] + unique_maps,
                                         state="readonly", width=18, font=("Arial", 8))
        map_filter_cb.pack(side="left", padx=4)
        map_filter_var.trace("w", lambda *a: _do_filter())

        tk.Label(ff, text=t_('ui', 'download_filter_author') + ":", bg=bg, fg="#aaa", font=("Arial", 8, "bold")).pack(side="left", padx=(8, 2))
        author_filter_var = tk.StringVar(value=all_label)
        author_filter_cb = tk.ttk.Combobox(ff, textvariable=author_filter_var,
                                              values=[all_label] + unique_authors,
                                              state="readonly", width=14, font=("Arial", 8))
        author_filter_cb.pack(side="left", padx=4)
        author_filter_var.trace("w", lambda *a: _do_filter())

        # ── Second filter row: search only ──
        ff2 = tk.Frame(self._download_frame, bg=bg)
        ff2.pack(fill="x", padx=8, pady=(0, 2))

        tk.Label(ff2, text="\U0001F50D", bg=bg, fg="#888", font=("Arial", 9)).pack(side="left", padx=(0, 4))
        search_var = tk.StringVar()
        search_entry = tk.ttk.Entry(ff2, textvariable=search_var, font=("Arial", 8), width=24)
        search_entry.pack(side="left", padx=(0, 8))
        search_var.trace("w", lambda *a: _do_filter())

        tf = tk.Frame(self._download_frame, bg=bg)
        tf.pack(fill="both", expand=True, padx=8, pady=4)

        columns = ("map", "comment", "author", "date", "preview")
        tree = tk.ttk.Treeview(tf, columns=columns, show="tree headings",
                                height=7, selectmode="browse")
        tree.heading("#0", text="")
        tree.heading("map", text=t_('ui', 'download_col_map'))
        tree.heading("comment", text=t_('ui', 'download_col_comment'))
        tree.heading("author", text=t_('ui', 'download_col_author'))
        tree.heading("date", text=t_('ui', 'download_col_date'))
        tree.heading("preview", text="")
        tree.column("#0", width=30, anchor="center", minwidth=30, stretch=False)
        tree.column("map", width=110)
        tree.column("comment", width=160)
        tree.column("author", width=85)
        tree.column("date", width=70)
        tree.column("preview", width=40, anchor="center")

        vsb = tk.ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        check_vars = {}

        def _do_filter(*args):
            mf = map_filter_var.get()
            af = author_filter_var.get()
            search_text = search_var.get().strip().lower()
            tree.delete(*tree.get_children())
            for it in items:
                if mf != all_label and it["map_name"] != mf:
                    continue
                if af != all_label and it["author"] != af:
                    continue
                if search_text:
                    haystack = f"{it['map_name']} {it['author']} {it['comment']} {it['source_name']}".lower()
                    if search_text not in haystack:
                        continue
                sid = it["scheme_id"]
                is_all = it["map_id"] == "all_maps"
                if sid not in check_vars:
                    check_vars[sid] = tk.BooleanVar(value=False)
                cb_state = "" if not is_all else "disabled"
                has_preview = not is_all
                tree.insert("", "end",
                            text="☐" if not is_all else "",
                            values=(it["map_name"], it["comment"],
                                    it["author"], it["created"],
                                    "Preview" if has_preview else ""),
                            iid=sid, tags=(cb_state,))

        def _toggle_check(event):
            row = tree.identify_row(event.y)
            if not row:
                return
            it = None
            for x in items:
                if x["scheme_id"] == row:
                    it = x
                    break
            if not it:
                return
            region = tree.identify_region(event.x, event.y)
            if region == "tree":
                if it["map_id"] == "all_maps":
                    return
                var = check_vars[row]
                var.set(not var.get())
                tree.item(row, text="☑" if var.get() else "☐")
            elif region == "cell":
                col = tree.identify_column(event.x)
                if col == "#5":
                    self._preview_scheme(it, self._download_frame)

        tree.bind("<ButtonRelease-1>", _toggle_check)

        self._preview_tree = tree

        bf = tk.Frame(self._download_frame, bg=bg)
        bf.pack(fill="x", padx=8, pady=(0, 8))

        def on_download():
            checked = [it for it in items if check_vars.get(it["scheme_id"], tk.BooleanVar(value=False)).get()]
            if not checked:
                sel = tree.selection()
                if sel:
                    checked = [it for it in items if it["scheme_id"] in sel]
            if not checked:
                return
            self._download_result = checked
            self._hide_download_inline()
            for cit in checked:
                self._handle_download_result(cit)
            self._show_custom_message(
                "Download",
                f"Downloaded {len(checked)} scheme(s).")

        def on_cancel():
            self._download_result = None
            self._hide_download_inline()

        tk.Button(bf, text="Cancel", bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=12, pady=4, command=on_cancel).pack(side="right", padx=2)
        tk.Button(bf, text="Download", bg="#446688", fg="white", bd=0,
                  font=("Arial", 9, "bold"), padx=12, pady=4, command=on_download).pack(side="right", padx=2)

        _do_filter()

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

        source = item.get("source", "public")
        is_group_scheme = (source != "public")

        choice = self._choose_download_action(map_name, is_all_maps, is_group_scheme)
        if choice is None:
            return

        if choice == "link" and is_group_scheme:
            drawing_id = item.get("scheme_id", "")
            if "__" in drawing_id:
                drawing_id = drawing_id.split("__", 1)[1]
            group_scheme = {
                "drawing_id": drawing_id,
                "group_id": source,
                "map_id": map_id,
                "map_name": item.get("map_name", map_id),
                "elements": elements,
                "comment": item.get("comment", ""),
                "updated_at": item.get("updated_at", ""),
                "_synced_at": item.get("updated_at", ""),
            }
            painter._group_schemes[drawing_id] = group_scheme
            painter._scheme_downloaded_at[drawing_id] = item.get("updated_at", "")
            self.app._save_group_schemes_to_cache()
            self._show_custom_message(
                "Download", f"Scheme linked to group '{item.get('source_name', source)}'.\nIt will auto-sync.")
            painter.redraw()
            self._refresh_linked_schemes_list()
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

    def _choose_download_action(self, map_name, is_all_maps, is_group_scheme=False):
        """Show choice dialog for download action. Returns 'replace', 'add', 'save_pc', 'link' or None."""
        dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, self.app.t('ui', 'download_confirm_title'))
        dialog_utils._DragHelper(dlg, hdr)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()

        tk.Label(dlg, text=self.app.t('ui', 'download_confirm_title'),
                 bg="#222", fg="#ffaa00", font=("Arial", 10, "bold")).pack(padx=20, pady=(14, 6))
        tk.Label(dlg, text=f" {map_name}",
                 bg="#222", fg="#cccccc", font=("Arial", 9), wraplength=360).pack(padx=20, pady=(0, 4))
        if is_group_scheme:
            tk.Label(dlg, text=self.app.t('ui', 'group_scheme_link'),
                     bg="#222", fg="#ffaa00", font=("Arial", 8)).pack(padx=20, pady=(0, 4))
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

        def on_link():
            result[0] = "link"
            dlg.destroy()

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(0, 12))
        tk.Button(bf, text=self.app.t('ui', 'download_replace'), bg="#556677", fg="white", bd=0,
                  font=("Arial", 9), padx=12, pady=4, command=on_replace).pack(side="left", padx=4)
        if is_group_scheme:
            tk.Button(bf, text="Link (sync)", bg="#557755", fg="#cfc", bd=0,
                      font=("Arial", 9, "bold"), padx=12, pady=4, command=on_link).pack(side="left", padx=4)
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
        pv.configure(bg="#111")
        pv.overrideredirect(True)
        pv.resizable(False, False)
        pv.transient(parent_dlg)
        pv.attributes("-topmost", True)
        pv.lift()
        pv.focus_force()

        hdr = tk.Frame(pv, bg="#2a2a2a", height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"Preview: {item['map_name']}", bg="#2a2a2a", fg="white",
                 font=("Arial", 9, "bold")).pack(side="left", padx=8)
        tk.Button(hdr, text="\u2715", bg="#2a2a2a", fg="#aaa", bd=0,
                  font=("Arial", 10), activebackground="#c33", activeforeground="white",
                  command=pv.destroy).pack(side="right", padx=4)

        class _DragHelper:
            def __init__(self, toplevel, frame):
                self.tl = toplevel; self.x = 0; self.y = 0
                frame.bind("<Button-1>", self.start)
                frame.bind("<B1-Motion>", self.drag)
            def start(self, e):
                self.x = e.x_root - self.tl.winfo_rootx()
                self.y = e.y_root - self.tl.winfo_rooty()
            def drag(self, e):
                self.tl.geometry(f"+{e.x_root - self.x}+{e.y_root - self.y}")
        _DragHelper(pv, hdr)

        pv.update_idletasks()
        cv_frame = tk.Frame(pv, bg="#111")
        cv_frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(cv_frame, width=pw, height=ph, bg="#111", highlightthickness=0)
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

        # Render elements on preview canvas with correct offset
        if isinstance(elements, list):
            map_id_cur = self.app.current_map_eng
            painter = self.app.painter
            if painter:
                painter._render_elements(canvas, elements, pw, ph,
                    offset_x=cx, offset_y=cy, img_w=new_w, img_h=new_h)

        tk.Button(pv, text="Close", bg="#444", fg="white", bd=0,
                  font=("Arial", 9), command=pv.destroy).pack(pady=4)

        self._center_on_root(pv)

    def is_in_edit_mode(self):
        return self._edit_obj is not None

    def has_any_tool_active(self):
        return self._active_tool_code is not None
