# PROJECT_PROGRESS.md - Прогрес проекту

## Версія: 1.00 (без PjOrion)

### Що зроблено

1. **Створено Python декодер для BigWorld XML**
   - Файл: `decode_xml.py`
   - Працює повністю на Python без зовнішніх програм
   - Підтримує всі типи даних: strings, integers, floats, booleans, blobs

2. **Оновлено всі основні скрипти проекту**
   - `parse_game_entities.py` - збір даних з клієнта
   - `extract_all_client_data.py` - екстракція .pkg файлів
   - `wot_decoder.py` - декодування XML
   - `tank_extractor.py` - екстрактор танкових даних

3. **Створено документацію**
   - `ORION_DECODER.md` - інструкція для PjOrion (резервний метод)
   - `PYTHON_DECODER.md` - повна інструкція Python декодера
   - `PROJECT_DOCUMENTATION.md` - повна документація проекту
   - `DECODER_XML.md` - оновлена інструкція декодування

### Як оновити дані після зміни версії гри

```bash
# 1. Розпакувати нові .pkg файли
python extract_all_client_data.py

# 2. Декодувати всі XML через Python
python -c "
from pathlib import Path
from decode_xml import WotXmlParser
d = WotXmlParser()
for f in Path('extracted_data').rglob('*.xml'):
    d.decode_file(str(f))
"

# 3. Зібрати дані
python parse_game_entities.py
```

### Структура проекту

```
├── decode_xml.py           # Python декодер (основний)
├── parse_game_entities.py  # Збір даних
├── extract_all_client_data.py  # Екстракція
├── wot_decoder.py          # Декодування XML
├── tank_extractor.py      # Екстрактор танків
├── tools/orion/            # PjOrion (резерв)
├── extracted_data/         # Дані клієнта
├── localization/           # Переклади (.mo)
└── documentation/          # Інструкції
```

### Технічні деталі

- **Формат даних**: BigWorld XML (заголовок `ENb`)
- **Python декодер**: повністю сумісний з форматом
- **.mo файли**: парсяться окремо (gettext format)

### Тестування

Всі основні модулі протестовані:
- ✅ decode_xml.py
- ✅ parse_game_entities.py
- ✅ extract_all_client_data.py
- ✅ wot_decoder.py
- ✅ tank_extractor.py
- ✅ parse_mo_localization.py