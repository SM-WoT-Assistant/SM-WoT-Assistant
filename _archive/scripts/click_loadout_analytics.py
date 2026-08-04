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

# Find and click "Loadout Analytics" tab
print("\n=== CLICKING LOADOUT ANALYTICS TAB ===")

# Try to find the tab - look for links with specific text
tabs = driver.find_elements(By.TAG_NAME, "a")
loadout_tab = None
for tab in tabs:
    text = tab.text.strip()
    if 'loadout' in text.lower() and 'analytics' in text.lower():
        print(f"Found tab: {text}")
        loadout_tab = tab
        break
    elif 'Loadout Analytics' in text:
        print(f"Found tab: {text}")
        loadout_tab = tab
        break

# Also try finding by href
if not loadout_tab:
    for tab in tabs:
        href = tab.get_attribute("href") or ""
        if 'loadout' in href.lower():
            print(f"Found href: {href}")
            loadout_tab = tab
            break

# Click the tab
if loadout_tab:
    print(f"Clicking: {loadout_tab.text}")
    try:
        loadout_tab.click()
        time.sleep(10)  # Wait for content to load
        print("Clicked, waiting for content...")
    except Exception as e:
        print(f"Error clicking: {e}")

# After clicking, get the new URL
print(f"New URL: {driver.current_url}")

# Get the page source
html = driver.page_source

# Save HTML
with open('tomato_loadout_tab.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Saved HTML to tomato_loadout_tab.html")

# Check text content now
text = driver.find_element("tag name", "body").text
print(f"\nTotal text length after click: {len(text)}")

# Search for consumables with percentages
print("\n=== SEARCHING FOR CONSUMABLES ===")
for name in ['Repair Kit', 'First Aid', 'Extinguisher', 'Rations']:
    if name in text and '%' in text:
        # Find context
        idx = text.find(name)
        context = text[max(0,idx-50):idx+150]
        print(f"\n{name}:")
        print(f"  {context}")

driver.quit()