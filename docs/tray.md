# Системний трей, Tray Watcher, Dev PID

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

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


## План А: mod-sync + безумовний автозапуск (16.10.2026)
1. **Мета:** після патчу гри `sm_tactics.wotmod` завжди в `mods/<поточна версія>/` — навіть коли основна програма не запущена (`launch_on_game_start=false`); наш файл прибирається зі старих версійних папок; `res_mods/` та сторонні моди (Aslain тощо) НІКОЛИ не чіпаються (#2041).
2. **`tray_watcher.py: _sync_mod(settings)`** — на старті та кожні ~60s у стандартному 5-сек циклі (`cycle % 12`): версія з `version.xml` (fallback `settings.game_version`, нормалізація regex `\d+\.\d+\.\d+\.\d+` + prefer-наявна-папка на диску — як `map_manager.apply_mod_mode`) → копіювання з `_find_wotmod_source()` (frozen: `_internal/sm_tactics.wotmod` біля exe; dev: project root) → `_cleanup_stale_wotmods()` (точне ім'я файлу, без wildcard #1492). `use_mod=false` → прибрати наш файл з усіх папок. Джерела немає → no-op (без half-sync).
3. **Гейт запуску програми:** `_launch_if_enabled(settings)` — `_launch_app()` ТІЛЬКИ за `launch_on_game_start=true`. Раніше гейт був у `main.py` (реєстр записувався/видалявся за чекбоксом) — через це при `false` не існував взагалі ні watcher, ні `close_with_game`.
4. **`main.py`:** `__init__` завжди `_set_windows_startup(True)` + `_ensure_tray_watcher_running()`. **`ui_manager._on_launch_on_game_start`**: лише зберігає налаштування + ensure — реєстр не чіпає (запис не видаляється при знятті чекбокса).
5. **tasklist-готча:** `tasklist /fi` обрізає колонку Image Name до **25 символів** (`SM WoT Assistant Tray Wat`); повна назва `...Tray Watcher.exe` у виводі ніколи не зустрічається → `_ensure_tray_watcher_running` перевіряє `basename[:25]` (інакше кожен старт при запущеному watcher'і породжує дублікат, що вмирає на mutex 183).
6. **`build.py: copy_data_files()`** бандлить `sm_tactics.wotmod` у дистрибутив (для `map_manager.apply_mod_mode` + `_find_wotmod_source` frozen-варіанта); WARNING якщо файл не зібрано `build_mod.py`.
7. **Верифікація 16.10.2026:** харнесс `_archive/scripts/harness_tray_modsync_2026_10_16.py` **27/0**; AST x4; smoke ensure-фікса (old=False/new=True); живий: `main.py --tray` → реєстр + watcher стартували; живий sync — мод забрали з `mods/2.4.1.0/` → відновлено за 65с.


## Сповiщення про помилки мода (16.10.2026)

tray_watcher — постiйний компонент пiсля Плану А, тому саме вiн гарантує помiчення поломок мода, коли основна програма не запущена (launch_on_game_start=false — типовий режим користувача).

**Скан game.log (~60с, тiльки поки гра запущена):** iнкрементальний offset + 2MB backward-baseline на стартi сесiї + останнi 3 рядки попереднього чанку (tail) для цiлiсностi import-pair на межi чанкiв. Сигнатури — _match_mod_error: `File "...mod_sm_tactics.py"` (не .pyc) → keyword протягом 4 рядкiв; `[SM Tactics] ... failed|not found|Error`; `Mod package ... sm_tactics ... error` (УСПIШНИЙ рядок «loaded» НЕ спрацьовує — фiкс 17.10); one-line `failed to load mod_sm_tactics.pyc: ... ImportError` (ASL-лоадер). Стороннi моди та успiшне логування мода не спрацьовують.

**Staleness-гейт (17.10, #2053):** game.log — append-only без ротацiї сесiй, backward-вiкно мiстить помилки СТАРИХ бiлдiв. Сповiщення ТIЛЬКИ якщо таймстамп помилки новiший за mtime встановленого mods/&lt;ver&gt;/sm_tactics.wotmod (_installed_mod_mtime + _error_is_fresh / log_reader._mod_error_stale). mod_mtime None (мод не встановлено) → гасимо (вiдсутнiсть файлу окремо ловить B2). Live-помилки завжди свiжi — гейт тiльки для backward/scan.

**Координацiя (_notify_mod_error) — сповiщення нiколи не дублюється:**
- `main()` програми живий (PID-реверт через tasklist [:25]-truncation-безпечний пошук) → watcher мовчить: LogWatcher програми ловить ту саму помилку наживо (live ~2с + backward one-shot при стартi) → dark_messagebox + Firebase critical + console;
- програма НЕ запущена → balloon (чистий ctypes: приховане вiкно + Shell_NotifyIconW NIM_ADD/NIF_INFO, системна iконка IDI_INFORMATION, ~20с, без постiйної iконки в треї) + прапорець %APPDATA%\SM WoT Assistant\mod_error_pending.json → програма при наступному стартi репортить у Firebase тихо (без messagebox) i видаляє прапорець.
Dedup watcher: один balloon за iгрову сесiю (reset на game-start edge).

**B2-доставка (~60с поки гра запущена):** use_mod=true + 3 поспiль 60s-циклi без sm_tactics.wotmod у mods/<поточна версiя>/ → balloon "Мод не встановлено у mods (<версiя>)" або "sm_tactics.wotmod вiдсутнiй в iнсталяцiї програми" (коли немає джерела) + flag-файл. Ловить тиху file-вiдсутнiсть (жодних слiдiв у логу). Reset лiчильника: файл з'явився / use_mod=false / гра зупинилась.

**Не чiпати:** res_mods/ та будь-якi стороннi моди — сигнатури прив'язанi тiльки до mod_sm_tactics.py / [SM Tactics] / sm_tactics.wotmod (#2041). Balloon-логiку НЕ дублювати в основнiй програмi (там канал #1889: messagebox+Firebase+console).

**_sync_mod guard (17.10, #clobber):** нiколи не затирати НОВIШИЙ dst старiшим src за mtime — вчора src iз _internal (13.10) затер зфiксований 16.10 бiлд у mods/2.4.1.0/ лише за рiзницею розмiрiв (мод пропав до наступного запуску). Guard: dmt &gt; smt → skip copy.

**Верифiкацiя:** _archive/scripts/harness_mod_error_notify_2026_10_16.py (v2, 69/0 — включаючи package-loaded no-fire, ASL one-line, staleness unit, sync-guard). Реплей реального game.log (18.8MB) з реальними settings: 0 сповiщень (усi старi помилки пригнiченi). Перезбiр watcher EXE: `python -c "import build; build.build_tray_watcher()"` → dist/SM WoT Assistant/SM WoT Assistant Tray Watcher.exe → копiювати у %LOCALAPPDATA%\SM WoT Assistant\.
