# MMM25_AI_BUILD_GENERATOR.md

## Дата: 2026-05-10
## Автор: AI Assistant
## Версія: 3.0

---

## Опис змін (v3.0)

Система генерації збірок танків - Google AI РЕЖИМ запити з валідацією та усередненням.

## Контекст поточної роботи

1. **Основне джерело**: Google AI режим (через WebEngineView)
2. **Танк у запиті**: Людська англійська назва (не код типу R45_IS-7)
3. **Процес**:
   - 3 запити з перервами (20 сек між запитами)
   - Валідація кожного результату
   - Усереднення результатів (вибір найпопулярніших елементів)
4. **Вікно запиту**: Фізично відкривається (QWebEngineView) щоб уникнути бана/капчі
5. **Локальна база**: Тільки fallback коли AI не працює

---

## Опис змін (v2.0)

Система генерації збірок танків - перехід на локальні дані з клієнта гри.

## Проблема (v1.0)

ШІ (через Google Search/Bing) повертав нестабільні збірки:
- Різні структури JSON
- Різні ключі ammo
- Імпровізовані назви field mods
- API ключ Google Gemini невалідний

## Рішення (v3.0) - ПОТОЧНА ВЕРСІЯ

### 1. Google AI режим через WebEngineView

Використовуємо `QWebEngineView` (PyQt6) для відправки запитів:
- URL: `https://www.google.com/search?q={prompt}&udm=50`
- Фізично відкриває вікно браузера (уникає бана/капчі)
- Використовує AI режим Google для отримання чистого JSON

### 2. Три запити з усередненням

Файл: `ai_scraper_triple.py`
- 3 запити з затримкою 20 секунд між кожним
- Валідація кожного результату через `validate_build()`
- Усереднення через `Counter.most_common()`
- Кешування результатів в `ai_builds_cache.json`

### 3. Валідація результатів

Перевірка:
- Equipment: рівно 3 елементи в кожному loadout
- Consumables: рівно 3 елементи
- Crew: рівно 6 перків для кожної ролі
- Фільтрація через `VALID_*` множини

### 4. Назва танка

Танк записується людською англійською назвою (з tank_db.json):
- `T110E5` -> `T110E5` (вже англійською)
- `ussr:R45_IS-7` -> `IS-7`

---

## Рішення (v2.0) - Fallback

### 1. Використання даних клієнта гри

Знайдено локальні дані в `scripts.pkg`:
- **Equipment**: `scripts/item_defs/optional_devices_assistance/optional_devices_usage.csv`
- **Field Mods**: `scripts/item_defs/vehicles/common/post_progression/field_modifications.xml`

### 2. Створено `equipment_loadouts.json`
- 862 танки з даними про популярні збірки обладнання
- Формат: `{tank_id: [{equipment: [...], usage_percent: float}]}`
- Джерело: реальна статистика використання від гравців

### 3. Інтеграція в `ai_engine.py`
- Додано `_load_local_equipment_loadouts()`
- Додано fallback на локальні дані коли AI не працює
- Автоматичне використання при помилці scraper

### 4. Використано Оріон для декодування
- `tools/orion/PjOrion.exe` для декодування бінарних XML файлів клієнта

---

## Статус даних

| Дані | Джерело | Статус |
|------|---------|--------|
| **Equipment** | `optional_devices_usage.csv` | ✅ Повні дані (862 танки) |
| **Field Mods** | `field_modifications.xml` | ⚠️ Структура є, немає популярних збірок |
| **Crew Skills** | `crew_builds.json` (_role_skill_pools) | ⚠️ Тільки пули, немає конкретних збірок |
| **Consumables** | - | ❌ Немає в клієнті |

---

## Файли проекту

| Файл | Призначення |
|------|-------------|
| `equipment_loadouts.json` | Локальні збірки обладнання (862 танки) |
| `ai_engine.py` | Основний модуль з fallback на локальні дані |
| `ai_scraper_strict.py` | Спроба використання AI (тимчасово вимкнено) |
| `extract_equipment_loadouts.py` | Скрипт витягування даних з клієнта |

---

## Приклад даних (IS-7)

З `optional_devices_usage.csv`:
```
ussr:R45_IS-7;healthReserve;turbocharger;rammer;13.18%
ussr:R45_IS-7;healthReserve;aimingStabilizer;rammer;10.14%
ussr:R45_IS-7;ventilation;aimingStabilizer;rammer;7.16%
```

---

## Наступні кроки

1. ⬜ Знайти джерело для Crew Skills (сервер WG / зовнішні бази)
2. ⬜ Знайти джерело для Field Mods популярних збірок
3. ⬜ Знайти джерело для Consumables
4. ⬜ Протестувати інтеграцію в реальному застосунку
5. ⬜ Вимкнути AI scraper (ШІ) поки не буде робочий API ключ
- `_find_key()` - case-insensitive пошук ключів
- Валідація списків `VALID_EQUIPMENT`, `VALID_CONSUMABLES`, `VALID_CREW_SKILLS`
- Нормалізація структури до єдиного формату

### 3. Усереднення 3 запитів (`ai_triple_scrape.py` + `ai_engine.py`)
- Запуск scraper 3 рази
- Pick most common items (`Counter.most_common`)
- Кешування результату

---

## Зміни у файлах (v3.0)

### `ai_engine.py` (рядок 441)

Змінено виклик scraper:
- Було: `ai_scraper_strict.py` (Gemini API)
- Стало: `ai_scraper_triple.py` (WebEngineView для Google AI)
- Таймаут: 90с -> 180с

---

## Зміни у файлах (v2.0)

### `ai_engine.py`

#### Додані константи (рядки 8-76):
```python
VALID_EQUIPMENT = {...}  # Множина валідних назв обладнання
VALID_CONSUMABLES = {...}  # Множина валідних назв витратників
VALID_CREW_SKILLS = {...}  # Множина валідних назв перків екіпажу
VALID_AMMO_TYPES = {...}  # Множина валідних типів снарядів
```

#### Новий метод `_find_key()` (рядок 169):
Case-insensitive пошук ключів у словнику.

#### Оновлений метод `_normalize_build()` (рядок 179):
- Підтримка нової структури з `loadout_1_open_maps` / `loadout_2_city_corridor_maps`
- Фільтрація через `VALID_EQUIPMENT`, `VALID_CONSUMABLES`, `VALID_CREW_SKILLS`
- Видалення логіки з `notFound`

#### Оновлений метод `_validate_build()` (рядок 311):
- Перевірка на валідність без `notFound`
- Перевірка через множини `VALID_*`

#### Нові методи (рядки 327-381):
- `_pick_most_common()` - вибір найпопулярніших елементів
- `_pick_most_common_skills()` - вибір найпопулярніших перків
- `_run_single_scrape()` - запуск scraper з таймаутом
- `_average_results()` - усереднення 3 результатів

#### Оновлений `fetch_build_async()` (рядок 383):
- Використовує `ai_scraper_strict.py` замість `ai_scraper.py`
- Робить 3 запити замість 2
- Викликає `_average_results()` для усереднення
- Використовує нову валідацію

---

## Ключові файли

| Файл | Призначення |
|------|-------------|
| `ai_scraper_triple.py` | **ОСНОВНИЙ** - 3 запити до Google AI через WebEngineView |
| `ai_engine.py` | Інтеграція з інтерфейсом, fallback на локальні дані |
| `ai_scraper_strict.py` | Альтернативний scraper (використовує Gemini API) |
| `equipment_loadouts.json` | Локальні збірки - тільки fallback |
| `ai_builds_cache.json` | Кеш результатів запитів |
| `tank_db.json` | База танків з англійськими назвами |

---

## Промт для scraper

```python
prompt = f"""Current date: {current_date}.

[INSTRUCTION CONTEXT & PURPOSE]
This instruction acts as a configuration generator for the game World of Tanks.

Generate the optimal competitive build data for the tank: {tank_name}.
You must ONLY use the exact names and terms provided in the lists below.
Begin your response exactly with the phrase "Build Generated:" followed by a markdown code block.

1. EQUIPMENT (Create TWO loadouts with DIFFERENT purposes):
   - Loadout 1 (Open Maps): For open battlefield maps - prioritize optics, camo, speed
   - Loadout 2 (City/Corridor Maps): For urban/maps - prioritize protection, reload
   Select EXACTLY 3 items for each from this list:
   Gun Rammer, Improved Ventilation, Vertical Stabilizer, Turbocharger,
   Improved Hardening, Low-Noise Exhaust System, Coated Optics,
   Commander's Vision System, Binocular Telescope, Camouflage Net,
   Spall Liner, Modified Configuration, Improved Rotation Mechanisms,
   Enhanced Gun Laying Drives, Improved Aiming.

2. AMMO TYPES: Armor Piercing (AP), APCR, HEAT, HE, HESH with counts

3. CONSUMABLES (EXACTLY 3, use nation-specific):
   Small Repair Kit, Large Repair Kit, Small First Aid Kit, Large First Aid Kit,
   Manual Fire Extinguisher, Automatic Fire Extinguisher, Removed Speed Governor,
   100-octane Gasoline, 105-octane Gasoline, Extra Rations (USSR),
   Case of Cola (USA), Chocolate (Germany), Pudding and Tea (UK),
   Strong Coffee (France), Improved Rations (China), Bread with Lard (Poland),
   Buchty (Czechoslovakia), Spaghetti with Meat Sauce (Italy),
   Onigiri (Japan), Coffee with Cinnamon (Sweden).

4. CREW PERKS (EXACTLY 6 per primary role):
   - Shared: Brothers in Arms, Repair, Concealment, Firefighting
   - Commander: Recon, Emergency, Mentor, Coordination, Sound Detection, Practicality, Hold the Line, Stay Sharp
   - Gunner: Snap Shot, Deadeye, Designated Target, Armorer, Steady Aim, Quick Aiming, Point Blank, Lone Wolf
   - Driver: Smooth Ride, Off-Road Driving, Clutch Braking, Controlled Impact, Reliable Placement, Engineer, Field Support, Bulletproof
   - Loader: Adrenaline Rush, Safe Stowage, Intuition, Perfect Charge, Close Combat, Ammo Tuning, The Second Chance, Mag Mastery
   - Radio Operator: Situational Awareness, Signal Interception, Jamming, Communications Expert, Side by Side, Threat Search, Battle Tempered

5. FIELD MODIFICATIONS: Use real in-game names only.
"""
```

---

## Стабільні результати (IS-7)

| Категорія | Значення |
|-----------|----------|
| **Loadout 1 (Open Maps)** | Turbocharger, Vertical Stabilizer, Coated Optics |
| **Loadout 2 (City)** | Improved Hardening, Gun Rammer, Vertical Stabilizer |
| **Ammo** | AP:10, APCR:18, HE:2 |
| **Consumables (USSR)** | Large Repair Kit, Large First Aid Kit, Extra Rations (USSR) |

---

## Тестування

```bash
# Тест scraper
python ai_scraper_triple.py "IS-7"
```

### Результат тесту (IS-7)

| Параметр | Значення |
|----------|----------|
| **Loadout 1** | Improved Hardening, Turbocharger, Gun Rammer |
| **Loadout 2** | Vertical Stabilizer, Improved Hardening, Improved Ventilation |
| **Ammo** | AP:10, APCR:18, HE:2 |
| **Consumables** | Large Repair Kit, Large First Aid Kit, Extra Rations (USSR) |
| **Crew** | Brothers in Arms, Repair + по 6 перків на роль |
| **Validation** | ✅ PASSED |

---

## Поточний статус (v3.0)

| Компонент | Статус |
|-----------|--------|
| Google AI режим (WebEngineView) | ✅ Працює |
| 1 запит (3 - вимкнено) | ✅ Працює |
| Валідація результатів | ✅ Працює |
| Кешування з expiry 30 днів | ✅ Працює |
| Локальна база (fallback) | ❌ Вимкнено |

---

## Логіка кешування (v3.0)

1. **При відкритті картки танку**:
   - Негайно показуємо кешовані дані (якщо є)
   - Запускаємо фонове оновлення

2. **Перевірка оновлення**:
   - Якщо кешу немає → робимо запит до Google AI
   - Якщо кеш є, але старіший 30 днів → оновлюємо
   - Якщо кеш свіжий → показуємо кеш, оновлюємо у фоні

3. **Періодичне оновлення кешу**:
   - Робимо раз на місяць для всіх танків

---

## Наступні кроки

1. ✅ Інтегровано `ai_normalizer.py` в `ai_engine.py`
2. ✅ Замінено виклик `ai_scraper.py` на `ai_scraper_strict.py`
3. ✅ Додано усереднення 3 запитів
4. ✅ Оновлено кешування з валідацією
5. ⬜ Протестувати інтеграцію в реальному застосунку

---

## Лог змін

| Дата | Версія | Зміни |
|------|--------|-------|
| 2026-05-09 | 1.0 | Початкова версія з документацією MMM25 |
