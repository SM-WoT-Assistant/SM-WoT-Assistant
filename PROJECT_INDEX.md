# WoT Assistant - Індекс проєкту

## Дата: 2026-05-14

---

## Огляд

**WoT Assistant** — це інструмент для аналізу та оптимізації збірки танків у грі World of Tanks. Проєкт поєднує дані з клієнта гри та сайту Tomato.gg для створення повної картини збірки танка (equipment, crew, perks, field mods).

---

## Структура проєкту

### 📁 Основні директорії

| Директорія | Опис | Вміст |
|------------|------|-------|
| `.vscode/` | VS Code налаштування | settings.json, extensions.json |
| `.kilo/` | AI agent metadata | package.json, agent-manager.json, plans/, worktrees/ |
| `extracted_data/` | XML дані з клієнта | 11 націй (china, usa, ussr, germany, france, uk, japan, czech, italy, poland, sweden), common/ |
| `extracted_icons/` | Іконки гри | ~1230 файлів (tank icons, equipment, crew, nations, tiers) |
| `extracted_maps/` | PNG мапи + метадані | 62 PNG мап, map_data.json, map_dictionary.json |
| `tools/orion/` | Orion аналізатор | PjOrion.exe, конфігурації |
| `maps/` | Креслення мап | 51 директорія з тактичними малюнками |
| `.venv*/` | Python віртуальні середовища | 3 версії для різних станів розробки |

---

## 📄 Файли даних (JSON)

| Файл | Розмір | Записів | Опис |
|------|--------|---------|------|
| `tank_db.json` | 231 KB | 1,139 | База танків (імена, нації, класи, ID) |
| `tank_tth.json` | 309 KB | 1,264 | Технічні характеристики танків (TTX) |
| `crew_builds.json` | 614 KB | 1,139 | Конфігурація екіпажу |
| `equipment_loadouts.json` | 427 KB | 862 | Локальні збірки обладнання |
| `tomato_build_cache.json` | 7 KB | 2 | Кеш збірок з Tomato.gg |
| `map_list.json` | 1 KB | 51 | Список мап |
| `map_drawings.json` | 4 KB | 5 | Креслення мап |
| `map_links.json` | 5 KB | 51 | Посилання на мапи |
| `locales.json` | - | - | Локалізація (українські назви) |
| `settings.json` | 1 KB | 22 | Налаштування програми |

---

## 🐍 Python скрипти (~85 файлів)

### Основні модулі

| Файл | Рядків | Опис |
|------|--------|------|
| `main.py` | 909 | Основний UI (Tkinter) - вікно, карти, режим бою, гарячі клавіші |
| `stats_ai.py` | 1086+ | AI Stats UI - перегляд БД танків з фільтрами, обладнання |
| `ai_engine.py` | 554 | AI логіка - нормалізація, кешування, валідація |
| `ai_assistant.py` | 97 | Інтеграція Gemini AI |
| `config.py` | 159 | Конфігурація - шляхи, локалізація (UA/EN/RU) |

### Екстракція з клієнта гри

| Файл | Опис |
|------|------|
| `tank_extractor.py` | Екстракція іконок танків |
| `map_extractor.py` | Екстракція мап з `arenas.mo` |
| `build_crew_builds.py` | Парсить XML → `crew_builds.json` |
| `extract_equipment_loadouts.py` | Витягує обладнання → `equipment_loadouts.json` |

### Скрейпінг Tomato.gg

| Файл | Опис |
|------|------|
| `tomato_selenium.py` | Основний скрепер (Selenium) - 586+ рядків |
| `tomato_scraper.py` | Альтернативний скрепер |
| `ai_scraper.py` | AI-скрепер (WebEngine + Google AI) |
| `ai_scraper_triple.py` | Потрійний скрепінг з усередненням |
| `ai_scraper_strict.py` | Строга валідація |
| `ai_normalizer.py` | Нормалізація даних |

### AI Engine

| Файл | Опис |
|------|------|
| `stats_ai.py` | Основний UI інтерфейс |
| `ai_engine.py` | AI логіка |
| `ai_assistant.py` | AI асистент |

### Оновлення

| Файл | Опис |
|------|------|
| `AUTO_UPDATE_GUIDE.py` | Інструкція з авто-оновлення |
| `tth_updater.py` | Оновлення TTX даних |
| `tth_orion_batch.py` | Пакетне оновлення з Orion |
| `map_updater.py` | Оновлення мап (selenium) |
| `arc_archive.py` | Архівування |
| `arc_sync.py` | Синхронізація |

### Менеджери

| Файл | Опис |
|------|------|
| `map_manager.py` | Менеджер мап (430+ рядків) |
| `map_renderer.py` | Рендерер мап |
| `log_reader.py` | Читач логів (battle detection) |
| `ui_manager.py` | Перемикання панелей |
| `window_manager.py` | Window positioning, click-through |
| `locale_manager.py` | Локалізація |
| `data_manager.py` | Завантаження/збереження даних |
| `painter.py` | Малювання на картах |
| `tactics_manager.py` | Імпорт/експорт тактики |

### Діагностика та тестування

| Файл | Опис |
|------|------|
| `diagnostic.py` | Діагностика системи |
| `test.py` | Основні тести |
| `test_build_db.py` | Тести бази даних |
| `test_auto_update.py` | Тести авто-оновлення |
| `test_tomato.py` | Тести Tomato |
| `test_tomato_scrape.py` | Тести скрепера |
| `check_db.py` | Перевірка БД |
| `check_tank_db.py` | Перевірка танків |

### Дебаг скрипти (~40 файлів)

```
debug_*.py          - debug_buttons, debug_screenshot, debug_crew, debug_equipment
check_*.py          - check_api, check_consumables, check_economics, check_setups
find_*.py           - find_tanks, find_refs3, find_consumables_data
click_*.py          - click_consumables, click_loadout_tab
analyze_*.py        - analyze_html, analyze_json, analyze_consumables
try_*.py            - try_api2, try_urls, try_pro_loadouts
selenium_*.py       - selenium_loadout_tab, selenium_parse_consumables
patch_*.py          - patch_ai, patch_db, patch_stats_ai_fm
```

---

## 📝 Документація (Markdown - 13 файлів)

### Основна документація

| Файл | Дата | Опис |
|------|------|------|
| `SYSTEM_DOCUMENTATION.md` | 2026-05-12 | Повна документація системи, архітектура, ключові рішення |
| `TOMATO_CLIENT_INTEGRATION.md` | 2026-05-12 | Інтеграція клієнт + Tomato.gg, структура crew_builds.json |
| `TOMATO_SCRAPER.md` | 2026-05-11 | Selenium скрепер для Tomato.gg |

### Зміни та історія

| Файл | Дата | Опис |
|------|------|------|
| `CHANGELOG.md` | 2026-05-10 | Історія змін (AI Build Display Fixes) |
| `CHANGES_DOCUMENTATION.md` | 2026-05-10 | Деталі реалізації minimap detection |
| `README_CHANGES.md` | 2026-05-10 | Quick reference для minimap |

### AI система

| Файл | Дата | Опис |
|------|------|------|
| `MMM25_AI_BUILD_GENERATOR.md` | 2026-05-10 | AI генератор збірок (v3.0 - Google AI mode) |

### Тестування та виправлення

| Файл | Дата | Опис |
|------|------|------|
| `TESTING_GUIDE.md` | 2026-05-10 | Minimap detection testing (11 test cases) |
| `TROUBLE_SHOOTING.md` | 2026-05-12 | Crew types, loader_radio fix |

### Сесії розробки

| Файл | Дата | Опис |
|------|------|------|
| `SESSION_2026-05-12_AMMO_FIX.md` | 2026-05-12 | Виправлення снарядів |
| `SESSION_2026-05-12_SIMPLIFICATION.md` | 2026-05-12 | Спрощення Tomato інтеграції |

---

## 🧪 Тестові файли

```
run_test.bat
tmp_gui_list.txt
tmp_test.py
tmp_xml_check.txt
scan_output.txt
```

---

## 📋 Логи

```
app.log
error.log
build_test.log
```

---

## 🔧 Конфігурація

```
.gitignore
.client_update_manifest.json
.vscode/settings.json
```

---

## Архітектура

```
┌──────────────────────────────────────────────────────────────┐
│                         main.py                               │
│               (Tkinter UI, Map Viewer, Battle Mode)           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌───────────────────────────────────┐ │
│  │   stats_ai.py    │  │         tomato_viewer.py         │ │
│  │  (AI Stats UI)   │  │      (WebView2 для Tomato.gg)     │ │
│  └────────┬─────────┘  └───────────────────────────────────┘ │
│           │                    │                              │
│  ┌────────▼────────────────────▼──────────────────────────┐  │
│  │                      ai_engine.py                       │  │
│  │           (AI логіка, кешування, нормалізація)         │  │
│  └────────┬────────────────────────────────────┬───────────┘  │
│           │                                    │              │
│  ┌────────▼────────┐                ┌──────────▼──────────┐  │
│  │  ai_assistant.py │                │ tomato_selenium.py │  │
│  │  (Gemini AI)     │                │    (Selenium)       │  │
│  └──────────────────┘                └────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                    JSON Database                       │   │
│  │  tank_db.json | tank_tth.json | crew_builds.json       │   │
│  │  equipment_loadouts.json | tomato_build_cache.json     │   │
│  │  map_*.json | settings.json                           │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐   │
│  │              WoT Client (extracted_data/)              │   │
│  │  11 nations XML | vehicle.xml | equipment.xml          │   │
│  │  extracted_icons/ | extracted_maps/                    │   │
│  └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## Залежності

### GUI
- `tkinter` (built-in) - основний UI
- `PyQt6` (ai_scraper*.py) - WebEngine для AI

### Web/Automation
- `selenium>=4.0` - Tomato.gg скрепінг
- `chromedriver` - веб-драйвер
- `requests` - завантаження мап
- `BeautifulSoup` - парсинг HTML
- `webdriver_manager` - авто-менеджер драйвера

### Image Processing
- `Pillow (PIL)` - мапи, іконки, рендеринг

### AI/ML
- `google.genai` - Gemini AI інтеграція

### System
- `keyboard` - гарячі клавіші
- `ctypes` - click-through вікна

### Data
- `json`, `os`, `re`, `threading` - стандартні
- `collections.Counter` - нормалізація

---

## Ключові рішення

1. **Клієнт гри** → структура екіпажу (ролі, кількість, вторинні)
2. **Клієнт гри** → валідація обладнання (чи доступно для танка)
3. **Tomato.gg** → збірки (обладнання, снаряди, витратні, перки, field mods)
4. **Кешування** → 30 днів для Tomato, версія клієнта для клієнтських даних
5. **AI** → Google Gemini через WebEngineView з потрійним скрепінгом

---

## Джерела даних

### Клієнт гри (пріоритет - структура + валідація)
- Оріон + XML файли з `extracted_data/<nation>/`
- 11 націй: USA, Germany, USSR, France, UK, China, Japan, Sweden, Poland, Czech, Italy
- 1,139 танків з повними даними

### Tomato.gg (пріоритет - збірки)
- Selenium скрепер для збору збірок
- WebEngine AI для альтернативного збору

---

## Статистика проєкту

| Метрика | Значення |
|---------|----------|
| Python файлів | ~85 |
| MD документація | 13 |
| JSON файлів | 10 |
| Директорій даних | 6 |
| Танків у БД | 1,139 |
| Мап | 51 |
| Націй | 11 |
| Рядків коду (основні) | ~3,500+ |

---

*Індекс створено автоматично*