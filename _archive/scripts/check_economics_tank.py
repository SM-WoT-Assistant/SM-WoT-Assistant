import json
import re

# Check the original __NEXT_DATA__ that was saved earlier
with open('tomato_next_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

props = data['props']['pageProps']

# Check economics for the specific tank
print("=== CHECKING ECONOMICS FOR IS-7 ===")
econ = props.get('economics', {}).get('data', [])

# Find IS-7 in economics data
for item in econ:
    if 'IS-7' in item.get('name', '') or item.get('tank_id') == 7169:
        print(f"Found IS-7 data:")
        print(f"  avg_consumables_cost: {item.get('avg_consumables_cost')}")
        print(f"  avg_repair_cost: {item.get('avg_repair_cost')}")
        print(f"  battles: {item.get('battles')}")
        break

# Check if there's another section with loadouts
print("\n=== CHECKING ALL EQUIPMENT STRUCTURE ===")
equip = props.get('equipment', {}).get('data', {})

# Check every key
for k, v in equip.items():
    if isinstance(v, list) and v:
        print(f"{k}: {len(v)} items")
        if k == 'popularSetups' and v:
            print(f"  First setup: {v[0]}")

# Try to find if there's a separate consumables section
print("\n=== SEARCHING FOR ANY 'LOADOUT' STRUCTURE ===")
def search_loadout(obj, path="", depth=0):
    if depth > 4:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if 'loadout' in k.lower():
                print(f"Found: {path}.{k}")
                if isinstance(v, dict):
                    print(f"  Keys: {list(v.keys())[:10]}")
                elif isinstance(v, list):
                    print(f"  Length: {len(v)}")
            search_loadout(v, f"{path}.{k}", depth+1)

search_loadout(props)