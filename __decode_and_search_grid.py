import os, sys, struct, base64

PROJECT = r"D:\!WORK\WOT\WOTtraner\WORK\SETUP S MAPS WoT Assistant_1.00"

class WotXmlParser:
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
        if not os.path.exists(input_path):
            return None
        with open(input_path, 'rb') as f:
            self.data = f.read()
        if len(self.data) < 4 or self.data[:4] != b'\x45\x4e\xa1\x62':
            try:
                return self.data.decode('utf-8', errors='replace')
            except:
                return None
        self.offset = 5
        self.dictionary = []
        while True:
            s = self.read_string()
            if not s:
                break
            self.dictionary.append(s)
        root_name = os.path.basename(input_path).split('.')[0]
        xml_content = self.read_element(root_name, 0)
        return "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" + xml_content
    
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
        self.all_tags.add(name)
        for child in children:
            tag_name = self.dictionary[child['id']]
            end_address = child['desc'] & 0x0FFFFFFF
            data_type = child['desc'] >> 28
            child_end_offset = data_start + end_address
            length = child_end_offset - self.offset
            child_indent = "  " * (depth + 1)
            self.all_tags.add(tag_name)
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


def search_in_xml(xml_text, filename):
    patterns = ['grid', 'Grid', 'GRID', 'division', 'Division', 'cell', 'Cell', 'square', 'Square', 'sector', 'Sector', 'coord', 'Coord', 'COORD', 'label', 'Label', 'minimap', 'Minimap', 'MiniMap', 'numColumns', 'numRows', 'column', 'Column', 'row', 'Row', 'letter', 'Letter', 'size', 'Size', 'segments', 'Segments', 'border', 'Border', 'outline', 'Outline', 'marker', 'Marker', 'bound', 'Bound', 'bbox', 'BBox', 'area', 'Area', 'mapSize', 'arenaSize', 'resolution', 'Resolution', 'subdivision', 'Subdivision', 'tile', 'Tile']
    found = []
    for i, line in enumerate(xml_text.splitlines(), 1):
        line_lower = line.lower()
        for pat in patterns:
            if pat.lower() in line_lower:
                found.append((filename, i, line.strip()))
                break
    return found


def main():
    parser = WotXmlParser()
    output_dir = os.path.join(PROJECT, "_decoded_search")
    os.makedirs(output_dir, exist_ok=True)
    all_findings = []
    all_tags = set()
    
    # 1. Decode all arena_defs
    arena_dir = os.path.join(PROJECT, "temp_scripts2", "scripts", "arena_defs")
    arena_files = sorted([f for f in os.listdir(arena_dir) if f.endswith('.xml')])
    print("=" * 80)
    print("DECODING ARENA DEFS XML FILES")
    print("=" * 80)
    for fname in arena_files:
        fpath = os.path.join(arena_dir, fname)
        try:
            xml_text = parser.decode_file(fpath)
            if xml_text:
                outpath = os.path.join(output_dir, f"decoded_{fname}")
                with open(outpath, 'w', encoding='utf-8') as f:
                    f.write(xml_text)
                all_tags.update(parser.all_tags)
                parser.all_tags = set()
                finds = search_in_xml(xml_text, fname)
                if finds:
                    all_findings.extend(finds)
                    for _, lineno, line in finds:
                        print(f"  >> [{fname}:{lineno}] {line[:200]}")
            else:
                print(f"  FAILED: {fname}")
        except Exception as e:
            print(f"  ERROR {fname}: {e}")
        else:
            if not finds:
                print(f"  (no grid-related patterns in {fname})")
    
    # 2. Decode command_mapping.xml
    print("\n" + "=" * 80)
    print("DECODING command_mapping.xml")
    print("=" * 80)
    cmd_path = os.path.join(PROJECT, "temp_scripts2", "scripts", "command_mapping.xml")
    try:
        xml_text = parser.decode_file(cmd_path)
        if xml_text:
            outpath = os.path.join(output_dir, "decoded_command_mapping.xml")
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(xml_text)
            finds = search_in_xml(xml_text, "command_mapping.xml")
            all_findings.extend(finds)
            for _, lineno, line in finds:
                print(f"  >> [command_mapping.xml:{lineno}] {line[:200]}")
            all_tags.update(parser.all_tags)
            parser.all_tags = set()
            if not finds:
                print("  (no grid-related patterns found)")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # 3. Decode maps_training_tactical_maps.xml
    print("\n" + "=" * 80)
    print("DECODING maps_training_tactical_maps.xml")
    print("=" * 80)
    train_path = os.path.join(PROJECT, "temp_scripts2", "scripts", "maps_training_tactical_maps.xml")
    try:
        xml_text = parser.decode_file(train_path)
        if xml_text:
            outpath = os.path.join(output_dir, "decoded_maps_training_tactical_maps.xml")
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(xml_text)
            finds = search_in_xml(xml_text, "maps_training_tactical_maps.xml")
            all_findings.extend(finds)
            for _, lineno, line in finds:
                print(f"  >> [maps_training_tactical_maps.xml:{lineno}] {line[:200]}")
            all_tags.update(parser.all_tags)
            parser.all_tags = set()
            if not finds:
                print("  (no grid-related patterns found)")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # 4. Decode PveMinimapController.def
    print("\n" + "=" * 80)
    print("DECODING PveMinimapController.def")
    print("=" * 80)
    pve_path = os.path.join(PROJECT, "temp_scripts2", "scripts", "component_defs", "PveMinimapController.def")
    try:
        xml_text = parser.decode_file(pve_path)
        if xml_text:
            outpath = os.path.join(output_dir, "decoded_PveMinimapController.def.xml")
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(xml_text)
            finds = search_in_xml(xml_text, "PveMinimapController.def")
            all_findings.extend(finds)
            for _, lineno, line in finds:
                print(f"  >> [PveMinimapController.def:{lineno}] {line[:200]}")
            all_tags.update(parser.all_tags)
            parser.all_tags = set()
            if not finds:
                print("  (no grid-related patterns found)")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # 5. Search ALL .def files for minimap/grid references
    print("\n" + "=" * 80)
    print("SEARCHING ALL .def FILES FOR MINIMAP/GRID REFERENCES")
    print("=" * 80)
    comp_defs_dir = os.path.join(PROJECT, "temp_scripts2", "scripts", "component_defs")
    for fname in sorted(os.listdir(comp_defs_dir)):
        if not fname.lower().endswith('.def'):
            continue
        fpath = os.path.join(comp_defs_dir, fname)
        with open(fpath, 'rb') as f:
            content = f.read()
        for pattern in [b'minimap', b'Minimap', b'MINIMAP', b'grid', b'Grid', b'GRID']:
            if pattern in content:
                print(f"\n  *** BINARY MATCH '{pattern.decode()}' in: {fname}")
                try:
                    parser2 = WotXmlParser()
                    xml_text = parser2.decode_file(fpath)
                    if xml_text:
                        outpath = os.path.join(output_dir, f"decoded_{fname}.xml")
                        with open(outpath, 'w', encoding='utf-8') as f:
                            f.write(xml_text)
                        print(f"    Decoded. Searching...")
                        finds = search_in_xml(xml_text, fname)
                        all_findings.extend(finds)
                        for _, lineno, line in finds:
                            print(f"    >> [{fname}:{lineno}] {line[:200]}")
                        all_tags.update(parser2.all_tags)
                except Exception as e:
                    print(f"    ERROR: {e}")
                break
    
    # 6. Decode spaces.xml
    print("\n" + "=" * 80)
    print("DECODING spaces.xml")
    print("=" * 80)
    spaces_path = os.path.join(PROJECT, "temp_scripts2", "scripts", "spaces.xml")
    try:
        xml_text = parser.decode_file(spaces_path)
        if xml_text:
            outpath = os.path.join(output_dir, "decoded_spaces.xml")
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(xml_text)
            finds = search_in_xml(xml_text, "spaces.xml")
            all_findings.extend(finds)
            for _, lineno, line in finds:
                print(f"  >> [spaces.xml:{lineno}] {line[:200]}")
            all_tags.update(parser.all_tags)
            parser.all_tags = set()
            if not finds:
                print("  (no grid-related patterns found)")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # 7. Decode entities.xml (might have grid/minimap entities)
    print("\n" + "=" * 80)
    print("DECODING entities.xml")
    print("=" * 80)
    entities_path = os.path.join(PROJECT, "temp_scripts2", "scripts", "entities.xml")
    try:
        xml_text = parser.decode_file(entities_path)
        if xml_text:
            outpath = os.path.join(output_dir, "decoded_entities.xml")
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(xml_text)
            finds = search_in_xml(xml_text, "entities.xml")
            all_findings.extend(finds)
            for _, lineno, line in finds:
                print(f"  >> [entities.xml:{lineno}] {line[:200]}")
            all_tags.update(parser.all_tags)
            parser.all_tags = set()
            if not finds:
                print("  (no grid-related patterns found)")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # 8. Decode components.xml
    print("\n" + "=" * 80)
    print("DECODING components.xml")
    print("=" * 80)
    comp_path = os.path.join(PROJECT, "temp_scripts2", "scripts", "components.xml")
    try:
        xml_text = parser.decode_file(comp_path)
        if xml_text:
            outpath = os.path.join(output_dir, "decoded_components.xml")
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(xml_text)
            finds = search_in_xml(xml_text, "components.xml")
            all_findings.extend(finds)
            for _, lineno, line in finds:
                print(f"  >> [components.xml:{lineno}] {line[:200]}")
            all_tags.update(parser.all_tags)
            parser.all_tags = set()
            if not finds:
                print("  (no grid-related patterns found)")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # === SUMMARY ===
    print("\n" + "=" * 80)
    print(f"SUMMARY: {len(all_findings)} total findings")
    print("=" * 80)
    for fname, lineno, line in all_findings:
        print(f"  [{fname}:{lineno}] {line[:250]}")
    
    print("\n" + "=" * 80)
    print(f"ALL UNIQUE XML TAGS ({len(all_tags)} total)")
    print("=" * 80)
    for tag in sorted(all_tags):
        print(f"  {tag}")
    
    print(f"\nDecoded files saved to: {output_dir}")


if __name__ == "__main__":
    main()
