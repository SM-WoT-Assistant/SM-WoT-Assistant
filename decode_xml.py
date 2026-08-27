import os
import struct
import base64

# XML 1.0 забороняє контрольні символи 0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F.
# Декодер інколи емітує їх з бінарних значень (напр. 0x0B у <crystal>
# optional_devices.xml) — це ламало ET.parse (28.08.2026).
_XML_INVALID_CHARS = dict.fromkeys(list(range(0x00, 0x09)) + [0x0B, 0x0C] + list(range(0x0E, 0x20)))


def sanitize_xml_text(text):
    """Прибирає символи, невалідні в XML 1.0 (поза \t \n \r)."""
    return text.translate(_XML_INVALID_CHARS)


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
    
    def decode_file(self, input_path, output_path):
        if not os.path.exists(input_path):
            return False
        
        with open(input_path, 'rb') as f:
            self.data = f.read()
        
        if len(self.data) < 4 or self.data[:4] != b'\x45\x4e\xa1\x62':
            return True  # Already decoded
        
        self.offset = 5
        self.dictionary = []
        
        while True:
            s = self.read_string()
            if not s:
                break
            self.dictionary.append(s)
        
        root_name = os.path.basename(input_path).split('.')[0]
        xml_content = self.read_element(root_name, 0)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
            f.write(sanitize_xml_text(xml_content))
        
        return True
    
    def read_element(self, name, depth):
        if self.offset + 6 > len(self.data):
            return ""
        
        children_count = struct.unpack_from('<H', self.data, self.offset)[0]
        if children_count > 50000:
            return ""
        self.offset += 2
        descriptor = struct.unpack_from('<I', self.data, self.offset)[0]
        self.offset += 4
        
        children = []
        for _ in range(children_count):
            if self.offset + 6 > len(self.data):
                break
            child_id = struct.unpack_from('<H', self.data, self.offset)[0]
            self.offset += 2
            data_desc = struct.unpack_from('<I', self.data, self.offset)[0]
            self.offset += 4
            children.append({'id': child_id, 'desc': data_desc})
        
        data_start = self.offset
        
        indent = "  " * depth
        result = f"{indent}<{name}>\n"
        
        for child in children:
            if child['id'] >= len(self.dictionary):
                self.offset = data_start + (child['desc'] & 0x0FFFFFFF)
                continue
            
            tag_name = self.dictionary[child['id']]
            end_address = child['desc'] & 0x0FFFFFFF
            data_type = child['desc'] >> 28
            
            child_end_offset = data_start + end_address
            if child_end_offset > len(self.data):
                child_end_offset = len(self.data)
            if self.offset > child_end_offset:
                self.offset = child_end_offset
                continue
            
            length = child_end_offset - self.offset
            
            child_indent = "  " * (depth + 1)
            
            if data_type == 0:
                if length == 0:
                    result += f"{child_indent}<{tag_name}></{tag_name}>\n"
                else:
                    if self.offset >= len(self.data):
                        result += f"{child_indent}<{tag_name}></{tag_name}>\n"
                    else:
                        result += self.read_element(tag_name, depth + 1)
            else:
                val = ""
                if data_type == 1:
                    val = self.data[self.offset:child_end_offset].decode('utf-8', errors='ignore')
                elif data_type == 2:
                    if length == 1: val = struct.unpack_from('<b', self.data, self.offset)[0]
                    elif length == 2: val = struct.unpack_from('<h', self.data, self.offset)[0]
                    elif length == 4: val = struct.unpack_from('<i', self.data, self.offset)[0]
                    elif length == 8: val = struct.unpack_from('<q', self.data, self.offset)[0]
                    else: val = 0
                elif data_type == 3:
                    num_floats = length // 4
                    floats = struct.unpack_from(f'<{num_floats}f', self.data, self.offset)
                    val = " ".join(f"{f:.6g}" for f in floats)
                elif data_type == 4:
                    if length > 0:
                        val = "true" if struct.unpack_from('<b', self.data, self.offset)[0] else "false"
                    else:
                        val = "false"
                else:
                    val = base64.b64encode(self.data[self.offset:child_end_offset]).decode('utf-8')
                
                result += f"{child_indent}<{tag_name}>\t{val}\t</{tag_name}>\n"
            
            self.offset = child_end_offset
        
        result += f"{indent}</{name}>\n"
        return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        parser = WotXmlParser()
        parser.decode_file(sys.argv[1], sys.argv[2])
        print(f"Decoded: {sys.argv[2]}")