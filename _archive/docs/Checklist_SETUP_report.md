# Checklist_SETUP_update.md - ЗВІТ

## КРОК 1: Проіндексувати проект та знайти клієнт гри ✓

**Знайдено:**
- Клієнт: `C:\Games\World_of_Tanks_EU`
- Оріон: `tools/orion/PjOrion.exe`
- Існуючі дані в `extracted_data/` та `game_entities.json`

## КРОК 2: Навчитися декодувати XML файли ✓

**Проблема:** Файли зберігаються в закодованому форматі ENb (перші байти: 69, 78, 161, 98)

**Рішення:**
```bash
cmd /c start /MIN /wait "" "tools\orion\PjOrion.exe" "--unpack-folder=extracted_data\common" "--exit"
```

**Тестування:**
```bash
python parse_game_entities.py
```
Результат: 299 обладнання, 22 витратні, 22 перки, 15 field mods

## КРОК 3: Розпакувати дані з клієнта ✓

**Знайдено пакети:**
- `scripts.pkg` — XML definitions (159 MB)
- `gui-part1.pkg` — іконки та GUI (1.3 GB)

**Структура extracted_data:**
```
extracted_data/common/
├── equipments.xml           # Обладнання + витратні
├── optional_devices.xml     # Deluxe/Experimental
└── post_progression/
    └── field_modifications.xml
```

## КРОК 4: Іконки та маппінг ✓

**Знайдено іконки:**
- В `gui-part1.pkg`: `gui/maps/icons/artefact/`
- Приклад: `handExtinguishers.png`, `largeRepairkit.png`, `rammer.png`

**Витягнуто:**
- 32 іконки в `extracted_icons/artefacts/`
- Створено `icon_mapping.json` з маппінгом ID → icon name

## КРОК 5: Локалізація - В ПРОЦЕСІ

**Проблема:** Імена мають формат `#artefacts:handExtinguishers_name`

**Потрібно:**
1. Знайти .mo файли локалізації
2. Розпакувати res/text/lc_messages/*.mo
3. Мапити ключі на англійські назви

**Файли локалізації:**
```
C:\Games\World_of_Tanks_EU\res\text\lc_messages\
├── artefacts.mo       (153 KB)
├── crew_perks.mo      (85 KB)
└── item_types.mo      (10 KB)
```

---

## ЩО ЗРОБЛЕНО

1. ✓ Знайдено клієнт гри
2. ✓ Знайдено та протестовано PjOrion
3. ✓ Створено DECODER_XML.md з повною документацією
4. ✓ extract_icons_and_map.py — витягує іконки та мапить
5. ✓ parse_game_entities.py — працює (генерує game_entities.json)
6. ✓ icon_mapping.json — створено
7. ✓ parse_mo_localization.py — парсить .mo файли
8. ✓ localization/ — знайдено переклади (cp1251)
9. ✓ create_english_names.py — маппінг на англійські назви
10. ✓ game_entities_english.json — **ГОТОВИЙ ФАЙЛ З АНГЛІЙСЬКИМИ НАЗВАМИ**

## НОВІ ФАЙЛИ

| Файл | Призначення |
|------|-------------|
| DECODER_XML.md | Повна інструкція |
| parse_mo_localization.py | Парсер .mo файлів |
| find_english.py | Пошук термінів в .mo |
| create_english_names.py | Маппінг на English |
| game_entities_english.json | **Результат: 299+22+22+15** |
| localization/ | 872+332+150 перекладів |

## РЕЗУЛЬТАТ

game_entities_english.json містить:
- 299 обладнання (англ. назви)
- 22 витратні (англ. назви)
- 22 перки (англ. назви)
- 15 field mods (англ. назви)

Приклад:
- handExtinguishers → "Manual Fire Extinguisher"
- rammer → "Gun Rammer"
- smallRepairkit → "Small Repair Kit"

## НАСТУПНІ КРОКИ

Для Checklist_SETUP_update.md:
1. Додати цей файл до промту
2. Продовжити збір даних по танкам (слоти, екіпаж)