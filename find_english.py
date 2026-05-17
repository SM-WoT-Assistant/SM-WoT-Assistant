import struct
import os
import json

def find_english_in_mo(mo_path, search_terms):
    """Find search terms in MO file and return translations"""
    results = {}
    
    with open(mo_path, 'rb') as f:
        magic = struct.unpack('<I', f.read(4))[0]
        if magic not in (0x950412de, 0x412de950):
            return {}
            
        f.seek(8)
        nstrings = struct.unpack('<I', f.read(4))[0]
        orig_tab = struct.unpack('<I', f.read(4))[0]
        trans_tab = struct.unpack('<I', f.read(4))[0]
        
        orig_data = []
        f.seek(orig_tab)
        for _ in range(nstrings):
            l = struct.unpack('<I', f.read(4))[0]
            o = struct.unpack('<I', f.read(4))[0]
            orig_data.append((l, o))
        
        trans_data = []
        f.seek(trans_tab)
        for _ in range(nstrings):
            l = struct.unpack('<I', f.read(4))[0]
            o = struct.unpack('<I', f.read(4))[0]
            trans_data.append((l, o))
        
        for search in search_terms:
            search_lower = search.lower()
            for i, (ol, oo) in enumerate(orig_data):
                if i >= len(trans_data):
                    break
                tl, to = trans_data[i]
                if ol == 0 or tl == 0:
                    continue
                    
                f.seek(oo)
                key = f.read(ol).decode('utf-8', errors='ignore').lower()
                
                if search_lower in key:
                    f.seek(to)
                    val = f.read(tl).decode('cp1251', errors='ignore')
                    
                    f.seek(oo)
                    key_orig = f.read(ol).decode('utf-8', errors='ignore')
                    
                    results[key_orig] = val
                    
        return results

# Search for specific terms
terms = [
    'handExtinguishers', 'rammer', 'ventilation', 'optics',
    'smallRepairkit', 'largeRepairkit', 'smallMedkit',
    'coatedOptics', 'turbocharger', 'stabilizer'
]

mo_path = r"C:\Games\World_of_Tanks_EU\res\text\lc_messages\artefacts.mo"

print("Searching artefacts.mo for English terms...")
results = find_english_in_mo(mo_path, terms)

for key, val in results.items():
    print(f"{key} = {val}")

# Save results
output_path = os.path.join(os.getcwd(), "localization", "english_search.json")
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nSaved to {output_path}")