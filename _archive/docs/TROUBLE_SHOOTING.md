# Tomato.gg Scraper - Troubleshooting Guide

## Date: 2026-05-12
## Version: 1.2

---

## Типи екіпажу в грі

### Тип 1: Окремий radioman (Maus)
- commander (6 скілів)
- radioman (6 скілів)  
- driver (6 скілів)
- gunner (6 скілів)
- loader (6 скілів)
- **Всього: 5 членів, кожен з 6 навичками**
- **Приклад**: G42_Maus

### Тип 2: Loader_radio (IS-7)
- commander (6 скілів)
- gunner (6 скілів)
- driver (6 скілів)
- loader (6 скілів)
- loader_radio (10 скілів = 6 loader + 4 radio)
- **Всього: 5 членів, останній з 10 навичками**
- **Приклад**: R45_IS-7

### Тип 3: Стандартний (4 члени)
- commander, gunner, driver, loader
- **Всього: 4 члени**
- **Приклад**: більшість СТ, ЛТ, ПТ

### Тип 4: Loader_radio без окремого loader (4 члени)
- commander, gunner, driver, loader_radio (10 скілів)
- Loader виконує роль радіооператора
- **Приклад**: Cz04_T50_51

---

## Як визначити тип з Tomato

Дивитись на структуру crew в Tomato:
- loader + loader_radio → Тип 2 (5 членів)
- loader_radio без loader → Тип 4 (4 члени)
- є radioman → Тип 1 (5 членів)
- 4 ролі → Тип 3 (4 члени)

---

## Проблема: 5-й член екіпажу (loader_radio)

### Симптом
- Скрапер віддає 5 членів екіпажу
- В UI показує тільки 4 або показує неправильні іконки

### Коріння проблеми
1. **Визначення loader_radio**: Tomato повертає роль "loader" з secondarySkills=8, а не "loader_radio"
2. **Маппінг в UI**: loader_radio попадає в той самий ключ що і звичайний loader
3. **Порядок перевірок**: "radio" в "loader_radio" маппився на radioman замість loader

### Рішення

#### 1. tomato_selenium.py - Визначення loader_radio
```python
# При парсингу перевіряємо secondarySkills
secondary = role_data.get("secondarySkills", [])
if secondary and len(secondary) > 0:
    # Це loader_radio - радіооператор
    parsed["crew_perks"]["loader_radio"] = top_skills + sec_skills
else:
    parsed["crew_perks"][role] = top_skills
```

#### 2. crew_builds.json - Правильна конфігурація
```json
"R45_IS-7": {
  "crew_members": [
    {"role": "commander", "also": []},
    {"role": "gunner", "also": []},
    {"role": "driver", "also": []},
    {"role": "loader", "also": []},
    {"role": "loader_radio", "also": ["radioman"]}
  ]
}
```

#### 3. stats_ai.py - Три місця виправлення

**3.1 process_tomato_data (рядки ~2184)**
```python
crew_perks = tomato_data.get("crew_perks", {})
crew_skills_map = {}
has_loader_radio = "loader_radio" in crew_perks

for role, skills in crew_perks.items():
    if isinstance(skills, list):
        if role == "loader_radio":
            # loader_radio = 5th crew member with 6 loader + 4 radio
            if "loader_radio" not in crew_skills_map:
                crew_skills_map["loader_radio"] = []
            crew_skills_map["loader_radio"].extend([map_skill(s) for s in skills[:10]])
        elif role == "loader":
            # Regular loader = 4th crew member (6 skills)
            if "loader" not in crew_skills_map:
                crew_skills_map["loader"] = []
            crew_skills_map["loader"].extend([map_skill(s) for s in skills[:6]])
        else:
            skill_ids = [map_skill(s) for s in skills[:6]]
            if role not in crew_skills_map:
                crew_skills_map[role] = []
            crew_skills_map[role].extend(skill_ids)
```

**3.2 Кешування (рядки ~2265)**
- Те саме що вище

**3.3 _update_ai_setup_ui (рядки ~2449)**
```python
# Handle loader_radio (5th crew member with 10 skills)
if role == "loader_radio":
    if "loader_radio" not in ai_crew:
        ai_crew["loader_radio"] = []
    ai_crew["loader_radio"].append(skills[:10])
    
    if "loader_radio" not in ai_crew_also:
        ai_crew_also["loader_radio"] = []
    ai_crew_also["loader_radio"].append([])
```

**3.4 Маппінг іконок (рядки ~2491)**
```python
role_str = member.get("role", "commander")
primary_r_icon = role_str.lower()

# Handle loader_radio FIRST - special case, map to loader
if "loader_radio" in primary_r_icon:
    primary_r_icon = "loader"
elif "radio" in primary_r_icon or "radioman" in primary_r_icon:
    primary_r_icon = "radioman"
elif "loader" in primary_r_icon:
    primary_r_icon = "loader"
# ... etc
```

---

## Структура екіпажу на Tomato

### Для різних танків

**4 члени (стандарт):**
- commander
- gunner  
- driver
- loader

**5 членів (важкі танки, наприклад IS-7):**
- commander
- gunner
- driver
- loader (6 навичок)
- loader з secondarySkills=8 → loader_radio (10 навичок: 6 loader + 4 radio)

### Ключова логіка
1. Кількість екіпажу = довжина масиву crew з Tomato
2. Якщо loader + secondarySkills → це loader_radio (радіооператор)
3. Брати топ-6 з skills + топ-4 з secondarySkills = 10 навичок

---

## Тестування

### Перевірка IS-7
```python
import tomato_selenium
result = tomato_selenium.fetch_build('R45_IS-7')
print('Crew roles:', list(result['crew_perks'].keys()))
# Очікуваний результат: ['commander', 'gunner', 'driver', 'loader', 'loader_radio']
```

### Перевірка в UI
1. Запустити app
2. Вибрати IS-7
3. Перевірити:
   - 5 рядків екіпажу
   - 1-я іконка: loader
   - 2-я іконка: radioman
   - 10 навичок в 5-му рядку

---

## Очищення кешу

Після змін обов'язково очистити кеш:
```python
with open('tomato_build_cache.json', 'w') as f:
    f.write('{}')
```