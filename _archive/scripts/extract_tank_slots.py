#!/usr/bin/env python3
"""
extract_tank_slots.py
Збирає інформацію по кожному танку:
- Кількість слотів обладнання
- Які типи обладнання можна встановлювати
- Слоти екіпажу (командир, навідник, мехвод, заряджаючий, радист)
- Польова модернізація
"""
import os
import json
import xml.etree.ElementTree as ET

BASE_DIR = os.getcwd()
EXTRACTED_DATA = os.path.join(BASE_DIR, "extracted_data")
OUTPUT_FILE = os.path.join(BASE_DIR, "tank_slots_db.json")

def parse_vehicle_xml(xml_path):
    """Парсить XML файли танка"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except:
        return None
    
    result = {
        "xml_path": xml_path,
        "equipment_slots": [],
        "crew_slots": [],
        "field_mods": [],
        "possible_equipment": [],
        "ammo_capacity": 0
    }
    
    # Знаходимо танк
    vehicle = root.find('.')
    if vehicle is None:
        return None
    
    # Equipment slots - шукаємо в vehicle/description
    # Зазвичай в XML є section "equipment" з типами
    
    # Crew slots
    crew = root.findall('.//crew')
    if crew:
        for c in crew:
            role = c.get('role', '')
            if role:
                result["crew_slots"].append(role)
    
    # Якщо немає crew в XML, дивимось в list.xml
    if not result["crew_slots"]:
        # Типові склади: HT, MT, LT, TD, SPG
        pass
    
    # Equipment - шукаємо optionalDevices
    opt_devices = root.findall('.//optionalDevice')
    if opt_devices:
        result["equipment_slots"] = [{} for _ in range(len(opt_devices))]
    
    # Field modifications - postProgression
    post_prog_path = xml_path.replace('\\', '/').replace('extracted_data/', '').replace('.xml', '')
    nation = post_prog_path.split('/')[0]
    
    # Шукаємо в post_progression
    post_prog_dir = os.path.join(EXTRACTED_DATA, "common", "post_progression", "field_modifications.xml")
    if os.path.exists(post_prog_dir):
        try:
            pt = ET.parse(post_prog_dir)
            proot = pt.getroot()
            # Тут будуть field mods для всіх танків
        except:
            pass
    
    return result

def collect_all_tanks():
    """Збирає всі танки з extracted_data"""
    tanks = {}
    
    nations = ['ussr', 'usa', 'germany', 'uk', 'france', 'china', 'japan', 'czech', 'poland', 'sweden', 'italy']
    
    for nation in nations:
        nation_dir = os.path.join(EXTRACTED_DATA, nation)
        if not os.path.exists(nation_dir):
            continue
            
        for root, dirs, files in os.walk(nation_dir):
            for f in files:
                if f.endswith('.xml') and f != 'list.xml' and f != 'customization.xml':
                    xml_path = os.path.join(root, f)
                    tank_data = parse_vehicle_xml(xml_path)
                    if tank_data:
                        tank_id = f.replace('.xml', '')
                        tanks[f"{nation}_{tank_id}"] = tank_data
    
    return tanks

def main():
    print("Collecting tank information...")
    
    # Спочатку подивимось на структуру одного танка
    sample_file = os.path.join(EXTRACTED_DATA, "ussr", "R01_IS.xml")
    
    if not os.path.exists(sample_file):
        print(f"Sample file not found: {sample_file}")
        return
    
    print(f"\n=== Analyzing {sample_file} ===")
    
    try:
        tree = ET.parse(sample_file)
        root = tree.getroot()
        
        print(f"Root tag: {root.tag}")
        
        # Знайти всі елементи
        all_elements = list(root.iter())
        print(f"Total elements: {len(all_elements)}")
        
        # Шукаємо ключові
        for elem in all_elements:
            tag = elem.tag.lower()
            if any(x in tag for x in ['equipment', 'crew', 'opt', 'slot', 'module']):
                print(f"  {elem.tag}: {elem.attrib}")
                
    except Exception as e:
        print(f"Error: {e}")
    
    # Збираємо всі танки
    print("\n=== Collecting all tanks ===")
    tanks = collect_all_tanks()
    print(f"Total tanks: {len(tanks)}")
    
    # Зберігаємо
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(tanks, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()