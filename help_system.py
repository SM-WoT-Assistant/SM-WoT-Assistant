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
                "[ F10 ] - Показати/Приховати вікно\n"
                "[  E  ] - Перемикання: БОЕВИЙ ↔ РЕДАКТОР\n"
                "[  F1 ] - Ця довідка\n\n"
                "--- Управління вікном (АНГ + БОРТ) ---\n"
                "Ctrl + ЛКМ        - Перетягування вікна (ангар)\n"
                "Ctrl + ЛКМ         - Перетягування вікна (бій)\n"
                "Ctrl + ↕ Стрілки   - Зміна розміру вікна\n"
                "Ctrl + ↔ Стрілки   - Зміна прозорості\n"
                "Ctrl+Shift +↕      - Зміна контрастності мапи\n\n"
                "--- Робота з фільтрами (Нижня панель) ---\n"
                "• РЕЖИМ БОЮ: Обирайте тип бою (Штурм, Натиск тощо),\n"
                "  щоб відфільтрувати список доступних мап зверху.\n"
                "• ТЕХНІКА: Вмикайте/вимикайте класи техніки, щоб миттєво\n"
                "  показати або сховати встановлені тактичні мітки на мапі.\n\n"
                "--- Малювання та Автоматизація ---\n"
                "ЛКМ / Double ПКМ - Поставити або Видалити мітку\n"
                "Авто-фільтри: Вимагають шлях до python.log у [ ⚙ ]"
            )
            
            # Тінь для тексту (для кращої читабельності)
            self.app.canvas.create_text(w//2 + 1, h//2 + 1, text=help_text, fill="black", 
                                       font=("Arial", 10, "bold"), justify="center", tags=self.help_tags)
            self.app.canvas.create_text(w//2, h//2, text=help_text, fill="white", 
                                       font=("Arial", 10, "bold"), justify="center", tags=self.help_tags)
            
            # Кнопка закриття
            self.app.canvas.create_text(w//2, h - 30, text="Натисніть F1 знову для закриття", 
                                       fill="#ffaa00", font=("Arial", 9, "italic"), tags=self.help_tags)
