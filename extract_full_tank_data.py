#!/usr/bin/env python3
"""
extract_full_tank_data.py
Додає можливе обладнання та field mods до кожного танка
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
        "available_equipment": [],
        "has_post_progression": False,
        "field_mods": []
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
    
    # Post progression - tree name
    pp_match = re.search(r'<postProgressionTree>([^<]+)', content)
    if pp_match:
        result["has_post_progression"] = True
        result["post_progression_tree"] = pp_match.group(1).strip()
    
    # optDevsOverrides - які типи обладнання доступні
    # Це показує які категорії обладнання можна встановлювати
    opt_devs = re.findall(r'<([a-zA-Z]+)>(<[^>]*>)?</\1>', content)
    # Шукаємо в optDevsOverrides
    opt_overrides = re.findall(r'<optDevsOverrides>(.*?)</optDevsOverrides>', content, re.DOTALL)
    if opt_overrides:
        for override in opt_overrides:
            # Знаходимо всі теги всередині
            items = re.findall(r'<([a-zA-Z_]+)>', override)
            result["available_equipment"].extend(items)
    
    result["available_equipment"] = list(set(result["available_equipment"]))
    
    return result

# Parse all
all_tanks = {}
for root_dir, dirs, files in os.walk(BASE):
    for f in files:
        if not f.endswith(".xml") or f in ["list.xml", "customization.xml"]:
            continue
        path = os.path.join(root_dir, f)
        data = parse_vehicle(path)
        if data:
            folder = os.path.basename(root_dir)
            data["nation"] = folder.split("_")[0] if "_" in folder else folder
            all_tanks[f.replace(".xml", "")] = data

print(f"Total: {len(all_tanks)}")

# Show samples
for k, v in list(all_tanks.items())[:5]:
    print(f"{k}:")
    print(f"  crew: {v['crew_roles']}")
    print(f"  equip_slots: {v['equipment_slots']}")
    print(f"  available_equipment: {v['available_equipment'][:5]}")
    print(f"  post_progression: {v.get('post_progression_tree', 'none')}")

with open("tank_slots_full.json", "w", encoding="utf-8") as f:
    json.dump(all_tanks, f, ensure_ascii=False, indent=2)
print("\nSaved to tank_slots_full.json")