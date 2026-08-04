#!/usr/bin/env python3
import os, re, json

BASE = r"D:\!WORK\WOT\WOTtraner\WORK\WoT_Assistant_4.0\tmp\tth_work"

def parse_xml_simple(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Strip xmlns
        content = re.sub(r'\s+xmlns:[a-z]+="[^"]*"', '', content)
        content = re.sub(r'\s+xmlns="[^"]*"', '', content)
        
        result = {"crew": [], "supply_slots": "", "has_post_progression": False}
        
        # Crew - find <crew>...</crew>
        crew_match = re.search(r'<crew>(.*?)</crew>', content, re.DOTALL)
        if crew_match:
            crew_content = crew_match.group(1)
            roles = re.findall(r'<([a-zA-Z_]+)>[^<]*</\1>', crew_content)
            result["crew"] = roles
        
        # Supply slots
        supply_match = re.search(r'<supplySlots>\s*([^\s<]+)', content)
        if supply_match:
            result["supply_slots"] = supply_match.group(1).strip()
        
        # Post progression
        if '<postProgressionTree>' in content:
            result["has_post_progression"] = True
        
        return result
    except Exception as e:
        return None

# Test
test_file = os.path.join(BASE, "ussr_0", "R01_IS.xml")
result = parse_xml_simple(test_file)
print("R01_IS result:", result)

# Parse all
all_tanks = {}
for root_dir, dirs, files in os.walk(BASE):
    for f in files:
        if not f.endswith(".xml") or f in ["list.xml", "customization.xml"]:
            continue
        path = os.path.join(root_dir, f)
        data = parse_xml_simple(path)
        if data:
            folder = os.path.basename(root_dir)
            data["nation"] = folder.split("_")[0] if "_" in folder else folder
            all_tanks[f.replace(".xml", "")] = data

print(f"Total tanks: {len(all_tanks)}")
for k, v in list(all_tanks.items())[:5]:
    print(f"{k}: crew={v['crew']}, slots={v['supply_slots'][:20] if v['supply_slots'] else 'none'}")

with open("tank_slots_db.json", "w", encoding="utf-8") as f:
    json.dump(all_tanks, f, ensure_ascii=False, indent=2)
print("Saved to tank_slots_db.json")