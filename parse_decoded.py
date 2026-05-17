#!/usr/bin/env python3
"""
extract_vehicle_slots_from_decoded.py
"""
import os
import xml.etree.ElementTree as ET
import json

BASE = r"D:\!WORK\WOT\WOTtraner\WORK\WoT_Assistant_4.0\tmp\tth_work"

def parse_vehicle(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except:
        return None
    
    result = {"equipment_slots": [], "crew_slots": [], "has_post_progression": False}
    
    # Equipment slots - optDevs
    opt_devs = root.find('.//optDevs')
    if opt_devs is not None:
        for dev in opt_devs:
            result["equipment_slots"].append({"tag": dev.tag, "id": dev.get('id', '')})
    
    # Crew
    crew = root.findall('.//crew')
    for c in crew:
        role = c.get('role', '')
        if role:
            result["crew_slots"].append(role)
    
    # Post progression
    if root.find('.//postProgressionTree') is not None:
        result["has_post_progression"] = True
    
    return result

# Test on R05_KV
path = os.path.join(BASE, "ussr_0", "R05_KV.xml")
result = parse_vehicle(path)
print("R05_KV:", json.dumps(result, indent=2))

# Parse all ussr vehicles
all_tanks = {}
for root, dirs, files in os.walk(BASE):
    for f in files:
        if f.endswith('.xml') and f not in ['list.xml', 'customization.xml']:
            xml_path = os.path.join(root, f)
            tank_id = f.replace('.xml', '')
            data = parse_vehicle(xml_path)
            if data and (data["equipment_slots"] or data["crew_slots"]):
                all_tanks[tank_id] = data

print(f"\nTotal tanks with slots: {len(all_tanks)}")
print("Sample:", list(all_tanks.items())[:3])