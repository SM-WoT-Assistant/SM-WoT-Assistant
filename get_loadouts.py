import sys
import time
import re
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)

# Try the working URL
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU?tab=loadouts"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(15)

# Get text
text = driver.find_element("tag name", "body").text
print(f"Text length: {len(text)}")

# Save to file
with open('tomato_loadouts_tab.txt', 'w', encoding='utf-8', errors='ignore') as f:
    f.write(text)
print("Saved to tomato_loadouts_tab.txt")

# Search for consumables with percentages
print("\n=== SEARCHING FOR CONSUMABLES WITH PERCENTAGES ===")
for line in text.split('\n'):
    line = line.strip()
    if not line:
        continue
    # Look for consumable name + percentage
    if any(w in line for w in ['Repair', 'Medkit', 'Extinguisher', 'Ration']) and '%' in line:
        print(f"  {line[:150]}")

driver.quit()