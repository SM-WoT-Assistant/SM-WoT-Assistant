import tkinter as tk

class HelpManager:
    def __init__(self, app):
        self.app = app
        self.visible = False
        self.help_tags = "help_overlay"

    def toggle_overlay(self):
        if not hasattr(self.app, 'canvas'): return
        
        self.visible = not self.visible
        self.app.canvas.delete(self.help_tags)
        
        if self.visible:
            w = self.app.canvas.winfo_width()
            h = self.app.canvas.winfo_height()
            if w < 10: w, h = self.app.w, self.app.h
            
            # Суцільна майже чорна підкладка для максимального контрасту
            self.app.canvas.create_rectangle(0, 0, w, h, fill="#080808", tags=self.help_tags)
            
            help_text = (
                "=== WoT Assistant: ГАРЯЧІ КЛАВІШІ ===\n\n"
                "[ F10 ] — Показати / Приховати вікно\n"
                "[  E  ] — Перемикання: БОЙОВИЙ ↔ РЕДАКТОР\n"
                "[  F1 ] — Ця довідка\n\n"
                "--- Керування вікном (Режим РЕДАКТОР) ---\n"
                "• Натисніть F8 для вмикання/вимикання режиму змін\n"
                "  Ctrl + ЛКМ        — Перетягнути вікно редактора\n"
                "  Ctrl + ↕ Стрілки  — Змінити розмір вікна\n"
                "  Ctrl + ↔ Стрілки  — Змінити прозорість\n"
                "  Ctrl+Shift + ↕    — Змінити контрастність мапи\n\n"
                "--- Керування вікном (Бойовий режим) ---\n"
                "• Натисніть F8 для вмикання/вимикання режиму змін\n"
                "  Ctrl + ЛКМ        — Перетягнути вікно у бою\n"
                "  Ctrl + ↕ Стрілки  — Змінити розмір вікна\n"
                "  Ctrl + ↔ Стрілки  — Змінити прозорість\n"
                "  Ctrl+Shift + ↕    — Змінити контрастність мапи\n\n"
                "--- Малювання (Режим РЕДАКТОР → MAPS) ---\n"
                "  ЛКМ + тягнути              — Створити маркер / текст\n"
                "  Ctrl + ЛКМ + тягнути       — Перемістити об'єкт\n"
                "  Ctrl + тягнути стрілочку   — Змінити напрямок вектора\n"
                "  Правий клік                — Контекстне меню\n"
                "  Ctrl + ↑ / ↓               — Змінити розмір виділеного\n"
                "  Ctrl + Z                   — Скасувати (Undo)\n\n"
                "--- Палітра малювання (кнопка з пензлем) ---\n"
                "  Ряд 1: Маркер, ЛТ, СТ, ТТ, ПТ, САУ\n"
                "  Ряд 2: Дерево + 8 тактичних значків\n"
                "  Кнопка «Видалити» — з'являється при редагуванні\n"
                "  Рядок стану показує тип редагованого об'єкта\n"
                "  Клік на пусте поле — знімає виділення\n\n"
                "--- Фільтри (Нижня панель) ---\n"
                "  РЕЖИМ БОЮ — фільтрація мап за типом бою\n"
                "  ТЕХНІКА    — фільтрація міток за класом техніки"
            )
            
            # Тінь для тексту (для кращої читабельності)
            self.app.canvas.create_text(w//2 + 1, h//2 + 1, text=help_text, fill="black", 
                                       font=("Arial", 10, "bold"), justify="center", tags=self.help_tags)
            self.app.canvas.create_text(w//2, h//2, text=help_text, fill="white", 
                                       font=("Arial", 10, "bold"), justify="center", tags=self.help_tags)
            
            # Кнопка закриття
            self.app.canvas.create_text(w//2, h - 30, text="Натисніть F1 знову для закриття", 
                                       fill="#ffaa00", font=("Arial", 9, "italic"), tags=self.help_tags)
