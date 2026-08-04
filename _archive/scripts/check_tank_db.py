#!/usr/bin/env python3
"""Check tank_db.json nation values."""
import json

with open("tank_db.json") as f:
    db = json.load(f)

# Sample first 3 tanks from each nation
nations = {}
for tag, info in db.items():
    nation = info.get("nation")
    if nation not in nations:
        nations[nation] = []
    if len(nations[nation]) < 3:
        nations[nation].append((tag, info))

print("Sample tanks by nation:")
for nation, tanks in sorted(nations.items()):
    print(f"\n{nation}:")
    for tag, info in tanks:
        print(f"  {tag}: name='{info['name']}', icon='{info.get('icon', 'NO ICON')}'")

print("\n" + "="*60)
print("Nation list for country flag mapping:")
for nation in sorted(nations.keys()):
    print(f"  - '{nation}'")
