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

