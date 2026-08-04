# PROJECT_DOCUMENTATION.md - Повна документація проекту

## ОГЛЯД ПРОЕКТУ

Мета проекту: Створення AI промпт-генератора для WoT конкурентних білдів з реальними даними з клієнта гри.

## ЩО ЗРОБЛЕНО

### 1. Витягування даних з клієнта гри

- Розпакування `.pkg` архівів (scripts.pkg, gui-part1.pkg, etc.)
- Збір обладнання (equipment), витратних (consumables), перків екіпажу (crew perks)
- Збір даних про танки, гармати, снаряди

### 2. Декодування XML файлів

**Два методи:**

**А) Через PjOrion (зовнішня програма):**
- Файли закодовані з заголовком `ENb` (BigWorld формат)
- Потрібен PjOrion для декодування
- Проблема: вікно з'являється при запуску
- Рішення: використати Python ctypes + tkinter для приховування вікна

**Б) Pure Python (власний декодер):**
- Повністю на Python, без зовнішніх програм
- Код у файлі `decode_xml.py`
- Працює швидко, без вікон
- Підтримує всі типи даних: strings, integers, floats, booleans, blobs

### 3. Парсинг даних

Скрипт `parse_game_entities.py`:
- Автоматично декодує закодовані XML файли
- Збирає обладнання, витратні, перки, field mods
- Зберігає результат у `game_entities.json`

## СТРУКТУРА ФАЙЛІВ

```
project/
├── tools/orion/
│   └── PjOrion.exe           # Зовнішній декодер (як резервний)
├── extracted_data/           # Дані з клієнта гри
│   ├── common/               # Спільні дані
│   │   ├── equipments-1.xml   # Обладнання
│   │   ├── optional_devices.xml
│   │   └── vehicle.xml
│   ├── ussr/                 # Танки СРСР
│   ├── usa/                  # Танки США
│   └── ...                   # Інші нації
├── decode_xml.py             # Python декодер (основний)
├── ORION_DECODER.md          # Інструкція для PjOrion
├── PYTHON_DECODER.md          # Інструкція для Python декодера
├── parse_game_entities.py    # Збір даних з клієнта
├── game_entities.json        # Результат (299 обладнань, 22 витратні)
└── PROJECT_DOCUMENTATION.md  # Цей файл
```

## ЯК ВІДНОВИТИ ПРОЕКТ ПІСЛЯ ЗБОЇВ

### Варіант 1: Python декодер не працює

1. Перевірити файл `decode_xml.py`
2. Порівняти вихід з результатом через PjOrion:
   ```bash
   # Python
   python decode_xml.py test.xml
   
   # PjOrion  
   python -c "subprocess.run(['tools/orion/PjOrion.exe', '--unpack-file', 'test.xml'])"
   ```
3. Перевірити структуру дескрипторів у файлі PYTHON_DECODER.md

### Варіант 2: PjOrion вікно з'являється

1. Використати метод з ORION_DECODER.md (ctypes + tkinter)
2. Або використати метод з CreateDesktopW для запуску на віртуальному столі

### Варіант 3: Потрібно декодувати всі файли

```python
# Декодувати всі XML в папці
from pathlib import Path
from decode_xml import WotXmlParser

decoder = WotXmlParser()
for xml_file in Path("extracted_data").rglob("*.xml"):
    decoder.decode_file(str(xml_file))
```

## КОРОТКА ШПАРГАЛКА

```bash
# 1. Розпакувати scripts.pkg
python -c "import zipfile; zipfile.ZipFile('scripts.pkg').extractall('extracted_data')"

# 2. Декодувати (Python)
python decode_xml.py extracted_data/common/equipments-1.xml

# 3. Зібрати дані
python parse_game_entities.py
```

## КОНТАКТИ ТА ПОСИЛАННЯ

- BigWorld XML Format: див. PYTHON_DECODER.md
- PjOrion: tools/orion/PjOrion.exe
- Тестування: порівняти вихід Python vs PjOrion на тестових файлах