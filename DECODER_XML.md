# DECODER_XML.md - Повна інструкція з декодування WoT клієнта

## ОГЛЯД

Ця інструкція описує повний процес отримання даних з клієнта гри World of Tanks:
1. Розпакування .pkg архівів
2. Декодування XML файлів через PjOrion
3. Збір локалізації (назви українською/англійською)
4. Маппінг іконок до предметів

---

## КРОК 1: РОЗПАКУВАННЯ .PKG ФАЙЛІВ

### Структура пакетів

| Пакет | Вміст | Розмір |
|-------|-------|--------|
| scripts.pkg | XML definitions (обладнання, танки, перки) | 159 MB |
| gui-part1.pkg | Іконки, UI елементи | 1.3 GB |
| gui-part2.pkg | Додаткові GUI елементи | 1.4 GB |
| vehicles_level_XX.pkg | Моделі танків | ~700MB-1.7GB |

### Розпакування через Python

```python
import zipfile

pkg_path = r"C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg"
output_dir = r"D:\project\extracted_data"

with zipfile.ZipFile(pkg_path, 'r') as zf:
    zf.extractall(output_dir)
```

Або через 7-Zip:
```bash
"C:\Program Files\7-Zip\7z.exe" x "C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg" -o"extracted_data" -y
```

### Структура після розпакування

```
extracted_data/
├── common/
│   ├── equipments.xml          # Обладнання + витратні
│   ├── optional_devices.xml    # Deluxe/Experimental
│   └── post_progression/
│       ├── field_modifications.xml
│       └── trees.xml
├── ussr/                       # Танки СРСР
│   ├── R01_IS.xml
│   └── ...
├── usa/                        # Танки США
├── germany/                    # Танки Німеччини
└── ...
```

---

## КРОК 2: ДЕКОДУВАННЯ ЧЕРЕЗ PJORION

### Проблема

Файли в .pkg архіві зберігаються в закодованому форматі:
- **До декодування:** Перші байти `69, 78, 161, 98` = "ENb"
- **Після декодування:** Перші байти `60, 63, 120, 109` = "<?xm" (нормальний XML)

### Команда декодування

```bash
cmd /c start /MIN /wait "" "tools\orion\PjOrion.exe" "--unpack-folder=extracted_data\common" "--exit"
```

### Опції PjOrion

```
--unpack-folder=<path>   Папка з XML для декодування
--unpack-file=<file>     Один файл
--exit                   Вихід після завершення
```

### Приклад для всіх папок

```bash
cmd /c start /MIN /wait "" "tools\orion\PjOrion.exe" "--unpack-folder=extracted_data\common" "--exit"
cmd /c start /MIN /wait "" "tools\orion\PjOrion.exe" "--unpack-folder=extracted_data\ussr" "--exit"
cmd /c start /MIN /wait "" "tools\orion\PjOrion.exe" "--unpack-folder=extracted_data\usa" "--exit"
```

---

## КРОК 3: ЗБІР ЛОКАЛІЗАЦІЇ

### Джерела локалізації

Локалізація зберігається в `.mo` файлах (gettext format):

| Файл | Вміст |
|------|-------|
| artefacts.mo | Назви обладнання, витратних |
| crew_perks.mo | Назви перків екіпажу |
| item_types.mo | Типи предметів |
| tankmen/messages.mo | Імена танкістів |

### Розташування .mo файлів

```
C:\Games\World_of_Tanks_EU\res\text\lc_messages\
├── artefacts.mo          (153 KB)
├── crew_perks.mo         (85 KB)
├── item_types.mo         (10 KB)
└── ...
```

### Читання .mo файлів

Потрібно встановити Python бібліотеку:
```bash
pip install python-gettext
```

```python
import gettext

mo = gettext.GNUTranslations(open('artefacts.mo', 'rb'))
name = mo.gettext('handExtinguishers_name')  # "Manual Fire Extinguisher"
```

---

## КРОК 4: МАППІНГ ІКОНOK

### Джерело іконок

Іконки зберігаються в `gui-part1.pkg`:
```
gui/maps/icons/artefact/
├── handExtinguishers.png
├── largeRepairkit.png
├── rammer.png
├── turbocharger.png
└── ...
```

### Розпакування іконок

```python
import zipfile

with zipfile.ZipFile("gui-part1.pkg", 'r') as z:
    for entry in z.infolist():
        if 'gui/maps/icons/artefact/' in entry.filename:
            filename = os.path.basename(entry.filename)
            with open(f"extracted_icons/artefacts/{filename}", 'wb') as f:
                f.write(z.read(entry.filename))
```

---

## КРОК 5: ГЕНЕРАЦІЯ game_entities.json

### Використання parse_game_entities.py

```bash
python parse_game_entities.py
```

### Що робить скрипт:
1. Запускає PjOrion на extracted_data/common
2. Парсить equipments.xml
3. Парсить optional_devices.xml  
4. Читає crew_builds.json для перків
5. Зберігає game_entities.json

### Результат game_entities.json

```json
{
  "equipment": {
    "rammer": {
      "id": "rammer",
      "name": "Gun Rammer",
      "icon": "rammer",
      "tags": "optionalDevice"
    }
  },
  "consumables": {
    "smallRepairkit": {
      "id": "smallRepairkit", 
      "name": "Small Repair Kit",
      "icon": "smallRepairkit"
    }
  }
}
```

---

## ПОВНИЙ WORKFLOW

### Для першого запуску:

```bash
# 1. Розпакувати scripts.pkg
python -c "
import zipfile
with zipfile.ZipFile(r'C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg', 'r') as z:
    z.extractall('extracted_data')
"

# 2. Розпакувати gui-part1.pkg (для іконок)
python -c "
import zipfile
with zipfile.ZipFile(r'C:\Games\World_of_Tanks_EU\res\packages\gui-part1.pkg', 'r') as z:
    z.extractall('extracted_gui')
"

# 3. Декодувати через PjOrion
cmd /c start /MIN /wait "" "tools\orion\PjOrion.exe" "--unpack-folder=extracted_data\common" "--exit"

# 4. Згенерувати game_entities.json
python parse_game_entities.py
```

### Для оновлення (після апдейту гри):

```bash
# Видалити старі дані
rm -rf extracted_data

# Повторити кроки 1-4
```

---

## СТРУКТУРА ДАНИХ ПІСЛЯ ОБРОБКИ

```
project/
├── extracted_data/
│   ├── common/
│   │   ├── equipments.xml          (ДЕКОДОВАНИЙ)
│   │   ├── optional_devices.xml     (ДЕКОДОВАНИЙ)
│   │   └── post_progression/
│   │       ├── field_modifications.xml
│   │       └── trees.xml
│   ├── ussr/                       (ДЕКОДОВАНІ)
│   ├── usa/
│   └── ...
├── extracted_gui/
│   └── gui/maps/icons/artefact/   (іконки)
├── extracted_icons/
│   └── artefacts/                  (скопійовані іконки)
├── tools/orion/
│   └── PjOrion.exe
├── game_entities.json              (РЕЗУЛЬТАТ)
├── icon_mapping.json
├── crew_builds.json
└── DECODER_XML.md                  (ЦЯ ІНСТРУКЦІЯ)
```

---

## ВІДОМІ ПРОБЛЕМИ

1. **PjOrion видаляє файли при відкритті в GUI** — працює через командний рядок
2. **Деякі файли не декодуються** — потрібно перезапустити
3. **Великі папки** — збільшити timeout до 60+ секунд

---

## КОРОТКА ШПАРГАЛКА

```bash
# Розпакувати
python extract_all_client_data.py

# Або вручну:
7z x scripts.pkg -oextracted_data -y
7z x gui-part1.pkg -oextracted_gui -y

# Декодувати
cmd /c start /MIN /wait "" "tools\orion\PjOrion.exe" "--unpack-folder=extracted_data\common" "--exit"

# Згенерувати
python parse_game_entities.py
```