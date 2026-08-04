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

