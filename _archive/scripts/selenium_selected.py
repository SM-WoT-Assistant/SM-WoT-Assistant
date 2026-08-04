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

# Look for "Consumables" section - find selected/consumed items
# They might have different class or be marked as selected

# Find the Consumables section and look for selected items
print("\n=== CONSUMABLES SECTION ===")
idx = html.find('Consumables__AllConsumables')
if idx >= 0:
    section = html[idx:idx+2000]
    print(section[:1000])

# Look for data-selected or similar attributes
print("\n=== LOOKING FOR SELECTED ITEMS ===")
# Find all consumable buttons/divs
consumable_pattern = r'<img alt="([^"]+)"[^>]*>'
all_imgs = re.findall(consumable_pattern, html)
print(f"All alt images with consumable-related names: {all_imgs}")

# Try JavaScript to find selected consumables
print("\n=== JAVASCRIPT - FIND SELECTED ===")
js_code = """
(function() {
    // Find the Consumables section
    var section = document.querySelector('[class*="Consumables"]');
    if (!section) return 'No section found';

    // Look for images in that section
    var imgs = section.querySelectorAll('img');
    var result = [];
    imgs.forEach(function(img) {
        result.push(img.alt);
    });

    // Also check for selected state (different style)
    var buttons = section.querySelectorAll('button');
    var selected = [];
    buttons.forEach(function(btn) {
        if (btn.getAttribute('data-state') === 'open' || btn.getAttribute('data-state') === 'checked') {
            var img = btn.querySelector('img');
            if (img) selected.push(img.alt);
        }
    });

    return {imgs: result, selected: selected};
})()
"""
result = driver.execute_script(js_code)
print(f"Result: {result}")

driver.quit()