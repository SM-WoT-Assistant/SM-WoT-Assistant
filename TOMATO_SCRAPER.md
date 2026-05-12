# Tomato.gg Scraper

## Дата: 2026-05-11
## Версія: 1.0

---

## Опис

Скрапер для отримання збірок танків з tomato.gg замість Google AI.

### Переваги
- **Реальні дані** - статистика використання від тисяч гравців
- **Повні дані** - обладнання, екіпаж, field mods, амуніція
- **Надійність** - дані не генеруються AI, а беруться з реальної гри

---

## Файли

| Файл | Призначення |
|------|-------------|
| `tomato_selenium.py` | Основний скрепер (Selenium) |
| `tomato_scraper.py` | Не працює (Qt WebEngine не рендерить React) |

---

## Використання

```bash
python tomato_selenium.py Pl15_60TP_Lewandowskiego
python tomato_selenium.py R45_IS-7
```

---

## Структура даних

### Вхідні дані з __NEXT_DATA__

```json
{
  "equipment": {
    "data": {
      "equipmentDist": [["Gun Rammer Class 1", 10786], ...]
    }
  },
  "crew": {
    "data": {
      "crew": [
        {"role": "commander", "skills": [["brotherhood", {"count": 14825}], ...]},
        ...
      ]
    }
  },
  "fieldMods": {
    "data": {
      "mods": [...],
      "boostSlotCounts": {...}
    }
  }
}
```

### Результат

```json
{
  "equipment_1": ["Gun Rammer", "Improved Hardening", "Vertical Stabilizer"],
  "equipment_2": ["Improved Ventilation", "Turbocharger", "..."],
  "crew_perks": {
    "commander": ["Brothers in Arms", "Repair", "Sixth Sense", ...],
    "gunner": [...],
    "driver": [...],
    "loader": [...]
  },
  "field_mods": {...},
  "source": "tomato.gg"
}
```

---

## Мапінг танків

Потрібно мапити tank_code -> tomato_id/slug.

### Поточний мапінг (18 танків)

| Tank Code | Tomato ID | Slug |
|-----------|-----------|------|
| Pl15_60TP_Lewandowskiego | 3473 | 60tp |
| R45_IS-7 | 7169 | is-7 |
| R90_IS-4M | 6145 | is-4 |
| G42_Maus | 6929 | maus |
| G89_Leopard1 | 2577 | leopard-1 |
| A69_T110E5 | 5633 | t110e5 |
| F10_AMX_50B | 6209 | amx-50-b |
| S11_Strv_103B | 4737 | strv-103b |
| Ch19_121 | 4145 | 121 |
| Cz17_Vz_55 | 2929 | vz-55 |
| It08_Progetto_M40_mod_65 | 2721 | progetto-65 |
| F18_Bat_Chatillon25t | 3649 | b-c-25-t |
| GB100_Manticore | 8193 | manticore |
| Pl21_CS_63 | 5265 | cs-63 |
| Cz04_T50_51 | 2417 | tvp-t-50-51 |
| S16_Kranvagn | 2433 | kranvagn |
| It13_Progetto_M35_mod_46 | 2289 | progett-46 |
| R97_Object_140 | 5633 | object-140 |

---

## Тестування

```bash
python test_tomato.py
```

Результат для 60TP:
- Equipment 1: Gun Rammer, Improved Hardening, Vertical Stabilizer
- Equipment 2: Improved Ventilation, Turbocharger, Innovative Loading System
- Crew: повні дані для commander/gunner/driver/loader
- Field mods: присутні

---

## Наступні кроки

1. Розширити мапінг на всі танки з tank_db.json (~900)
2. Інтегрувати в ai_engine.py замість Google AI запитів
3. Додати кешування (збереження в файл)
4. Оптимізувати швидкість (кэшувати мапінг)

---

## Проблеми

- **Qt WebEngine не працює** - не рендерить React контент tomato.gg
- **Selenium працює** - використовує реальний Chrome

---

## Залежності

```
selenium>=4.0
chromedriver (в системі)
```