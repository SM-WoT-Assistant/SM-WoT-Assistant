import sys
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info
import time

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(10)

# Look for consumables in page source
html = driver.page_source.lower()

print("\n=== SEARCH IN HTML FOR CONSUMABLES ===")
keywords = ['consumable', 'repair kit', 'medkit', 'extinguisher', 'rations', 'cola', 'chocolate', 'coffee', 'food']
for kw in keywords:
    if kw in html:
        count = html.count(kw)
        print(f"  FOUND: '{kw}' ({count} times)")
    else:
        print(f"  MISSING: '{kw}'")

# Look for specific UI sections
print("\n=== LOOKING FOR UI SECTIONS ===")
if 'consumable' in html:
    idx = html.find('consumable')
    print(f"Found 'consumable' at position {idx}")
    print(f"Context: {html[max(0,idx-50):idx+100]}")

driver.quit()
print("\nDone")