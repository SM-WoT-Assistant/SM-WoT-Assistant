# ui_manager.py
import tkinter as tk
from tkinter import ttk
import stats_ai

class UIManager:
    def __init__(self, app):
        self.app = app
        self.root = app.root

    def setup_ui(self):
        self.app.top_bar = tk.Frame(self.app.root, bg="#222", height=32)
        self.app.top_bar.pack_propagate(False)
        self.app.top_bar.pack(side="top", fill="x")
        
        tk.Button(self.app.top_bar, text="✕", bg="#800", fg="white", command=self.app.quit_app, bd=0, padx=10).pack(side="right", pady=2)
        
        self.app.settings_btn = tk.Button(self.app.top_bar, text="⚙", bg="#333", fg="white", bd=0, command=self.app.toggle_settings)
        self.app.settings_btn.pack(side="right", padx=5)
        
        self.app.settings_menu = tk.Menu(self.app.settings_btn, tearoff=0, bg="#333", fg="white")
        self.app.settings_menu.add_command(label="Вказати папку гри (WoT)", command=self.app.ask_wot_path)
        self.app.settings_menu.add_separator()
        self.app.settings_menu.add_command(label="Оновити мапи (Примусово)", command=self.app.map_mgr.run_map_updater)
        self.app.settings_menu.add_separator()
        self.app.settings_menu.add_checkbutton(label="Авто-фільтри (за логом)", variable=self.app.auto_sync_var, command=self.app.save_settings)
        self.app.settings_menu.add_checkbutton(label="Авто-вибір режиму бою", variable=self.app.auto_mode_filter_var, command=self.app.save_settings)
        self.app.settings_menu.add_checkbutton(label="Авто-вибір виду техніки", variable=self.app.auto_vehicle_filter_var, command=self.app.save_settings)
        self.app.settings_menu.add_checkbutton(label="Авто-бойовий режим", variable=self.app.auto_battle_var, command=self.app.save_settings)
        self.app.settings_menu.add_separator()
        self.app.settings_menu.add_command(label="Встановити AI Key (Gemini)", command=self.app.ask_ai_key)
        self.app.settings_menu.add_separator()
        self.app.settings_menu.add_command(label="Допомога (F1)", command=self.app.help_manager.toggle_overlay)
        self.app.settings_menu.bind("<Unmap>", self.app._on_settings_unmap)

        self.app.battle_status_top = tk.Frame(self.app.root, bg="#111", height=18)
        self.app.battle_status_top.pack_propagate(False)
        self.app.battle_status_label = tk.Label(self.app.battle_status_top, text="", bg="#111", fg="#bbbbbb", font=("Arial", 8))
        self.app.battle_status_label.pack(side="left", padx=6)

        self.app.btn_mode_ai_stats = tk.Button(self.app.top_bar, text="SETUP", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=self.app.switch_to_ai_stats)
        self.app.btn_mode_ai_stats.pack(side="left", padx=5, pady=2)
        
        self.app.btn_mode_maps_1 = tk.Button(self.app.top_bar, text="TACTIC", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=lambda: self.app.switch_to_maps(1))
        self.app.btn_mode_maps_1.pack(side="left", padx=5, pady=2)

        self.app.btn_mode_maps_2 = tk.Button(self.app.top_bar, text="MAPS", padx=10, bg="#444", fg="#bbbbbb", bd=0, font=("Arial", 8, "bold"), anchor='center', command=lambda: self.app.switch_to_maps(2))
        self.app.btn_mode_maps_2.pack(side="left", padx=5, pady=2)

        self.app.map_toolbar = tk.Frame(self.app.top_bar, bg="#222")
        self.app.map_var = tk.StringVar()
        self.app.map_selector = ttk.Combobox(self.app.map_toolbar, textvariable=self.app.map_var, state="readonly", width=15)
        self.app.map_selector.bind("<<ComboboxSelected>>", self.app.on_map_select)
        self.app.map_selector.pack(side="left", padx=5, pady=2)
        
        self.app.draw_btn = tk.Button(self.app.map_toolbar, text=self.app.t('ui', 'draw'), width=12, bg="#444", fg="gray", bd=0, font=("Arial", 8, "bold"), command=self.app.show_draw_menu)
        self.app.draw_btn.pack(side="left", padx=5, pady=2)
        self.app.draw_menu = tk.Menu(self.app.draw_btn, tearoff=0, bg="#333", fg="white", activebackground="#ffaa00", activeforeground="black")
        self.app.draw_menu.add_command(label=self.app.t('ui', 'marker'), command=lambda: self.app.set_painter_tool("marker"))
        self.app.draw_menu.add_separator()
        self.app.draw_menu.add_command(label=self.app.t('ui', 'text_sign'), command=lambda: self.app.set_painter_tool("text"))
        self.app.draw_menu.add_separator()
        self.app.draw_menu.add_command(label=self.app.t('ui', 'clear'), command=lambda: self.app.painter.clear_all())
        self.app.draw_menu.add_separator()
        self.app.draw_menu.add_command(label="Експорт тактики (.json)", command=self.app.export_current_tactic)
        self.app.draw_menu.add_command(label="Імпорт тактики (.json)", command=self.app.import_external_tactic)

        self.app.status_label = tk.Label(self.app.root, text="[HANGAR]", bg="#111", fg="gray", font=("Arial", 8))
        self.app.filter_panel = tk.Frame(self.app.root, bg="#222", bd=1, relief="solid")
        self.build_filters()

        self.app.canvas = tk.Canvas(self.app.root, bg="black", highlightthickness=0)
        self.app.browser_frame = tk.Frame(self.app.root, bg="#000")
        self.app.browser_frame.bind("<Configure>", self.app.win_mgr.resize_tomato_window)
        
        self.app.ai_frame = tk.Frame(self.app.root, bg="#111")
        self.app.stats_ai_module = stats_ai.StatsAI(self.app.ai_frame, self.app.tank_db, self.app.popular_tanks, self.app)
        
        self.app.canvas.pack(side="top", fill="both", expand=True)

    def show_view(self, view_name, **kwargs):
        self.app.active_view = view_name

        # Reset all buttons and hide all widgets first
        self.app.btn_mode_maps_1.config(bg="#444", fg="#bbbbbb")
        self.app.btn_mode_maps_2.config(bg="#444", fg="#bbbbbb")
        self.app.btn_mode_ai_stats.config(bg="#444", fg="#bbbbbb")
        
        if hasattr(self.app, 'tomato') and self.app.tomato:
            self.app.tomato.stop()
            self.app.tomato_hwnd = None
            
        self.app.browser_frame.pack_forget()
        self.app.canvas.pack_forget() 
        self.app.filter_panel.pack_forget()
        self.app.status_label.pack_forget()
        self.app.ai_frame.pack_forget()
        self.app.map_toolbar.pack_forget()
        
        # Ensure top bar is always visible
        self.app.top_bar.pack_forget()
        self.app.top_bar.pack(side="top", fill="x")

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
            self.app.canvas.pack(side="top", fill="both", expand=True) 
            
            self.app.map_mgr.load_map_list()

        elif view_name == "stats":
            self.app.status_label.config(text="[СТАТ] Запуск браузера...", fg="yellow")
            self.app.status_label.pack(side="bottom", fill="x")
            self.app.browser_frame.pack(side="top", fill="both", expand=True)
            
            loading_label = tk.Label(
                self.app.browser_frame,
                text="\n\n     ⏳ Інформація завантажується...\n\n",
                bg="#000", fg="#cccccc", font=("Segoe UI", 14)
            )
            loading_label.pack(expand=True)
            self.app.browser_frame.update()

            if hasattr(self.app, 'tomato') and self.app.tomato:
                self.app.tomato_hwnd = None
                self.app.tomato.launch()
                self.app.root.after(200, self.app.win_mgr.dock_tomato_window)

                def cleanup_loading_when_docked():
                    if self.app.tomato_hwnd:
                        try: loading_label.destroy()
                        except Exception: pass
                    else: self.app.root.after(200, cleanup_loading_when_docked)
                self.app.root.after(200, cleanup_loading_when_docked)
            else:
                self.app.status_label.config(text="[ПОМИЛКА] Модуль tomato_viewer.py не знайдено!", fg="red")

        elif view_name == "ai_stats":
            self.app.btn_mode_ai_stats.config(bg="#ffaa00", fg="black")
            self.app.ai_frame.pack(side="top", fill="both", expand=True)
            self.app.status_label.config(text="[СТАТ АІ] Оберіть танк для отримання збірки", fg="cyan")
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
