# Історія змін (changelog)

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

## Single-instance mutex fix (04.08.2026, v1.0.66)
1. **Баг**: `ctypes.windll.kernel32.CreateMutexW` + `ctypes.windll.kernel32.GetLastError()` — GetLastError читається через windll-хендл БЕЗ `use_last_error=True`, тому ЗАВЖДИ повертає 0 → перевірка `== 183` ніколи не спрацьовувала → single-instance тихо не працював: стартували дублі процесів (два tray_watcher.exe, два admin.exe — підтверджено в дикій природі).
2. **Фікс** (4 файли: main.py:83, launcher.py:68, tray_watcher.py:211, admin_app.py:1034): патерн `_k32 = ctypes.WinDLL("kernel32", use_last_error=True)` + `_k32.CreateMutexW.argtypes = (c_void_p, c_bool, c_wchar_p)` + `_k32.CreateMutexW.restype = c_void_p` + перевірка `ctypes.get_last_error() == 183`.
3. **Перевірено** (03-04.08.2026): smoke — 2-й інстанс main.py виходить за ~8с; 2-й dev tray_watcher виходить; встановлені старі EXE (v1.0.65) дають дублі — новий реліз лікує.
4. **tray_watcher.py:13** — `DEBUG = False` (релізна гігієна; DEBUG-принти залишаються в коді).
5. **Реліз**: v1.0.66 (03.08-батч: мутекс-фікс ×4, PUT null у firebase_reporter.py:66/admin_build_generator.py:45, захист дублікатів назв груп firebase_groups.py, автовисота DrawingPalette painting_palette.py, [SYNC]-теги stats_ai.py, чищення тестових залишків). admin_version.txt → 1.0.4.


## Реорганізація документації (04.08.2026)
- AGENTS.md (51 КБ, 30 секцій) розбито: правила лишились у AGENTS.md (~140 рядків), тематичні знання → docs/ (13 файлів), історія → docs/changelog.md.
- ARCHITECTURE.md → docs/architecture.md, STRUCTURE.md → docs/structure.md (як є, без змін вмісту).
- Застарілі .md (tomato, AI browser, Orion, чеклісти, PROJECT_*) → _archive/docs/.

## 03-04.08.2026 (v1.0.66, адмінка v1.0.4)
1. Мутекс-фікс ×4 (#1474): main.py, launcher.py, tray_watcher.py, admin_app.py — WinDLL(use_last_error=True) + get_last_error()==183.
2. PUT null видалення (#1470): firebase_reporter.py:66, admin_build_generator.py:45.
3. Захист дублікатів назв груп (#1469): firebase_groups.py create/join.
4. Автовисота DrawingPalette: painting_palette.py (3 правки: _saved_pos, _refresh_linked_schemes_list, _adapt_palette_height).
5. Лог-теги [AI Browser]→[SYNC]: stats_ai.py.
6. Чищення тестових залишків: opencode — копія.json, пусті папки public/admin/, temp_scripts/decoded_test/, DEBUG=False (tray_watcher.py:13).
7. Реліз v1.0.66: build.py повний цикл (PyInstaller → NSIS → ZIP → GitHub release → RTDB) + firebase deploy --only hosting.
8. Адмінка v1.0.4: build_admin.py → onedir у dist/SM WoT Assistant Admin/ (канонічна точка; root-однофайловик прибрано; clean() чистить папку і root).

## Історія до 04.08.2026 (з архівованого CHANGELOG.md, 22.05)
# WoT Assistant - AI Build Display Fixes

## Підсумок змін (2026-05-10)

### Мета
Виправити UI для відображення AI білдів - додати індикатори номерів (1 і 2) перед секціями обладнання, потім знову увімкнути AI запити.

### Що було зроблено

#### 1. AI Engine
- Переключено з 3 запитів на 1 запит для Google AI
- Вимкнено local database fallback (AI only)
- Додано логіку закінчення кешу через 30 днів
- Використовується Google AI режим через WebEngineView (без API ключів)

#### 2. UI Fixes (stats_ai.py)

**Виправлення IndentationError (лінія 1999):**
- Видалено зайвий відступ у секції loading_labels
- Код `icon_box.pack...` був неправильно відступлений

**Виправлення geometry manager конфлікту (grid/pack):**
- Додано індикатори номерів 1 і 2 перед обладнанням
- Використовується `pack` для цифр (в батьківському фреймі)
- Обладнання тепер рендериться в окремих фреймах (`equip_grid_frame_1`, `equip_grid_frame_2`) з `grid`
- Це вирішує помилку: "cannot use geometry manager grid inside ... which already has slaves managed by pack"

#### 3. Видалено дублікати коду
- Видалено повторювані блоки створення міток 1 і 2
- Код тепер чистіший і не дублюється

### Структура коду

```python
# Цифра 1 перед обладнанням (використовує pack)
self._loadout_num_label.pack(side="left", padx=(0, 2))

# Оборудование в отдельном фрейме с grid
equip_grid_frame_1 = tk.Frame(equip_body, bg="#111111")
equip_grid_frame_1.pack(side="left", fill="none", expand=False)
render_items(equip_grid_frame_1, build_data.get("equipment_1", []), "artefacts")

# Цифра 2 перед обладнанням (використовує pack)
self._loadout_num_label_2.pack(side="left", padx=(0, 2))

# Оборудование в отдельном фрейме с grid
equip_grid_frame_2 = tk.Frame(equip_body_2, bg="#111111")
equip_grid_frame_2.pack(side="left", fill="none", expand=False)
render_items(equip_grid_frame_2, build_data.get("equipment_2", []), "artefacts")
```

### Наступні кроки
1. Перевірити чи працює UI після фіксу
2. Ввімкнути AI запити в ai_engine.py
3. При потребі відновити loading placeholders

### Файли
- `stats_ai.py` - Основний UI з виправленнями
- `ai_engine.py` - AI двигун (запити вимкнені)
- `ai_scraper_triple.py` - Скрейпер для Google AI режиму
- `MMM25_AI_BUILD_GENERATOR.md` - Документація

### Ключові рішення
- Single request замість triple для швидшої відповіді
- Cache expiry: 30 днів
- Використання WebEngineView для Google AI
