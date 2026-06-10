import os
import tkinter as tk
from tkinter import ttk
import config
import stats_ai
import firebase_identity

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

        self.app.settings_btn = tk.Button(self.app.top_bar, text="⚙", bg="#333", fg="white", bd=0, command=self.app.toggle_settings)
        self.app.settings_btn.pack(side="right", padx=5, pady=7)
        
        self.app.settings_menu = tk.Menu(self.app.settings_btn, tearoff=0, bg="#333", fg="white")
        self.app.settings_menu.add_command(label="Вказати папку гри (WoT)", command=self.app.ask_wot_path)
        self.app.settings_menu.add_separator()
        self.app.settings_menu.add_checkbutton(label="Авто-фільтри (за логом)", variable=self.app.auto_sync_var, command=self.app.save_settings)
        self.app.settings_menu.add_checkbutton(label="Авто-вибір режиму бою", variable=self.app.auto_mode_filter_var, command=self.app.save_settings)
        self.app.settings_menu.add_checkbutton(label="Авто-вибір виду техніки", variable=self.app.auto_vehicle_filter_var, command=self.app.save_settings)
        self.app.settings_menu.add_checkbutton(label="Авто-бойовий режим", variable=self.app.auto_battle_var, command=self.app.save_settings)
        self.app.settings_menu.add_separator()
        self.app.settings_menu.add_checkbutton(label="Автооновлення", variable=self.app.auto_update_var, command=self.app.save_settings)
        self.app.settings_menu.add_separator()
        self.app.settings_menu.add_command(label="Допомога (F1)", command=self.app.help_manager.toggle_overlay)
        self.app.settings_menu.bind("<Unmap>", self.app._on_settings_unmap)

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
        self.app.map_selector.pack(side="left", padx=5, pady=2)
        
        self.app.draw_btn = tk.Button(self.app.map_toolbar, text=self.app.t('ui', 'draw'), width=12, bg="#444", fg="gray", bd=0, font=("Arial", 8, "bold"), command=self.app.toggle_palette)
        self.app.draw_btn.pack(side="left", padx=5, pady=2)

        self.app.status_label = tk.Label(self.app.root, text="[HANGAR]", bg="#222", fg="gray", font=("Arial", 8))
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
        self.app.identity_publish_btn = tk.Button(
            self.app.identity_bar, text="Опублікувати", bg="#335555", fg="#ccc", bd=0,
            font=("Arial", 8), padx=8,
            command=self._open_publish_site
        )
        self.app.identity_publish_btn.pack(side="right", padx=3, pady=3)

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
            self.app.identity_action_btn.config(text="Вийти", bg="#553333", fg="#cc9999")
            if self.app.active_view == "maps" and self.app.map_mode == 2:
                self.app.identity_publish_btn.pack(side="right", padx=3, pady=3)
            else:
                self.app.identity_publish_btn.pack_forget()
        else:
            self.app.identity_nick_label.config(text="  Не зареєстровано")
            self.app.identity_pin_label.config(text="")
            self.app.identity_action_btn.config(text="Зареєструватись", bg="#335533", fg="#99cc99")
            self.app.identity_publish_btn.pack_forget()

    def _identity_action(self):
        if firebase_identity.is_registered():
            self._confirm_logout()
        else:
            self._show_registration_dialog()

    def _open_publish_site(self):
        import os
        nick = firebase_identity.get_nickname()
        url = "https://sm-wot-assistant.web.app/schemes.html"
        if nick:
            from urllib.parse import quote
            url += f"?nick={quote(nick)}"
        os.startfile(url)

    def _confirm_logout(self):
        dlg = tk.Toplevel(self.app.root)
        dlg.title("Вийти")
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        dlg.minsize(260, 100)
        dlg.attributes("-topmost", True)
        dlg.grab_set()
        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - 130
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - 50
        dlg.geometry(f"+{cx}+{cy}")

        tk.Label(dlg, text="Вийти з облікового запису?\nМалюнки не будуть втрачені.",
                 font=("Arial", 10), bg="#2a2a2a", fg="#cccccc", justify="center").pack(pady=(15, 10))

        bf = tk.Frame(dlg, bg="#2a2a2a")
        bf.pack(pady=(0, 10))
        def on_yes():
            dlg.destroy()
            os.remove(os.path.join(config.USER_DATA_DIR, "identity.json"))
            self._refresh_identity_bar()
            self.app.status_label.config(text="Ви вийшли з облікового запису.", fg="#ffb347")
            self.app.root.after(3000, lambda: self.app.status_label.config(text="[HANGAR]", fg="gray"))
        tk.Button(bf, text="  Так  ", bg="#553333", fg="white", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=on_yes).pack(side="left", padx=10)
        tk.Button(bf, text="  Ні  ", bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=4, command=dlg.destroy).pack(side="left", padx=10)
        self.app.root.wait_window(dlg)

    def _show_registration_dialog(self):
        dlg = tk.Toplevel(self.app.root)
        dlg.title("Реєстрація")
        dlg.configure(bg="#222")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        dlg.grab_set()

        tk.Label(dlg, text="SM WoT Assistant", font=("Arial", 14, "bold"),
                 bg="#222", fg="#ff4500").pack(pady=(15, 5))
        tk.Label(dlg, text="Створіть обліковий запис для публікації малюнків",
                 font=("Arial", 9), bg="#222", fg="#aaa").pack(pady=(0, 10))

        f = tk.Frame(dlg, bg="#222")
        f.pack(padx=25, pady=5)

        tk.Label(f, text="Нікнейм:", font=("Arial", 10), bg="#222", fg="#ccc",
                 anchor="e", width=10).grid(row=0, column=0, padx=(0, 10), pady=5, sticky="e")
        nick_var = tk.StringVar()
        nick_entry = tk.Entry(f, textvariable=nick_var, font=("Arial", 11),
                              bg="#333", fg="white", insertbackground="white",
                              width=18, relief="flat", bd=4)
        nick_entry.grid(row=0, column=1, pady=5)

        tk.Label(f, text="PIN (4 цифри):", font=("Arial", 10), bg="#222", fg="#ccc",
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
                self.app.status_label.config(text=f"[АКАУНТ] Ласкаво просимо, {nick}!", fg="lime")
                self.app.root.after(3000, lambda: self.app.status_label.config(text="[HANGAR]", fg="gray"))
            else:
                status_var.set(msg)

        tk.Button(bf, text="  Зареєструватись  ", bg="#335533", fg="#99cc99", bd=0,
                  font=("Arial", 10, "bold"), padx=15, pady=6,
                  command=do_register).pack(side="left", padx=10)

        def skip_registration():
            dlg.destroy()
        tk.Button(bf, text="  Пропустити  ", bg="#444", fg="#aaa", bd=0,
                  font=("Arial", 9), padx=15, pady=6,
                  command=skip_registration).pack(side="left", padx=10)

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

        if view_name == "maps" and kwargs.get('mode', 1) == 2 and firebase_identity.is_registered():
            self.app.identity_publish_btn.pack(side="right", padx=3, pady=3)
        else:
            self.app.identity_publish_btn.pack_forget()

        if view_name == "maps":
            mode = kwargs.get('mode', 1)
            self.app.map_mode = mode
            if mode == 1:
                self.app.btn_mode_maps_1.config(bg="#ff4500", fg="white")
                self.app.battle_status_top.pack(side="top", fill="x")
                self.app.map_toolbar.pack(side="left", fill="x", expand=True, padx=10)
                self.app.status_label.pack(side="bottom", fill="x")
            else:
                self.app.btn_mode_maps_2.config(bg="#ff4500", fg="white")
                self.app.filter_panel.pack(side="bottom", fill="x")
                self.app.status_label.pack(side="bottom", fill="x")
                self.app.status_label.config(height=2, bg="#1a1a1a")
                self.app.map_toolbar.pack(side="left", fill="x", expand=True, padx=10)
            self.app.canvas.pack(side="top", fill="both", expand=True)
            
            self.app.map_mgr.load_map_list()

        elif view_name == "stats":
            if hasattr(self.app, 'drawing_palette') and self.app.drawing_palette.winfo_viewable():
                self.app.drawing_palette.withdraw()
            self.app.status_label.config(text="[СТАТ] Запуск браузера...", fg="yellow", height=1, bg="#222")
            self.app.status_label.pack(side="bottom", fill="x")
            self.app.browser_frame.pack(side="top", fill="both", expand=True)
            
            loading_label = tk.Label(
                self.app.browser_frame,
                text="\n\n     ⏳ Інформація завантажується...\n\n",
                bg="#000", fg="#cccccc", font=("Segoe UI", 14)
            )
            loading_label.pack(expand=True)

        elif view_name == "ai_stats":
            if hasattr(self.app, 'drawing_palette') and self.app.drawing_palette.winfo_viewable():
                self.app.drawing_palette.withdraw()
            self.app.btn_mode_ai_stats.config(bg="#ffaa00", fg="black")
            self.app.ai_frame.pack(side="top", fill="both", expand=True)
            self.app.status_label.config(text="[СТАТ АІ] Оберіть танк для отримання збірки", fg="cyan", height=1, bg="#222")
            self.app.status_label.pack(side="bottom", fill="x")
            if hasattr(self.app, 'stats_ai_module'): self.app.stats_ai_module.refresh_ai_view()

    def build_filters(self):
        for w in self.app.filter_panel.winfo_children(): w.destroy()
        self.app.filters_container = tk.Frame(self.app.filter_panel, bg="#222")
        self.app.filters_container.pack(expand=True, pady=4)
        m_frame = tk.LabelFrame(self.app.filters_container, text=" РЕЖИМ БОЮ ", bg="#222", fg="#aaa", font=("Arial", 8, "bold"))
        m_frame.pack(side="left", padx=5)
        for t, v in [("Стандарт", "Standard"), ("Зустріч", "Encounter"), ("Штурм", "Assault"), ("НАТИСК", "Onslaught")]:
            clr = "#ffaa00" if v == "Onslaught" else "white"
            tk.Radiobutton(m_frame, text=t, variable=self.app.selected_battle_mode, value=v, bg="#222", fg=clr, selectcolor="black").pack(side="left", padx=3)
        c_frame = tk.LabelFrame(self.app.filters_container, text=" ТЕХНІКА ", bg="#222", fg="#aaa", font=("Arial", 8, "bold"))
        c_frame.pack(side="left", padx=5)
        for cls, var in self.app.selected_classes.items():
            tk.Checkbutton(c_frame, text=cls, variable=var, bg="#222", fg="white", selectcolor="black").pack(side="left", padx=3)
