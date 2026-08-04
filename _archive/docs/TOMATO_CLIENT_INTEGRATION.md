# Tomato.gg + Клієнт Грі - Документація

## Дата: 2026-05-12
## Версія: 2.0

---

## Джерела даних

### 1. Клієнт гри (пріоритет)
- **Оріон** (`tools/orion/PjOrion.exe`) - декодує бінарні XML з `scripts.pkg`
- XML файли в `extracted_data/<nation>/`
- Джерело для: **екіпаж**, **ролі**, **другорядні ролі**

### 2. Tomato.gg (пріоритет для збірок)
- **Selenium** - скрейпить популярні збірки
- Джерело для: **обладнання**, **перки екіпажу**, **field mods**
- Дані більш актуальні (від реальних гравців)

---

## Архітектура інтеграції

```
┌─────────────────────────────────────────────────────────────┐
│                     stats_ai.py                              │
├─────────────────────────────────────────────────────────────┤
│  1. crew_builds.json (з клієнта гри)                        │
│     → Визначає кількість членів екіпажу                    │
│     → Визначає ролі (commander, gunner, driver, loader)    │
│     → Визначає другорядні ролі (radioman, loader_radio)     │
│                                                              │
│  2. Tomato scraper (tomato_selenium.py)                     │
│     → Обладнання (equipment_1, equipment_2)                 │
│     → Перки екіпажу (crew_perks)                            │
│     → Field mods                                            │
└─────────────────────────────────────────────────────────────┘
```

---

##crew_builds.json - структура

### Джерело
Скрипт: `build_crew_builds.py`
- Парсить XML з `extracted_data/<nation>/*.xml`
- Витягує тег `<crew>` з ролями та другорядними ролями

### Приклад IS-7 (5 членів)
```json
{
  "R45_IS-7": {
    "crew_members": [
      {"role": "commander", "also": []},
      {"role": "gunner", "also": []},
      {"role": "driver", "also": []},
      {"role": "loader", "also": []},
      {"role": "loader_radio", "also": ["radioman"]}
    ]
  }
}
```

### Типи екіпажу

| Тип | Приклад | Опис |
|-----|---------|------|
| **4 члени** | Більшість СТ, ЛТ | commander, gunner, driver, loader |
| **5 членів (loader_radio)** | IS-7 | loader + loader_radio (10 навичок) |
| **6 членів** | Maus, E-100 | commander, radioman, driver, gunner, loader, loader_radio |

**Примітка:** Кількість членів береться з XML клієнта гри.

---

## Tomato scraper - логіка

### Визначення loader_radio
```python
# tomato_selenium.py - parse_tomato_data()
secondary = role_data.get("secondarySkills", [])
if secondary:
    # Це loader_radio - радіооператор
    parsed["crew_perks"]["loader_radio"] = top_skills + sec_skills
```

### Маппінг в UI
```python
# stats_ai.py - process_tomato_data()
if role == "loader_radio":
    crew_skills_map["loader_radio"] = skills[:10]
elif role == "loader":
    crew_skills_map["loader"] = skills[:6]
```

---

## Проблеми та рішення

### Проблема: Дублювання ролей в XML
XML може мати два `<loader>` - перший звичайний, другий з радіо.

**Рішення** (`build_crew_builds.py`):
```python
# Якщо друга роль має also → перейменувати в loader_radio
if role in seen and also:
    if role == "loader" and "radioman" in also:
        out.append({"role": "loader_radio", "also": also})
```

---

## Як оновити дані

### 1. Оновлення клієнта гри
```bash
# Перезапустити екстракцію (якщо є нові пакети)
python tank_extractor.py

# Перебудувати crew_builds.json
python build_crew_builds.py
```

### 2. Оновлення Tomato
```bash
# Очистити кеш
echo {} > tomato_build_cache.json
```

---

## Тестування

### Перевірка IS-7
```python
# Запуск скрипту
python build_crew_builds.py

# Перевірка результату
import json
with open('crew_builds.json') as f:
    data = json.load(f)
    is7 = data['tanks']['R45_IS-7']
    print(is7['crew_members'])
```

### Перевірка в app
1. Запустити app
2. Вибрати IS-7
3. Перевірити 5 рядків екіпажу
4. Перевірити іконки (loader + radioman)
5. Перевірити 10 навичок в 5-му рядку

---

## Файли

| Файл | Призначення |
|------|-------------|
| `build_crew_builds.py` | Парсить XML клієнта, генерує crew_builds.json |
| `tomato_selenium.py` | Скрейпить Tomato.gg |
| `stats_ai.py` | UI, інтегрує дані клієнта + Tomato |
| `crew_builds.json` | Конфігурація екіпажу (1139 танків) |
| `tomato_build_cache.json` | Кеш збірок Tomato |
| `TROUBLE_SHOOTING.md` | Документація проблем |

---

## Важливі замітки

1. ** crew_builds.json** генерується автоматично - НЕ редагувати вручну!
2. При оновленні гри - перезапустити `build_crew_builds.py`
3. Tomato кеш очищувати після змін в парсері
4. Використовувати Tomato для перків, клієнт для структури екіпажу