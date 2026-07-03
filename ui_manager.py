import os
import webbrowser
import tkinter as tk
from tkinter import ttk
import config
import stats_ai
import firebase_identity
import language_module
import dialog_utils

class UIManager:
    def __init__(self, app):
        self.app = app
        self.root = app.root

    def setup_ui(self):
        self.app.top_bar = tk.Frame(self.app.root, bg="#222")
        self.app.top_bar.pack(side="top", fill="x")

        # Right side buttons in top_bar (span both rows)
        tk.Frame(self.app.top_bar, width=7, bg="#222").pack(side="right")

        self.app.btn_format_lock = tk.Button(self.app.top_bar, text=chr(0xF023),
            font=("FontAwesome", 11), bg="#444", fg="#bbbbbb", bd=0, width=3, padx=2,
            command=self.app.toggle_formatting_mode)

        tk.Button(self.app.top_bar, text=chr(0xF00D), bg="#800", fg="white", bd=0,
                  width=3, padx=2, font=("FontAwesome", 11),
                  command=self.app.quit_app).pack(side="right", pady=2)

        tk.Button(self.app.top_bar, text=chr(0xF068), bg="#444", fg="white", bd=0,
                  width=3, padx=2, font=("FontAwesome", 11),
                  command=self.app.toggle_visibility).pack(side="right", pady=2)

        self.app.settings_btn = tk.Button(self.app.top_bar, text=chr(0xF013), bg="#333", fg="white",
                                           bd=0, width=3, padx=2, font=("FontAwesome", 11),
                                           command=self._show_settings_menu)
        self.app.settings_btn.pack(side="right", padx=5, pady=2)

        self.app.btn_format_lock.pack(side="right", padx=(1,5), pady=2)

        # Left button frame spans full height (mode buttons expand with second_row)
        btn_frame = tk.Frame(self.app.top_bar, bg="#222")
        btn_frame.pack(side="left", fill="y")

        tk.Frame(btn_frame, width=7, bg="#222").pack(side="left", fill="y")

        self.app.btn_mode_ai_stats = tk.Button(btn_frame, text="SETUP", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=self.app.switch_to_ai_stats)
        self.app.btn_mode_ai_stats.pack(side="left", padx=(0, 1), pady=2)

        self.app.btn_mode_maps_2 = tk.Button(btn_frame, text="MAPS", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=lambda: self.app.switch_to_maps(2))
        self.app.btn_mode_maps_2.pack(side="left", padx=1, pady=2)

        self.app.btn_mode_maps_1 = tk.Button(btn_frame, text="TACTIC", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=lambda: self.app.switch_to_maps(1))
        self.app.btn_mode_maps_1.pack(side="left", padx=(1, 0), pady=2)

        # Content frame for horizontal space between mode buttons and right buttons
        content_frame = tk.Frame(self.app.top_bar, bg="#222")
        content_frame.pack(side="left", fill="both", expand=True)

        # Top row: map toolbar
        top_row = tk.Frame(content_frame, bg="#222")
        top_row.pack(side="top", fill="x")

        self.app.map_toolbar = tk.Frame(top_row, bg="#222")
        self.app.map_var = tk.StringVar()
        self.app.map_selector = ttk.Combobox(self.app.map_toolbar, textvariable=self.app.map_var, state="readonly", width=15, postcommand=self.app._combo_postcommand)
        self.app.map_selector.bind("<<ComboboxSelected>>", self.app.on_map_select)
        self.app.map_selector.pack(side="left", padx=5, pady=2)

        self.app.draw_btn = tk.Button(self.app.map_toolbar, text=self.app.t('ui', 'draw').upper(), width=12, bg="#444", fg="gray", bd=0, font=("Arial", 8, "bold"), command=self.app.toggle_palette)
        self.app.draw_btn.pack(side="left", padx=5, pady=2)

        # Second row: group selector + token button (shown only with maps)
        second_row = tk.Frame(content_frame, bg="#222")
        self.app.group_selector = ttk.Combobox(second_row, state="readonly", width=15, font=("Arial", 8))
        self.app.group_selector.pack(side="left", padx=5, pady=2)
        self.app.group_selector.bind("<<ComboboxSelected>>", self._on_group_select)

        self.app.group_token_btn = tk.Button(second_row, text="", bg="#333", fg="#999", bd=0, font=("Arial", 8, "bold"), width=12)
        self.app.group_token_btn.pack(side="left", padx=5, pady=2)

        self.app.second_row = second_row

        self._build_identity_bar()
        self._refresh_identity_bar()

        self.app.battle_status_top = tk.Frame(self.app.root, bg="#111", height=18)
        self.app.battle_status_top.pack_propagate(False)
        self.app.battle_status_label = tk.Label(self.app.battle_status_top, text="", bg="#111", fg="#bbbbbb", font=("Arial", 8))
        self.app.battle_status_label.pack(side="left", padx=6)

        self.app.status_label = tk.Label(self.app.root, text=self.app.t('ui', 'hangar_status'), bg="#222", fg="gray", font=("Arial", 8))
        self.app.filter_panel = tk.Frame(self.app.root, bg="#222", bd=1, relief="solid")
        self.build_filters()

        self.app.canvas = tk.Canvas(self.app.root, bg="black", highlightthickness=0)
        self.app.browser_frame = tk.Frame(self.app.root, bg="#000")

        self.app.ai_frame = tk.Frame(self.app.root, bg="#111")
        self.app.stats_ai_module = stats_ai.StatsAI(self.app.ai_frame, self.app.tank_db, self.app.popular_tanks, self.app)

        self.app.canvas.pack(side="top", fill="both", expand=True)

    def _build_identity_bar(self):
        self.app.identity_bar = tk.Frame(self.app.root, bg="#1a1a1a", height=28)
        self.app.identity_bar.pack_propagate(False)
        self.app.identity_bar.pack(side="top", fill="x")

        self.app.identity_nick_label = tk.Label(
            self.app.identity_bar, text="", bg="#1a1a1a", fg="#cccccc",
            font=("Arial", 9, "bold")
        )
        self.app.identity_nick_label.pack(side="left", padx=10, pady=4)

        self.app.identity_pin_label = tk.Label(
            self.app.identity_bar, text="", bg="#1a1a1a", fg="#888888",
            font=("Arial", 8)
        )
        self.app.identity_pin_label.pack(side="left", padx=(2, 8), pady=4)

        self.app.identity_edit_btn = tk.Button(
            self.app.identity_bar, text=self.app.t('ui', 'edit_btn'), bg="#333", fg="#999", bd=0,
            font=("Arial", 8), padx=6,
            command=self._show_edit_dialog
        )
        self.app.identity_edit_btn.pack(side="right", padx=5, pady=3)

        self.app.identity_action_btn = tk.Button(
            self.app.identity_bar, text="", bg="#333", fg="#ccc", bd=0,
            font=("Arial", 8), padx=8,
            command=self._identity_action
        )
        self.app.identity_action_btn.pack(side="right", padx=10, pady=3)

    def _refresh_group_selector(self):
        import firebase_groups
        if not hasattr(self.app, 'group_selector') or not self.app.group_selector:
            return
        if not firebase_identity.is_registered() or not firebase_identity.is_connected():
            try:
                self.app.group_selector.pack_forget()
                self.app.group_token_btn.pack_forget()
            except Exception:
                pass
            self.app.group_selector["values"] = []
            self.app.active_group_id = firebase_groups.PUBLIC_GROUP_ID
            return

        groups = firebase_groups.get_user_groups()
        has_custom = any(gid != firebase_groups.PUBLIC_GROUP_ID for gid in groups)
        if not has_custom:
            try:
                self.app.group_selector.pack_forget()
                self.app.group_token_btn.pack_forget()
            except Exception:
                pass
            self.app.group_selector["values"] = []
            self.app.active_group_id = firebase_groups.PUBLIC_GROUP_ID
            return
        self.app.group_selector.pack(side="left", padx=5, pady=2)
        self.app._cached_groups = groups
        names = []
        id_map = {}
        for gid, ginfo in groups.items():
            if gid == firebase_groups.PUBLIC_GROUP_ID:
                label = self.app.t('ui', 'public')
            else:
                name = ginfo.get("name", gid) if isinstance(ginfo, dict) else gid
                label = name
            names.append(label)
            id_map[label] = gid

        self.app._group_id_map = id_map
        self.app.group_selector["values"] = names

        active_id = self.app.settings.get("active_group", firebase_groups.PUBLIC_GROUP_ID)
        if active_id not in groups:
            active_id = firebase_groups.PUBLIC_GROUP_ID
        active_label = None
        for lbl, gid in id_map.items():
            if gid == active_id:
                active_label = lbl
                break
        if active_label is None and names:
            active_label = names[0]
            active_id = id_map.get(active_label, firebase_groups.PUBLIC_GROUP_ID)

        self.app.group_selector.set(active_label or "Public")
        self.app.active_group_id = active_id

        # Update token button
        if active_id == firebase_groups.PUBLIC_GROUP_ID or not firebase_identity.is_registered():
            self.app.group_token_btn.pack_forget()
        else:
            ginfo = groups.get(active_id, {})
            role = ginfo.get("role", "") if isinstance(ginfo, dict) else ""
            if role == "officer":
                invite_code = ginfo.get("invite_code", "") if isinstance(ginfo, dict) else ""
                if not invite_code:
                    try:
                        gd = firebase_groups.get_group_info(active_id)
                        invite_code = gd.get("invite_code", "") if gd else ""
                    except Exception:
                        invite_code = ""
                code_text = invite_code[:8] if invite_code else "------"
                self.app.group_token_btn.config(
                    text=f"📋 {code_text}", fg="#ffaa00",
                    command=lambda c=invite_code: self._copy_group_token(c))
            else:
                self.app.group_token_btn.config(text="🔒", fg="#666", command=None)
            self.app.group_token_btn.pack(side="left", padx=5, pady=2)

    def _copy_group_token(self, code):
        if not code:
            return
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(code)

    def _update_token_from_cache(self):
        """Оновлює token_btn з кешованих даних без RTDB запиту."""
        import firebase_groups
        active_id = getattr(self.app, "active_group_id", firebase_groups.PUBLIC_GROUP_ID)
        groups = getattr(self.app, "_cached_groups", {})
        if active_id == firebase_groups.PUBLIC_GROUP_ID or not firebase_identity.is_registered():
            try:
                self.app.group_token_btn.pack_forget()
            except Exception:
                pass
            return
        ginfo = groups.get(active_id)
        if not isinstance(ginfo, dict):
            ginfo = {}
        role = ginfo.get("role", "")
        if role == "officer":
            invite_code = ginfo.get("invite_code", "")
            if not invite_code:
                try:
                    import firebase_groups
                    gd = firebase_groups.get_group_info(active_id)
                    invite_code = gd.get("invite_code", "") if gd else ""
                    if invite_code:
                        groups[active_id]["invite_code"] = invite_code
                except Exception:
                    invite_code = ""
            code_text = invite_code[:8] if invite_code else "------"
            self.app.group_token_btn.config(
                text=f"📋 {code_text}", fg="#ffaa00",
                command=lambda c=invite_code: self._copy_group_token(c))
        else:
            self.app.group_token_btn.config(text="🔒", fg="#666", command=None)
        self.app.group_token_btn.pack(side="left", padx=5, pady=2)

    def _on_group_select(self, event=None):
        sel = self.app.group_selector.get()
        if not sel or not hasattr(self.app, '_group_id_map'):
            return
        gid = self.app._group_id_map.get(sel, "public")
        self.app.active_group_id = gid
        self.app.settings["active_group"] = gid
        self.app.save_settings()
        # Update token button from cache
        self._update_token_from_cache()
        import firebase_groups
        if self.app.active_view == "maps":
            if gid != firebase_groups.PUBLIC_GROUP_ID:
                self.app._start_group_sync()
            else:
                self.app._stop_group_sync()
            # Reload map list with filter
            self.app.map_mgr.load_map_list()
            # If current map is filtered out, select first available
            if self.app.map_selector["values"]:
                if not self.app.map_var.get() or self.app.map_var.get() not in self.app.map_selector["values"]:
                    self.app.map_selector.current(0)
                    self.app.on_map_select()

    def _refresh_identity_bar(self):
        if firebase_identity.is_registered():
            nick = firebase_identity.get_nickname()
            pin_text = firebase_identity.get_pin_text()
            if firebase_identity.is_connected():
                self.app.identity_nick_label.config(text=f"  {nick}")
                self.app.identity_pin_label.config(text=f"PIN: {pin_text}" if pin_text else "", fg="#888888")
                self.app.identity_action_btn.config(text=self.app.t('ui', 'disconnect'), bg="#553333", fg="#cc9999")
                self.app.identity_edit_btn.pack(side="right", padx=5, pady=3)
            else:
                self.app.identity_nick_label.config(text=f"  {nick}", fg="#666666")
                self.app.identity_pin_label.config(text=f"PIN: {pin_text}" if pin_text else "", fg="#444444")
                self.app.identity_action_btn.config(text=self.app.t('ui', 'connect'), bg="#334455", fg="#99ccff")
                self.app.identity_edit_btn.pack_forget()
            self._refresh_group_selector()
        else:
            self.app.identity_nick_label.config(text="  " + self.app.t('ui', 'not_connected'))
            self.app.identity_pin_label.config(text="")
            self.app.identity_action_btn.config(text=self.app.t('ui', 'register'), bg="#335533", fg="#99cc99")
            self.app.identity_edit_btn.pack_forget()
            try:
                self.app.group_selector.pack_forget()
                self.app.group_token_btn.pack_forget()
            except Exception:
                pass

    def _identity_action(self):
        if firebase_identity.is_registered():
            if firebase_identity.is_connected():
                self._confirm_disconnect()
            else:
                self._do_connect()
        else:
            self._show_registration_dialog()

    def _show_settings_menu(self):
        if hasattr(self, '_settings_win') and self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.destroy()
            self._settings_win = None
            return

        menu = tk.Toplevel(self.app.root)
        self._settings_win = menu
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        menu.configure(bg="#252525", bd=1, relief="solid", highlightthickness=0)

        x = self.app.settings_btn.winfo_rootx() - 100
        y = self.app.settings_btn.winfo_rooty() + self.app.settings_btn.winfo_height() + 2
        menu.geometry(f"260x260+{x}+{y}")  # тимчасова висота, буде перерахована після пакування

        def make_btn(text, cmd):
            btn = tk.Button(menu, text=text, command=cmd, anchor="w",
                           bg="#252525", fg="#cccccc", activebackground="#444",
                           activeforeground="#ffffff", bd=0, font=("Arial", 9),
                           padx=12, pady=4)
            btn.pack(fill="x")

        def make_chk(text, var):
            cb = tk.Checkbutton(menu, text=text, variable=var, command=self.app.save_settings,
                               anchor="w", bg="#252525", fg="#cccccc",
                               selectcolor="#252525", activebackground="#444",
                               activeforeground="#ffffff", bd=0, font=("Arial", 9),
                               padx=12, pady=3)
            cb.pack(fill="x")

        def sep():
            tk.Frame(menu, height=1, bg="#444").pack(fill="x", padx=12, pady=4)

        make_btn(self.app.t('ui', 'set_wot_path'), self.app.ask_wot_path)
        sep()
        make_chk(self.app.t('ui', 'auto_sync'), self.app.auto_sync_var)
        make_chk(self.app.t('ui', 'auto_mode_filter'), self.app.auto_mode_filter_var)
        make_chk(self.app.t('ui', 'auto_vehicle_filter'), self.app.auto_vehicle_filter_var)
        make_chk(self.app.t('ui', 'auto_battle'), self.app.auto_battle_var)
        sep()
        make_chk(self.app.t('ui', 'auto_update'), self.app.auto_update_var)
        sep()
        make_btn(self.app.t('ui', 'help_btn'), self.app.help_manager.toggle_overlay)
        sep()
        make_btn(self.app.t('ui', 'help_website'), lambda: webbrowser.open("https://sm-wot-assistant.web.app"))
        sep()

        ver_label = tk.Label(menu, text=f"v{config.load_version()}",
                            bg="#252525", fg="#666666", font=("Arial", 8))
        ver_label.pack(pady=(4, 6))

        menu.update_idletasks()
        menu.geometry(f"260x{menu.winfo_reqheight()}+{x}+{y}")

        def close():
            try:
                self._settings_win = None
                menu.destroy()
            except Exception:
                pass

        menu.bind("<FocusOut>", lambda e: self.app.root.after(100, close))
        menu.bind("<Escape>", lambda e: close())
        menu.focus_set()

    def _confirm_disconnect(self):
        dlg = tk.Toplevel(self.app.root)
        dlg.title(self.app.t('ui', 'confirm_disconnect_title'))
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        dlg.minsize(260, 100)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()
        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - 130
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - 50
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text=self.app.t('ui', 'confirm_disconnect_msg'),
                 font=("Arial", 10), bg="#2a2a2a", fg="#cccccc", justify="center").pack(pady=(15, 10))

        bf = tk.Frame(dlg, bg="#2a2a2a")
        bf.pack(pady=(0, 10))
        def on_yes():
            firebase_identity.disconnect()
            dlg.destroy()
            self._refresh_identity_bar()
        tk.Button(bf, text=self.app.t('ui', 'yes'), bg="#553333", fg="white", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_yes).pack(side="left", padx=10)
        tk.Button(bf, text=self.app.t('ui', 'no'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=dlg.destroy).pack(side="left", padx=10)
        self.app.root.wait_window(dlg)

    def _do_connect(self):
        ok, msg = firebase_identity.connect()
        if ok:
            self._refresh_identity_bar()
        else:
            self._show_connect_error_dialog(msg)

    def _show_connect_error_dialog(self, msg):
        dlg = tk.Toplevel(self.app.root)
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()

        tk.Label(dlg, text=msg, font=("Arial", 10), bg="#2a2a2a",
                 fg="#ff6666", wraplength=300, justify="center").pack(pady=(15, 10))

        bf = tk.Frame(dlg, bg="#2a2a2a")
        bf.pack(pady=(0, 10))

        def clear_and_register():
            dlg.destroy()
            try:
                os.remove(os.path.join(config.USER_DATA_DIR, "identity.json"))
            except Exception:
                pass
            self._show_registration_dialog()

        def retry():
            dlg.destroy()
            ok2, msg2 = firebase_identity.connect()
            if ok2:
                self._refresh_identity_bar()
            else:
                self._show_connect_error_dialog(msg2)

        tk.Button(bf, text="Clear & Register", bg="#553333", fg="white", bd=0,
                  font=("Arial", 9), padx=10, pady=4, command=clear_and_register).pack(side="left", padx=5)
        tk.Button(bf, text=self.app.t('ui', 'connect'), bg="#334455", fg="#99ccff", bd=0,
                  font=("Arial", 9), padx=10, pady=4, command=retry).pack(side="left", padx=5)
        tk.Button(bf, text=self.app.t('ui', 'btn_cancel'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=10, pady=4, command=dlg.destroy).pack(side="left", padx=5)

        dlg.update_idletasks()
        w = dlg.winfo_reqwidth()
        h = dlg.winfo_reqheight()
        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - w // 2
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - h // 2
        dlg.geometry(f"+{cx}+{cy}")
        self.app.root.wait_window(dlg)

    def _show_registration_dialog(self):
        dlg = tk.Toplevel(self.app.root)
        dlg.title(self.app.t('ui', 'registration_title'))
        dlg.configure(bg="#222")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()

        tk.Label(dlg, text="SM WoT Assistant", font=("Arial", 14, "bold"),
                 bg="#222", fg="#ff4500").pack(pady=(15, 5))
        tk.Label(dlg, text=self.app.t('ui', 'registration_msg'),
                 font=("Arial", 9), bg="#222", fg="#aaa").pack(pady=(0, 10))

        f = tk.Frame(dlg, bg="#222")
        f.pack(padx=25, pady=5)

        tk.Label(f, text=self.app.t('ui', 'nickname_label'), font=("Arial", 10), bg="#222", fg="#ccc",
                 anchor="e", width=10).grid(row=0, column=0, padx=(0, 10), pady=5, sticky="e")
        nick_var = tk.StringVar()
        nick_entry = tk.Entry(f, textvariable=nick_var, font=("Arial", 11),
                              bg="#333", fg="white", insertbackground="white",
                              width=18, relief="flat", bd=4)
        nick_entry.grid(row=0, column=1, pady=5)

        tk.Label(f, text=self.app.t('ui', 'pin_label'), font=("Arial", 10), bg="#222", fg="#ccc",
                 anchor="e", width=10).grid(row=1, column=0, padx=(0, 10), pady=5, sticky="e")
        pin_var = tk.StringVar()
        pin_entry = tk.Entry(f, textvariable=pin_var, font=("Arial", 11),
                              bg="#333", fg="white", insertbackground="white",
                              width=18, relief="flat", bd=4, show="•")
        pin_entry.grid(row=1, column=1, pady=5)

        nick_available = tk.BooleanVar(value=True)
        nick_validate_job = tk.StringVar()

        def check_nick_debounce():
            nick = nick_var.get().strip()
            if len(nick) < 2:
                nick_entry.config(bg="#333")
                nick_available.set(True)
                register_btn.config(state="normal")
                return
            avail = firebase_identity.check_nickname_available(nick)
            nick_available.set(avail)
            if avail:
                nick_entry.config(bg="#2a4a2a")
                register_btn.config(state="normal")
            else:
                nick_entry.config(bg="#4a2a2a")
                register_btn.config(state="disabled")

        def on_nick_key(event=None):
            job = nick_validate_job.get()
            if job:
                try:
                    dlg.after_cancel(job)
                except Exception:
                    pass
            nick_validate_job.set(dlg.after(400, check_nick_debounce))

        status_var = tk.StringVar()
        status_label = tk.Label(dlg, textvariable=status_var, font=("Arial", 9),
                                bg="#222", fg="#ff6666", wraplength=280)
        status_label.pack(pady=(5, 0))

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(10, 15))

        def do_register():
            nick = nick_var.get().strip()
            pin = pin_var.get().strip()
            ok, msg = firebase_identity.register(nick, pin)
            if ok:
                dlg.destroy()
                self._refresh_identity_bar()
            else:
                status_var.set(msg)

        def do_login():
            nick = nick_var.get().strip()
            pin = pin_var.get().strip()
            ok, msg = firebase_identity.login(nick, pin)
            if ok:
                dlg.destroy()
                self._refresh_identity_bar()
            else:
                status_var.set(msg)

        login_btn = tk.Button(bf, text=self.app.t('ui', 'login'), bg="#334455", fg="#99ccff", bd=0,
                  font=("Arial", 10, "bold"), padx=15, pady=6,
                  command=do_login)
        login_btn.pack(side="left", padx=5)
        register_btn = tk.Button(bf, text=self.app.t('ui', 'register'), bg="#335533", fg="#99cc99", bd=0,
                  font=("Arial", 10, "bold"), padx=15, pady=6,
                  command=do_register)
        register_btn.pack(side="left", padx=5)

        def skip_registration():
            dlg.destroy()
        tk.Button(bf, text=self.app.t('ui', 'skip'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=6,
                  command=skip_registration).pack(side="left", padx=5)

        nick_entry.bind("<KeyRelease>", on_nick_key)
        nick_entry.bind("<Return>", lambda e: pin_entry.focus_set())
        pin_entry.bind("<Return>", lambda e: do_register())

        dlg.update_idletasks()
        w = dlg.winfo_reqwidth()
        h = dlg.winfo_reqheight()
        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - w // 2
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - h // 2
        dlg.geometry(f"+{cx}+{cy}")

        nick_entry.focus_set()
        self.app.root.wait_window(dlg)

    def _show_edit_dialog(self):
        """Діалог зміни нікнейму та PIN (з валідацією)."""
        dlg = tk.Toplevel(self.app.root)
        dlg.title(self.app.t('ui', 'edit'))
        dlg.configure(bg="#222")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()

        f = tk.Frame(dlg, bg="#222")
        f.pack(padx=25, pady=15)

        # Nickname row
        tk.Label(f, text=self.app.t('ui', 'nickname_label'), font=("Arial", 10),
                 bg="#222", fg="#ccc", anchor="e", width=10).grid(row=0, column=0, padx=(0, 10), pady=5, sticky="e")
        nick_var = tk.StringVar(value=firebase_identity.get_nickname())
        nick_entry = tk.Entry(f, textvariable=nick_var, font=("Arial", 11),
                              bg="#333", fg="white", insertbackground="white",
                              width=18, relief="flat", bd=4)
        nick_entry.grid(row=0, column=1, pady=5)

        # PIN row
        tk.Label(f, text=self.app.t('ui', 'pin_label'), font=("Arial", 10),
                 bg="#222", fg="#ccc", anchor="e", width=10).grid(row=1, column=0, padx=(0, 10), pady=5, sticky="e")
        pin_var = tk.StringVar(value=firebase_identity.get_pin_text())
        pin_entry = tk.Entry(f, textvariable=pin_var, font=("Arial", 11),
                             bg="#333", fg="white", insertbackground="white",
                             width=18, relief="flat", bd=4, show="•")
        pin_entry.grid(row=1, column=1, pady=5)

        # New PIN row
        tk.Label(f, text=self.app.t('ui', 'new_pin'), font=("Arial", 10),
                 bg="#222", fg="#ccc", anchor="e", width=10).grid(row=2, column=0, padx=(0, 10), pady=5, sticky="e")
        new_pin_var = tk.StringVar()
        new_pin_entry = tk.Entry(f, textvariable=new_pin_var, font=("Arial", 11),
                                 bg="#333", fg="white", insertbackground="white",
                                 width=18, relief="flat", bd=4, show="•")
        new_pin_entry.grid(row=2, column=1, pady=5)

        nick_available = tk.BooleanVar(value=True)
        own_nick = firebase_identity.get_nickname().lower()
        nick_validate_job = tk.StringVar()

        def check_nick_debounce():
            nick = nick_var.get().strip()
            if len(nick) < 2 or nick.lower() == own_nick:
                nick_entry.config(bg="#333")
                nick_available.set(True)
                save_btn.config(state="normal")
                return
            avail = firebase_identity.check_nickname_available(nick)
            nick_available.set(avail)
            if avail:
                nick_entry.config(bg="#2a4a2a")
                save_btn.config(state="normal")
            else:
                nick_entry.config(bg="#4a2a2a")
                save_btn.config(state="disabled")

        def on_nick_key(event=None):
            job = nick_validate_job.get()
            if job:
                try:
                    dlg.after_cancel(job)
                except Exception:
                    pass
            nick_validate_job.set(dlg.after(400, check_nick_debounce))

        status_var = tk.StringVar()
        status_label = tk.Label(dlg, textvariable=status_var, font=("Arial", 9),
                                bg="#222", fg="#ff6666", wraplength=280)
        status_label.pack(pady=(5, 0))

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(10, 15))

        def do_save():
            nick = nick_var.get().strip()
            pin = pin_var.get().strip()
            new_pin = new_pin_var.get().strip()
            if not nick_available.get():
                status_var.set("Nickname is taken")
                return
            if not pin:
                status_var.set("Current PIN is required")
                return
            if new_pin and (len(new_pin) != 4 or not new_pin.isdigit()):
                status_var.set("New PIN must be 4 digits")
                return
            if not firebase_identity.verify_pin(pin):
                status_var.set(self.app.t('ui', 'wrong_pin'))
                return
            # Change nickname
            if nick != firebase_identity.get_nickname():
                if not firebase_identity.check_nickname_available(nick):
                    status_var.set("Nickname is taken")
                    return
            ok, msg = firebase_identity.change_nickname(nick, pin)
            if not ok:
                status_var.set(msg)
                return
            # Change PIN if provided
            if new_pin:
                firebase_identity.change_pin(pin, new_pin)
            dlg.destroy()
            self._refresh_identity_bar()

        save_btn = tk.Button(bf, text=self.app.t('ui', 'save'), bg="#335533", fg="#99cc99", bd=0,
                   font=("Arial", 10, "bold"), padx=15, pady=6, command=do_save)
        save_btn.pack(side="left", padx=5)
        tk.Button(bf, text=self.app.t('ui', 'btn_cancel'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=6, command=dlg.destroy).pack(side="left", padx=5)

        nick_entry.bind("<KeyRelease>", on_nick_key)
        nick_entry.bind("<Return>", lambda e: pin_entry.focus_set())
        pin_entry.bind("<Return>", lambda e: new_pin_entry.focus_set())
        new_pin_entry.bind("<Return>", lambda e: do_save())

        dlg.update_idletasks()
        w = dlg.winfo_reqwidth()
        h = dlg.winfo_reqheight()
        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - w // 2
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - h // 2
        dlg.geometry(f"+{cx}+{cy}")

        nick_entry.focus_set()
        self.app.root.wait_window(dlg)

    def show_view(self, view_name, **kwargs):
        self.app.active_view = view_name

        self.app.btn_mode_maps_1.config(bg="#444", fg="#bbbbbb")
        self.app.btn_mode_maps_2.config(bg="#444", fg="#bbbbbb")
        self.app.btn_mode_ai_stats.config(bg="#444", fg="#bbbbbb")
        
        self.app.browser_frame.pack_forget()
        self.app.canvas.pack_forget() 
        self.app.filter_panel.pack_forget()
        self.app.status_label.pack_forget()
        self.app.ai_frame.pack_forget()
        self.app.map_toolbar.pack_forget()
        self.app.battle_status_top.pack_forget()

        self.app.top_bar.pack_forget()
        self.app.identity_bar.pack_forget()
        self.app.top_bar.pack(side="top", fill="x")
        self.app.identity_bar.pack(side="top", fill="x")

        if hasattr(self.app, 'second_row'):
            self.app.second_row.pack_forget()

        if view_name == "maps":
            show_second = (
                firebase_identity.is_registered() and
                hasattr(self.app, '_cached_groups') and
                len(self.app._cached_groups) > 1
            )
            if show_second:
                self.app.second_row.pack(side="top", fill="x")
            mode = kwargs.get('mode', 1)
            self.app.map_mode = mode
            if mode == 1:
                self.app.btn_mode_maps_1.config(bg="#ff4500", fg="white")
            else:
                self.app.btn_mode_maps_2.config(bg="#ff4500", fg="white")
            self.app.map_toolbar.pack(side="left", fill="x", expand=True, padx=(0, 10))
            self.app.filter_panel.pack(side="bottom", fill="x")
            self.app.status_label.pack(side="bottom", fill="x")
            self.app.status_label.config(height=2, bg="#1a1a1a")
            self.app.canvas.pack(side="top", fill="both", expand=True)

            self.app.map_mgr.load_map_list()

            if hasattr(self.app, '_po_win') and self.app._po_win.winfo_exists():
                self.app._po_win.withdraw()
                self.app.root.update_idletasks()
                if not self.app._hidden_by_f10:
                    self.app._po_win.deiconify()
                    self.app._sync_po_pos()
                    self.app.root.update_idletasks()
                    self.app.root.after(100, self.app._sync_po_pos)
                self.app.painter.redraw()

            import firebase_groups
            if hasattr(self.app, 'active_group_id') and self.app.active_group_id != firebase_groups.PUBLIC_GROUP_ID:
                self.app._start_group_sync()
            else:
                self.app._stop_group_sync()

        elif view_name == "stats":
            if hasattr(self.app, '_po_win') and self.app._po_win.winfo_exists() and self.app._po_win.state() != "withdrawn":
                self.app._po_win.withdraw()
            if hasattr(self.app, 'drawing_palette') and self.app.drawing_palette.winfo_viewable():
                self.app.drawing_palette.withdraw()
            self.app.status_label.pack(side="bottom", fill="x")
            self.app.browser_frame.pack(side="top", fill="both", expand=True)
            
            loading_label = tk.Label(
                self.app.browser_frame,
                text="\n\n     ⏳ " + self.app.t('ui', 'info_loading') + "\n\n",
                bg="#000", fg="#cccccc", font=("Segoe UI", 14)
            )
            loading_label.pack(expand=True)

        elif view_name == "ai_stats":
            if hasattr(self.app, '_po_win') and self.app._po_win.winfo_exists() and self.app._po_win.state() != "withdrawn":
                self.app._po_win.withdraw()
            if hasattr(self.app, 'drawing_palette') and self.app.drawing_palette.winfo_viewable():
                self.app.drawing_palette.withdraw()
            self.app.btn_mode_ai_stats.config(bg="#ffaa00", fg="black")
            self.app.ai_frame.pack(side="top", fill="both", expand=True)
            self.app.status_label.pack(side="bottom", fill="x")
            if hasattr(self.app, 'stats_ai_module'): self.app.stats_ai_module.refresh_ai_view()

    def build_filters(self):
        for w in self.app.filter_panel.winfo_children(): w.destroy()
        self.app.filters_container = tk.Frame(self.app.filter_panel, bg="#222")
        self.app.filters_container.pack(expand=True, pady=4)
        m_frame = tk.LabelFrame(self.app.filters_container, text=" " + self.app.t('ui', 'battle_mode_label') + " ", bg="#222", fg="#aaa", font=("Arial", 8, "bold"))
        m_frame.pack(side="left", padx=5)
        _mode_mo = {"Standard": "type/ctf/name", "Encounter": "type/domination/name", "Assault": "type/assault/name", "Onslaught": "type/comp7/name"}
        lm = language_module.get_lang_module()
        for mode_key, v in [("Standard", "Standard"), ("Encounter", "Encounter"), ("Assault", "Assault"), ("Onslaught", "Onslaught")]:
            mo_key = _mode_mo.get(mode_key)
            txt = lm.t(mo_key) if mo_key else None
            if not txt:
                txt = self.app.t('ui', mode_key.lower() + '_battle')
            clr = "#ffaa00" if v == "Onslaught" else "white"
            tk.Radiobutton(m_frame, text=txt, variable=self.app.selected_battle_mode, value=v, bg="#222", fg=clr, selectcolor="black").pack(side="left", padx=3)
        c_frame = tk.LabelFrame(self.app.filters_container, text=" " + self.app.t('ui', 'vehicle_class_label') + " ", bg="#222", fg="#aaa", font=("Arial", 8, "bold"))
        c_frame.pack(side="left", padx=5)
        for cls, var in self.app.selected_classes.items():
            tk.Checkbutton(c_frame, text=cls, variable=var, bg="#222", fg="white", selectcolor="black").pack(side="left", padx=3)
