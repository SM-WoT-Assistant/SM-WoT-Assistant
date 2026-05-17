import sys
import time
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

# Click on Loadout tab
print("\n=== CLICKING LOADOUT TAB ===")
try:
    # Find and click Loadout button
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        text = btn.text.lower()
        if 'loadout' in text or 'analytics' in text:
            print(f"Clicking: {btn.text}")
            btn.click()
            time.sleep(5)
            break
except Exception as e:
    print(f"Error: {e}")

# Get page source after clicking
html = driver.page_source

# Look for loadout items - maybe they're in a different section now
print("\n=== LOOKING FOR LOADOUT ===")

# Search for loadout related content
for keyword in ['loadout', 'setup', 'build']:
    count = html.lower().count(keyword)
    print(f"  {keyword}: {count} times")

# Try to find JSON data for loadout
print("\n=== LOOKING FOR LOADOUT JSON ===")
scripts = driver.find_elements(By.TAG_NAME, "script")
for script in scripts:
    text = script.get_attribute("text") or ""
    if 'loadout' in text.lower() and 'equipment' in text.lower():
        # Found something
        idx = text.lower().find('loadout')
        print(f"Found loadout in script")
        print(f"Context: {text[max(0,idx):idx+200]}")
        break

driver.quit()