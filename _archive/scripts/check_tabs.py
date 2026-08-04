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

# Get all buttons/links on page
print("\n=== ALL BUTTONS/TABS ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
tabs = []
for btn in buttons:
    text = btn.text.strip()
    if text:
        tabs.append(text)
print(f"Found {len(tabs)} buttons with text:")
for t in tabs[:20]:
    print(f"  - {t}")

# Check URL structure
print(f"\nCurrent URL: {driver.current_url}")

# Try clicking on different tabs to see URL changes
print("\n=== TRY CLICKING TABS ===")
nav_items = driver.find_elements(By.CSS_SELECTOR, "nav a, [class*=nav], [role=navigation] a")
for item in nav_items[:10]:
    href = item.get_attribute("href")
    text = item.text
    print(f"  {text}: {href}")

# Also try finding links
print("\n=== ALL LINKS WITH HREF ===")
links = driver.find_elements(By.TAG_NAME, "a")
for link in links[:15]:
    href = link.get_attribute("href")
    text = link.text.strip()[:30]
    if href and 'tomato' in href:
        print(f"  {text}: {href}")

driver.quit()