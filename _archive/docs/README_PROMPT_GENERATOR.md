# Prompt Generator for World of Tanks Competitive Builds

## Опис
Генерує AI-промт з реальними даними з клієнта гри World of Tanks. Промт містить два варіанти build (Main і Alternate).

## Джерела даних (з клієнта гри)
- **tank_slots_full.json**: Кількість слотів обладнання для кожного танка
- **tank_db.json**: Tier та клас танка
- **crew_builds.json**: Склад екіпажу, пули перків (_role_skill_pools), політика перків (_perk_policy)
- **game_entities_english.json**: Англійські назви обладнання

## Основні функції
1. **Обладнання залежить від tier танка**
   - Tier 1-4 = Tier 3 equipment
   - Tier 5-7 = Tier 2 equipment
   - Tier 8-10 = Tier 1 equipment

2. **Фільтрація за класом танка**
   - SPG виключає: Vertical Stabilizer, Grousers

3. **Перки з клієнта гри**
   - Беруться з _role_skill_pools
   - Кількість перків за tier з _perk_policy:
     - Tier 1-4: 1 перк
     - Tier 5-6: 2 перки
     - Tier 7: 4 перки
     - Tier 8-10: 6 перків

4. **loader_radio обробка**
   - Показується як Loader (6 перків) + Radioman (4 перки)
   - Два рядки з підказкою що це одна людина

## Структура виводу
1. **Equipment**: Main + Alternate (різні набори обладнання)
2. **Ammo**: Main + Alternate (різні типи/кількість снарядів)
3. **Consumables**: Main + Alternate (різні витратні)
4. **Crew Perks**: однакові для обох варіантів (екіпаж один)
5. **Field Modifications**: однакові для обох варіантів

## Використання
```bash
python generate_prompt_v2.py
```

## Приклад виводу
- Файл: prompt_is7_v3.txt
- Танк: IS-7 (Tier 10, HT)
- Слоти обладнання: 3
- Доступне обладнання: 15 найменувань

## Підтримувані танки
Всі танки з tank_slots_full.json (близько 1264 танка)