#!/usr/bin/env python3
"""
extract_slots_from_decoded.py
"""
import os
import xml.etree.ElementTree as ET
import json

BASE = r"D:\!WORK\WOT\WOTtraner\WORK\WoT_Assistant_4.0\tmp\tth_work"

def parse_vehicle(xml_path):
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        root = ET.fromstring(content)
    except:
        return None
    
    result = {
        "crew_slots": [],
        "equipment_slot_count": 0,
        "has_post_progression": False,
        "supply_slots": []
    }
    
    # Crew slots
    crew_elem = root.find('.//crew')
    if crew_elem is not None:
        for child in crew_elem:
            result["crew_slots"].append(child.tag)
    
    # Equipment slots - from supplySlots
    supply = root.find('.//supplySlots')
    if supply is not None and supply.text:
        slots = supply.text.strip().split()
        result["supply_slots"] = slots
        # Count equipment slots (typically 1 = equipment, 6-8 = consumables)
        result["equipment_slot_count"] = slots.count('1')
    
    # Post progression
    if root.find('.//postProgressionTree') is not None:
        result["has_post_progression"] = True
    
    return result

# Parse all vehicles
all_tanks = {}
for root, dirs, files in os.walk(BASE):
    for f in files:
        if not f.endswith('.xml') or f in ['list.xml', 'customization.xml']:
            continue
        
        xml_path = os.path.join(root, f)
        tank_id = f.replace('.xml', '')
        
        # Get nation from folder
        folder = os.path.basename(os.path.dirname(xml_path))
        nation = folder.split('_')[0]
        
        data = parse_vehicle(xml_path)
        if data:
            data["nation"] = nation
            all_tanks[tank_id] = data

print(f"Total tanks: {len(all_tanks)}")

# Save to file
with open("tank_slots_db.json", "w", encoding="utf-8") as f:
    json.dump(all_tanks, f, ensure_ascii=False, indent=2)

print("Saved to tank_slots_db.json")

# Print samples
for i, (k, v) in enumerate(list(all_tanks.items())[:5]):
    print(f"{k}: crew={v['crew_slots']}, equip_slots={v['equipment_slot_count']}")