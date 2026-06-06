# Правила роботи з проектом WoT Assistant

## Джерела даних (СУВОРО)
1. ВСІ дані беруться ТІЛЬКИ з клієнта гри (WotXmlParser декодування XML) або з відповідей ШІ.
2. НІЯКИХ хардкоджених списків, фалбеків, кешів без прямого дозволу.
3. КОЖНЕ твердження "це з клієнта" має супроводжуватись доказом: файл + рядок коду.

## Картка танка
1. Вся інформація про білд — тільки з відповіді ШІ.
2. Якщо ШІ не відповів — показувати пусті секції (без фалбеків).
3. Запит до ШІ формується на основі даних з game_entities_english.json + decoded XML клієнта.
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

## Cross-session пам'ять (Magic Context plugin)
1. Пам'ять автоматично інжектиться в контекст — перевірка на старті НЕ ПОТРІБНА.
2. **Наприкінці сесії:** зберегти ключові факти в `ctx_memory`:
   - над чим працювали (поточне завдання)
   - які баги/проблеми знайдено
   - які рішення прийнято
   - наступний крок
3. **Під час сесії:** зберігати важливі архітектурні рішення, знайдені шляхи файлів, конфігурації, робочі команди негайно після їх виявлення.
4. **magic-context.jsonc** (02.06.2026): налаштовано на максимум — memory.injection_budget_tokens=20000, auto_promote=true, promotion_threshold=2, retrieval_count=1, auto_search score_threshold=0.3, pin_key_files enabled, embedding=local, sidekick enabled, two_pass historian.
