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

## Активні кеші проекту (станом на 27.05.2026)
1. `popular_tanks_cache.json` — дисковий кеш популярних танків з відповіді ШІ (stats_ai.py:18, 7 днів, fail_count)
2. `composite_cache` — in-memory dict, кеш композитних іконок танків (stats_ai.py:82)
3. `loadout_icon_cache` — in-memory dict, кеш іконок обладнання/витратних/перків (stats_ai.py:84)
4. `tth_icon_cache` — in-memory dict, кеш іконок рядків ТТХ (stats_ai.py:85)
5. `_field_mod_pairs_cache` — in-memory dict, кеш пар польової модернізації (stats_ai.py:86)
6. `service_messages.json` — дискова черга службових подій для відкладеної доставки (service_messages.py:13)
7. `ukrainian_map_names_cache.json` — дисковий кеш назв мап (map_extractor.py:111)
8. `ai_builds_cache.json` — дисковий кеш AI build для карток танків (stats_ai.py:35, 30 днів, fail_count)
   - `ENABLE_AI_BUILD_CACHE=False` — режим збору даних (AI запускається при кожному заході)
   - fail_count скидається при успіху, log_event кожні 3 невдачі (`_handle_ai_build_failure`, stats_ai.py:47)
   - `_is_cache_expired(updated_iso, max_days=7)` — спільна функція з параметром (stats_ai.py:76)

## Неактивні/тимчасово вимкнені кеші
1. `equipment_loadouts.json` — вимкнено для тестування AI механізму (stats_ai.py:2285)
2. `crew_builds.json` override — вимкнено для тестування AI механізму (stats_ai.py:2286)
3. `ai_builds_cache.json` — вимкнено для тестування (stats_ai.py:19, ENABLE_AI_BUILD_CACHE=False)

## Зміна в генерації промпту (28.05.2026)
1. `generate_prompt_v2.py:575` — "Current date: 2026-05-28." замінено на "2026 year"
   - Причина: рядок "Current date: ..." блокував AI відповідь для окремих танків (Google AI Mode ігнорував запит з повною датою для певних назв)
   - Рік динамічний: `datetime.now().strftime("%Y")`

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
