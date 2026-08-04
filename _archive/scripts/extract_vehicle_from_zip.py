#!/usr/bin/env python3
"""
extract_vehicle_data_from_zip.py
Працює напряму з scripts.pkg - не потрібно розпаковувати
"""
import zipfile
import os
import json
import xml.etree.ElementTree as ET

SCRIPTS_PKG = r"C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg"

def find_vehicle_xml_files():
    """Знаходить всі XML файли танків в архіві"""
    with zipfile.ZipFile(SCRIPTS_PKG, 'r') as zf:
        vehicles = [f for f in zf.namelist() 
                   if 'item_defs/vehicles/' in f and f.endswith('.xml') and 'components' not in f]
    
    print(f"Found {len(vehicles)} vehicle XML files")
    return vehicles

def parse_vehicle_from_zip(zf, filename):
    """Парсить XML танка напряму з архіву"""
    try:
        content = zf.read(filename)
        # Спробуємо декодувати
        try:
            xml_text = content.decode('utf-8')
        except:
            # Може бути закодовано - пробуємо інші кодування
            try:
                xml_text = content.decode('cp1251')
            except:
                return None
            
        # Перевіряємо чи це XML
        if not xml_text.strip().startswith('<'):
            return None
            
        root = ET.fromstring(xml_text)
        
        result = {
            "filename": filename,
            "nation": filename.split('/')[3] if len(filename.split('/')) > 3 else "unknown",
            "tank_id": os.path.basename(filename).replace('.xml', ''),
            "equipment_slots": [],
            "crew_slots": [],
            "has_post_progression": False,
        }
        
        # Equipment slots
        # Шукаємо <optionalDevice> або <devices>
        devices = root.findall('.//optionalDevice')
        if devices:
            result["equipment_slots"] = [{} for _ in devices]
        
        # Crew
        crew = root.findall('.//crew')
        roles = set()
        for c in crew:
            role = c.get('role', '')
            if role:
                roles.add(role)
        result["crew_slots"] = sorted(list(roles))
        
        # Check for postProgression
        if root.find('.//postProgression') is not None:
            result["has_post_progression"] = True
            
        return result
        
    except Exception as e:
        return None

def main():
    print("Extracting vehicle data from scripts.pkg...")
    
    with zipfile.ZipFile(SCRIPTS_PKG, 'r') as zf:
        vehicles = find_vehicle_xml_files()
        
        # Парсимо перші 5 для тесту
        results = []
        for i, v in enumerate(vehicles[:10]):
            print(f"Parsing {i+1}/10: {v}")
            data = parse_vehicle_from_zip(zf, v)
            if data:
                results.append(data)
                print(f"  Crew: {data.get('crew_slots', [])}")
                print(f"  Equipment slots: {len(data.get('equipment_slots', []))}")
        
        # Зберігаємо
        with open("vehicle_slots_test.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\nSaved {len(results)} vehicles to vehicle_slots_test.json")

if __name__ == "__main__":
    main()