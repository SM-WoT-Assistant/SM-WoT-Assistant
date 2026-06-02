import os, sys, struct, base64

PROJECT = r"D:\!WORK\WOT\WOTtraner\WORK\SETUP S MAPS WoT Assistant_1.00"

class WP:
    def __init__(self):
        self.dictionary = []
        self.data = b''
        self.offset = 0
        self.all_tags = set()
    def read_string(self):
        start = self.offset
        while self.offset < len(self.data) and self.data[self.offset] != 0:
            self.offset += 1
        s = self.data[start:self.offset].decode('utf-8', errors='ignore')
        self.offset += 1
        return s
    def decode_file(self, input_path):
        if not os.path.exists(input_path): return None
        with open(input_path, 'rb') as f:
            self.data = f.read()
        if len(self.data) < 4 or self.data[:4] != b'\x45\x4e\xa1\x62':
            try: return self.data.decode('utf-8', errors='replace')
            except: return None
        self.offset = 5
        self.dictionary = []
        while True:
            s = self.read_string()
            if not s: break
            self.dictionary.append(s)
        root_name = os.path.basename(input_path).split('.')[0]
        xml = '<?xml version="1.0" encoding="utf-8"?>\n'
        xml += self.read_element(root_name, 0)
        return xml
    def read_element(self, name, depth):
        if self.offset >= len(self.data): return ''
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
        indent = '  ' * depth
        result = indent + '<' + name + '>\n'
        self.all_tags.add(name)
        for child in children:
            tag_name = self.dictionary[child['id']]
            end_address = child['desc'] & 0x0FFFFFFF
            data_type = child['desc'] >> 28
            child_end_offset = data_start + end_address
            length = child_end_offset - self.offset
            child_indent = '  ' * (depth + 1)
            self.all_tags.add(tag_name)
            if data_type == 0:
                if length == 0: result += child_indent + '<' + tag_name + '></' + tag_name + '>\n'
                else: result += self.read_element(tag_name, depth + 1)
            else:
                val = ''
                if data_type == 1: val = self.data[self.offset:child_end_offset].decode('utf-8', errors='ignore')
                elif data_type == 2:
                    if length == 1: val = struct.unpack_from('<b', self.data, self.offset)[0]
                    elif length == 2: val = struct.unpack_from('<h', self.data, self.offset)[0]
                    elif length == 4: val = struct.unpack_from('<i', self.data, self.offset)[0]
                    elif length == 8: val = struct.unpack_from('<q', self.data, self.offset)[0]
                    else: val = 0
                elif data_type == 3:
                    num_floats = length // 4
                    floats = struct.unpack_from('<' + str(num_floats) + 'f', self.data, self.offset)
                    val = ' '.join(f'{f:.6g}' for f in floats)
                elif data_type == 4:
                    val = 'true' if length > 0 and struct.unpack_from('<b', self.data, self.offset)[0] else 'false'
                else:
                    val = base64.b64encode(self.data[self.offset:child_end_offset]).decode('utf-8')
                result += child_indent + '<' + tag_name + '>' + '\t' + str(val) + '\t</' + tag_name + '>\n'
            self.offset = child_end_offset
        result += indent + '</' + name + '>\n'
        return result

output_dir = os.path.join(PROJECT, '_decoded_search')

files_to_check = [
    ('DeathZoneAreaTriggerMask.def', os.path.join(PROJECT, 'temp_scripts2', 'scripts', 'user_data_object_defs', 'DeathZoneAreaTriggerMask.def')),
    ('PolygonalAreaTriggerUDO.def', os.path.join(PROJECT, 'temp_scripts2', 'scripts', 'user_data_object_defs', 'PolygonalAreaTriggerUDO.def')),
    ('PolygonalDeathZoneAreaTrigger.def', os.path.join(PROJECT, 'temp_scripts2', 'scripts', 'user_data_object_defs', 'PolygonalDeathZoneAreaTrigger.def')),
]
patterns = ['grid', 'Grid', 'GRID', 'minimap', 'Minimap', 'cell', 'Cell', 'coord', 'Coord', 'border', 'Border', 'bound', 'Bound', 'marker', 'Marker', 'label', 'Label']

for fname, fpath in files_to_check:
    print()
    print('=== ' + fname + ' ===')
    try:
        p = WP()
        xml = p.decode_file(fpath)
        if xml:
            outpath = os.path.join(output_dir, 'decoded_' + fname + '.xml')
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(xml)
            print('  All tags: ' + str(sorted(p.all_tags)))
            found = False
            for i, line in enumerate(xml.splitlines(), 1):
                for pat in patterns:
                    if pat.lower() in line.lower():
                        print('  [' + str(i) + '] ' + line.strip()[:200])
                        found = True
                        break
            if not found:
                print('  No grid/minimap related content')
        else:
            print('  Could not decode')
    except Exception as e:
        print('  ERROR: ' + str(e))

ts2 = os.path.join(PROJECT, 'temp_scripts2')
specific_terms = [
    b'minimapGrid', b'gridSize', b'GridSize', b'numColumns', b'numRows',
    b'MINIMAP_GRID', b'grid_cols', b'grid_rows', b'gridColumns', b'gridRows',
    b'gridCell', b'GridCell', b'highlightCell', b'HighlightCell',
    b'MINIMAP_CELL', b'minimap_cell'
]
print()
print('=== Searching for grid definition terms in ALL temp_scripts2 files ===')
for root, dirs, files in os.walk(ts2):
    for f in files:
        fp = os.path.join(root, f)
        try:
            with open(fp, 'rb') as fh:
                data = fh.read()
            for term in specific_terms:
                if term in data:
                    print('  FOUND ' + term.decode() + ' in ' + fp)
        except:
            pass
print('  Search complete.')
