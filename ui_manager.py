import os
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
        self.app.top_bar = tk.Frame(self.app.root, bg="#222", height=32)
        self.app.top_bar.pack_propagate(False)
        self.app.top_bar.pack(side="top", fill="x")
        
        tk.Frame(self.app.top_bar, width=7, bg="#222").pack(side="right")

        tk.Button(self.app.top_bar, text="✕", bg="#800", fg="white", command=self.app.quit_app, bd=0, padx=10).pack(side="right", pady=7)

        self.app.settings_btn = tk.Button(self.app.top_bar, text="⚙", bg="#333", fg="white", bd=0, command=self._show_settings_menu)
        self.app.settings_btn.pack(side="right", padx=5, pady=7)

        self._build_identity_bar()

        self.app.battle_status_top = tk.Frame(self.app.root, bg="#111", height=18)
        self.app.battle_status_top.pack_propagate(False)
        self.app.battle_status_label = tk.Label(self.app.battle_status_top, text="", bg="#111", fg="#bbbbbb", font=("Arial", 8))
        self.app.battle_status_label.pack(side="left", padx=6)

        tk.Frame(self.app.top_bar, width=7, bg="#222").pack(side="left")

        self.app.btn_mode_ai_stats = tk.Button(self.app.top_bar, text="SETUP", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=self.app.switch_to_ai_stats)
        self.app.btn_mode_ai_stats.pack(side="left", padx=(0,1), pady=7)

        self.app.btn_mode_maps_2 = tk.Button(self.app.top_bar, text="MAPS", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=lambda: self.app.switch_to_maps(2))
        self.app.btn_mode_maps_2.pack(side="left", padx=1, pady=7)

        self.app.btn_mode_maps_1 = tk.Button(self.app.top_bar, text="TACTIC", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=lambda: self.app.switch_to_maps(1))
        self.app.btn_mode_maps_1.pack(side="left", padx=1, pady=7)

        self.app.map_toolbar = tk.Frame(self.app.top_bar, bg="#222")
        self.app.map_var = tk.StringVar()
        self.app.map_selector = ttk.Combobox(self.app.map_toolbar, textvariable=self.app.map_var, state="readonly", width=15)
        self.app.map_selector.bind("<<ComboboxSelected>>", self.app.on_map_select)
        self.app.map_selector.configure(postcommand=self.app._combo_postcommand)
        self.app.map_selector.bind("<FocusOut>", self.app._combo_focus_out_restore, "+")
        self.app.map_selector.pack(side="left", padx=5, pady=2)
        
        self.app.draw_btn = tk.Button(self.app.map_toolbar, text=self.app.t('ui', 'draw').upper(), width=12, bg="#444", fg="gray", bd=0, font=("Arial", 8, "bold"), command=self.app.toggle_palette)
        self.app.draw_btn.pack(side="left", padx=5, pady=2)

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
        self.app.identity_pin_label.pack(side="left", padx=(2, 15), pady=4)
        self.app.identity_action_btn = tk.Button(
            self.app.identity_bar, text="", bg="#333", fg="#ccc", bd=0,
            font=("Arial", 8), padx=8,
            command=self._identity_action
        )
        self.app.identity_action_btn.pack(side="right", padx=10, pady=3)

        self._refresh_identity_bar()

    def _refresh_identity_bar(self):
        if firebase_identity.is_registered():
            nick = firebase_identity.get_nickname()
            pin_text = firebase_identity.get_pin_text()
            self.app.identity_nick_label.config(text=f"  {nick}")
            self.app.identity_pin_label.config(text=f"PIN: {pin_text}" if pin_text else "", fg="#888888")
            self.app.identity_action_btn.config(text=self.app.t('ui', 'logout'), bg="#553333", fg="#cc9999")
        else:
            self.app.identity_nick_label.config(text="  " + self.app.t('ui', 'not_registered'))
            self.app.identity_pin_label.config(text="")
            self.app.identity_action_btn.config(text=self.app.t('ui', 'register'), bg="#335533", fg="#99cc99")

    def _identity_action(self):
        if firebase_identity.is_registered():
            self._confirm_logout()
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
        menu.geometry(f"260x260+{x}+{y}")

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

        ver_label = tk.Label(menu, text=f"v{config.load_version()}",
                            bg="#252525", fg="#666666", font=("Arial", 8))
        ver_label.pack(pady=(4, 6))

        def close():
            try:
                self._settings_win = None
                menu.destroy()
            except Exception:
                pass

        menu.bind("<FocusOut>", lambda e: self.app.root.after(100, close))
        menu.bind("<Escape>", lambda e: close())
        menu.focus_set()

    def _confirm_logout(self):
        dlg = tk.Toplevel(self.app.root)
        dlg.title(self.app.t('ui', 'confirm_logout_title'))
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        dlg.minsize(260, 100)
        dlg.attributes("-topmost", True)
        dialog_utils._set_dark_title_bar(dlg)
        dlg.grab_set()
        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - 130
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - 50
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text=self.app.t('ui', 'confirm_logout_msg'),
                 font=("Arial", 10), bg="#2a2a2a", fg="#cccccc", justify="center").pack(pady=(15, 10))

        bf = tk.Frame(dlg, bg="#2a2a2a")
        bf.pack(pady=(0, 10))
        def on_yes():
            dlg.destroy()
            os.remove(os.path.join(config.USER_DATA_DIR, "identity.json"))
            self._refresh_identity_bar()
            pass
        tk.Button(bf, text=self.app.t('ui', 'yes'), bg="#553333", fg="white", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_yes).pack(side="left", padx=10)
        tk.Button(bf, text=self.app.t('ui', 'no'), bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=dlg.destroy).pack(side="left", padx=10)
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
                pass
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

        tk.Button(bf, text=self.app.t('ui', 'login'), bg="#334455", fg="#99ccff", bd=0,
                  font=("Arial", 10, "bold"), padx=15, pady=6,
                  command=do_login).pack(side="left", padx=5)
        tk.Button(bf, text=self.app.t('ui', 'register'), bg="#335533", fg="#99cc99", bd=0,
                  font=("Arial", 10, "bold"), padx=15, pady=6,
                  command=do_register).pack(side="left", padx=5)

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

        if view_name == "maps":
            mode = kwargs.get('mode', 1)
            self.app.map_mode = mode
            if mode == 1:
                self.app.btn_mode_maps_1.config(bg="#ff4500", fg="white")
            else:
                self.app.btn_mode_maps_2.config(bg="#ff4500", fg="white")
            self.app.map_toolbar.pack(side="left", fill="x", expand=True, padx=10)
            self.app.filter_panel.pack(side="bottom", fill="x")
            self.app.status_label.pack(side="bottom", fill="x")
            self.app.status_label.config(height=2, bg="#1a1a1a")
            self.app.canvas.pack(side="top", fill="both", expand=True)

            self.app.map_mgr.load_map_list()

            if hasattr(self.app, '_po_win') and self.app._po_win.winfo_exists():
                self.app._po_win.withdraw()
                self.app.root.update_idletasks()
                self.app._po_win.deiconify()
                self.app._sync_po_pos()
                self.app.root.update_idletasks()
                self.app.painter.redraw()
                self.app._start_po_sync_timer()

        elif view_name == "stats":
            self.app._stop_po_sync_timer()
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
            self.app._stop_po_sync_timer()
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
