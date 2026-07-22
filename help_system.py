import tkinter as tk
import config

class HelpManager:
    def __init__(self, app):
        self.app = app
        self._help_win = None

    def toggle_overlay(self):
        if self._help_win is not None and self._help_win.winfo_exists():
            self._help_win.destroy()
            self._help_win = None
            return

        self._help_win = tk.Toplevel(self.app.root)
        self._help_win.overrideredirect(True)
        self._help_win.attributes("-topmost", True)
        self._help_win.configure(bg="#1a1a1a")
        self._help_win.grab_set()

        self._drag = {"x": 0, "y": 0}
        self._build_ui()

        self._help_win.update_idletasks()
        w = self._help_win.winfo_reqwidth()
        h = self._help_win.winfo_reqheight()
        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - w // 2
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - h // 2
        sw = self._help_win.winfo_screenwidth()
        sh = self._help_win.winfo_screenheight()
        cx = max(0, min(cx, sw - w - 20))
        cy = max(0, min(cy, sh - h - 20))
        self._help_win.geometry(f"{w}x{h}+{cx}+{cy}")
        self._help_win.focus_force()

    def _drag_start(self, event):
        self._drag["x"] = event.x
        self._drag["y"] = event.y

    def _drag_move(self, event):
        x = self._help_win.winfo_x() + event.x - self._drag["x"]
        y = self._help_win.winfo_y() + event.y - self._drag["y"]
        self._help_win.geometry(f"+{x}+{y}")

    def _make_helpers(self, parent, bg, hotkey_fg, desc_fg, title_fg, hint_fg):
        _r = [0]
        def row(hotkey, desc, first=False, wrap=280):
            p = (6, 0) if first else (0, 0)
            tk.Label(parent, text=hotkey, bg=bg, fg=hotkey_fg, font=("Arial", 9, "bold"),
                     anchor="w").grid(row=_r[0], column=0, sticky="w", pady=p, padx=(0, 8))
            kw = {"text": desc, "bg": bg, "fg": desc_fg, "font": ("Arial", 9),
                   "anchor": "w", "justify": "left"}
            if wrap:
                kw["wraplength"] = wrap
            tk.Label(parent, **kw).grid(row=_r[0], column=1, sticky="w", pady=p)
            _r[0] += 1
        def section(title):
            sep = tk.Frame(parent, bg="#333", height=1)
            sep.grid(row=_r[0], column=0, columnspan=2, sticky="ew", pady=(8, 4))
            _r[0] += 1
            tk.Label(parent, text=title, bg=bg, fg=title_fg, font=("Arial", 9, "bold"),
                     anchor="w").grid(row=_r[0], column=0, columnspan=2, sticky="w", pady=(0, 4))
            _r[0] += 1
        def hint(text):
            tk.Label(parent, text=text, bg=bg, fg=hint_fg, font=("Arial", 8),
                     anchor="w").grid(row=_r[0], column=0, columnspan=2, sticky="w", pady=(0, 2))
            _r[0] += 1
        def frow(fr_left, desc):
            fr_left.grid(row=_r[0], column=0, sticky="w", pady=(6, 0), padx=(0, 8))
            tk.Label(parent, text=desc, bg=bg, fg=desc_fg, font=("Arial", 9), anchor="w").grid(row=_r[0], column=1, sticky="w", pady=(6, 0))
            _r[0] += 1
        def final_sep():
            tk.Frame(parent, bg="#333", height=1).grid(row=_r[0], column=0, columnspan=2, sticky="ew", pady=(8, 4))
            _r[0] += 1
        def sep():
            tk.Frame(parent, bg="#444", height=1).grid(row=_r[0], column=0, columnspan=2, sticky="ew", pady=(2, 2))
            _r[0] += 1
        def close_label(text):
            tk.Label(parent, text=text, bg=bg, fg=hint_fg, font=("Arial", 8)).grid(row=_r[0], column=0, columnspan=2, pady=(0, 4))
            _r[0] += 1
        return row, section, hint, frow, final_sep, sep, close_label

    def _build_ui(self):
        bg = "#1a1a1a"
        hdr_bg = "#2a2a2a"
        hotkey_fg = "#ffffff"
        desc_fg = "#aaaaaa"
        title_fg = "#ffaa00"
        hint_fg = "#666666"

        hdr = tk.Frame(self._help_win, bg=hdr_bg, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text=f"  {self.app.t('ui', 'help_title').format(version=config.load_version())}", bg=hdr_bg, fg=title_fg,
                 font=("Arial", 9, "bold")).pack(side="left")
        tk.Button(hdr, text="\u2715", bg=hdr_bg, fg="#aaa", bd=0,
                  font=("Arial", 8), command=lambda: self.toggle_overlay()).pack(side="right", padx=4)

        hdr.bind("<Button-1>", self._drag_start)
        hdr.bind("<B1-Motion>", self._drag_move)
        hdr.bind("<Enter>", lambda e: hdr.config(cursor="fleur"))

        body = tk.Frame(self._help_win, bg=bg)
        body.pack(fill="both", expand=True, padx=12, pady=(8, 4))

        left_col = tk.Frame(body, bg=bg)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right_col = tk.Frame(body, bg=bg)
        right_col.pack(side="right", fill="both", expand=True, padx=(6, 0))

        l_row, l_section, l_hint, l_frow, l_final, l_sep, l_close = self._make_helpers(
            left_col, bg, hotkey_fg, desc_fg, title_fg, hint_fg)
        r_row, r_section, r_hint, r_frow, r_final, r_sep, r_close = self._make_helpers(
            right_col, bg, hotkey_fg, desc_fg, title_fg, hint_fg)

        # ── LEFT COLUMN ──────────────────────────────────

        l_section(self.app.t('ui', 'help_section_editor'))
        l_row("F10", self.app.t('ui', 'help_f10'), first=True)
        l_hint(self.app.t('ui', 'help_restore_btn'))
        fr = tk.Frame(left_col, bg=bg)
        tk.Label(fr, text=chr(0xF023), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr, text=chr(0xF09C), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr, text=" / F8", font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg, anchor="w").pack(side="left")
        l_frow(fr, self.app.t('ui', 'help_f8'))
        l_row("TAB", self.app.t('ui', 'help_e'))
        l_row("F1", self.app.t('ui', 'help_f1'))

        l_section(self.app.t('ui', 'help_section_battle'))
        fr_b = tk.Frame(left_col, bg=bg)
        tk.Label(fr_b, text="Ctrl + ", font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr_b, text=chr(0xF09C), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr_b, text=chr(0xF023), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr_b, text=" / F8", font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        l_frow(fr_b, self.app.t('ui', 'help_f8'))
        l_row("LMB", self.app.t('ui', 'help_ctrl_lmb_battle'))
        fr_r = tk.Frame(left_col, bg=bg)
        tk.Label(fr_r, text=chr(0xF0E2), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        l_frow(fr_r, self.app.t('ui', 'help_battle_reset'))
        l_hint(self.app.t('ui', 'help_unhide_battle'))

        l_section(self.app.t('ui', 'help_section_draw'))
        l_row("LMB + drag", self.app.t('ui', 'help_lmb_drag'))
        l_row("Ctrl + LMB + drag", self.app.t('ui', 'help_ctrl_lmb_drag'))
        l_row("Ctrl + drag arrow", self.app.t('ui', 'help_ctrl_arrow_drag'))
        l_row(self.app.t('ui', 'help_hotkey_right_click'), self.app.t('ui', 'help_right_click'))
        l_row("Ctrl + \u2191", self.app.t('ui', 'help_ctrl_up'))
        l_row("Ctrl + \u2193", self.app.t('ui', 'help_ctrl_down'))
        l_row("Ctrl + Z", self.app.t('ui', 'help_ctrl_z'))

        l_section(self.app.t('ui', 'help_section_palette'))
        l_row(self.app.t('ui', 'help_hotkey_row1'), self.app.t('ui', 'help_palette_row1'))
        l_row(self.app.t('ui', 'help_hotkey_row2'), self.app.t('ui', 'help_palette_row2'))
        l_row(self.app.t('ui', 'help_hotkey_delete'), self.app.t('ui', 'help_palette_delete'))
        l_row(self.app.t('ui', 'help_hotkey_status_row'), self.app.t('ui', 'help_palette_status'))
        l_row(self.app.t('ui', 'help_hotkey_click_empty'), self.app.t('ui', 'help_palette_click_empty'))

        l_section(self.app.t('ui', 'help_section_io'))
        l_row(self.app.t('ui', 'help_hotkey_publish'), self.app.t('ui', 'help_publish_map'))
        l_row(self.app.t('ui', 'help_hotkey_publish_all'), self.app.t('ui', 'help_publish_all'))
        l_row(self.app.t('ui', 'save_btn').upper(), self.app.t('ui', 'help_export'))
        l_row(self.app.t('ui', 'help_hotkey_save_all'), self.app.t('ui', 'help_all_export'))
        l_row(self.app.t('ui', 'load_btn').upper(), self.app.t('ui', 'help_import'))
        l_final()
        l_close(self.app.t('ui', 'help_close'))

        # ── RIGHT COLUMN ─────────────────────────────────

        r_section(self.app.t('ui', 'help_section_filters'))
        r_row(self.app.t('ui', 'battle_mode_label'), self.app.t('ui', 'help_filter_mode'))
        r_row(self.app.t('ui', 'vehicle_class_label'), self.app.t('ui', 'help_filter_class'))

        r_section(self.app.t('ui', 'help_section_groups'))
        r_row(self.app.t('ui', 'help_group_filter_label'), self.app.t('ui', 'help_group_filter_desc'))
        r_sep()
        fr_gic = tk.Frame(right_col, bg=bg)
        tk.Label(fr_gic, text=chr(0xF0C5), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr_gic, text=" / ", font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr_gic, text=chr(0xF023), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_gic, self.app.t('ui', 'help_group_token'))
        r_sep()
        r_row(self.app.t('ui', 'group_create'), self.app.t('ui', 'help_group_create_desc'))
        r_sep()
        r_row(self.app.t('ui', 'group_join'), self.app.t('ui', 'help_group_join_desc'))
        r_sep()
        r_row(self.app.t('ui', 'group_manage'), self.app.t('ui', 'help_group_manage_desc'))
        r_sep()
        r_row(self.app.t('ui', 'publish_map'), self.app.t('ui', 'help_group_publish_desc'))

        r_section(self.app.t('ui', 'help_section_settings'))
        fr_s1 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s1, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s1, text=" " + self.app.t('ui', 'auto_sync'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s1, self.app.t('ui', 'help_setting_auto_sync'))
        fr_s2 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s2, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s2, text=" " + self.app.t('ui', 'unhide_on_battle'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s2, self.app.t('ui', 'help_setting_unhide_on_battle'))
        fr_s3 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s3, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s3, text=" " + self.app.t('ui', 'auto_mode_filter'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s3, self.app.t('ui', 'help_setting_auto_mode_filter'))
        fr_s4 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s4, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s4, text=" " + self.app.t('ui', 'auto_vehicle_filter'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s4, self.app.t('ui', 'help_setting_auto_vehicle_filter'))
        fr_s5 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s5, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s5, text=" " + self.app.t('ui', 'auto_battle'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s5, self.app.t('ui', 'help_setting_auto_battle'))
        fr_s6 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s6, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s6, text=" " + self.app.t('ui', 'auto_update'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s6, self.app.t('ui', 'help_setting_auto_update'))
        fr_s7 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s7, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s7, text=" " + self.app.t('ui', 'launch_on_game_start'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s7, self.app.t('ui', 'help_setting_launch_on_game_start'))
        fr_s8 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s8, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s8, text=" " + self.app.t('ui', 'start_minimized'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s8, self.app.t('ui', 'help_setting_start_minimized'))
        fr_s9 = tk.Frame(right_col, bg=bg)
        tk.Label(fr_s9, text=chr(0xF14A), font=("FontAwesome", 10), bg=bg, fg="#aaa").pack(side="left")
        tk.Label(fr_s9, text=" " + self.app.t('ui', 'close_with_game'), font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        r_frow(fr_s9, self.app.t('ui', 'help_setting_close_with_game'))
