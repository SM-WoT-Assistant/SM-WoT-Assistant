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
    
    def parse_file(self, filepath, output_path):
        abs_path = os.path.abspath(filepath)
        if not os.path.exists(abs_path):
            print(f"Error: File {abs_path} not found.")
            return False
        
        with open(abs_path, 'rb') as f:
            self.data = f.read()
        
        if len(self.data) < 4 or self.data[:4] != b'\x45\x4e\xa1\x62':
            print("Error: File is not packed BigWorld XML.")
            return False
        
        self.offset = 5
        self.dictionary = []
        
        while True:
            s = self.read_string()
            if not s:
                break
            self.dictionary.append(s)
        
        root_name = os.path.basename(filepath).split('.')[0]
        xml_content = self.read_element(root_name, 0)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
            f.write(xml_content)
        
        print(f"Success: {output_path}")
        return True
    
    def read_element(self, name, depth):
        if self.offset >= len(self.data):
            return ""
        
        children_count = struct.unpack_from('<H', self.data, self.offset)[0]
        self.offset += 2
        descriptor = struct.unpack_from('<I', self.data, self.offset)[0]
        self.offset += 4
        
        children = []
        for _ in range(children_count):
            child_id = struct.unpack_from('<H', self.data, self.offset)[0]
            self.offset += 2
            data_desc = struct.unpack_from('<I', self.data, self.offset)[0]
            self.offset += 4
            children.append({'id': child_id, 'desc': data_desc})
        
        data_start = self.offset
        
        indent = "  " * depth
        result = f"{indent}<{name}>\n"
        
        for child in children:
            tag_name = self.dictionary[child['id']]
            end_address = child['desc'] & 0x0FFFFFFF
            data_type = child['desc'] >> 28
            
            child_end_offset = data_start + end_address
            length = child_end_offset - self.offset
            
            child_indent = "  " * (depth + 1)
            
            if data_type == 0:
                if length == 0:
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
    parser = WotXmlParser()
    parser.parse_file(r"test_data\encoded.xml", r"test_data\python_decoded.xml")