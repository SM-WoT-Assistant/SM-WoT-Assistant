import os
import re
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1280,900")

driver = webdriver.Chrome(options=chrome_options)

tank_id = "7169"
url = f"https://tomato.gg/tanks/{tank_id}/is-7/EU"
print(f"Loading: {url}")
driver.get(url)
time.sleep(3)

page_source = driver.page_source
driver.quit()

match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>([^<]+)</script>', page_source)
if not match:
    print("No __NEXT_DATA__")
    exit()

data = json.loads(match.group(1))
next_data = data.get("props", {}).get("pageProps", {})

# Check all pageProps for consumables
print("\n=== ALL PAGE PROPS KEYS ===")
for key in next_data.keys():
    print(f"  {key}")

# Check popularSetups structure more carefully
equip = next_data.get("equipment", {})
if isinstance(equip, dict):
    equip_data = equip.get("data", {})
    ps = equip_data.get("popularSetups", [])

    print("\n=== CHECKING POPULAR SETUPS STRUCTURE ===")
    for i, setup in enumerate(ps[:5]):
        if isinstance(setup, list) and len(setup) >= 2:
            loadout = setup[0]
            stats = setup[1]
            print(f"\nSetup {i+1}:")
            print(f"  Loadout: {loadout}")
            print(f"  Stats keys: {list(stats.keys())}")

            # Check if loadout is a dict with consumables
            if isinstance(loadout, dict):
                print(f"  Loadout keys: {list(loadout.keys())}")
                if "consumables" in loadout:
                    print(f"  CONSUMABLES: {loadout['consumables']}")