# PYTHON_DECODER.md - Як декодувати XML без PjOrion (Pure Python)

## ПОВНИЙ КОД ДЕКОДЕРА

Зберегти як `decode_xml.py`:

```python
import os
import struct
import base64

class WotXmlParser:
    def __init__(self):
        self.dictionary = []
        self.data = b''
        self.offset = 0
    
    def read_string(self):
        start = self.offset
        while self.offset < len(self.data) and self.data[self.offset] != 0:
            self.offset += 1
        s = self.data[start:self.offset].decode('utf-8', errors='ignore')
        self.offset += 1
        return s
    
    def decode_file(self, input_path, output_path=None):
        if output_path is None:
            output_path = input_path
        
        if not os.path.exists(input_path):
            return False
        
        with open(input_path, 'rb') as f:
            self.data = f.read()
        
        # Перевірка магічного заголовка BigWorld: ENb
        if len(self.data) < 4 or self.data[:4] != b'\x45\x4e\xa1\x62':
            return True  # Вже розкодований
        
        self.offset = 5
        self.dictionary = []
        
        # Читаємо словник тегів
        while True:
            s = self.read_string()
            if not s:
                break
            self.dictionary.append(s)
        
        root_name = os.path.basename(input_path).split('.')[0]
        xml_content = self._read_element(root_name, 0)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
            f.write(xml_content)
        
        return True
    
    def _read_element(self, name, depth):
        if self.offset >= len(self.data):
            return ""
        
        # Заголовок елемента: 2 байти (children count) + 4 байти (descriptor)
        children_count = struct.unpack_from('<H', self.data, self.offset)[0]
        self.offset += 2
        struct.unpack_from('<I', self.data, self.offset)[0]  # descriptor (не використовується)
        self.offset += 4
        
        # Читаємо дескриптори всіх дітей
        children = []
        for _ in range(children_count):
            child_id = struct.unpack_from('<H', self.data, self.offset)[0]
            self.offset += 2
            data_desc = struct.unpack_from('<I', self.data, self.offset)[0]
            self.offset += 4
            children.append({'id': child_id, 'desc': data_desc})
        
        # Дані починаються після всіх дескрипторів
        data_start = self.offset
        
        result = f"{'  ' * depth}<{name}>\n"
        
        for child in children:
            tag_name = self.dictionary[child['id']]
            end_address = child['desc'] & 0x0FFFFFFF  # 28 біт - адреса
            data_type = child['desc'] >> 28            # 4 біти - тип даних
            
            child_end_offset = data_start + end_address
            length = child_end_offset - self.offset
            
            if data_type == 0:  # Element (вкладений вузол)
                if length == 0:
                    result += f"{'  ' * (depth+1)}<{tag_name}></{tag_name}>\n"
                else:
                    result += self._read_element(tag_name, depth + 1)
            else:  # Прості типи даних
                val = ""
                if data_type == 1:  # String
                    val = self.data[self.offset:child_end_offset].decode('utf-8', errors='ignore')
                elif data_type == 2:  # Integer
                    if length == 1: val = struct.unpack_from('<b', self.data, self.offset)[0]
                    elif length == 2: val = struct.unpack_from('<h', self.data, self.offset)[0]
                    elif length == 4: val = struct.unpack_from('<i', self.data, self.offset)[0]
                    elif length == 8: val = struct.unpack_from('<q', self.data, self.offset)[0]
                    else: val = 0
                elif data_type == 3:  # Float / Vector
                    num_floats = length // 4
                    floats = struct.unpack_from(f'<{num_floats}f', self.data, self.offset)
                    val = " ".join(f"{f:.6g}" for f in floats)
                elif data_type == 4:  # Boolean
                    val = "true" if (length > 0 and struct.unpack_from('<b', self.data, self.offset)[0]) else "false"
                else:  # Base64 Blob
                    val = base64.b64encode(self.data[self.offset:child_end_offset]).decode('utf-8')
                
                result += f"{'  ' * (depth+1)}<{tag_name}>\t{val}\t</{tag_name}>\n"
            
            # Синхронізуємо зміщення
            self.offset = child_end_offset
        
        result += f"{'  ' * depth}</{name}>\n"
        return result


if __name__ == "__main__":
    import sys
    parser = WotXmlParser()
    if len(sys.argv) >= 2:
        parser.decode_file(sys.argv[1])
        print(f"Decoded: {sys.argv[1]}")
```

## Використання

```bash
python decode_xml.py extracted_data/common/equipments-1.xml
```

## Типи даних у дескрипторі

| Тип | Значення | Опис |
|-----|----------|------|
| Element | 0 | Вкладений XML елемент |
| String | 1 | Текстовий рядок |
| Integer | 2 | Ціле число (1/2/4/8 байт) |
| Float | 3 | Число з плаваючою крапкою |
| Boolean | 4 | Логічне значення (true/false) |
| Blob | 5+ | Двійкові дані (base64) |

## Структура файлу

```
[Заголовок: 4 байта "ENb" + 1 байт прапорця]
[Словник тегів: null-terminated рядки]
[Бінарне дерево даних]
```

## Перевірка працездатності

```python
# Тестовий файл
python -c "
from decode_xml import WotXmlParser
p = WotXmlParser()
p.decode_file('test.xml', 'test_decoded.xml')
# Порівняти з результатом через PjOrion
"