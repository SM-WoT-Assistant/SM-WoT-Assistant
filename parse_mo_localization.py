#!/usr/bin/env python3
"""
parse_mo_localization.py
Читає .mo файли локалізації WoT та створює маппінг ключ → назва
"""
import os
import struct

class MOParser:
    """Простий парсер .mo файлів (gettext binary)"""
    
    def __init__(self, mo_path):
        self.mo_path = mo_path
        self.translations = {}
        
    def parse(self):
        with open(self.mo_path, 'rb') as f:
            # Читаємо заголовок MO файлу
            magic = struct.unpack('<I', f.read(4))[0]
            
            # Перевіряємо формат (little-endian)
            if magic == 0x950412de:
                is_le = True
            elif magic == 0x412de950:
                is_le = False
            else:
                print(f"Invalid MO file: {self.mo_path}")
                return
            
            # Читаємо кількість рядків
            f.seek(8)
            nstrings = struct.unpack('<I', f.read(4))[0]
            orig_tab_offset = struct.unpack('<I', f.read(4))[0]
            trans_tab_offset = struct.unpack('<I', f.read(4))[0]
            
            # Читаємо таблиці
            f.seek(orig_tab_offset)
            orig_lengths = []
            orig_offsets = []
            for _ in range(nstrings):
                length = struct.unpack('<I', f.read(4))[0]
                offset = struct.unpack('<I', f.read(4))[0]
                orig_lengths.append(length)
                orig_offsets.append(offset)
            
            f.seek(trans_tab_offset)
            trans_lengths = []
            trans_offsets = []
            for _ in range(nstrings):
                length = struct.unpack('<I', f.read(4))[0]
                offset = struct.unpack('<I', f.read(4))[0]
                trans_lengths.append(length)
                trans_offsets.append(offset)
            
            # Читаємо переклади
            for i in range(nstrings):
                if trans_lengths[i] == 0:
                    continue
                    
                f.seek(trans_offsets[i])
                trans = f.read(trans_lengths[i])
                
                f.seek(orig_offsets[i])
                orig = f.read(orig_lengths[i])
                
                try:
                    orig_str = orig.decode('utf-8')
                    trans_str = trans.decode('utf-8')
                    self.translations[orig_str] = trans_str
                except:
                    pass
        
        return self.translations
    
    def get(self, key, default=None):
        return self.translations.get(key, default)

def main():
    base_path = r"C:\Games\World_of_Tanks_EU\res\text\lc_messages"
    output_dir = os.path.join(os.getcwd(), "localization")
    os.makedirs(output_dir, exist_ok=True)
    
    files_to_parse = {
        "artefacts": "artefacts.mo",
        "crew_perks": "crew_perks.mo", 
        "item_types": "item_types.mo"
    }
    
    all_translations = {}
    
    for name, filename in files_to_parse.items():
        mo_path = os.path.join(base_path, filename)
        
        if not os.path.exists(mo_path):
            print(f"NOT FOUND: {mo_path}")
            continue
            
        print(f"\nParsing {filename}...")
        parser = MOParser(mo_path)
        translations = parser.parse()
        
        print(f"  Found {len(translations)} translations")
        
        # Зберігаємо окремо
        out_file = os.path.join(output_dir, f"{name}_translations.json")
        with open(out_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(translations, f, ensure_ascii=False, indent=2)
        
        all_translations[name] = translations
    
    # Зберігаємо все разом
    all_file = os.path.join(output_dir, "all_translations.json")
    with open(all_file, 'w', encoding='utf-8') as f:
        import json
        json.dump(all_translations, f, ensure_ascii=False, indent=2)
    
    print(f"\nDONE! Saved to {output_dir}")

if __name__ == "__main__":
    main()