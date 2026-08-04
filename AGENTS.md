# Правила роботи з проектом WoT Assistant

## Критичне правило (СУВОРО, 100-й раз)
1. **НІКОЛИ НІЧОГО НЕ ВИГАДУВАТИ!** Жодних власних інтерпретацій, фантазій, "напевно", "мабуть", "можна припустити". Тільки те, що є в коді, документації та відповідях користувача.
2. Якщо не впевнений — запитай, а не вигадуй.

## Джерела даних (СУВОРО)
1. ВСІ дані беруться ТІЛЬКИ з клієнта гри (WotXmlParser декодування XML) або з відповідей ШІ.
2. НІЯКИХ хардкоджених списків, фалбеків, кешів без прямого дозволу.
3. КОЖНЕ твердження "це з клієнта" має супроводжуватись доказом: файл + рядок коду.

## Картка танка
1. Вся інформація про білд — з Firebase RTDB (`builds/tanks/{tag}`), кешується локально в `ai_builds_cache.json`.
2. Якщо Firebase недоступний і кеш порожній — показувати пусті секції (без фалбеків).
3. Промпти для генерації білдів зберігаються на Firebase (`prompts/tanks/{tag}`), використовуються адміном.
4. Кешування включаємо тільки за прямим наказом і документуємо у цей файл всі кеші які працюють у проекті.

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

## Cache validation rules (25.07.2026, дійсні для Firebase архітектури)
1. **stats_ai.py:_is_build_complete()** — статична валідація: перевіряє `equipment_1` та `consumables_1` не пусті.
2. **stats_ai.py:_apply_ai_build()** — кешує білд тільки якщо `_is_build_complete(build_data) == True`. Інакше — `not caching`.
3. **stats_ai.py:_parse_ai_tank_build()** — якщо `loadout1_eq` та `loadout2_eq` обидва пусті → `return {}`. Те саме для consumables.
4. **stats_ai.py:process_ai_response()** — видалено. Валідація на `len(valid_tanks) < 5` тепер у `_sync_popular_tanks()`.
5. **stats_ai.py:__init__** — при завантаженні кешу теги, що не знайдені в `tank_db`, матчаться через `_build_name_to_tag_lookup()`. Якщо після резолву <5 валідних — кеш ігнорується.

## Активні кеші проекту (станом на 27.05.2026)
1. `popular_tanks_cache.json` — дисковий кеш популярних танків з відповіді ШІ (stats_ai.py:18, 7 днів, fail_count)
2. `composite_cache` — in-memory dict, кеш композитних іконок танків (stats_ai.py:82)
3. `loadout_icon_cache` — in-memory dict, кеш іконок обладнання/витратних/перків (stats_ai.py:84)
4. `tth_icon_cache` — in-memory dict, кеш іконок рядків ТТХ (stats_ai.py:85)
5. `_field_mod_pairs_cache` — in-memory dict, кеш пар польової модернізації (stats_ai.py:86)
6. `service_messages.json` — дискова черга службових подій для відкладеної доставки (service_messages.py:13)
7. `ukrainian_map_names_cache.json` — дисковий кеш назв мап (map_extractor.py:111)
8. `ai_builds_cache.json` — дисковий кеш AI build для карток танків (stats_ai.py:35, 30 днів, fail_count)
   - `ENABLE_AI_BUILD_CACHE=True`
   - fail_count скидається при успіху, log_event кожні 3 невдачі (`_handle_ai_build_failure`, stats_ai.py:47)
   - `_is_cache_expired(updated_iso, max_days=7)` — спільна функція з параметром (stats_ai.py:76)

## Неактивні/тимчасово вимкнені кеші
1. `equipment_loadouts.json` — вимкнено для тестування AI механізму (stats_ai.py:2285)
2. `crew_builds.json` override — вимкнено для тестування AI механізму (stats_ai.py:2286)

## Зміна в генерації промпту (28.05.2026)
1. `generate_prompt_v2.py:575` — "Current date: 2026-05-28." замінено на "2026 year"
   - Причина: рядок "Current date: ..." блокував AI відповідь для окремих танків (Google AI Mode ігнорував запит з повною датою для певних назв)
   - Рік динамічний: `datetime.now().strftime("%Y")`
2. `generate_prompt_v2.py:610` — крапку після year прибрано ("2026 year." → "2026 year")
   - Причина: крапка блокувала AI відповідь для T-46, BT-SV, Ram II, WZ-111 (та сама проблема що й з повною датою)

## Мапи та сітка координат (30.05.2026)
1. Сітка 10×10 (колонки 0-9, рядки A-J) малюється поверх карти в MAPS режимі (map_renderer.py:draw_grid).
2. Координати сітки обчислюються з `boundingBox` з `map_data.json` — діленням на 10 по X та Z.
3. Підписи колонок (цифри 0-9) — зверху та знизу, рядків (букви A-J) — зліва та справа, на темно-сірій рамці (#333333) навколо карти.
4. Лінії та підписи сітки — сірі (#777777).
5. Рамка сітки 25px (`grid_border`), реалізована як outline навколо квадратної мапи (map_renderer.py:draw_grid). Крайові лінії сітки (0/10) пропущено — вони під рамкою.
6. При зміні розміру сітки (grid_cols/grid_rows) — змінити в map_renderer.py:9-10.

## Механіки гри (з клієнта)
1. Слоти обладнання: Tier 1→0, Tier 2→1, Tier 3→1, Tier 4-5→2, Tier 6-11→3 (tank_slots_full.json: equipment_slots)
2. Кількість перків: Tier 1-4→1, Tier 5-6→2, Tier 7→4, Tier 8-11→6 (crew_builds.json: _perk_policy.primary_perk_count_by_tier)
3. Secondary перки: завжди 3 (crew_builds.json: _perk_policy.secondary_perk_bonus_per_role)
4. Польова модернізація: Tier 6-10 включно. Tier 1-5 та 11 — НЕМАЄ.
5. Post-progression (experimental обладнання): tank_slots_full.json: has_post_progression
6. Екіпаж: 2-6 осіб. Secondary ролі — масив `also` з crew_builds.json

## AGENTS.md
1. Цей файл читається перед кожною дією.
2. Якщо правило порушено — негайно виправити.
3. Після кожного виправлення — негайно перевірити результат (тест або запуск).

## Overlay для малюнків (30.05.2026)
1. Малюнки користувача рендеряться на окремому Toplevel (`_po_win`) з `-transparentcolor=#010101` та `alpha=1.0`.
2. Це дозволяє змінювати прозорість ГОЛОВНОГО вікна (мапи) незалежно від малюнків.
3. Overlay показується тільки при `active_view == "maps"`, ховається при перемиканні на stats/ai_stats.
4. Позиція синхронізується через Configure на canvas та root (`_sync_po_pos`).
5. MapPainter отримує overlay canvas замість основного.
6. Події (click/drag/right-click) біндяться на обидва канваси (main + overlay) через `bind_events_to()` (painter.py:232), викликається з `_init_painter_overlay()` (main.py:159-160).

## Релізний механізм (09.06.2026)

### Створення релізу
Кожен білд автоматично створює GitHub release + публікує в RTDB.
1. `python build.py` — білд + GitHub release + RTDB (поточна VERSION)
2. `python build.py 1.0.2` — оновити VERSION → білд + GitHub release + RTDB
3. `python build.py 1.0.2 --date=2026-06-21` — білд з кастомною датою релізу

### Фази білду (build.py)
1. **Pre-flight** — валідація semver (X.Y.Z), Python 3.12+PyInstaller, NSIS (makensis.exe), gh CLI, критичні файли (main.py, VERSION, wot_assistant.spec, logo.png), git status
2. **Clean** — видалення `dist/SM WoT Assistant/` та `build/`
3. **PyInstaller** (onedir) → `copy_data_files()` (3065 data files) → NSIS installer
4. **Rename** onedir: `dist/SM WoT Assistant/` → `dist/SM WoT Assistant vX.Y.Z/`
5. **Portable ZIP**: `SM_WoT_Assistant_Portable_vX.Y.Z.zip` (~390 MB)
6. **Verify**: EXE, 10 critical JSONs, VERSION, fonts, maps/≥50, extracted_maps/≥60, extracted_icons/≥8
7. **Manifest**: `dist/build_manifest_vX.Y.Z.txt` (усі файли + розміри)

### Артефакти релізу в dist/
- `SM WoT Assistant vX.Y.Z/` — версіонований onedir (~5795 файлів, ~750 MB)
- `SM_WoT_Assistant_Setup_vX.Y.Z.exe` — NSIS інсталер (~320 MB, lzma 42.4%)
- `SM_WoT_Assistant_Portable_vX.Y.Z.zip` — portable ZIP (~390 MB)
- `build_manifest_vX.Y.Z.txt` — маніфест білду

### Інструменти для білду
- Python: Python 3.12 (PyInstaller 6.20.0) — Python 3.14 має баг DATA TOC
- NSIS: `C:\Program Files (x86)\NSIS\makensis.exe` (build.py:find_nsis auto-detect)
- GitHub CLI: `gh` (обов'язково)
- `PyInstaller 6.x` баг: DATA entries з Analysis не потрапляють у COLLECT → обхід: `copy_data_files()` копіює дані вручну після PyInstaller

### Включення файлів у бандл (copy_data_files)
- Усі `*.json` з кореня проєкту, КРІМ: `opencode.json`, `magic-context.jsonc`, `_fill_progress.json`, `.*_manifest.json` (3), `tomato_*.json` (6), `ukrainian_map_names.json`, `vehicle_slots_*.json` (2)
- `VERSION`, TTF шрифти (xvmsymbol.ttf, fontawesome-webfont.ttf), .mo файли (3), `logo.png`
- `maps/` (51 папка), `extracted_maps/` (63 файли), `extracted_icons/` (8 піддиректорій), `extracted_data/common/post_progression/`
- `wot_assistant.spec` — синхронізований exclusion-list (довідково, не використовується через баг)

### Версія у вікнах програми
- Головне вікно: `main.py:1107` — `root.title(f"SM WoT Assistant v{config.load_version()}")`
- Splash: `main.py:1045` — `config.load_version()`
- Редактор (водяний знак): `map_renderer.py:249` — `config.load_version()`
- Довідка (F1): `help_system.py:49` — `config.load_version()` (через import config)
- AI WebView: `ai_webview_gui.py:28` — `_read_version()` (читає VERSION, не імпортує config)

### Seeding файлів у AppData (перший запуск)
- `config.DEFAULT_FILES` (config.py:34) = `["settings.json", "locales.json", "map_drawings.json", "service_messages.json", "popular_tanks_cache.json", "ai_builds_cache.json"]`
- `main.py:1093-1101` — копіює з `config.BUNDLE_DIR` в `config.USER_DATA_DIR` якщо файл ще не існує
### Auto-commit версії

build.py автоматично комітить VERSION та installer.nsi після оновлення версії (build.py:commit_version_files). Окремо комітити не треба — це робить build.py перед білдом.

### Порядок дій для нового релізу

`python build.py X.Y.Z` робить все: білд + GitHub release + RTDB. Verify phase перевіряє автоматично.
Після білду запустити `dist/SM WoT Assistant vX.Y.Z/SM WoT Assistant.exe` — smoke test.

## Системний трей (29.06.2026)
1. **F10 / кнопка `─`** — `toggle_visibility()` (main.py:639) → `_minimize_to_tray()` ховає вікно в системний трей.
2. **`tray_icon.py`** — чистий ctypes WinAPI (`Shell_NotifyIconW(NIM_ADD/DELETE)`), жодних зовнішніх залежностей.
3. **Трей-іконка** — `icon.ico` з кореня проєкту, завантажується через `LoadImageW`, розмір системної small icon.
4. **Message-only window** — `CreateWindowExW` + `HWND_MESSAGE` + кастомний `WNDPROC` через `WINFUNCTYPE`.
5. **Polling 250ms** — `after()` цикл перевіряє `_click_flag` встановлену WNDPROC при `WM_LBUTTONUP`/`WM_RBUTTONUP`.
6. **`_hidden_by_f10`** — прапорець-захист, блокує всі шляхи що можуть показати оверлей поки програма в треї:
   - `_lift_overlay()` (main.py:296)
   - `_on_root_show()` (main.py:307)
   - `_restore_overlay_state()` (main.py:733)
   - `on_map_select()` (main.py:711)
   - `show_view("maps")` (ui_manager.py:335)
7. **Кнопка `─`** — в `top_bar` перед ✕ (ui_manager.py:27), стиль: `bg="#444", fg="white", padx=10, font=("Arial", 12, "bold")`.
8. **Cleanup** — `quit_app()` видаляє трей-іконку (`TrayIcon.remove()` → `Shell_NotifyIconW(NIM_DELETE)` + `DestroyWindow` + `DestroyIcon`).
9. **Build** — `tray_icon.py` імпортується з `main.py`, автоматично підхоплюється PyInstaller. `icon.ico` вже включено в `copy_data_files()`.

## Система груп та схем (30.06.2026)
1. **firebase_groups.py** — модуль управління групами в RTDB. Функції: `create_group()`, `join_group()`, `leave_group()`, `get_user_groups()`, `publish_to_group()`, `update_group_scheme()`, `get_group_schemes()`, `get_group_schemes_meta()`, `import_between_groups()`.
2. **RTDB структура:** `groups/{group_id}/{name, description, invite_code, members/{uid}, schemes/{drawing_id}}`. `user_groups/{uid}/{gid}` — швидкий пошук груп користувача.
3. **Group selector** (ui_manager.py:setup_ui) — `ttk.Combobox` в `map_toolbar` після `draw_btn`. Показує "Public" та список груп. Другий віджет — `group_token_btn` з інвайт-кодом (officer) або 🔒 (member). Показується тільки для зареєстрованих.
4. **Фільтр мап:** коли вибрана не-Public група, `load_map_list()` (map_manager.py:400) фільтрує список мап — тільки ті, що мають схеми у вибраній групі.
5. **Фільтр схем:** `painter.py:redraw()` рендерить тільки схеми з group_id == active_group_id.
6. **Group management** (painting_palette.py:_build_ui) — секція Groups на дні палітри (після _status_lbl). Кнопки Create/Join/Manage відкривають `overrideredirect(True)` кастомні діалоги (через `dialog_utils._DragHelper`).
7. **Кастомні діалоги:** всі діалоги груп (Create, Join, Manage) використовують `overrideredirect(True)` + кастомний темний header (`bg="#2a2a2a"`, title + ✕ close button) + `dialog_utils._DragHelper` для перетягування.
8. **Групова схема** — публікується в `groups/{gid}/schemes/{drawing_id}`, не потрапляє в публічні `schemes/`. Сайт (schemes.html) не бачить групових схем.
9. **Вибір публікації:** якщо активна група != public → Publish публікує в групу. Якщо public → у публічні schemes/ (як раніше).
10. **Download діалог** (painting_palette.py:_download_populate, _build_download_ui): завантажує публічні схеми + схеми з груп користувача. Додано колонку Source (Group/Public) та фільтр Source.
11. **Link (auto-sync)** — групові схеми можна встановити як посилання (painter._group_schemes), вони відображаються разом з локальними малюнками і автоматично оновлюються при зміні на сервері.
12. **Sync polling 60s** (main.py:_start_group_sync, _sync_cycle): перевіряє updated_at в RTDB кожні 60с. При зміні показує `overrideredirect(True)` сповіщення "Scheme updated by OfficerName. Download now?".
13. **Кеш групових схем** (config.GROUP_CACHE_FILE = `group_schemes_cache.json` в USER_DATA_DIR): зберігається при завершенні, завантажується при старті.
14. **database.rules.json** — додано індекси для `groups/` (invite_code, created_at) та `user_groups/`.
15. **_DragHelper** (dialog_utils.py:17-25) — клас для перетягування `overrideredirect` вікон. Параметри: `toplevel`, `frame`. Використовується в усіх кастомних діалогах.
16. **Токен групи:** інвайт-код з кнопкою Copy на top_bar поруч з group_selector. Для officer — показує код (#ffaa00) + clipboard copy. Для member — 🔒. Для Public — прихований.
17. **_show_group_sync_notification** (main.py:1815) — `overrideredirect(True)` + кастомний header + `_DragHelper`.
18. **Захист від дублікатів назв груп** (03.08.2026): у одного користувача не може бути двох груп з однаковою назвою. `create_group()` (firebase_groups.py) перевіряє `get_user_groups(uid)` перед PUT — при збігу назви (case-insensitive) повертає (None, "Ви вже маєте групу з такою назвою") БЕЗ створення. `join_group()` — та сама перевірка назви цільової групи ПІСЛЯ гілки "вже член" (повторний join своєї групи працює). UI не змінювався — do_create/do_join вже показують повернену помилку через status_var. Причина бага: користувач створив дві групи "001" (5eb72871/5147D4 та 98e53f80/B22858) → `_group_id_map` (ui_manager.py:199) колізія ключа label → обидва items селектора вели до однієї групи → "однаковий інвайт". Дубль 5eb72871 видалено з RTDB.
19. **`_put(path, None)` фікс** (03.08.2026, firebase_reporter.py:66, admin_build_generator.py:45 `_put_json`): `requests.put(json=None)` не шле тіло → RTDB 400 → ВСІ видалення тихо не працювали (leave_group, kick_member, delete_group, delete_group_scheme, admin `_cleanup_old_error_reports`). Тепер `data is None` → `requests.put(url, data=b"null", headers={"Content-Type": "application/json"})` → 200. DELETE-еквівалент: PUT null.

## Overlay startup fix (29.06.2026, повторюваний баг)

## Overlay startup fix (29.06.2026, повторюваний баг)
1. `_sync_po_pos()` у `finish_startup_splash()` (main.py:1637-1638) — overlay завжди `withdrawn` після зміни геометрії. **ОБОВ'ЯЗКОВО** викликати `_po_win.deiconify()` перед `_sync_po_pos()`.
2. `on_map_select()` (main.py:720-721) — `lift()` не працює для withdrawn вікна. **ОБОВ'ЯЗКОВО** перевіряти `state() == "withdrawn"` → `deiconify() + _sync_po_pos()`.
3. `get_edit_extra_height()` має fallback 130 (main.py:329) — при зміні кількості панелей (додаванні/видаленні) fallback ТРЕБА оновлювати.
4. `window_manager.py:97` — `settings.get("edit_h", self.app.w + 130)` — 130 в default edit_h.
5. `finish_startup_splash()` ПОВИНЕН перераховувати `self.h = self.w + get_edit_extra_height()` після створення всіх панелей, щоб перезаписати stale edit_h з settings.
6. Після `root.deiconify()` → `winfo_rootx/y()` може бути (0,0) поки window manager не поставив вікно. **ОБОВ'ЯЗКОВО** використовувати `root.after(100, ...)` для першого `_sync_po_pos()`.
7. Ці шість пунктів треба перевіряти при КОЖНІЙ зміні `finish_startup_splash()`, `on_map_select()`, `get_edit_extra_height()`, `initialize_window()` — без винятків.
8. **`root.minsize(self.w, self.h)`** — обов'язково після зміни геометрії в `finish_startup_splash()`, щоб вікно ніколи не ставало меншим за сумарний розмір всіх елементів.

## Tray Watcher (19.07.2026)
1. **tray_watcher.py** — мінімальний процес-спостерігач (чистий stdlib + ctypes, без tkinter/PIL/requests).
2. **Принцип роботи:** стартує з Windows (HKCU\Run), слідкує за WorldOfTanks.exe кожні 5с. Коли гра запускається → запускає launcher.exe (повноцінний лаунчер зі сплешем). Після запуску програми — продовжує спостереження.
3. **close_with_game:** новий чекбокс в Settings. Якщо True + гра закрилась → tray_watcher TerminateProcess для SM WoT Assistant v*.exe. Після закриття — повертається до спостереження.
4. **Ланцюжок:** Windows boot → tray_watcher.exe (0 вікон) → WoT запустився → launcher.exe (splash) → main.exe (--tray якщо start_minimized) → WoT закрився + close_with_game → main.exe закривається → повернення до спостереження.
5. **HKCU\Run тепер:** `"C:\...\SM WoT Assistant Tray Watcher.exe"` (замість `launcher.exe --tray`). Fallback на launcher --tray якщо tray_watcher.exe не знайдено.
6. **launcher.py:_launch_main()** — тепер читає start_minimized з settings.json і передає --tray до main.exe.
7. build.py:build_tray_watcher() — збирає tray_watcher.py як --onefile (без hidden-imports, тільки stdlib). Верифікація білду перевіряє наявність Tray Watcher EXE.

## Dev PID file (22.07.2026)
1. **dev_pid.txt** (`%APPDATA%\SM WoT Assistant\dev_pid.txt`) — механізм для роботи tray_watcher з dev-версією (`python main.py`). PID-файл вирішує дві проблеми: (1) `_find_main_pids()` не бачить `python.exe`, (2) mutex блокує запуск frozen EXE поруч з dev.
2. **main.py:** `_write_dev_pid()` пише PID при старті (тільки не frozen) → `atexit.register(_dev_pid_cleanup)` на чистку. Явне `_dev_pid_cleanup()` перед обома `os._exit(0)` в update-шляхах.
3. **tray_watcher.py:** `_find_dev_pid()` — читає dev_pid.txt, валідує що PID живий і це `python.exe`/`pythonw.exe` (через CreateToolhelp32Snapshot, не `OpenProcess`). `_get_main_pids()` об'єднує frozen EXE + dev PID. `_launch_app()` пропускає запуск якщо `_get_main_pids()` не пустий (dev вже працює). `_close_main_app()` вбиває всі PID з `_get_main_pids()` включно з dev.
4. **Безпека:** stale PID-файл після hard crash не шкодить — `_find_dev_pid()` валідує що PID живий і це саме python. Жодних змін в `launcher.py`, `build.py`, HKCU\Run.
5. **PE_SIZE fix:** `PE_SIZE` (sizeof PROCESSENTRY32W) змінено з hardcoded 556 на 568/556 залежно від бітності (`ctypes.sizeof(ctypes.c_void_p)`). 556 — для 32-bit, 568 — для 64-bit. Це виправляє баг через який `Process32FirstW` падав з `ERROR_BAD_LENGTH` на 64-bit Windows, роблячи всі функції сканування процесів (`_is_wot_running`, `_find_main_pids`, `_find_dev_pid`) повністю несправними.

## Firebase Distribution Architecture (25.07.2026)
1. **Всі AI білди та промпти** зберігаються на Firebase RTDB — клієнт більше НЕ запускає AI WebView.
2. **Білди:** `builds/tanks/{tag}`, версія `builds/version`, склад `builds/scripts_fingerprint`.
3. **Промпти:** `prompts/tanks/{tag}`, `prompts/popular_tanks` — для адміна (генерація).
4. **Popular tanks:** `popular_tanks/data`, `popular_tanks/version`.
5. **Pending updates:** `pending_updates/popular_tanks/` та `pending_updates/builds/` — тригери для адміна.
6. **stats_ai.py:** AI WebView ВИДАЛЕНО (`launch_ai_browser`, `process_ai_response`, `_handle_ai_failure`, `_re_enable_ui`). Замінено на `_sync_popular_tanks()` та `_sync_builds()` — Firebase fetch при старті.
7. **stats_ai.py `needs_ai_refresh()`** — завжди повертає `False` (AI не використовується).
8. **stats_ai.py `stop_browser()`** — no-op.
9. **main.py:** AI стартап видалено (`_start_ai_phase`, `_ai_progress_creep`, `_on_ai_ready`, `_cancel_ai_timers`, `_ai_safety_timeout`). `_on_startup_ready()` → `finish_startup_splash()` → фоновий `_start_firebase_sync()`.
10. **main.py:** `--ai-webview` CLI handling ВИДАЛЕНО.
11. **Кеші залишаються:** `ai_builds_cache.json` (994 білди, включено в бандл), `popular_tanks_cache.json` (сідається з `popular_tanks_seed.json`).
12. **`_load_ai_build_cache()`** тепер повертає 5 значень: `(builds, updated, fail_count, version, scripts_fingerprint)`.
13. **`_save_ai_build_cache_bulk()`** — новий bulk save для Firebase.
14. **builds_table.py** — one-time скрипт для початкової заливки всіх білдів + промптів + популярних танків у Firebase.
15. **prompts_cache.json** — 994 промпти, згенеровані `builds_table.py`, включено в бандл (не в DEFAULT_FILES — використовується тільки адміном).

## Rebalance detection chain (27.07.2026)
1. **map_manager.py:check_game_version()** — при виявленні зміни версії гри (`version_changed=True`) або зміни вмісту `scripts.pkg` (`ext.has_changed()`) записує тригер у Firebase: `firebase_reporter._put("pending_updates/builds", {status:"idle", version, scripts_pkg_changed:true})`.
2. **admin_build_generator.py --listen** — полінг `pending_updates/builds` кожні 10с. При появі `status=="generating"` запускає `generate_builds(driver, tank_db, prompts, force=True)` — генерація ВСІХ танків з ігноруванням кешу.
3. **`_update_builds_version()`** — після генерації оновлює `builds/version` (інкремент) та `builds/scripts_fingerprint` (MD5 від `{ver, ts}`).
4. **stats_ai.py:_sync_builds()** — при старті клієнта порівнює `remote_version != local_version` → force re-sync ALL танків.
5. **Повний ланцюжок:** `scripts.pkg змінився → client detect → pending_updates → admin --listen pick up → generate_all → bump version+fingerprint → client sync`.

## admin.html changes (27.07.2026)
1. **Видалено**: кнопка "Regenerate All Builds" (непрактично — 994 танки через AI).
2. **Видалено**: `#builds-table-container` (незавершений placeholder "Loading...").
3. **Auto-expand**: секції (Errors, Schemes, Releases, AI Builds) з новими даними відкриваються автоматично, заголовок отримує `✦` та колір `#ff4500`.
4. **Highlight**: нові рядки (`isFresh()` перевірка по `admin_last_visit`) отримують CSS клас `row-new` з анімацією затемнення 3s.
5. **`_lastBuildsVersion`** — зберігається в `localStorage`, при зміні секція AI Builds авто-розкривається.

## Admin app fixes (31.07.2026)
1. **WoT path auto-detect** (admin_app.py:_resolve_wot_path) — ланцюг: CLI `--wot-path` → admin_settings.json → головний `%APPDATA%/SM WoT Assistant/settings.json` wot_path → common paths (той самий список що map_manager.py). Валідація через `version.xml`. Знайдений шлях зберігається в admin_settings.json.
2. **Хрестик → трей** — `_on_close()` робить `root.withdraw()` (програма живе, фоновий цикл працює). Повний вихід — вікно → ⚙ → **Exit** (з 31.07.2026, вечір; раніше був трей-меню).
3. **Трей-іконка — тільки показати вікно** — ЛКМ (0x0202) або даблклік (0x0203) → `deiconify()+lift()` прямо у wndproc. **КОНТЕКСТНОГО МЕНЮ НЕМАЄ.** Причина: три незалежні спроби меню (tk_popup, menu.post, кастомний Toplevel) падали з крахом `abort()` 0xC0000409 в ucrtbase (offset 0x7286e — функція abort; підтверджено Event Log Id 1000). Корінь: reentrant Tk-виклики / file I/O зсередини трей-callback (wndproc виконується в dispatch-контексті Tk). **Правило: трей wndproc = чистий форвардер — тільки простий присвоєння/деiconify, жодного Tk, жодного I/O, жодної логіки поза try/except.**
4. **Балон при старті в трей** — "Running in tray (WoT: ...)" через `tray.show_notification()`.
5. **build_admin.py selenium hidden imports** — `selenium.webdriver.chrome.webdriver` (критичний, lazy-import selenium 4), `selenium.webdriver.chrome.service`, `selenium.webdriver.chrome.options`, `selenium.webdriver.common.service`, `selenium.webdriver.common.selenium_manager`, `selenium.webdriver.common.driver_finder`. Без них frozen EXE падав: `No module named 'selenium.webdriver.chrome.webdriver'` — генерація НЕ працювала ніколи.
6. **Генерація вимагає закритий Chrome** — `_create_driver()` використовує реальний профіль `C:\Users\PRO\AppData\Local\Google\Chrome\User Data` + `--profile-directory=Default`; якщо Chrome запущений — "session not created: Chrome instance exited" (профіль заблокований).
7. **Маніфест змін танків у AppData** (admin_app.py:_resolve_manifest) — `.tank_extract_manifest.json` тепер живе в `%APPDATA%/SM WoT Assistant/`, НЕ в CWD. Причина: frozen onefile CWD = `%TEMP%\_MEIxxxxx`, відносний шлях маніфесту не знаходився → `old={}` → detect завжди повертав ВСІ 1309 танків → авто-генерація при кожному старті/таймері (30 хв WG / 60 хв scan) → вікна Chrome з домашньою сторінкою (handoff у запущений Chrome) + балон "Chrome instance exited" вічно. Сід при першому запуску: CWD-копія ТІЛЬКИ якщо свіжа (detect по ній == 0), інакше snapshot поточного scripts.pkg (`snapshot_manifest()`) → перший запуск завжди = 0 змін. Всі 3 виклики `detect_changed_tanks()` передають `manifest_path=self._manifest_path`.
8. **Оновлення маніфесту після генерації** — `update_manifest_for_tags(wot_path, manifest_path, tags)` (admin_build_generator.py): після `ok=True` записи згенерованих тегів оновлюються поточними fingerprint-ами → танки не редетектуються вічно кожні 60 хв. Семантика збігається з існуючим pop queue. `_MANIFEST_LOCK` (threading.Lock) захищає читання detect + записи (snapshot/update).
9. **⚙ шестірня → випадаюче меню** — `_show_settings_menu()` (tk.Menu tk_popup під кнопкою, той самий паттерн що в головній програмі): чекбокси Start with Windows / Start minimized to tray + пункт "WoT Path..." → `_show_wot_path_dialog()` (маленький Toplevel з полем шляху + Save). З 31.07.2026 (вечір) додано **Exit** в кінці меню — єдиний шлях повного виходу. Старого діалогу Admin Settings зі всіма налаштуваннями більше немає.

## Admin app i18n + log (01.08.2026)
1. **Реверс логу** (admin_app.py:_log) — нові повідомлення вставляються в `"1.0"` (зверху), автоскрол `see("1.0")`, обрізання `delete("1000.0", tk.END)` (макс. 1000 рядків у widget). Файл `admin.log` НЕ змінюється (як був append).
2. **Копіювання повідомлень** — ПКМ на логу (і на тексті хелпу) → контекстне меню Copy / Select All (будується свіжим при кожному popup — завжди актуальна мова). `_copy_selection(widget)` → clipboard. Ctrl+C працює штатно.
3. **i18n EN/UK** — авторитетний словник `_TR_EN` (99 ключів) в admin_app.py. `self.t(key, **fmt)` повертає поточну мову (`_lang` з admin_settings.json ключ `lang`, default "en"). Кнопка-перемикач EN/UK у топбарі поруч із ⚙ (текст = мова, в яку перемикає). `_apply_lang()` оновлює всі widget-референси з `_tr_widgets` (кнопки, карти, статус).
4. **Кеш української** — `%APPDATA%/SM WoT Assistant/admin_uk_cache.json` = `{"en_snapshot", "uk", "updated_at"}`. `_load_uk_translations()`: при збігу `en_snapshot` з `_TR_EN` → використовує кеш БЕЗ запитів до Google; при зміні ключів → перекладає ТІЛЬКИ змінені/нові через `deep_translator.GoogleTranslator` (`_translate_en2uk`, фолбек на англ). Офлайн → англійська.
5. **Seed** — `admin_uk_seed.json` в репо (згенеровано при розробці, 99 ключів + вручну виправлені криві переклади Google), бандлиться в EXE (`build_admin.py --add-data`), при відсутності кешу використовується як джерело → на свіжій інсталяції нуль запитів.
6. **Захист перекладу** — `_shield()/_unshield()`: плейсхолдери `{n}`, `{path}` і токени (SM WoT Assistant, scripts.pkg, WoT, WG, AI, F1, Ctrl...) захищаються від перекручення Google. Кнопкові мітки перекладаються (не в списку токенів).
7. **Хелп по F1** — `_show_help()`: темний Toplevel 680×560 з read-only ScrolledText, контент `_help_text()` з `_TR_EN` (розділи: Кнопки, Налаштування, Трей, Фонова автоматизація, Лог, F1). Той самий діалог — з меню ⚙ → **Help**. Контент генерується при відкритті (актуальна мова).
8. **Що НЕ перекладається** — `root.title` "SM WoT Assistant Admin vX.Y.Z" (mutex `FindWindowW` шукає за title — second-instance restore), трей tip, назва програми в топбарі.
9. **build_admin.py** — додано `--hidden-import deep_translator` + `--add-data admin_uk_seed.json`. deep_translator підтягує requests/certifi/charset_normalizer автоматично; опційні pypdf/docx2txt/openai не потрібні (GoogleTranslator їх не використовує).
10. **Логіка перекладу з фонових потоків** — `self.t()` тільки читає dict (thread-safe), трей-сповіщення і логи в `_do_scan`/`_do_generate`/`_start_background` перекладаються при виклику.

## Admin app RTDB статус (01.08.2026)
1. **Новий вузол `admin_app/`** — адмінка публікує свою інфу в RTDB: `version` (з admin_version.txt), `last_seen` (epoch-секунди, heartbeat кожні 60с у `_start_background` + при старті), `status` (`idle`/`generating`/`offline`), `last_generation` (`{at: ISO, count, ok}`).
2. **Дата оновлення бази/промптів** — при успіху генерації (`_do_generate`) адмінка пише `builds/last_generated_at` + `prompts/last_generated_at` (однаковий ISO — білди і промпти генеруються разом) та `popular_tanks/last_generated_at` при успіху `_do_popular`.
3. **Живий статус генерації на сайті** — `_do_generate` тепер пише `pending_updates/builds` через `_update_pending_status` (generating/done/error) — раніше це робив тільки CLI-демон `--listen`, GUI-генерація сайт не показувала.
4. **admin.html** — секція "Admin App (Desktop)" стала живою: Admin Version, Status (Online якщо `last_seen` < 5 хв, зелений/червоний), Activity (Idle/Generating), Last Generation (кількість + дата), Builds/Prompts/Popular updated (формат `YYYY-MM-DD HH:MM` без timezone-конвертації — таймстемпи пишуться локальним часом адмінки). `loadAdminAppData()` — при ініціалізації + поллінг кожні 60с.
5. **`_exit_app`** пише `status=offline` (daemon thread — не блокує вихід). При hard-kill статус застаріє через 5 хв за `last_seen`.
6. **RTDB rules** — змін не треба (`.read/.write: true` відкриті). Вузол `admin_app/` не конфліктує з клієнтським синком (stats_ai читає тільки `builds/` та `popular_tanks/`).

## Admin tiers_devices з клієнта (01.08.2026, вечір)
1. **Причина fallback-спаму** (`parse_tiers_devices returned empty`): frozen адмін EXE не мав `temp_scripts/decoded/tiers_devices_decoded.xml` та `temp_scripts2/scripts/.../tiers_devices.xml` (не бандлялись у build_admin.py) → `load_tiers_devices()` повертала `{}` → generate_prompt_v2 падав у hardcoded fallback з `report_fallback` при КОЖНІЙ генерації (8 помилок на сайті за 2 дні).
2. **Виправлення**: `parse_tiers_devices.py` — НОВИЙ перший кандидат: `{wot_path}/res/packages/scripts.pkg` (шлях з `config.SETTINGS_FILE` = AppData settings.json, патерн map_extractor.py:16-18) → `zipfile.ZipFile` (scripts.pkg — це ZIP, запис `scripts/item_defs/vehicles/common/optional_devices/tiers_devices.xml`, 31031 B, бінарний BigWorld `45 4e a1 62`) → `_ensure_decoded` з вихідною директорією `config.USER_DATA_DIR` (писемна; старий шлях `base_dir/temp_scripts/decoded/` ніхто більше не читає) → парс. `_try_client_pkg()` повертає шлях кешованої raw-копії (`tiers_devices_raw.xml` в AppData) або None.
3. **Версія `0.0.0` у звітах**: `firebase_reporter._report_version()` — якщо в `BUNDLE_DIR` є `admin_version.txt` І (frozen АБО немає `VERSION`) → версія з нього (`1.0.2`); інакше `config.load_version()`. Frozen main не змінився (admin_version.txt не бандлиться), dev main не змінився (VERSION є), dev admin = main version (прийнятний компроміс).
4. **build_admin.py** — додано `--add-data temp_scripts/decoded/tiers_devices_decoded.xml → temp_scripts/decoded/` (статичний резерв на випадок зміни структури pkg).
5. **Автоочищення error_reports**: `admin_app.py:_cleanup_old_error_reports()` — REST-запит `error_reports.json?orderBy="timestamp"&endAt="{now-60d UTC}"` (тільки старі записи) → `PUT null` по кожному ключу (патерн delete_group_scheme), подвійна перевірка парсингом `%Y-%m-%dT%H:%M:%SZ` (непарсибельні НЕ видаляються). Запуск: перша ітерація `_start_background` + кожні 24 год (`_last_cleanup`). Лог через ключ `log_cleanup_done` ("Cleaned {n} old error reports (>60 days)").

## mo_maps cache fix + ration source fix (02.08.2026)
1. **R1 (language_module.py:380)**: `generate_mo_maps(lm, lang)` → `generate_mo_maps(src, lang)` де `src = _lang_module if _lang_module is not None else lm`. Причина: у гілці "no change" (кеш `localization/<lang>` існує) `lm.dictionaries` порожній → generate_mo_maps очищав EQUIP_MAP/CONS_MAP/CREW_SKILL_MAP і перезаписував `mo_maps_{lang}.json` ПОРОЖНІМ при кожному повторному запуску. `_lang_module` гарантовано заповнений через `load_cache()` в обох гілках. Перевірено: smoke-запуск створив `mo_maps_uk.json` (26 КБ) на повторному запуску з наявним кешем.
2. **R2 (generate_prompt_v2.py:382)**: `_cons_rev_map()` тепер реверсить `ai_engine.AI_CONS_MAP` (той самий словник, що парсер відповідей) замість `stats_data.CONS_MAP`. Причина: адмінський процес не викликає `generate_mo_maps` → CONS_MAP порожній → `_build_nation_rations()` і `_get_consumables_from_game_data()` (список витратних для Main/Advanced loadout) падали на fallback з `game_entities.json`, де `name = "#artefacts:ration_uk/name"` (нерезолвлені ключі) — сміття в НОВИХ промптах: `Slot 3: MUST be "#artefacts:ration_uk/name"`. Після фіксу NATION_RATIONS = 11 націй з англійськими назвами ("Pudding and Tea", "Bread with Lard", "Improved Rations"...), 0 назв з `#` у списку витратних. Loadout 2 (Advanced) слот 3 завжди = національний раціон (generate_prompt_v2.py:557-561, 660, 674).
3. **admin_version.txt** → 1.0.3 (правило #1446: зміни адмін-програми після 1.0.2 вимагають бамп).

## Cross-session пам'ять (Magic Context plugin)
1. Пам'ять автоматично інжектиться в контекст — перевірка на старті НЕ ПОТРІБНА.
2. **Наприкінці сесії:** зберегти ключові факти в `ctx_memory`:
   - над чим працювали (поточне завдання)
   - які баги/проблеми знайдено
   - які рішення прийнято
   - наступний крок
3. **Під час сесії:** зберегти важливі архітектурні рішення, знайдені шляхи файлів, конфігурації, робочі команди негайно після їх виявлення.
4. **magic-context.jsonc** (02.06.2026): налаштовано на максимум — memory.injection_budget_tokens=20000, auto_promote=true, promotion_threshold=2, retrieval_count=1, auto_search score_threshold=0.3, pin_key_files enabled, embedding=local, sidekick enabled, two_pass historian.

## Single-instance mutex fix (04.08.2026, v1.0.66)
1. **Баг**: `ctypes.windll.kernel32.CreateMutexW` + `ctypes.windll.kernel32.GetLastError()` — GetLastError читається через windll-хендл БЕЗ `use_last_error=True`, тому ЗАВЖДИ повертає 0 → перевірка `== 183` ніколи не спрацьовувала → single-instance тихо не працював: стартували дублі процесів (два tray_watcher.exe, два admin.exe — підтверджено в дикій природі).
2. **Фікс** (4 файли: main.py:83, launcher.py:68, tray_watcher.py:211, admin_app.py:1034): патерн `_k32 = ctypes.WinDLL("kernel32", use_last_error=True)` + `_k32.CreateMutexW.argtypes = (c_void_p, c_bool, c_wchar_p)` + `_k32.CreateMutexW.restype = c_void_p` + перевірка `ctypes.get_last_error() == 183`.
3. **Перевірено** (03-04.08.2026): smoke — 2-й інстанс main.py виходить за ~8с; 2-й dev tray_watcher виходить; встановлені старі EXE (v1.0.65) дають дублі — новий реліз лікує.
4. **tray_watcher.py:13** — `DEBUG = False` (релізна гігієна; DEBUG-принти залишаються в коді).
5. **Реліз**: v1.0.66 (03.08-батч: мутекс-фікс ×4, PUT null у firebase_reporter.py:66/admin_build_generator.py:45, захист дублікатів назв груп firebase_groups.py, автовисота DrawingPalette painting_palette.py, [SYNC]-теги stats_ai.py, чищення тестових залишків). admin_version.txt → 1.0.4.

## Admin build layout onedir (04.08.2026, admin v1.0.4)
1. **build_admin.py** збирає адмінку як **--onedir** у `dist/SM WoT Assistant Admin/` (EXE + `_internal/` з бандлом: admin_version.txt, admin_uk_seed.json, tiers_devices_decoded.xml тощо). Раніше був --onefile у корінь dist — міняли через плутанину двох EXE з однаковою назвою (dist root та стара папка).
2. **PyInstaller onedir** додає ім'я програми до distpath (`distpath/<name>/`) — тому `--distpath` = корінь `dist`, а не `dist/SM WoT Assistant Admin` (інакше подвійне вкладення).
3. **clean()** перед збіркою: `shutil.rmtree(dist/SM WoT Assistant Admin)` + видалення старих `dist/SM WoT Assistant Admin*.exe` з кореня. Канонічна точка запуску: `dist/SM WoT Assistant Admin/SM WoT Assistant Admin.exe`.
4. **Перед перезбіркою** вбити запущену адмінку (працюючий EXE заблокований Windows → clean() падає з PermissionError WinError 5; стара інстанція також блокує нову через мутекс).
