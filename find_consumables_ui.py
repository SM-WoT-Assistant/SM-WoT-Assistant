import sys
import time
import re
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(10)

# Try to find and click on "Consumables" section/tab
print("\n=== LOOKING FOR CONSUMABLES UI ELEMENT ===")

# Find all buttons and look for Consumables-related text
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text and ('consum' in text.lower() or 'equipment' in text.lower() or 'loadout' in text.lower()):
        print(f"Button: {text}")

# Try to find consumables section in the page
# Check for data attributes or class names containing "consumable"
print("\n=== LOOKING FOR CONSUMABLE ELEMENTS ===")

consumable_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='consumable'], [id*='consumable']")
print(f"Found {len(consumable_elements)} elements with 'consumable' in class/id")

# Get inner HTML of first consumable element if found
if consumable_elements:
    for i, elem in enumerate(consumable_elements[:3]):
        html_content = elem.get_attribute('innerHTML')
        print(f"\nElement {i}: {html_content[:500]}")

# Try JavaScript to find all elements with consumable data
print("\n=== JAVASCRIPT: FIND CONSUMABLES DATA ===")
js_code = """
(function() {
    // Look for any element containing percentage data near consumable words
    var allText = document.body.innerText;
    var lines = allText.split('\\n');

    var results = [];
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line.includes('%') &&
            (line.includes('Repair') || line.includes('Kit') || line.includes('Aid') ||
             line.includes('Extinguisher') || line.includes('Ration'))) {
            results.push(line);
        }
    }
    return results.slice(0, 20);
})()
"""

result = driver.execute_script(js_code)
print(f"Found {len(result)} lines with consumables and percentages:")
for r in result:
    print(f"  {r}")

driver.quit()