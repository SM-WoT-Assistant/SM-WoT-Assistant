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

# Try to find and click "Loadout" or "Analytics" tab
print("\n=== LOOKING FOR LOADOUT/ANALYTICS TAB ===")

# Find all links/buttons that might be tabs
all_elements = driver.find_elements(By.CSS_SELECTOR, "a, button, [role=tab]")
tabs_found = []
for elem in all_elements:
    try:
        text = elem.text.strip()
        href = elem.get_attribute("href") or ""
        if text and ('loadout' in text.lower() or 'analytics' in text.lower() or 'equipment' in text.lower()):
            tabs_found.append((text, href))
    except:
        pass

print(f"Found {len(tabs_found)} tab elements:")
for t in tabs_found[:10]:
    print(f"  Text: {t[0]}, href: {t[1]}")

# Try clicking on elements with Loadout in text
for elem in all_elements:
    try:
        text = elem.text.lower()
        if 'loadout' in text or 'analytics' in text:
            print(f"\nClicking: {elem.text}")
            elem.click()
            time.sleep(5)
            break
    except Exception as e:
        pass

# Get current URL after potential navigation
print(f"\nCurrent URL: {driver.current_url}")

# Save new HTML after clicking
html = driver.page_source
with open('tomato_is7_after_click.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Saved HTML to tomato_is7_after_click.html")

# Search for percentages again
print("\n=== SEARCHING FOR CONSUMABLES WITH PERCENTAGES ===")
consumable_words = ['Repair Kit', 'First Aid', 'Extinguisher', 'Rations']
for word in consumable_words:
    pattern = rf'.{{0,100}}{re.escape(word)}.{{0,100}}\d+\.?\d*%'
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f"\n{word} - Found {len(matches)} matches:")
        for m in matches[:3]:
            clean = re.sub(r'<[^>]+>', ' ', m)
            clean = re.sub(r'\s+', ' ', clean).strip()
            print(f"  {clean[:200]}")

# Check __NEXT_DATA__ again
print("\n=== CHECKING __NEXT_DATA__ AFTER CLICK ===")
match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if match:
    next_data = json.loads(match.group(1))
    props = next_data.get('props', {}).get('pageProps', {})
    print(f"Keys in pageProps: {list(props.keys())}")

driver.quit()