# Історія змін (changelog)

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

## v1.0.67 (06.08.2026)

**Зміни після v1.0.66 (коміти 9990b5e..446bc4e, гілка api-integration):**
- Повернуто 2 мапи (59_asia_great_wall / Кордон Імперії, 37_caucasus / Перевал) — прибрано з `_EVENT_MAP_IDS`; 44 мапи в Standard (ctf).
- Назви мап завжди в мові клієнта гри: `regenerate_map_dictionary(_lang_module)` на кожному старті (деталі нижче, розділ 04.08.2026).
- Фікс дрейфу позиції вікна редагування: `WindowManager._cursor_over_app()` WindowFromPoint + GetParent-ланцюг, mode-гейт drag (деталі нижче).
- Аудит 04.08: 125 мертвих модулів → `_archive/scripts/`, чистка dist/GitHub/RTDB (5 останніх), реорганізація docs (13 тематичних файлів).
- Реліз: повний цикл build.py (PyInstaller → NSIS → ZIP → verify → manifest → GitHub release → RTDB) + Release Cleanup Protocol (лишились v1.0.63–v1.0.67).
- Адмінка не змінювалась (v1.0.4, onedir).

---

## Виправлення мап та дрейфу позиції вікна (04.08.2026)

**Назви мап завжди в мові клієнта гри (language_module.py):**
- **Проблема:** `regenerate_map_dictionary(lm)` запускалась ТІЛЬКИ при зміні мови клієнта (гілка "rebuilding"). Коли мова не змінювалась — «no change, skipping rebuild» — словник назв мап не оновлювався. Тому dev-словник лишався англійським від епохи EN-клієнта (03.08) назавжди: dev-запуск показував англійські назви, встановлений бандл — українські.
- **Фікс:** виклик `regenerate_map_dictionary(_lang_module)` перенесено після популяції `_lang_module` з кешу (крізь обидві гілки) — словник перегенерується з клієнта (arenas.mo) у мові клієнта на КОЖНОМУ старті. Гварди: `dictionaries.get("arenas")` + try/except + «10+ валідних записів» у самій функції (порожні дані не зіпсують словник). У no-change гілці `lm.dictionaries` порожні (#1451) — тому використовується `_lang_module`, а не `lm`.
- **Ефект:** назви мап завжди з клієнта в мові клієнта (зараз uk: «Кордон імперії», «Перевал», «Карелія»); dev і встановлений консистентні; хардкоджений `MAP_NAMES_EN` не використовується для відображення (тільки тактичні папки/публікація).
- Верифікація: AST; ізольована регенерація з uk-кешу (89 мап, укр. назви); живий запуск — регенерація відбулась навіть при «no change»; `t_map` повертає укр. назви.

**Повернуто дві мапи, які не показувались у MAPS/TACTIC (аудит: 59 мап клієнта vs список програми):**
- `59_asia_great_wall` (Кордон Імперії / Empire's Border) — прибрано з `_EVENT_MAP_IDS` (map_manager.py:19). Мапа жива в клієнті (ctf, CRC збігається), всі дані є (мінімапа, тактична картинка `maps/Empires_Border/map.webp`, словник) — виключав лише застарілий хардкод-сет із v1.0.54.
- `37_caucasus` (Перевал / Mountain Pass) — прибрано з `_EVENT_MAP_IDS` + виправлено назву в `config.py:100`: `"Pass"` → `"Mountain Pass"` (назва з клієнтського .mo `arenas.mo`; тактична папка `maps/Mountain_Pass` існує, але `_resolve_tactic_folder` не знаходила її через хибну назву `"Pass"`).
- Підтверджено правильно сховані (клієнтські XML через WotXmlParser): sm24/nom (StoryMode/NewOnboarding-сценарії), `*_scc` (SCC), `*_ls26_*` (Last Stand, у arenas.mo взагалі немає назв), epic/BR, `140/141/142`, `*_wt` (не в клієнті).
- Після фіксу: 44 мапи в Standard (ctf).

**Усунено дрейф позиції вікна редагування (window_manager.py):**
- **Корінь:** регресія `a70e476` (25.06.2026) прибрала mode-гейт у `_monitor_mouse_drag.drag_ready` → F8 (клейке Lock/форматування) + будь-яке ЛКМ у грі (приціл, мінімапа) тягнуло вікно за курсором; `save_settings()` на відпуск ЛКМ назавжди зберігав зсув у `edit_x/edit_y` → вікно "з часом" опинялось на місці бойового вікна (низ-праворуч). Попередні фікси (7b3faf7, 2707d98) правили лише save/restore-симптоми.
- **Фікс:** новий `WindowManager._cursor_over_app()` (WindowFromPoint + winfo_id/GetParent, чистий ctypes, потокобезпечний) + гейт: глобальний drag дозволений у norm-режимі (фіча перетягування click-through вікна) і в edit — лише коли курсор над вікном програми. Той самий гейт застосовано до Alt+ЛКМ хука `_setup_mouse_drag` (живий у dev; у білді `mouse` не бандлиться).
- **Другий раунд (живий дебаг, #1463):** перша версія гейта блокувала drag по канвасу — WindowFromPoint над канвасом повертає hwnd ОВЕРЛЕЯ `_po_win` (він покриває весь канвас; map рендериться на ньому), а не рута → гейт не розпізнавав вікно → "вікно редагування взагалі не переміщується". Діагностика на живому застосунку (EnumWindows + WFP-проби + тимчасові [DEBUG]-принти в моніторі) виявила ще дві пастки: (1) WFP повертає дочірні WS_CHILD hwnd (canvas/entry — 2 рівні нижче клієнтського), (2) кеш hwnd оверлея заповнювався нулем на старті (до створення `_po_win`) і більше не перевірявся. **Фінальний фікс:** `_cursor_over_app()` піднімається ланцюгом `GetParent` до 8 рівнів і порівнює з {клієнтський/wrapper рута, клієнтський/wrapper оверлея}; нульовий кеш оверлея не закріплюється (перевірка повторюється); продовження drag розв'язане від `over_app` (тягнемо поки затиснута ЛКМ — перетин межі вікна не обриває drag).
- Верифікація (живий застосунок, 4 фази): F8 ON + drag по ЦЕНТРУ КАНВАСА → рухається ✓; топ-бар → рухається ✓; поза вікном → НЕ рухається ✓ (анти-drift); F8 OFF + канвас → НЕ рухається ✓. Позиція вікна відновлена, [DEBUG]-принти прибрані, AST-аудит чистий.

---

## Аудит файлів і сховищ (04.08.2026)

**Локальні файли (97.8 GB → 8.6 GB, -89.2 GB):**
- 125 мертвих модулів → `_archive/scripts/` (git mv, історія збережена): старий AI-пайплайн (ai_assistant/ai_normalizer/ai_scraper×3/ai_triple_scrape/ai_webview_gui), старі промпти (generate_prompt v1, generate_prompt_is7), легасі-декодер (bw_xml, decode_vehicle_xml, __decode_defs, __decode_and_search_grid, decode_xml.orig, debug_decode_xml), old_stats_ai, patch_* ×11, fix* ×4, check_* ×14, debug-скрипти, find_* ×7, deep_* ×3, analyze_* ×4, tomato/selenium/click-ера ×23 (tomato_selenium, open_tomato_consumables, explore_tomato_sections...), try_*/get_*/search_* ×9, arc_* ×2, разові утиліти (quick_parse, read_arenas, parse_decoded, parse_slots×2, repair_tth, temp_extract, tmp_test, generate_chars, diagnostic, AUTO_UPDATE_GUIDE, field_mods_report), екстрактори-разовики (extract_vehicle_slots×2, extract_slots_from_decoded, extract_full_tank_data, extract_all_client_data, build_field_mod_pairs_by_tank, create_tank_slots_db, create_english_names, add_english_tank_names, add_field_mods, parse_mo_localization), builds_table.py, network_requests.py, test.py, xvm_chars.png, show_xvm.html, run_test.bat, temp_list.xml, scripts.pkg.zip (бекап клієнтського пакета).
- 23 тестові артефакти — git rm: tomato_*.html ×12, tomato_*.json ×6, scraper_test_out.html, vehicle_slots_test.json, vehicle_slots_v2.json, tui.json.
- Untracked: temp_scripts.zip (162 MB), *.log, *_err/_out.txt ×10, tmp/, __pycache__ — видалено.
- extracted_gui/ (1.26 GB, розпакований gui-part1.pkg — застосунок не читає) — видалено.
- dist/: 90.3 GB → 4.8 GB (лишились v1.0.62-v1.0.66 + Admin).

**Збережені (перевірено імпорти):** tth_updater, extract_equipment_loadouts, build_crew_builds, name_localizer, map_updater, ukrainian_map_names.json, map_links.json, ai_engine (AI_CONS_MAP для generate_prompt_v2:382), .client_update_manifest.json.

**GitHub (50.64 GB → 2.88 GB):** видалено 60 старіших релізів (v1.0.1-v1.0.61), лишились v1.0.62-v1.0.66 (теги збережені).

**RTDB versions/ (45 → 6 ключів):** видалено 1_0_22-1_0_61 + легасі-вузол admin (адмінка без auto-update з #1431); лишились 1_0_62-1_0_66 + latest.

**Нові правила:** AGENTS.md — Release Cleanup Protocol (dist/GitHub/RTDB → 5 останніх після кожного релізу) + No dead code (новий .py без імпортерів → одразу в _archive/scripts/; тестові виводи не комітити). docs/release.md — розділ з повною процедурою.

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
