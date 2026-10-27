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
- `maps/Pilsen/map.webp` містив терен Редширу (corr 0.186) → тимчасово замінено мінікартою `114_czech.png` (corr 1.0). **27.10.2026** з сайту завантажено справжній фон Промзони (див. секцію про URL нижче).
- `maps/Nibelburg/map.webp` не існував → мапа переносилась у кінець TACTIC-списку (b4f2148) і виглядала як «дубль в іншому місці» відносно MAPS. Створено з `212_epic_random_valley.png` → обидва списки тепер по 45 рядків, Нібельбурґ 23-й у TACTIC і MAPS, позиції ідентичні, дублікатів немає.

**Незмінне:** `unavailable_tactic_maps.json` НЕ поповнюється на 404 (фікс b4f2148 — чорний список отруював би мапу першим ранковим sweep до її появи на сайті).

---

## URL фонів: DOM сайту → map_links.json → resolve_site_url (27.10.2026)

**Корінь проблеми:** код будував URL за назвою мапи — `images.wotmapsbyyaya.com/maps/{name}.webp`.
Сайт же зберігає зображення як **`maps/{name}{timestamp}.webp`** (поле `R2ImageURL`, Cloudflare R2),
а legacy-об'єкт `maps/{name}.webp` існує не завжди і не завжди належить тій мапі:
`maps/pilsen.webp` містив байти Редширу (ETag від 18.05.2026, 94590 байт) — тому TACTIC показував чужу мапу.

**Що змінилося:**
1. **`sync_all` читає DOM замість шаблону** (`map_updater._card_entry`):
   - назва: `data-name` → `href` (`/map/El%20Halluf`) → `id` (legacy). Старий ланцюжок **лише через `id`** після редизайну карток давав 0 мап і sync падав у «МАПИ НЕ ЗНАЙДЕНО»;
   - URL: `<img src>` картки; суфікс `Card` (прев'ю) відрізається → повнорозмірний об'єкт; без `Card` (CloudFront-URL) — як є; без `<img>` — fallback-шаблон.
2. **Споживачі беруть URL із `map_links.json`**: `map_updater.resolve_site_url(eng, links)` → реальний запис, інакше legacy-шаблон. Викликається з обох гілок sweep (`map_manager`: додавання + ETag-перевірка) і з pending-синку (`main._bg_sync`). Ключі зіставляються нормалізовано (апостроф: `Empire's Border` (клієнт) ↔ `Empires Border` (сайт)).
3. **`map_links.json` = єдине джерело правди про URL** (заповнюється `sync_all` і `download_single_map`).

**Вирішено (Pilsen):** `map_links["Pilsen"]` = `…/pilsen1779159262103.webp` (70806 байт, corr **0.763** з `114_czech`, 0.1497 з `34_redshire`) → у TACTIC тепер справжня Промзона з накресленням сайту; `ensure_map_background` повертає `ok` (мінікарту поверх не кладе); маніфест `114_czech` оновлено на ETag реального об'єкта → sweep отримує **304** і нічого не перекачує.

**Обмеження:** повний `sync_all` після цього фіксу оновив би URL всіх 44 мап на timestamped-об'єкти (видалення + перекачка з перевіркою гварда) — під час релізу **не запускався** навмисно, щоб не переписувати працюючі фони.

