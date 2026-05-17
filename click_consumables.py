import sys
import time
import json
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)

url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU?tab=loadouts"

print(f"Loading: {url}")
driver = create_driver()

# Set page load strategy
driver.set_page_load_timeout(60)

driver.get(url)
time.sleep(20)  # Wait for everything

# Try to find and click on "Consumables" button/tab in the UI
print("\n=== TRYING TO FIND AND CLICK CONSUMABLES UI ===")

# Use JavaScript to find any clickable consumable element
js_click = """
(function() {
    // Try to find any element with 'Consumables' text and click it
    var elements = document.querySelectorAll('button, a, div');
    for (var i = 0; i < elements.length; i++) {
        if (elements[i].innerText && elements[i].innerText.includes('Consumable')) {
            console.log('Found: ' + elements[i].innerText);
            try {
                elements[i].click();
                return 'Clicked: ' + elements[i].innerText;
            } catch(e) {
                return 'Error: ' + e;
            }
        }
    }
    return 'Not found';
})()
"""
result = driver.execute_script(js_click)
print(f"Result: {result}")

time.sleep(5)  # Wait for any content to load

# Get HTML
html = driver.page_source

# Search for consumables data patterns
print("\n=== SEARCHING FOR CONSUMABLES DATA IN HTML ===")

# Look for any JSON with consumable usage data
import re
# Search for any number pattern that looks like: repair kit name + percentage
for name in ['Small Repair Kit', 'Large Repair Kit', 'Small First Aid']:
    pattern = rf'{re.escape(name)}[^{{}}]{{0,100}}\d+\.\d+%'
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f"\nFound: {name}")
        for m in matches[:3]:
            print(f"  {m[:100]}")

# Also check if there's any data that looks like: [item1, item2, item3, percentage]
pattern2 = r'\[.*(?:Kit|Extinguisher|Ration).*\]'
matches2 = re.findall(pattern2, html)
print(f"\nFound {len(matches2)} array patterns with consumables")

driver.quit()