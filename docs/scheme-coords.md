# Scheme Coordinate Contract (КОНТРАКТ координат схем)

**Цей документ — єдине джерело правди для простору координат схем.**
Порушення контракту = зсув схем у редакторі, в моді на мінімапі або на
сайті. Перед зміною будь-якого коду, що стосується `coords`, прочитайте
цей документ повністю.

## Формат

Кожен елемент малюнка зберігає координати як **image-fraction 0..1**:

- **Простір**: дріб від ПРЯМОКУТНИКА ЗОБРАЖЕННЯ МАПИ (не канваса, не вікна).
- **Одиниця**: `coords = [x1, y1, x2, y2, ...]` — пари `(x, y)`;
  `text_coords = [x, y]`; `class_icon_coords = [x, y]`.
- **Походження**: top-left зображення мапи (не екрана).
- **Напрямок Y**: вниз (y=0 — верх мапи).
- **Форма**: зображення мапи — КВАДРАТ `img_size × img_size`.

## Джерело геометрії (ОДНЕ на весь проєкт)

`painter.py: MapPainter._img_rect()` → `app._map_img_rect` —
єдине джерело `(org_x, org_y, img_w, img_h)`. Його встановлює
`map_renderer.py: show_main_splash()` при кожному рендері мапи.

Рендер: `px = org_x + u * img_w`, `py = org_y + v * img_h`.
Створення/рух: `u = (px_event - org_x) / img_w`.

**ЗАБОРОНЕНО** нормалізувати coords через `winfo_width()`/`winfo_height()`
канваса — це історична причина зсуву (коміт `8085639`, 02.10.2026).

## norm-маркер

Кожен елемент при **створенні** та **завершенні руху** отримує
`"norm": "img"`. Це:
1. засвідчує, що coords у image-просторі;
2. робить one-shot міграцію legacy-даних (`tactics_manager.migrate_legacy_elements`)
   ідемпотентною (наявний `norm` → пропуск).

Нові елементи БЕЗ `norm` — регресія. Тест `test_scheme_coords.py` ловить це.

## Споживачі формату (УСІ той самий простір)

| Ланка | Код | Трансформація coords |
|---|---|---|
| Рендер редактора | `painter.py:_render_elements` | НІ ( множення через `_img_rect`) |
| Створення/рух | `painter.py:on_press/on_move_drag` | НІ (делення через `_img_rect`) |
| Збереження | `tactics_manager.py:save_scheme_to_db` | НІ (сирий JSON) |
| Завантаження схем | `tactics_manager.py:load_scheme_from_db` | НІ |
| Firebase публікація | `firebase_drawings.publish_drawing` | НІ (`json.dumps`) |
| Firebase завантаження | `firebase_drawings.download_drawing` | НІ (`json.loads`) |
| Групові схеми | `painter._group_schemes` → той самий `_render_elements` | НІ |
| Імпорт/експорт | `tactics_manager.py:export/import_*` | НІ (pass-through) |
| **Мод Python** | `mod/res/.../mod_sm_tactics.py` | НІ (читає `saved_schemes.json` напряму) |
| **Мод AS3** | `mod/src/.../SmTacticsOverlay.as: px()` | НІ (`[nx·_size, ny·_size]`, `_size` = квадрат мінімапи) |

**Будь-яка трансформація coords поза `_img_rect()` — порушення контракту.**
Виняток: one-shot міграція legacy-даних (без `norm`) при завантаженні.

## Мод на мінімапі

AS3 `px()` множить image-fraction на квадрат `_size` (ширина `flags.width`
у `minimap.entriesContainer`) — той самий простір, що й редактор.
Калібровано живцем 05.10.2026 (рамка на сітці ±1px). `text_coords`
споживаються тим самим `px()`.

## Верифікація

`python test_scheme_coords.py` — постійний регресійний тест (запускати
перед кожним білдом і після змін у coords-шляхах):
- round-trip save/load ≡ (coords без змін);
- інваріантність вікна (800×800 vs 1200×1200 → однакова фракція мапи);
- AS3-паритет формули;
- firebase/import pass-through без мутацій;
- наявність `norm:"img"` на створених/руханих елементах.

## Історія

- **02.10.2026** коміт `8085639`: перехід канвас-дроби → image-дроби
  (листбокс-фікс). Старі дані мігрували one-shot міграцією (13.10.2026).
- **13.10.2026**: повне очищення legacy-схем (локально + RTDB `schemes/`),
  контракт зафіксовано цим документом + `test_scheme_coords.py`.
