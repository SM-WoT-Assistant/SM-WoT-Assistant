# DECODER_XML.md - Декодування XML файлів WoT клієнта

## ШВИДКА ШПАРГАЛКА

### Python декодер (РЕКОМЕНДОВАНО)

```bash
python decode_xml.py extracted_data/common/equipments-1.xml
```

### PjOrion (резервний)

```powershell
$proc = Start-Process -FilePath "tools\orion\PjOrion.exe" -ArgumentList "--unpack-file=""ШЛЯХ""" -PassThru -WindowStyle Hidden
Start-Sleep 10
if (!$proc.HasExited) { Stop-Process $proc.Id -Force }
```

---

## ПОВНА ІНСТРУКЦІЯ

### Розпакування .pkg файлів

```python
import zipfile
with zipfile.ZipFile('scripts.pkg', 'r') as z:
    z.extractall('extracted_data')
```

### Перевірка чи файл закодований

```python
with open('file.xml', 'rb') as f:
    first = f.read(4)
# Закодований: ENb (перші байти 69, 78, 161, 98)
# Розкодований: < (перший байт 60)
```

### Python декодер

Див. файл `decode_xml.py` або `PYTHON_DECODER.md`

### PjOrion

Див. файл `ORION_DECODER.md`

---

## ОПЦІЇ PJORION

```
--unpack-file=<file>     Один файл
--unpack-folder=<path>   Папка
--exit                   Вихід після завершення
```

## ТИПИ ДАНИХ У BIGWORLD XML

| Тип | Код | Опис |
|-----|-----|------|
| Element | 0 | Вкладений вузол |
| String | 1 | Текст |
| Integer | 2 | Число |
| Float | 3 | Дробове |
| Boolean | 4 | true/false |
| Blob | 5+ | base64