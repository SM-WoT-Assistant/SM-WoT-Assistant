import re
import json
from bs4 import BeautifulSoup

with open("debug_consumables.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find __NEXT_DATA__
match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if not match:
    print("No __NEXT_DATA__ found")
    exit()

data = json.loads(match.group(1))
next_data = data.get("props", {}).get("pageProps", {})

print("=== PAGE PROPS KEYS ===")
for key in next_data.keys():
    print(f"  {key}")

# Check equipment section
equip = next_data.get("equipment", {})
if isinstance(equip, dict):
    equip_data = equip.get("data", {})
    print(f"\n=== EQUIPMENT DATA KEYS ===")
    for key in equip_data.keys():
        print(f"  {key}")

    # Check popularSetups
    ps = equip_data.get("popularSetups", [])
    print(f"\n=== POPULAR SETUPS (first 3) ===")
    for i, setup in enumerate(ps[:3]):
        if isinstance(setup, list) and len(setup) >= 2:
            loadout = setup[0]
            stats = setup[1]
            print(f"Setup {i+1}: {loadout}, wn8={stats.get('wn8')}, count={stats.get('count')}")

# Check if there's a separate section for consumables in the equipment data
# Maybe they are in a different key like "consumablesDist" or similar
for key in equip_data.keys():
    if "consum" in key.lower():
        print(f"\n=== CONSUMABLES-RELATED KEY: {key} ===")
        print(json.dumps(equip_data[key], indent=2)[:2000])