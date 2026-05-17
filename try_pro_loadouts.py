import sys
import time
import re
import json
sys.path.insert(0, '.')
from tomato_selenium import create_driver

tank_id = 7169
tank_slug = "is-7"

urls = [
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU?tab=loadouts&view=pro",
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU/loadouts",
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU?view=pro",
]

driver = create_driver()

for url in urls:
    print(f"\n=== Trying: {url} ===")
    driver.get(url)
    time.sleep(12)
    
    text = driver.find_element("tag name", "body").text
    
    consumables_found = False
    for name in ['Repair Kit', 'Medkit', 'Extinguisher']:
        if name in text and '%' in text:
            print(f"Found: {name}")
            consumables_found = True
    
    if not consumables_found:
        print("No consumables found")
        
    print(f"URL after load: {driver.current_url}")

driver.quit()