import sys
import time
import re
import json
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(10)

# Try to scroll to bottom to load all content
print("\n=== SCROLLING TO LOAD ALL CONTENT ===")
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(3)

# Try to find navigation tabs on the page
print("\n=== LOOKING FOR NAVIGATION TABS ===")

# Find all links that might be tabs
nav_links = driver.find_elements(By.CSS_SELECTOR, "nav a, [class*=nav] a, .nav a, header a")
for link in nav_links[:20]:
    try:
        text = link.text.strip()
        href = link.get_attribute("href") or ""
        if text:
            print(f"  {text}: {href[:80]}")
    except:
        pass

# Try to find section headers on the page
print("\n=== LOOKING FOR SECTION HEADERS ===")
headers = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, [class*=header], [class*=section]")
for header in headers[:20]:
    try:
        text = header.text.strip()
        if text:
            print(f"  {text[:60]}")
    except:
        pass

# Let's try direct URL patterns that might work
print("\n=== TRYING ALTERNATIVE URL PATTERNS ===")

# Try scrolling to consumables section manually
# First, find any element with "consumable" text
consumable_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Consumable')]")
for elem in consumable_elements:
    print(f"Found element: {elem.text[:50]}")
    try:
        # Click on it to expand
        elem.click()
        time.sleep(3)
    except:
        pass

# Save the HTML after interaction
html = driver.page_source
with open('tomato_is7_with_interaction.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("\nSaved HTML to tomato_is7_with_interaction.html")

# Check for percentages now
print("\n=== CHECKING FOR CONSUMABLE PERCENTAGES ===")
for name in ['Repair Kit', 'First Aid', 'Extinguisher', 'Rations']:
    count = html.count(name)
    print(f"  {name}: {count} times")

driver.quit()