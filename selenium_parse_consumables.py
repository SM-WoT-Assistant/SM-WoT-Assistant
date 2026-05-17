import sys
import time
import re
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(10)

html = driver.page_source

# Find all consumable names in alt attributes
print("\n=== CONSUMABLE NAMES FROM HTML ===")
alt_pattern = r'<img alt="([^"]+)"[^>]*>'
all_alts = re.findall(alt_pattern, html)

consumables = [alt for alt in all_alts if 'kit' in alt.lower() or 'extinguisher' in alt.lower() or 'ration' in alt.lower() or 'cola' in alt.lower() or 'coffee' in alt.lower() or 'chocolate' in alt.lower() or 'fuel' in alt.lower()]

print("Unique consumables found:")
unique_cons = set(consumables)
for c in sorted(unique_cons):
    count = consumables.count(c)
    print(f"  {c} ({count})")

# Also try to find via JavaScript - maybe data is in React state
print("\n=== TRY JAVASCRIPT ===")
js_code = """
(function() {
    // Try to find data in React components
    var buttons = document.querySelectorAll('button');
    var consumables = [];
    for (var i = 0; i < buttons.length; i++) {
        var text = buttons[i].innerText || '';
        var alt = buttons[i].querySelector('img')?.alt || '';
        if (text.toLowerCase().includes('consumable') || alt.includes('kit') || alt.includes('ration')) {
            consumables.push({text: text, alt: alt});
        }
    }
    return consumables.slice(0, 20);
})()
"""
result = driver.execute_script(js_code)
print(f"Found {len(result)} elements")

driver.quit()