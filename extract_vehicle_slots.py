#!/usr/bin/env python3
"""
extract_vehicle_slots.py
Витягує слоти обладнання та екіпажу з vehicle XML в scripts.pkg
"""
import zipfile
import os
import json
import xml.etree.ElementTree as ET

SCRIPTS_PKG = r"C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg"

def decode_content(content):
    """Спробувати декодувати контент"""
    for enc in ['utf-8', 'cp1251', 'latin-1']:
        try:
            return content.decode(enc)
        except:
            continue
    return None

def parse_vehicle_xml(content):
    """Парсить XML танка"""
    xml_text = decode_content(content)
    if not xml_text or '<' not in xml_text[:100]:
        return None
    
    try:
        root = ET.fromstring(xml_text)
    except:
        return None
    
    result = {
        "equipment_slots": [],
        "crew_slots": [],
        "has_post_progression": False,
        "has_field_mods": False
    }
    
    # Equipment slots - дивимось в <optDevs>
    opt_devs = root.find('.//optDevs')
    if opt_devs is not None:
        for dev in opt_devs:
            slot_info = dev.attrib.copy()
            result["equipment_slots"].append(slot_info)
    
    # Якщо немає optDevs, шукаємо optionalDevice
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
    
    # Перевіряємо наявність postProgression
    if root.find('.//postProgressionTree') is not None:
        result["has_post_progression"] = True
    
    return result

def main():
    print("Extracting vehicle slots from scripts.pkg...")
    
    result = {}
    
    with zipfile.ZipFile(SCRIPTS_PKG, 'r') as zf:
        files = [f for f in zf.namelist() 
                 if 'item_defs/vehicles/' in f and f.endswith('.xml') 
                 and 'components' not in f and 'list.xml' not in f]
        
        print(f"Total vehicle files: {len(files)}")
        
        for i, fname in enumerate(files[:50]):  # Тест перші 50
            try:
                content = zf.read(fname)
                vehicle_data = parse_vehicle_xml(content)
                
                if vehicle_data and (vehicle_data["equipment_slots"] or vehicle_data["crew_slots"]):
                    tank_id = os.path.basename(fname).replace('.xml', '')
                    result[tank_id] = vehicle_data
                    
                    if i < 5:
                        print(f"  {tank_id}: equip={len(vehicle_data['equipment_slots'])}, crew={len(vehicle_data['crew_slots'])}")
                        
            except Exception as e:
                pass
                
            if (i + 1) % 20 == 0:
                print(f"Processed: {i+1}/{min(50, len(files))}")
    
    print(f"\nTotal parsed: {len(result)}")
    
    with open("vehicle_slots_test.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("Saved to vehicle_slots_test.json")

if __name__ == "__main__":
    main()