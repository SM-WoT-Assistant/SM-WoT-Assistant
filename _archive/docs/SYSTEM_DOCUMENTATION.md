# WoT Assistant - Повна документація системи

## Дата: 2026-05-12
## Версія: 3.1

---

## 1. Джерела даних

### 1.1 Клієнт гри (пріоритет - структура + валідація)

Оріон + XML файли з `extracted_data/<nation>/`

| Дані | Файл | Опис |
|------|------|------|
| **Екіпаж** | `build_crew_builds.py` → `crew_builds.json` | Парсить `<crew>` з XML, 1139 танків |
| **Обладнання** | `extract_equipment_loadouts.py` → `equipment_loadouts.json` | З scripts.pkg, 862 танки |
| **Валідація** | `equipment_loadouts.json` | Перевірка доступності обладнання |

### 1.2 Tomato.gg (пріоритет - збірки)

`tomato_selenium.py` - Selenium скрейпер

| Дані | Опис |
|------|------|
| **Equipment** | Популярні збірки (2 слоти) |
| **Снаряди** | Типи снарядів і кількість |
| **Витратні** | Ремкомплекти, аптечки, раціони |
| **Crew Perks** | Перки екіпажу з статистикою |
| **Field Mods** | Популярні модифікації |

---

## 2. Архітектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         stats_ai.py                              │
│                         (Основний UI)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐    ┌────────────────────────────────┐ │
│  │   crew_builds.json   │    │     tomato_build_cache.json    │ │
│  │   (З КЛІЄНТА ГРИ)    │    │       (З TOMATO.GG)           │ │
│  │                     │    │                                │ │
│  │ - Ролі екіпажу       │    │ - Equipment (2 loadouts)     │ │
│  │ - Кількість членів   │    │ - Снаряди                    │ │
│  │ - Вторинні ролі      │    │ - Витратні                   │ │
│  │                     │    │ - Crew Perks                  │ │
│  │                     │    │ - Field Mods                  │ │
│  └─────────────────────┘    └────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │           equipment_loadouts.json (Клієнт)                 │ │
│  │           Валідація обладнання з Tomato                     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Валідація

### Обладнання
1. Завантажується `equipment_loadouts.json` (862 танки)
2. Ключ: `nation:tag` (наприклад `ussr:R45_IS-7`)
3. Збирається множина доступного обладнання клієнта
4. Обладнання з Tomato мапиться до ID клієнта і фільтрується

### Мапінг обладнання (Tomato → Клієнт)
```python
TOMATO_TO_CLIENT_EQUIP = {
    "Improved Hardening": "healthreserve",
    "Improved Ventilation": "improved ventilation",
    "Vertical Stabilizer": "vertical stabilizer",
    "Turbocharger": "turbocharger",
    "Gun Rammer": "gun rammer",
    ...
}
```

### Що НЕ валідується (тільки з Tomato)
- Снаряди (ammo)
- Витратні (consumables)
- Перки (crew perks)

---

## 2. Архітектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         stats_ai.py                              │
│                         (Основний UI)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐    ┌────────────────────────────────┐ │
│  │   crew_builds.json   │    │     tomato_build_cache.json    │ │
│  │   (З КЛІЄНТА ГРИ)    │    │       (З TOMATO.GG)           │ │
│  │                     │    │                                │ │
│  │ - Ролі екіпажу       │    │ - Equipment (2 loadouts)      │ │
│  │ - Кількість членів   │    │ - Crew Perks                  │ │
│  │ - Другорядні ролі    │    │ - Field Mods                  │ │
│  └─────────────────────┘    └────────────────────────────────┘ │
│                                                                  │
│  Результат: Повний сетап танка                                   │
│  - Equipment 1 (Open Maps)                                       │
│  - Equipment 2 (City Maps)                                       │
│  - Crew (4-6 членів з навичками)                                 │
│  - Field Mods                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Файли

### 3.1 Екстракція (Клієнт гри)

| Файл | Призначення | Джерело |
|------|-------------|---------|
| `tank_extractor.py` | Екстракція іконок та XML | `res/packages/` |
| `map_extractor.py` | Екстракція мап | `arenas.mo` |
| `build_crew_builds.py` |Crew конфігурація | `extracted_data/` |
| `extract_equipment_loadouts.py` | Обладнання | `scripts.pkg` |

### 3.2 Скрейпинг (Tomato)

| Файл | Призначення |
|------|-------------|
| `tomato_selenium.py` | Основний скрепер (Selenium) |
| `TOMATO_SCRAPER.md` | Документація скрепера |

### 3.3 Дані

| Файл | Призначення |
|------|-------------|
| `crew_builds.json` | Конфігурація екіпажу (1139 танків) |
| `tomato_build_cache.json` | Кеш збірок Tomato |
| `equipment_loadouts.json` | Локальні збірки обладнання |
| `tank_db.json` | База танків |
| `tank_tth.json` | TTX танків |

---

## 4. Типи екіпажу

Визначаються з XML клієнта гри:

| Тип | Членів | Приклад |
|-----|--------|---------|
| **Стандарт** | 4 | СТ, ЛТ, більшість ПТ |
| **5 членів** | 5 | IS-7 (commander, gunner, driver, loader, loader_radio) |
| **6 членів** | 6 | Maus, E-100 |

### Логіка визначення ролей

**Правило:** Другий loader перетворюється на loader_radio ТІЛЬКИ якщо немає окремого radioman.

- **IS-7:** Немає radioman → другий loader = loader_radio (з вторинною роллю radioman)
- **Maus:** Є radioman → два звичайних loader (без вторинних ролей)

### Приклад XML (IS-7)
```xml
<crew>
  <commander></commander>
  <gunner></gunner>
  <driver></driver>
  <loader></loader>
  <loader>	radioman	</loader>
</crew>
```

### Приклад XML (Maus)
```xml
<crew>
  <commander></commander>
  <radioman></radioman>
  <driver></driver>
  <gunner></gunner>
  <loader></loader>
  <loader></loader>
</crew>
```

### Результат у crew_builds.json

**IS-7:**
```json
{
  "crew_members": [
    {"role": "commander", "also": []},
    {"role": "gunner", "also": []},
    {"role": "driver", "also": []},
    {"role": "loader", "also": []},
    {"role": "loader_radio", "also": ["radioman"]}
  ]
}
```

**Maus:**
```json
{
  "crew_members": [
    {"role": "commander", "also": []},
    {"role": "radioman", "also": []},
    {"role": "driver", "also": []},
    {"role": "gunner", "also": []},
    {"role": "loader", "also": []},
    {"role": "loader", "also": []}
  ]
}
```

---

## 5. Скрейпер Tomato

### 5.1 Структура даних

```json
{
  "equipment_1": ["Improved Hardening", "Gun Rammer", "Turbocharger"],
  "equipment_2": ["Vertical Stabilizer", "Improved Hardening", "Gun Rammer"],
  "crew_perks": {
    "commander": ["Brothers in Arms", "Repair", ...],
    "gunner": [...],
    "driver": [...],
    "loader": [...],
    "loader_radio": [...]  // 10 навичок = 6 loader + 4 radio
  },
  "field_mods": [...]
}
```

### 5.2 Визначення loader_radio

```python
# tomato_selenium.py
secondary = role_data.get("secondarySkills", [])
if secondary:
    # Це loader_radio - радіооператор
    parsed["crew_perks"]["loader_radio"] = top_skills + sec_skills
```

---

## 6. Оновлення даних

### 6.1 Оновлення даних з клієнта гри

**ПРАВИЛО:** Дані з клієнта гри оновлюються **ТІЛЬКИ при зміні версії клієнта**.

При старті програми:
1. Перевіряється версія клієнта (`version.xml`)
2. Якщо версія ЗМІНИЛАСЬ → оновлюються дані з клієнта
3. При оновленні перевіряються маніфести (size+CRC) для пакетів
4. Якщо пакети НЕ змінились → розпаковка/декодування пропускається

| Дані | Джерело | Файл | Коли оновлюється |
|------|---------|------|------------------|
| **Екіпаж** | XML | `build_crew_builds.py` | При зміні версії клієнта |
| **Обладнання** | scripts.pkg | `extract_equipment_loadouts.py` | При зміні версії клієнта |
| **Мапи** | res/packages | `map_extractor.py` | При зміні версії клієнта |
| **Танки** | res/packages | `tank_extractor.py` | При зміні версії клієнта + перевірка маніфесту |
| **Збірки Tomato** | Tomato.gg | `tomato_selenium.py` | Кожні 30 днів |

### 6.2 Перевірка змін пакетів (tank_extractor.py)

Перед розпакуванням файлів з `res/packages/` перевіряються маніфести:

| Маніфест | Що перевіряє |
|----------|--------------|
| `.tank_extract_manifest.json` | size + CRC файлів у packages |
| `.icon_extract_manifest.json` | стан пакету іконок |

**Логіка:**
- Якщо версія клієнта змінилась → перевіряємо маніфести
- Якщо пакети змінились → розпаковуємо/декодуємо
- Якщо пакети НЕ змінились → пропускаємо (швидкий старт)

### 6.3 Автоматичний процес при старті

```
Старт програми
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Перевірка версії клієнта (version.xml)                  │
│     └─ Якщо ЗМІНИЛАСЬ → оновлення всіх даних з клієнта    │
│     └─ Якщо НЕ змінилась → дані з клієнта НЕ оновлюються  │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
   Готово (швидкий старт)
```

### 6.4 Ручне оновлення

```bash
# Перебудувати екіпаж
python build_crew_builds.py

# Перебудувати обладнання
python extract_equipment_loadouts.py

# Очистити кеш Tomato
python -c "open('tomato_build_cache.json', 'w').write('{}')"
```

### 6.2 Ручне оновлення (для тестування)

Якщо потрібно примусово перебудувати дані:

```bash
# Перебудувати екіпаж
python build_crew_builds.py

# Перебудувати обладнання
python extract_equipment_loadouts.py

# Очистити кеш Tomato
python -c "open('tomato_build_cache.json', 'w').write('{}')"
```

### 6.3 Джерела даних при оновленні

| Дані | Джерело | Файл для оновлення |
|------|---------|-------------------|
| **Екіпаж** | Клієнт (XML) | `extracted_data/<nation>/*.xml` → `build_crew_builds.py` |
| **Обладнання** | Клієнт (CSV) | `scripts.pkg` → `extract_equipment_loadouts.py` |
| **Снаряди** | Tomato.gg | Автоматично (кеш 30 днів) |
| **Перки** | Tomato.gg | Автоматично (кеш 30 днів) |
| **Epic перки** | Tomato.gg | Автоматично (кеш 30 днів) |

### 6.4 Валідація з клієнта

```
Клієнт (пріоритет)          Tomato.gg (пріоритет)
       │                           │
       ▼                           ▼
┌─────────────────┐      ┌─────────────────┐
│  crew_members   │      │  equipment_1    │
│  (ролі, к-сть)  │      │  equipment_2    │
├─────────────────┤      ├─────────────────┤
│ equipment_set   │      │  crew_perks     │
│ (доступне)      │      │  field_mods     │
└─────────────────┘      │  ammo           │
                         └─────────────────┘
```

**Валідація працює:**
- ✅ Обладнання - фільтрується через client_available_set (862 танки)
- ✅ Екіпаж - з клієнта (ролі, кількість, вторинні ролі)
- ⚠️ Снаряди - тільки з Tomato (немає в клієнті)
- ⚠️ Перки (включаючи епік) - тільки з Tomato (немає в клієнті)

### 6.5 Автоматичний процес при старті

```
Старт програми
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Перевірка версії клієнта (version.xml)                  │
│     └─ Якщо ЗМІНИЛАСЬ → оновлення всіх даних з клієнта    │
│     └─ Якщо НЕ змінилась → дані з клієнта НЕ оновлюються  │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
   Готово (швидкий старт)
```

---

## 7. Тестування

### 7.1 Перевіркаcrew_builds.json

```python
import json

with open('crew_builds.json') as f:
    data = json.load(f)

# IS-7
is7 = data['tanks']['R45_IS-7']
print(f"IS-7: {len(is7['crew_members'])} members")
for m in is7['crew_members']:
    print(f"  - {m['role']} also={m.get('also', [])}")

# Maus
maus = data['tanks']['G42_Maus']
print(f"Maus: {len(maus['crew_members'])} members")
```

### 7.2 Перевірка Tomato

```python
import tomato_selenium

result = tomato_selenium.fetch_build('R45_IS-7')
print(result['crew_perks'].keys())
```

---

## 8. Виправлення проблем

### Проблема: Дублювання ролей в XML
**Рішення** (`build_crew_builds.py`):
```python
# Якщо друга роль того ж типу → перейменувати в loader_radio
if role_count[role] > 1:
    if role == "loader":
        out.append({"role": "loader_radio", "also": also})
```

### Проблема: loader_radio не показується в UI
**Рішення** (`stats_ai.py`):
```python
# Зберігати як "loader_radio" ключ
if role == "loader_radio":
    crew_skills_map["loader_radio"] = skills[:10]
```

---

## 9. Мапінг танків (Tomato)

| Tank Code | Tomato ID | Slug |
|-----------|-----------|------|
| Pl15_60TP_Lewandowskiego | 3473 | 60tp |
| R45_IS-7 | 7169 | is-7 |
| G42_Maus | 6929 | maus |
| R90_IS-4M | 6145 | is-4 |
| G89_Leopard1 | 2577 | leopard-1 |
| ... | ... | ... |

---

## 10. Залежності

```
selenium>=4.0
chromedriver
Python 3.14
```

---

## 11. Скрипти

### 11.1 build_crew_builds.py

Парсить XML файли з `extracted_data/<nation>/` і генерує `crew_builds.json`.

**Вхід:** XML файли з клієнта
**Вихід:** crew_builds.json (1139 танків)

**Логіка:**
1. Читає всі XML файли танків
2. Парсить тег `<crew>` → ролі + вторинні ролі
3. Обробляє дублікати рольових:
   - Якщо є radioman → loader залишається loader
   - Якщо немає radioman → другий loader = loader_radio
4. Для танків без XML → дефолтні ролі за класом

### 11.2 extract_equipment_loadouts.py

Витягує популярні збірки обладнання з `scripts.pkg`.

**Вхід:** `C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg`
**Вихід:** equipment_loadouts.json (862 танки)

**Джерело:** `scripts/item_defs/optional_devices_assistance/optional_devices_usage.csv`

---

## 12. Ключові рішення

1. **Клієнт гри** → структура екіпажу (ролі, кількість, вторинні)
2. **Клієнт гри** → валідація обладнання (чи доступно для танка)
3. **Tomato.gg** → збірки (обладнання, снаряди, витратні, перки, field mods)
4. **Кешування** → 30 днів для Tomato, версія клієнта для клієнтських даних
5. **Автогенерація** → crew_builds.json з XML