#!/usr/bin/env python3
"""
create_tank_slots_db.py
Створює повну базу слотів для кожного танка
"""
import os, re, json

BASE = r"D:\!WORK\WOT\WOTtraner\WORK\WoT_Assistant_4.0\tmp\tth_work"

def parse_vehicle(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = re.sub(r'\s+xmlns:[a-z]+="[^"]*"', '', content)
        content = re.sub(r'\s+xmlns="[^"]*"', '', content)
    except:
        return None
    
    result = {
        "crew_roles": [],
        "equipment_slots": 0,
        "consumable_slots": [],
        "has_post_progression": False
    }
    
    # Crew
    crew_match = re.search(r'<crew>(.*?)</crew>', content, re.DOTALL)
    if crew_match:
        crew_content = crew_match.group(1)
        roles = re.findall(r'<([a-zA-Z_]+)>[^<]*</\1>', crew_content)
        result["crew_roles"] = roles
    
    # Supply slots - count equipment (1-5) before consumables (6,7,8)
    # FIX: Count all numbers BEFORE first 6/7/8, not just '1'
    supply_match = re.search(r'<supplySlots>([^<]+)', content)
    if supply_match:
        slots = supply_match.group(1).strip().split()
        equipment_count = 0
        for s in slots:
            if s in ['6', '7', '8']:
                break
            equipment_count += 1
        result["equipment_slots"] = equipment_count
        result["consumable_slots"] = [s for s in slots if s in ['6', '7', '8']]
    
    # Post progression
    result["has_post_progression"] = '<postProgressionTree>' in content
    
    return result

# Parse all tanks
all_tanks = {}
for root_dir, dirs, files in os.walk(BASE):
    for f in files:
        if not f.endswith(".xml") or f in ["list.xml", "customization.xml"]:
            continue
        path = os.path.join(root_dir, f)
        data = parse_vehicle(path)
        if data:
            folder = os.path.basename(root_dir)
            nation = folder.split("_")[0] if "_" in folder else folder
            data["nation"] = nation
            all_tanks[f.replace(".xml", "")] = data

# Print statistics
print(f"Total tanks: {len(all_tanks)}")

# Count by nation
nations = {}
for k, v in all_tanks.items():
    n = v.get("nation", "unknown")
    nations[n] = nations.get(n, 0) + 1
print("By nation:", nations)

# Equipment slots distribution
equip_counts = {}
for k, v in all_tanks.items():
    c = v.get("equipment_slots", 0)
    equip_counts[c] = equip_counts.get(c, 0) + 1
print("Equipment slots distribution:", equip_counts)

# Show sample
print("\nSamples:")
for k, v in list(all_tanks.items())[:3]:
    print(f"  {k}: crew={v['crew_roles']}, equip={v['equipment_slots']}, consumables={v['consumable_slots']}")

# Save
with open("tank_slots_db.json", "w", encoding="utf-8") as f:
    json.dump(all_tanks, f, ensure_ascii=False, indent=2)
print("\nSaved to tank_slots_db.json")