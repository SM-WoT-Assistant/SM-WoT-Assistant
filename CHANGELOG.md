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