#!/usr/bin/env python3
"""
parse_mo_localization.py - with encoding support
"""
import os
import struct
import codecs

class MOParser:
    def __init__(self, mo_path):
        self.mo_path = mo_path
        self.translations = {}
        
    def parse(self, encoding='utf-8'):
        with open(self.mo_path, 'rb') as f:
            magic = struct.unpack('<I', f.read(4))[0]
            if magic == 0x950412de:
                is_le = True
            elif magic == 0x412de950:
                is_le = False
            else:
                return {}
                
            f.seek(8)
            nstrings = struct.unpack('<I', f.read(4))[0]
            orig_tab_offset = struct.unpack('<I', f.read(4))[0]
            trans_tab_offset = struct.unpack('<I', f.read(4))[0]
            
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
            
            for i in range(nstrings):
                if trans_lengths[i] == 0:
                    continue
                    
                f.seek(trans_offsets[i])
                trans = f.read(trans_lengths[i])
                
                f.seek(orig_offsets[i])
                orig = f.read(orig_lengths[i])
                
                try:
                    orig_str = orig.decode('utf-8')
                    trans_str = trans.decode(encoding, errors='ignore')
                    if trans_str.strip():
                        self.translations[orig_str] = trans_str
                except:
                    pass
        
        return self.translations

def test_encodings():
    base_path = r"C:\Games\World_of_Tanks_EU\res\text\lc_messages"
    mo_path = os.path.join(base_path, "artefacts.mo")
    
    encodings = ['utf-8', 'cp1251', 'latin-1', 'iso-8859-1', 'cp1252']
    
    for enc in encodings:
        print(f"\n=== Testing {enc} ===")
        parser = MOParser(mo_path)
        t = parser.parse(enc)
        
        # Шукаємо handExtinguishers
        for k, v in t.items():
            if 'handExtinguishers' in k and 'name' in k:
                print(f"  {k} = {v}")

if __name__ == "__main__":
    test_encodings()