import os
import re
import json

filename = "temp_pages/R45_IS-7.html"
if not os.path.exists(filename):
    print("File not found, running scraper...")
    exit(1)

with open(filename, "r", encoding="utf-8") as f:
    page_source = f.read()

match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>([^<]+)</script>', page_source)
if not match:
    print("No __NEXT_DATA__")
    exit()

data = json.loads(match.group(1))
next_data = data.get("props", {}).get("pageProps", {})

# Check equipment data structure
equip = next_data.get("equipment", {})
if isinstance(equip, dict):
    equip_data = equip.get("data", {})
    print(f"Equipment data keys: {list(equip_data.keys())}")

    if "popularSetups" in equip_data:
        ps = equip_data["popularSetups"]
        print(f"\n=== Popular setups: {len(ps)} ===")
        for i, setup in enumerate(ps[:3]):
            print(f"\nSetup {i+1}:")
            print(f"  Full setup: {setup}")