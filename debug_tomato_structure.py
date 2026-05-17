import re
import json

# Read the saved HTML file
with open("tomato_is7_full.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find the next-data script
match = re.search(r'window\.__NEXT_DATA__\s*=\s*(\{.*?\});</script>', html, re.DOTALL)

if not match:
    print("No __NEXT_DATA__ found")
    exit()

data = json.loads(match.group(1))
next_data = data.get("props", {}).get("pageProps", {})

print("=== ALL KEYS IN PAGE PROPS ===")
for key in next_data.keys():
    print(f"  - {key}")

print("\n=== CHECKING FOR CONSUMABLES ===")
for key in next_data.keys():
    if "consum" in key.lower() or "kit" in key.lower():
        print(f"Found: {key}")
        print(json.dumps(next_data[key], indent=2)[:2000])

# Check equipment data structure
if "equipment" in next_data:
    equip = next_data["equipment"]
    print("\n=== EQUIPMENT STRUCTURE ===")
    if isinstance(equip, dict):
        print(f"Keys: {list(equip.keys())}")
        if "data" in equip:
            equip_data = equip["data"]
            print(f"Equipment data keys: {list(equip_data.keys())}")
            if "popularSetups" in equip_data:
                ps = equip_data["popularSetups"]
                print(f"\nFound {len(ps)} popular setups")
                if ps:
                    print(f"First setup: {ps[0]}")
            if "loadouts" in equip_data:
                loadouts = equip_data["loadouts"]
                print(f"\n=== LOADOUTS ({len(loadouts)} items) ===")
                print(json.dumps(loadouts, indent=2)[:3000])