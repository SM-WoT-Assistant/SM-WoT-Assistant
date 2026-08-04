# Painter, DrawingPalette, Overlay

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

## Painter (30.05.2026)
1. **Редагування маркера/тексту:** правий клік → контекстне меню (painter.py:on_right_click) → Редагувати / Видалити. Редагування через `DrawingPalette` (painting_palette.py) — live sync без модального діалогу.
2. **Видалення:** контекстне меню → Видалити → підтвердження (кастомний діалог, painter.py:_confirm_delete). Або кнопка «Видалити» в DrawingPalette (painting_palette.py:_delete_selected → painter.py:_delete_edited_object).
3. **Зміна напрямку вектора:** Ctrl+перетягування кінчика стрілки (target_kind "marker_tip") — рухається тільки кінець, початок фіксований.
4. **Текст маркера** — не рухається при переміщенні маркера (абсолютна позиція).
5. **Іконки класів:** ПТ=0x2E, САУ=0x2D (XVMSymbol font).
6. **Іконка "Зламане дерево"** (06.06.2026): FontAwesome символ `chr(0xF18C)` (fontawesome-webfont.ttf). Рендериться через `canvas.create_text` з шрифтом FontAwesome, колір через fill=. SVG-рендеринг через PyQt6 видалено. Кешування не потрібне (шрифтовий символ).
7. **DrawingPalette** (painting_palette.py) — плаваюча палітра замість старого `draw_menu` + `PainterDialog`. Авто-deactivate після створення об'єкта. Ctrl+Z undo через keyboard хук. Ctrl+↑/↓ resize в edit mode (debounce 150ms від double-fire keyboard+bind_all).
8. **PainterDialog** (painter.py) — ВИДАЛЕНО (06.06.2026). Замінено на DrawingPalette.
9. **Автовисота DrawingPalette** (03.08.2026): (a) `show()` викликає `_refresh_linked_schemes_list()` після відновлення `_saved_pos` — висота підганяється під поточний контент (секція Groups + linked schemes) при КОЖНОМУ показі. (b) `_adapt_palette_height()` оновлює `_saved_pos` при зміні висоти — збережена геометрія завжди актуальна. (c) `_hide_download_inline()` викликає `_adapt_palette_height()` — після закриття Download (580×780) кнопки груп не обрізаються. Корінь старого бага: `show()` скидав висоту на 520 з `_saved_pos` (встановленого `_restore_position()`), перезаписуючи підігнану висоту; `_adapt_palette_height` викликався тільки при create/join групи.


## Overlay для малюнків (30.05.2026)
1. Малюнки користувача рендеряться на окремому Toplevel (`_po_win`) з `-transparentcolor=#010101` та `alpha=1.0`.
2. Це дозволяє змінювати прозорість ГОЛОВНОГО вікна (мапи) незалежно від малюнків.
3. Overlay показується тільки при `active_view == "maps"`, ховається при перемиканні на stats/ai_stats.
4. Позиція синхронізується через Configure на canvas та root (`_sync_po_pos`).
5. MapPainter отримує overlay canvas замість основного.
6. Події (click/drag/right-click) біндяться на обидва канваси (main + overlay) через `bind_events_to()` (painter.py:232), викликається з `_init_painter_overlay()` (main.py:159-160).


## Overlay startup fix (29.06.2026, повторюваний баг)
1. `_sync_po_pos()` у `finish_startup_splash()` (main.py:1637-1638) — overlay завжди `withdrawn` після зміни геометрії. **ОБОВ'ЯЗКОВО** викликати `_po_win.deiconify()` перед `_sync_po_pos()`.
2. `on_map_select()` (main.py:720-721) — `lift()` не працює для withdrawn вікна. **ОБОВ'ЯЗКОВО** перевіряти `state() == "withdrawn"` → `deiconify() + _sync_po_pos()`.
3. `get_edit_extra_height()` має fallback 130 (main.py:329) — при зміні кількості панелей (додаванні/видаленні) fallback ТРЕБА оновлювати.
4. `window_manager.py:97` — `settings.get("edit_h", self.app.w + 130)` — 130 в default edit_h.
5. `finish_startup_splash()` ПОВИНЕН перераховувати `self.h = self.w + get_edit_extra_height()` після створення всіх панелей, щоб перезаписати stale edit_h з settings.
6. Після `root.deiconify()` → `winfo_rootx/y()` може бути (0,0) поки window manager не поставив вікно. **ОБОВ'ЯЗКОВО** використовувати `root.after(100, ...)` для першого `_sync_po_pos()`.
7. Ці шість пунктів треба перевіряти при КОЖНІЙ зміні `finish_startup_splash()`, `on_map_select()`, `get_edit_extra_height()`, `initialize_window()` — без винятків.
8. **`root.minsize(self.w, self.h)`** — обов'язково після зміни геометрії в `finish_startup_splash()`, щоб вікно ніколи не ставало меншим за сумарний розмір всіх елементів.

