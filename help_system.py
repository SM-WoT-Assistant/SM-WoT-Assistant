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
        tk.Button(hdr, text="✕", bg=hdr_bg, fg="#aaa", bd=0,
                  font=("Arial", 8), command=lambda: self.toggle_overlay()).pack(side="right", padx=4)

        hdr.bind("<Button-1>", self._drag_start)
        hdr.bind("<B1-Motion>", self._drag_move)
        hdr.bind("<Enter>", lambda e: hdr.config(cursor="fleur"))

        body = tk.Frame(self._help_win, bg=bg)
        body.pack(fill="both", expand=True, padx=12, pady=(8, 4))

        # Two-column layout
        cols = tk.Frame(body, bg=bg)
        cols.pack(fill="both", expand=True)

        left_col = tk.Frame(cols, bg=bg)
        left_col.pack(side="left", fill="y", anchor="n")

        right_col = tk.Frame(cols, bg=bg)
        right_col.pack(side="left", fill="both", expand=True, anchor="n", padx=(16, 0))

        def make_helpers(frame):
            _r = [0]
            def row(hotkey, desc, first=False, wrap=0):
                p = (6, 0) if first else (0, 0)
                tk.Label(frame, text=hotkey, bg=bg, fg=hotkey_fg, font=("Arial", 9, "bold"),
                         anchor="w").grid(row=_r[0], column=0, sticky="w", pady=p, padx=(0, 8))
                kw = {"text": desc, "bg": bg, "fg": desc_fg, "font": ("Arial", 9),
                       "anchor": "w", "justify": "left"}
                if wrap:
                    kw["wraplength"] = wrap
                tk.Label(frame, **kw).grid(row=_r[0], column=1, sticky="w", pady=p)
                _r[0] += 1

            def section(title):
                sep = tk.Frame(frame, bg="#333", height=1)
                sep.grid(row=_r[0], column=0, columnspan=2, sticky="ew", pady=(8, 4))
                _r[0] += 1
                tk.Label(frame, text=title, bg=bg, fg=title_fg, font=("Arial", 9, "bold"),
                         anchor="w").grid(row=_r[0], column=0, columnspan=2, sticky="w", pady=(0, 4))
                _r[0] += 1

            def hint(text):
                tk.Label(frame, text=text, bg=bg, fg=hint_fg, font=("Arial", 8),
                         anchor="w").grid(row=_r[0], column=0, columnspan=2, sticky="w", pady=(0, 2))
                _r[0] += 1

            return _r, row, section, hint

        # ─── Left column ───
        _rl, row_l, section_l, hint_l = make_helpers(left_col)

        row_l("F10", self.app.t('ui', 'help_f10'), first=True)
        hint_l(self.app.t('ui', 'help_restore_btn'))
        fr = tk.Frame(left_col, bg=bg)
        tk.Label(fr, text=chr(0xF023), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr, text=chr(0xF09C), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr, text="  F8", font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg, anchor="w").pack(side="left")
        fr.grid(row=_rl[0], column=0, sticky="w", pady=(6, 0), padx=(0, 8))
        tk.Label(left_col, text=self.app.t('ui', 'help_f8'), bg=bg, fg=desc_fg, font=("Arial", 9), anchor="w").grid(row=_rl[0], column=1, sticky="w", pady=(6, 0))
        _rl[0] += 1
        row_l("TAB", self.app.t('ui', 'help_e'))
        row_l("F1", self.app.t('ui', 'help_f1'))

        # Formatting Mode (F8 Lock ON) — repurposed from unused Editor keys
        section_l(self.app.t('ui', 'help_section_editor'))
        hint_l(self.app.t('ui', 'help_hint_editor'))
        row_l("LMB + drag", self.app.t('ui', 'help_ctrl_lmb'))
        row_l("\u2191 / \u2193", self.app.t('ui', 'help_ctrl_updown'))
        row_l("\u2190 / \u2192", self.app.t('ui', 'help_ctrl_leftright'))
        row_l("Shift + \u2191 / \u2193", self.app.t('ui', 'help_ctrlshift_updown'))

        section_l(self.app.t('ui', 'help_section_battle'))
        bfr = tk.Frame(left_col, bg=bg)
        tk.Label(bfr, text="Ctrl  ", font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(bfr, text=chr(0xF023), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(bfr, text=chr(0xF09C), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(bfr, text="  F8", font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg, anchor="w").pack(side="left")
        bfr.grid(row=_rl[0], column=0, sticky="w", pady=(6, 0), padx=(0, 8))
        tk.Label(left_col, text=self.app.t('ui', 'help_ctrl_lmb_battle'), bg=bg, fg=desc_fg, font=("Arial", 9), anchor="w", wraplength=280).grid(row=_rl[0], column=1, sticky="w", pady=(6, 0))
        _rl[0] += 1
        hint_l(self.app.t('ui', 'help_unhide_battle'))
        hint_l(self.app.t('ui', 'help_f8_icon_battle'))

        section_l(self.app.t('ui', 'help_section_draw'))
        row_l("LMB + drag", self.app.t('ui', 'help_lmb_drag'))
        row_l("Ctrl + LMB + drag", self.app.t('ui', 'help_ctrl_lmb_drag'))
        row_l("Ctrl + drag arrow", self.app.t('ui', 'help_ctrl_arrow_drag'))
        row_l("Right click", self.app.t('ui', 'help_right_click'))
        row_l("Ctrl + \u2191", self.app.t('ui', 'help_ctrl_up'))
        row_l("Ctrl + \u2193", self.app.t('ui', 'help_ctrl_down'))
        row_l("Ctrl + Z", self.app.t('ui', 'help_ctrl_z'))

        section_l(self.app.t('ui', 'help_section_palette'))
        row_l("Row 1", self.app.t('ui', 'help_palette_row1'))
        row_l("Row 2", self.app.t('ui', 'help_palette_row2'))
        row_l("Delete", self.app.t('ui', 'help_palette_delete'))
        row_l("Status row", self.app.t('ui', 'help_palette_status'))
        row_l("Click empty", self.app.t('ui', 'help_palette_click_empty'))

        section_l(self.app.t('ui', 'help_section_io'))
        row_l("PUBLISH", self.app.t('ui', 'help_publish_map'))
        row_l("PUBLISH ALL", self.app.t('ui', 'help_publish_all'))
        row_l(self.app.t('ui', 'save_btn').upper(), self.app.t('ui', 'help_export'))
        row_l("SAVE ALL", self.app.t('ui', 'help_all_export'))
        row_l(self.app.t('ui', 'load_btn').upper(), self.app.t('ui', 'help_import'))

        # ─── Right column ───
        _rr, row_r, section_r, hint_r = make_helpers(right_col)

        section_r(self.app.t('ui', 'help_section_filters'))
        row_r(self.app.t('ui', 'battle_mode_label'), self.app.t('ui', 'help_filter_mode'))
        row_r(self.app.t('ui', 'vehicle_class_label'), self.app.t('ui', 'help_filter_class'))

        section_r(self.app.t('ui', 'help_section_groups'))
        row_r(self.app.t('ui', 'help_group_filter_label'), self.app.t('ui', 'help_group_filter_desc'), wrap=280)
        row_r("\U0001F4CB/\U0001F512", self.app.t('ui', 'help_group_token'), wrap=280)
        row_r(self.app.t('ui', 'group_create'), self.app.t('ui', 'help_group_create_desc'), wrap=280)
        row_r(self.app.t('ui', 'group_join'), self.app.t('ui', 'help_group_join_desc'), wrap=280)
        row_r(self.app.t('ui', 'group_manage'), self.app.t('ui', 'help_group_manage_desc'), wrap=280)
        row_r(self.app.t('ui', 'publish_map'), self.app.t('ui', 'help_group_publish_desc'), wrap=280)

        section_r(self.app.t('ui', 'help_section_startup'))
        row_r(self.app.t('ui', 'run_at_startup'), self.app.t('ui', 'help_run_at_startup'), wrap=280)
        row_r(self.app.t('ui', 'launch_on_game_start'), self.app.t('ui', 'help_launch_on_game_start'), wrap=280)
        row_r(self.app.t('ui', 'start_minimized'), self.app.t('ui', 'help_start_minimized'), wrap=280)

        # ─── Bottom separator + close ───
        tk.Frame(body, bg="#333", height=1).pack(fill="x", pady=(8, 4))
        tk.Label(body, text=self.app.t('ui', 'help_close'), bg=bg, fg=hint_fg,
                 font=("Arial", 8)).pack()