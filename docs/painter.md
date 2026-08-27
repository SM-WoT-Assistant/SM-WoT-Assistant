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
8.  **`root.minsize(self.w, self.h)`** — обов'язково після зміни геометрії в `finish_startup_splash()`, щоб вікно ніколи не ставало меншим за сумарний розмір всіх елементів.
9.  **Фокус після малювання + персистенція товщини/розміру (19.08.2026):**
    - Після створення об'єкта `on_release` викликає `_edit_object_at(len(drawings[map_id]) - 1)` (painter.py:674) — виділення/редагування лишається на намальованому елементі (заміна старого `palette._deactivate_tool()` без виділення).
    - Escape знімає виділення: `<Escape>` bind на обох канвасах (painter.py:151) → `on_escape_deselect` → `palette.exit_edit_mode()`; палітра має власний `<Escape>` bind (painting_palette.py:73). ЛКП на порожньому місці — `painter.py:261-268` (клік по об'єкту = edit, по порожньому = `exit_edit_mode()`).
    - Товщина/розмір персистентні: `_thickness` (painter.py:50) і `_thickness_var`/`_size_var` (painting_palette.py:59-62) ініціалізуються з `settings.draw_thickness`/`draw_size` (дефолт 3 / 1.0); зміни слайдерів пишуть у settings + `app.save_settings()` (`_save_draw_prefs`), гвард `_loading_obj` блокує перезапис при завантаженні об'єкта в палітру; нові об'єкти отримують збережені значення через `"thickness": self._thickness` (painter.py:638) та `obj["scale"] = self._size_var.get()` (`_write_to_object`, painting_palette.py:1537/1565).

## Фільтри/буфер — фінальний стан (27.08-28.08.2026, кроки 1-3)
1. **Значки класів ВИДАЛЕНО** — чекбокси палітри (LT/MT/HT/TD/SPG) — це чисті теги `obj["classes"]`; іконки на елементах не малюються. Легаси `class_icon_coords` у збережених JSON інертний (preserve в undo/переміщенні, painter.py ~189-190/454/530).
2. **Фільтрація завжди активна** (`is_visible`; гейт `sync_schemes_with_mode` видалений разом з чекбоксом/ключем): порожні теги = видно всюди; теги = перетин з фільтром вікна редагування (радіо режиму + чекбокси класів) або авто-визначенням перед боєм. UK-легасі класи нормалізуються (`_UKR_TO_EN`, painter.py:821).
3. **Чекбокси режимів палітри ВИДАЛЕНО** (рішення юзера 26.08): режим задається радіо вікна редагування. `mode_vars`/`mode_labels`/UI-блок прибрані; `_write_to_object` більше не пише `obj["modes"]`; старий `battle_mode` ключ видалено (залишився `battle_mode_label`).
4. **Буфер обміну Ctrl+C/Ctrl+V** (крок 2 + фікси 28.08): диспетчер по keycode (VK 67=copy, 86=paste) на `<Control-KeyPress>` — root (painter.__init__), оверлей `_po_win` (main.py `_init_painter_overlay`), палітра, обидва канваси (bind_events_to); `"break"` = однократне спрацювання. **Біт state 0x8 НЕ фільтрується** — на реальних Windows супроводжує звичайний Ctrl (state=12, доказ [CLIP] 28.08). Гард текстових полів (`_clipboard_focus_in_field`: entry/text/spinbox/combobox) лишає нативне копіювання. Копія: зсув +20px каскадом (`_paste_count` скидається на copy), `modes=[]` (універсальна), класи з поточних чекбоксів палітри; зберігається через `data_mgr.save_drawings` БЕЗ `_strip_duplicates` (свідоме дублювання); у `_creation_history` (Ctrl+Z); одразу виділена. Статус-підказки (`element_copied/pasted/copy_none/paste_none`).
5. **on_press select-all блок** — вкладеність всередині `if self._select_all:` ОБОВ'ЯЗКОВА (розвкладеність давала UnboundLocalError: palette, фікс f18e245).


