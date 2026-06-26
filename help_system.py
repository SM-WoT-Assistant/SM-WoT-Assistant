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

        cx = self.app.root.winfo_x() + self.app.root.winfo_width() // 2 - 250
        cy = self.app.root.winfo_y() + self.app.root.winfo_height() // 2 - 300
        self._help_win.geometry(f"+{cx}+{cy}")
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

        def row(hotkey, desc, first=False):
            p = (6, 0) if first else (0, 0)
            tk.Label(body, text=hotkey, bg=bg, fg=hotkey_fg, font=("Arial", 9, "bold"),
                     anchor="w", width=20).grid(row=_r[0], column=0, sticky="w", pady=p, padx=(0, 8))
            tk.Label(body, text=desc, bg=bg, fg=desc_fg, font=("Arial", 9),
                     anchor="w", width=36).grid(row=_r[0], column=1, sticky="w", pady=p)
            _r[0] += 1

        def section(title):
            sep = tk.Frame(body, bg="#333", height=1)
            sep.grid(row=_r[0], column=0, columnspan=2, sticky="ew", pady=(8, 4))
            _r[0] += 1
            tk.Label(body, text=title, bg=bg, fg=title_fg, font=("Arial", 9, "bold"),
                     anchor="w").grid(row=_r[0], column=0, columnspan=2, sticky="w", pady=(0, 4))
            _r[0] += 1

        def hint(text):
            tk.Label(body, text=text, bg=bg, fg=hint_fg, font=("Arial", 8),
                     anchor="w").grid(row=_r[0], column=0, columnspan=2, sticky="w", pady=(0, 2))
            _r[0] += 1

        _r = [0]

        row("F10", self.app.t('ui', 'help_f10'), first=True)
        fr = tk.Frame(body, bg=bg)
        tk.Label(fr, text=chr(0xF023), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr, text=chr(0xF09C), font=("FontAwesome", 10), bg=bg, fg=hotkey_fg).pack(side="left")
        tk.Label(fr, text="  F8", font=("Arial", 9, "bold"), bg=bg, fg=hotkey_fg, anchor="w", width=17).pack(side="left")
        fr.grid(row=_r[0], column=0, sticky="w", pady=(6, 0), padx=(0, 8))
        tk.Label(body, text=self.app.t('ui', 'help_f8'), bg=bg, fg=desc_fg, font=("Arial", 9), anchor="w", width=36).grid(row=_r[0], column=1, sticky="w", pady=(6, 0))
        _r[0] += 1
        row("TAB", self.app.t('ui', 'help_e'))
        row("F1", self.app.t('ui', 'help_f1'))

        section(self.app.t('ui', 'help_section_draw'))
        row("LMB + drag", self.app.t('ui', 'help_lmb_drag'))
        row("Ctrl + LMB + drag", self.app.t('ui', 'help_ctrl_lmb_drag'))
        row("Ctrl + drag arrow", self.app.t('ui', 'help_ctrl_arrow_drag'))
        row("Right click", self.app.t('ui', 'help_right_click'))
        row("Ctrl + \u2191", self.app.t('ui', 'help_ctrl_up'))
        row("Ctrl + \u2193", self.app.t('ui', 'help_ctrl_down'))
        row("Ctrl + Z", self.app.t('ui', 'help_ctrl_z'))

        section(self.app.t('ui', 'help_section_palette'))
        row("Row 1", self.app.t('ui', 'help_palette_row1'))
        row("Row 2", self.app.t('ui', 'help_palette_row2'))
        row("Delete", self.app.t('ui', 'help_palette_delete'))
        row("Status row", self.app.t('ui', 'help_palette_status'))
        row("Click empty", self.app.t('ui', 'help_palette_click_empty'))

        section(self.app.t('ui', 'help_section_io'))
        row("PUBLISH", self.app.t('ui', 'help_publish_map'))
        row("PUBLISH ALL", self.app.t('ui', 'help_publish_all'))
        row(self.app.t('ui', 'save_btn').upper(), self.app.t('ui', 'help_export'))
        row("SAVE ALL", self.app.t('ui', 'help_all_export'))
        row(self.app.t('ui', 'load_btn').upper(), self.app.t('ui', 'help_import'))

        section(self.app.t('ui', 'help_section_filters'))
        row(self.app.t('ui', 'battle_mode_label'), self.app.t('ui', 'help_filter_mode'))
        row(self.app.t('ui', 'vehicle_class_label'), self.app.t('ui', 'help_filter_class'))

        tk.Frame(body, bg="#333", height=1).grid(row=_r[0], column=0, columnspan=2, sticky="ew", pady=(8, 4))
        _r[0] += 1
        tk.Label(body, text=self.app.t('ui', 'help_close'), bg=bg, fg=hint_fg,
                 font=("Arial", 8)).grid(row=_r[0], column=0, columnspan=2, pady=(0, 4))