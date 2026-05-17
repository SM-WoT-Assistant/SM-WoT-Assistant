#!/usr/bin/env python3
import os, xml.etree.ElementTree as ET, json

BASE = r"D:\!WORK\WOT\WOTtraner\WORK\WoT_Assistant_4.0\tmp\tth_work"

def parse_vehicle(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace(' xmlns:xmlref="http://bwt/xmlref"', '')
        root = ET.fromstring(content)
    except:
        return None
    
    result = {"crew": [], "supply_slots": "", "has_post_progression": False}
    
    crew = root.find("crew")
    if crew is not None:
        result["crew"] = [c.tag for c in crew]
    
    supply = root.find("supplySlots")
    if supply is not None and supply.text:
        result["supply_slots"] = supply.text.strip()
    
    if root.find("postProgressionTree") is not None:
        result["has_post_progression"] = True
    
    return result

all_tanks = {}
for root_dir, dirs, files in os.walk(BASE):
    for f in files:
        if not f.endswith(".xml") or f in ["list.xml", "customization.xml"]:
            continue
        path = os.path.join(root_dir, f)
        data = parse_vehicle(path)
        if data:
            folder = os.path.basename(root_dir)
            nation = folder.split("_")[0]
            data["nation"] = nation
            all_tanks[f.replace(".xml", "")] = data

print(f"Total: {len(all_tanks)}")
for k, v in list(all_tanks.items())[:3]:
    print(f"{k}: {v}")