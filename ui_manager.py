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
            command=lambda: self.app.toggle_formatting_mode(True))

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
        self.app.btn_mode_ai_stats.pack(side="left", padx=(0, 1), fill="y")

        self.app.btn_mode_maps_2 = tk.Button(btn_frame, text="MAPS", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=lambda: self.app.switch_to_maps(2))
        self.app.btn_mode_maps_2.pack(side="left", padx=1, fill="y")

        self.app.btn_mode_maps_1 = tk.Button(btn_frame, text="TACTIC", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=lambda: self.app.switch_to_maps(1))
        self.app.btn_mode_maps_1.pack(side="left", padx=(1, 0), fill="y")

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

        self.app.btn_format_lock_battle = tk.Button(self.app.battle_status_top, text=chr(0xF023),
            font=("FontAwesome", 8), bg="#333", fg="#bbbbbb", bd=0, width=2,
            command=lambda: self.app.toggle_formatting_mode(True))
        self.app.btn_format_lock_battle.pack(side="left", padx=(3, 1))

        self.app.btn_reset_position = tk.Button(self.app.battle_status_top,
            text=chr(0xF0E2), font=("FontAwesome", 8), bg="#333", fg="#888",
            bd=0, width=2, command=self.app._reset_norm_position)
        self.app.btn_reset_position.pack(side="left", padx=(1, 0))

        self.app.battle_status_label = tk.Label(self.app.battle_status_top, text="", bg="#111", fg="#bbbbbb", font=("Arial", 8))
        self.app.battle_status_label.pack(side="left", padx=6)

        self.app.status_label = tk.Label(self.app.root, text=self.app.t('ui', 'hangar_status'), bg="#222", fg="gray", font=("Arial", 8))
        self.app.filter_panel = tk.Frame(self.app.root, bg="#222", bd=1, relief="solid")
        self.build_filters()

        self.app.canvas = tk.Canvas(self.app.root, bg="black", highlightthickness=0)
        self.app.browser_frame = tk.Frame(self.app.root, bg="#000")

        self.app.ai_frame = tk.Frame(self.app.root, bg="#111")
        try:
            self.app.stats_ai_module = stats_ai.StatsAI(self.app.ai_frame, self.app.tank_db, self.app.popular_tanks, self.app)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[DEBUG] StatsAI init failed: {e}")
            self.app.stats_ai_module = None

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
                self.app.second_row.pack_forget()
            except Exception:
                pass
            self.app.group_selector["values"] = []
            self.app.active_group_id = firebase_groups.PUBLIC_GROUP_ID
            self.app._cached_groups = {}
            self.app.top_bar.update_idletasks()
            self.app._adjust_for_canvas()
            return

        groups = getattr(self.app, '_cached_groups', {}) or {}
        has_custom = any(gid != firebase_groups.PUBLIC_GROUP_ID for gid in groups)
        if not has_custom:
            try:
                self.app.group_selector.pack_forget()
                self.app.group_token_btn.pack_forget()
                self.app.second_row.pack_forget()
            except Exception:
                pass
            self.app.group_selector["values"] = []
            self.app.active_group_id = firebase_groups.PUBLIC_GROUP_ID
            self.app._cached_groups = {}
            self.app.top_bar.update_idletasks()
            self.app._adjust_for_canvas()
            return
        if getattr(self.app, 'active_view', None) == "maps":
            self.app.second_row.pack(side="top", fill="x")
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
        self.app.top_bar.update_idletasks()

    def _copy_group_token(self, code):
        if not code:
            return
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(code)
        self._show_copied_popup(self.app.group_token_btn)

    def _show_copied_popup(self, anchor_widget):
        popup = tk.Toplevel(self.app.root)
        popup.overrideredirect(True)
        popup.configure(bg="#222")
        popup.attributes("-topmost", True)
        tk.Label(popup, text=self.app.t('ui', 'copied_to_clipboard'), bg="#222", fg="#4c4",
                 font=("Arial", 9, "bold")).pack(padx=16, pady=8)
        popup.update_idletasks()
        px = anchor_widget.winfo_rootx() + anchor_widget.winfo_width()//2 - popup.winfo_reqwidth()//2
        py = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()//2 - popup.winfo_reqheight()//2
        popup.geometry(f"+{px}+{py}")
        popup.lift()
        popup.grab_set()
        self.app.root.after(2000, lambda: (popup.grab_release(), popup.destroy()))

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
            # Refresh linked schemes list in palette
            if hasattr(self.app, 'drawing_palette') and self.app.drawing_palette.winfo_exists():
                self.app.drawing_palette._refresh_linked_schemes_list()
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
            import firebase_groups
            self.app._cached_groups = firebase_groups.get_user_groups()
            self._refresh_group_selector()
        else:
            self.app.identity_nick_label.config(text="  " + self.app.t('ui', 'not_connected'))
            self.app.identity_pin_label.config(text="")
            self.app.identity_action_btn.config(text=self.app.t('ui', 'register'), bg="#335533", fg="#99cc99")
            self.app.identity_edit_btn.pack_forget()
            try:
                self.app.group_selector.pack_forget()
                self.app.group_token_btn.pack_forget()
                self.app.second_row.pack_forget()
            except Exception:
                pass
        
        # Синхронізувати висоту canvas після зміни ідентичності
        if self.app.active_view == "maps" and self.app.mode == "edit":
            self.app.root.after(50, self.app._adjust_for_canvas)

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
        menu.geometry(f"+{x}+{y}")  # тільки позиція, ширина визначиться після пакування

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
            return cb

        def sep():
            tk.Frame(menu, height=1, bg="#444").pack(fill="x", padx=12, pady=4)

        make_btn(self.app.t('ui', 'set_wot_path'), self.app.ask_wot_path)
        sep()
        make_chk(self.app.t('ui', 'auto_sync'), self.app.auto_sync_var)
        make_chk(self.app.t('ui', 'unhide_on_battle'), self.app._unhide_on_battle_var)
        make_chk(self.app.t('ui', 'auto_mode_filter'), self.app.auto_mode_filter_var)
        make_chk(self.app.t('ui', 'auto_vehicle_filter'), self.app.auto_vehicle_filter_var)
        make_chk(self.app.t('ui', 'sync_schemes_with_mode'), self.app.sync_schemes_with_mode)
        make_chk(self.app.t('ui', 'auto_battle'), self.app.auto_battle_var)
        chk_auto_size = make_chk(self.app.t('ui', 'auto_window_size'), self.app._auto_window_size_var)
        chk_auto_size.configure(command=self.app._on_auto_window_size_toggle)
        sep()
        make_chk(self.app.t('ui', 'auto_update'), self.app.auto_update_var)
        sep()

        # ─── Game launch settings ───
        chk_launch_game = make_chk(self.app.t('ui', 'launch_on_game_start'), self.app._launch_on_game_start_var)
        chk_minimized = make_chk(self.app.t('ui', 'start_minimized'), self.app._start_minimized_var)
        chk_close_game = make_chk(self.app.t('ui', 'close_with_game'), self.app._close_with_game_var)

        def _on_launch_on_game_start():
            enabled = self.app._launch_on_game_start_var.get()
            self.app._set_windows_startup(enabled)
            if enabled:
                self.app._ensure_tray_watcher_running()
            else:
                self.app._stop_tray_watcher()
            self.app.save_settings()

        chk_launch_game.configure(command=_on_launch_on_game_start)

        sep()
        make_btn(self.app.t('ui', 'help_btn'), self.app.help_manager.toggle_overlay)
        sep()
        make_btn(self.app.t('ui', 'help_website'), lambda: webbrowser.open("https://sm-wot-assistant.web.app"))
        make_btn("TACTIC maps: wotmapsbyyaya.com", lambda: webbrowser.open("https://wotmapsbyyaya.com/maps"))
        sep()

        ver_label = tk.Label(menu, text=f"v{config.load_version()}",
                            bg="#252525", fg="#666666", font=("Arial", 8))
        ver_label.pack(pady=(4, 6))

        menu.update_idletasks()
        w = menu.winfo_reqwidth()
        h = menu.winfo_reqheight()
        sw = menu.winfo_screenwidth()
        sh = menu.winfo_screenheight()
        x = max(0, min(x, sw - w - 10))
        y = max(0, min(y, sh - h - 10))
        menu.geometry(f"{w}x{h}+{x}+{y}")

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
        dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, self.app.t('ui', 'confirm_disconnect_title'))
        dialog_utils._DragHelper(dlg, hdr)
        dlg.grab_set()
        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - 130
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - 50
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text=self.app.t('ui', 'confirm_disconnect_msg'),
                 font=("Arial", 10), bg="#2a2a2a", fg="#cccccc", wraplength=360, justify="center").pack(pady=(15, 10))

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
        dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, self.app.t('ui', 'confirm_title'))
        dialog_utils._DragHelper(dlg, hdr)
        dlg.grab_set()

        tk.Label(dlg, text=msg, font=("Arial", 10), bg="#222",
                 fg="#ff6666", wraplength=360, justify="center").pack(pady=(15, 10))

        bf = tk.Frame(dlg, bg="#222")
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

        tk.Button(bf, text=self.app.t('ui', 'clear_register_btn'), bg="#553333", fg="white", bd=0,
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
        dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, self.app.t('ui', 'registration_title'))
        dialog_utils._DragHelper(dlg, hdr)
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

        def _make_entry_menu(entry):
            m = tk.Menu(entry, tearoff=0, bg="#333", fg="#ccc")
            m.add_command(label="Cut", command=lambda: entry.event_generate("<<Cut>>"))
            m.add_command(label="Copy", command=lambda: entry.event_generate("<<Copy>>"))
            m.add_command(label="Paste", command=lambda: entry.event_generate("<<Paste>>"))
            m.add_command(label="Select All", command=lambda: entry.event_generate("<<SelectAll>>"))
            def show(e):
                m.tk_popup(e.x_root, e.y_root)
                self.app.root.after(100, lambda: m.grab_release())
            entry.bind("<Button-3>", show)
        _make_entry_menu(nick_entry)
        _make_entry_menu(pin_entry)

        status_var = tk.StringVar()
        status_label = tk.Label(dlg, textvariable=status_var, font=("Arial", 9),
                                bg="#222", fg="#ff6666", wraplength=280)
        status_label.pack(pady=(5, 0))

        bf = tk.Frame(dlg, bg="#222")
        bf.pack(pady=(10, 15))

        def do_register():
            nick = nick_var.get().strip()
            pin = pin_var.get().strip()
            if nick and not firebase_identity.check_nickname_available(nick):
                status_var.set("Цей нікнейм вже зайнятий.")
                return
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
        dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, self.app.t('ui', 'edit'))
        dialog_utils._DragHelper(dlg, hdr)
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
        self.app.settings["_saved_view"] = view_name
        if view_name == "maps":
            self.app.settings["_saved_map_mode"] = kwargs.get("mode", 1)

        self.app.btn_mode_maps_1.config(bg="#444", fg="#bbbbbb")
        self.app.btn_mode_maps_2.config(bg="#444", fg="#bbbbbb")
        self.app.btn_mode_ai_stats.config(bg="#444", fg="#bbbbbb")
        
        if view_name != "ai_stats":
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
                    self.app.root.after(150, self.app.painter.redraw)
                else:
                    self.app.painter.redraw()

            import firebase_groups
            if hasattr(self.app, 'active_group_id') and self.app.active_group_id != firebase_groups.PUBLIC_GROUP_ID:
                self.app._start_group_sync()
            else:
                self.app._stop_group_sync()

            if hasattr(self.app, 'drawing_palette'):
                self.app.drawing_palette._refresh_linked_schemes_list()

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
            stats = getattr(self.app, 'stats_ai_module', None)
            if stats:
                def do_ai_switch():
                    if self.app.active_view != "ai_stats":
                        return
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
                    self.app.status_label.pack(side="bottom", fill="x")
                    self.app.ai_frame.pack(side="top", fill="both", expand=True)
                    self.app.root.update_idletasks()
                    self.app.root.update_idletasks()
                cw = self.app.root.winfo_width() - 20
                if cw > 100:
                    stats._last_cols = max(1, cw // 171)
                stats.refresh_ai_view(on_complete=do_ai_switch)
            else:
                self.app.status_label.pack(side="bottom", fill="x")
                self.app.ai_frame.pack(side="top", fill="both", expand=True)
                self.app.root.update_idletasks()
                self.app.root.update_idletasks()

    def build_filters(self):
        for w in self.app.filter_panel.winfo_children(): w.destroy()
        self.app.filters_container = tk.Frame(self.app.filter_panel, bg="#222")
        self.app.filters_container.pack(expand=True, pady=4)
        m_frame = tk.LabelFrame(self.app.filters_container, text=" " + self.app.t('ui', 'battle_mode_label') + " ", bg="#222", fg="#aaa", font=("Arial", 8, "bold"))
        m_frame.pack(side="left", padx=5)
        _mode_mo = {"Standard": "type/ctf/name", "Encounter": "type/domination/name", "Storm": "type/assault/name", "Onslaught": "type/comp7/name", "OnslaughtLight": "type/comp7/name"}
        lm = language_module.get_lang_module()
        for mode_key, v in [("Standard", "Standard"), ("Encounter", "Encounter"), ("Storm", "Storm"), ("Onslaught", "Onslaught"), ("OnslaughtLight", "OnslaughtLight")]:
            mo_key = _mode_mo.get(mode_key)
            txt = lm.t(mo_key) if mo_key else None
            if not txt:
                txt = self.app.t('ui', 'mode_' + mode_key.lower())
            if mode_key == "Onslaught":
                txt += " 10"
            elif mode_key == "OnslaughtLight":
                txt += " 8"
            clr = "#ffaa00" if v in ("Onslaught", "OnslaughtLight") else "white"
            tk.Radiobutton(m_frame, text=txt, variable=self.app.selected_battle_mode, value=v, bg="#222", fg=clr, selectcolor="black").pack(side="left", padx=3)
        c_frame = tk.LabelFrame(self.app.filters_container, text=" " + self.app.t('ui', 'vehicle_class_label') + " ", bg="#222", fg="#aaa", font=("Arial", 8, "bold"))
        c_frame.pack(side="left", padx=5)
        for cls, var in self.app.selected_classes.items():
            tk.Checkbutton(c_frame, text=cls, variable=var, bg="#222", fg="white", selectcolor="black").pack(side="left", padx=3)
