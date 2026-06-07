import tkinter as tk

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

        tk.Label(hdr, text="  WoT Assistant: ДОВІДКА", bg=hdr_bg, fg=title_fg,
                 font=("Arial", 9, "bold")).pack(side="left")
        tk.Button(hdr, text="✕", bg=hdr_bg, fg="#aaa", bd=0,
                  font=("Arial", 8), command=lambda: self.toggle_overlay()).pack(side="right", padx=4)

        hdr.bind("<Button-1>", self._drag_start)
        hdr.bind("<B1-Motion>", self._drag_move)
        hdr.bind("<Enter>", lambda e: hdr.config(cursor="fleur"))

        body = tk.Frame(self._help_win, bg=bg)
        body.pack(fill="both", expand=True, padx=12, pady=(8, 4))

        TK = tk.Label(body, bg=bg, fg=desc_fg, font=("Arial", 9), anchor="w", width=20)
        TD = tk.Label(body, bg=bg, fg=desc_fg, font=("Arial", 9), anchor="w", width=36)

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

        row("F10", "Показати / Приховати вікно", first=True)
        row("E", "Перемикання: БОЙОВИЙ ↔ РЕДАКТОР")
        row("F1", "Ця довідка")

        section("Керування вікном (Режим РЕДАКТОР)")
        hint("• Натисніть F8 для вмикання/вимикання режиму змін")
        row("Ctrl + ЛКМ", "Перетягнути вікно редактора")
        row("Ctrl + ↕", "Змінити розмір вікна")
        row("Ctrl + ↔", "Змінити прозорість")
        row("Ctrl+Shift + ↕", "Змінити контрастність мапи")

        section("Керування вікном (Бойовий режим)")
        hint("• Натисніть F8 для вмикання/вимикання режиму змін")
        row("Ctrl + ЛКМ", "Перетягнути вікно у бою")
        row("Ctrl + ↕", "Змінити розмір вікна")
        row("Ctrl + ↔", "Змінити прозорість")
        row("Ctrl+Shift + ↕", "Змінити контрастність мапи")

        section("Малювання (Режим РЕДАКТОР → MAPS)")
        row("ЛКМ + тягнути", "Створити маркер / текст")
        row("Ctrl + ЛКМ + тягнути", "Перемістити об'єкт")
        row("Ctrl + тягнути стрілочку", "Змінити напрямок вектора")
        row("Правий клік", "Контекстне меню")
        row("Ctrl + ↑", "Збільшити виділений об'єкт")
        row("Ctrl + ↓", "Зменшити виділений об'єкт")
        row("Ctrl + Z", "Скасувати (Undo)")

        section("Палітра малювання (кнопка з пензлем)")
        row("Ряд 1", "Маркер, ЛТ, СТ, ТТ, ПТ, САУ")
        row("Ряд 2", "Дерево + 8 тактичних значків")
        row("«Видалити»", "З'являється при редагуванні")
        row("Рядок стану", "Показує тип редагованого об'єкта")
        row("Клік на пусте поле", "Знімає виділення")

        section("Фільтри (Нижня панель)")
        row("РЕЖИМ БОЮ", "Фільтрація мап за типом бою")
        row("ТЕХНІКА", "Фільтрація міток за класом техніки")

        tk.Frame(body, bg="#333", height=1).grid(row=_r[0], column=0, columnspan=2, sticky="ew", pady=(8, 4))
        _r[0] += 1
        tk.Label(body, text="Натисніть F1 для закриття", bg=bg, fg=hint_fg,
                 font=("Arial", 8)).grid(row=_r[0], column=0, columnspan=2, pady=(0, 4))
