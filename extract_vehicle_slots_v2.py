#!/usr/bin/env python3
"""
extract_vehicle_slots_v2.py
Витягує слоти з vehicle XML - з очищенням формату
"""
import zipfile
import os
import json
import re
import xml.etree.ElementTree as ET

SCRIPTS_PKG = r"C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg"

def clean_xml(content):
    """Очищує закодований XML контент"""
    content = content.strip()
    content = re.sub(r'^<[^>]+>', '<root>', content, count=1)
    content = re.sub(r'</[^>]+>\s*$', '</root>', content)
    content = re.sub(r'\s*<xmlns:[^>]+>[^<]*</xmlns:[^>]+>', '', content)
    content = re.sub(r'\s*xmlns:[a-zA-Z0-9_]+="[^"]*"', '', content)
    content = re.sub(r'\s+xmlns="[^"]*"', '', content)
    return content

def parse_xml_root_safe(content):
    """Парсить XML з очищенням"""
    content = (content or "").strip()
    if not content:
        return None
    if '<' not in content[:100]:
        return None
    candidates = [
        content,
        clean_xml(content),
        re.sub(r'<\?xml[^>]*\?>', '', content).strip(),
    ]
    for cand in candidates:
        try:
            return ET.fromstring(cand)
        except Exception:
            continue
    return None

def parse_vehicle_xml(content_bytes):
    """Парсить XML танка з bytes"""
    try:
        content = content_bytes.decode('utf-8', errors='ignore')
    except:
        try:
            content = content_bytes.decode('cp1251', errors='ignore')
        except:
            return None
    
    root = parse_xml_root_safe(content)
    if root is None:
        return None
    
    result = {
        "equipment_slots": [],
        "crew_slots": [],
        "has_post_progression": False
    }
    
    # Equipment slots
    opt_devs = root.find('.//optDevs')
    if opt_devs is not None:
        for dev in opt_devs:
            result["equipment_slots"].append(dev.attrib)
    
    if not result["equipment_slots"]:
        opt_devices = root.findall('.//optionalDevice')
        for i, _ in enumerate(opt_devices):
            result["equipment_slots"].append({"slot": i})
    
    # Crew slots
    crew = root.findall('.//crew')
    for c in crew:
        role = c.get('role', '')
        if role:
            result["crew_slots"].append(role)
    
    # Post progression
    if root.find('.//postProgressionTree') is not None:
        result["has_post_progression"] = True
    
    return result

def main():
    print("Extracting vehicle slots (v2)...")
    
    result = {}
    
    with zipfile.ZipFile(SCRIPTS_PKG, 'r') as zf:
        files = [f for f in zf.namelist() 
                 if 'item_defs/vehicles/' in f and f.endswith('.xml') 
                 and 'components' not in f and 'list.xml' not in f]
        
        print(f"Total: {len(files)}")
        
        # Тест на перших 20 файлах
        for i, fname in enumerate(files[:20]):
            try:
                content = zf.read(fname)
                
                # Перевіримо перші байти
                first_bytes = content[:20]
                has_xml_marker = b'<' in first_bytes
                
                vehicle_data = parse_vehicle_xml(content)
                
                if vehicle_data:
                    tank_id = os.path.basename(fname).replace('.xml', '')
                    result[tank_id] = vehicle_data
                    print(f"  {tank_id}: equip={len(vehicle_data['equipment_slots'])}, crew={len(vehicle_data['crew_slots'])}")
                elif i < 5:
                    print(f"  {fname}: XML parse failed, has '<': {has_xml_marker}")
                    
            except Exception as e:
                if i < 3:
                    print(f"  Error {fname}: {e}")
    
    print(f"\nParsed: {len(result)}")
    
    with open("vehicle_slots_v2.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("Saved to vehicle_slots_v2.json")

if __name__ == "__main__":
    main()