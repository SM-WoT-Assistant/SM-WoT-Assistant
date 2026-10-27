# Мапи та сітка координат

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

## Мапи та сітка координат (30.05.2026)
1. Сітка 10×10 (колонки 0-9, рядки A-J) малюється поверх карти в MAPS режимі (map_renderer.py:draw_grid).
2. Координати сітки обчислюються з `boundingBox` з `map_data.json` — діленням на 10 по X та Z.
3. Підписи колонок (цифри 0-9) — зверху та знизу, рядків (букви A-J) — зліва та справа, на темно-сірій рамці (#333333) навколо карти.
4. Лінії та підписи сітки — сірі (#777777).
5. Рамка сітки 25px (`grid_border`), реалізована як outline навколо квадратної мапи (map_renderer.py:draw_grid). Крайові лінії сітки (0/10) пропущено — вони під рамкою.
6. При зміні розміру сітки (grid_cols/grid_rows) — змінити в map_renderer.py:9-10.

---

## Натиск (comp7): бази, спавни, окрема мінікарта (23.09.2026)
1. У Натиску гра використовує **`mmap_comp7.dds`** (інша графіка, ніж `mmap.dds`) — екстрактується як `extracted_maps/{map_id}_comp7.png` (`map_extractor.py`), у MAPS + фільтр Onslaught/OnslaughtLight завантажується першим (`load_and_resize_map`).
2. Арени з суфіксом **`_comp7_nb`** — окремий space pkg з **іншими** базами/spawns (приклад: `28_desert` vs `28_desert_comp7_nb`). Raw id з логу зберігається в `WotAssistantHQ.battle_map_data_id`; `map_renderer._resolve_map_data_id()` використовує його лише коли він відповідає поточній мапі (після обрізки суфікса для dictionary/combobox).
3. **Вкладений** `<gameplayTypes><comp7><boundingBox>` (6 мап: Prohorovka, Ruinberg, Erlenberg, Siegfried Line, Erland Alaska, Airfield) парситься у `wot_decoder.py` як `gameplayTypes.comp7.boundingBox`; у comp7-режимі сітка/бази/спавни використовують його (`map_renderer._active_bbox`), якщо він ≠ кореневому bbox.
4. `draw_arena_bases` використовує **той самий scaled border**, що `draw_grid` (`max(5, int(grid_border * min(cw,ch)/800))`) — інакше бази зсуваються при canvas ≠ 800px.
5. Бази малюються за `selected_battle_mode` (Standard/Encounter/Storm/Onslaught) — `gameplayTypes[ctf|domination|assault|comp7]`. `217_er_alaska` comp7: `spawns=[]` **так само в клієнті** (немає `teamSpawnPoints`).
6. Click-through при закритому замку: `window_manager.set_clickthrough` застосовує `WS_EX_TRANSPARENT` до **root і overlay `_po_win`**; Ctrl вимикає прозорість обох для unlock (`_update_lock_clickthrough`). Малюнки лишаються видимими.

---

## IMAGE GUARD: звірка тактичних фонів з клієнтом (26.10.2026)

**Два джерела фону залежно від режиму:**
- **MAPS** — завжди `extracted_maps/<id>.png` (піксель-у-піксель `mmap.dds` з `spaces/*.pkg`). Тут помилок не буває.
- **TACTIC** — завжди `maps/<Folder>/map.webp` зі стороннього сайту (wotmapsbyyaya.com), через `_resolve_tactic_folder` → `MapRenderer.load_and_resize_map`.

**Правило:** клієнт гри — джерело істини; сайт дає ТІЛЬКИ накреслення поверх мінікарти. Тому кожен TACTIC-фон звіряється з `extracted_maps/<id>.png`.

**Що робить guard (`map_updater.py`):**
| Функція | Коли | Що робить |
|---|---|---|
| `verify_image_for_name(eng, data)` | перед записом завантажених байтів (`download_single_map`, `sync_all`) | (ok, corr); невалідні байти **не пишуться** |
| `verify_map_background(map_id)` | sweep, якщо перекачка відхилена | (ok, corr) для наявного локального фону |
| `ensure_local_backgrounds(ids)` | перед мережевим sweep, офлайн (~2.3 с / 45 мап) | `ok` / `repaired` / `created` / `skipped` |
| `ensure_map_background(id)` | один файл | ремонтує або створює `map.webp` з мінікарти клієнта |

**Метрика:** Pearson по 96×96 відтінкам сірого (після зняття середнього), поріг **0.5**.
Виміряно на 45 кандидатах: валідні 0.730–0.968 (медіана 0.908), чужі 0.186 і 0.397 → запас ≥40%.

**Кандидати** — `_tactic_candidate_ids()` (ті самі фільтри, що `load_map_list`):
без `type/*`/`h33_*`, без `invalid_map|hangar_v4|_default_`, без `_EVENT_MAP_IDS`,
з `ctf` у `gameplayTypes` (або відсутні у `map_data.json`).

**Дзеркало:** `_resolve_tactic_folder` продубльовано в `map_updater.py` — напряму імпортувати `map_manager` не можна (він лени-імпортує `map_updater` → цикл). Обидві функції читають тільки `config.TECH_MAPS_STAGING` — міняти разом.

**Вирішені випадки (26.10.2026):**
- `maps/Pilsen/map.webp` містив терен Редширу (corr 0.186) → замінено мінікартою `114_czech.png` (corr 1.0). ETag у маніфесті = серверний → sweep отримує 304 і не перекачує; якщо сайт виправиться — ETag зміниться і валідний фон приїде сам.
- `maps/Nibelburg/map.webp` не існував → мапа переносилась у кінець TACTIC-списку (b4f2148) і виглядала як «дубль в іншому місці» відносно MAPS. Створено з `212_epic_random_valley.png` → обидва списки тепер по 45 рядків, Нібельбурґ 23-й у TACTIC і MAPS, позиції ідентичні, дублікатів немає.

**Незмінне:** `unavailable_tactic_maps.json` НЕ поповнюється на 404 (фікс b4f2148 — чорний список отруював би мапу першим ранковим sweep до її появи на сайті).

