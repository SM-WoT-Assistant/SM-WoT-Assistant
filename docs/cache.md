# Кеші проекту

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

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



---

## mo_maps cache fix + ration source fix (02.08.2026)
Повна секція — у docs/admin.md (mo_maps cache fix + ration source fix). Коротко: generate_mo_maps викликається з language_module.setup() з src=_lang_module (не lm) — у кеш-гілці lm.dictionaries порожній, інакше мапи обнуляться на кожному старті (#1451). Раніон-джерело: _cons_rev_map() реверс ai_engine.AI_CONS_MAP (#1486).
