from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import json
from bs4 import BeautifulSoup

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1280,900")

driver = webdriver.Chrome(options=chrome_options)

url = "https://tomato.gg/tanks/7169/is-7/EU?tab=loadouts"
print(f"Loading: {url}")
driver.get(url)

# Wait for page to load
time.sleep(15)

# Scroll down to make content visible
print("Scrolling...")
driver.execute_script("window.scrollTo(0, 800)")
time.sleep(3)

# Try to find and click Consumables button using multiple strategies
print("\n=== TRYING TO FIND CONSUMABLES BUTTON ===")

# Method 1: Look for button with "Consumable" text
try:
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        text = btn.text.strip()
        if "Consumable" in text:
            print(f"Found button: '{text}'")
            driver.execute_script("arguments[0].scrollIntoView();", btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", btn)
            print("Clicked!")
            time.sleep(8)
            break
except Exception as e:
    print(f"Method 1 error: {e}")

# Method 2: Try clicking by looking for elements with specific classes or XPath
if not driver.page_source.__contains__("tableComponents__TableContainer"):
    print("Trying Method 2: XPath search...")
    try:
        # Try to find any element that might be the consumables tab
        xpath = "//button[contains(@class, 'rt-Button') or contains(@class, 'Button')] | //span[contains(text(), 'Consumable')]"
        elements = driver.find_elements(By.XPATH, xpath)
        for elem in elements[:10]:
            text = elem.text.strip()
            print(f"  Element: '{text}'")
    except Exception as e:
        print(f"Method 2 error: {e}")

# Method 3: Try scrolling to the equipment section and looking for tabs
print("\nTrying Method 3: Find tabs in the page...")
try:
    # Look for tab-like elements
    all_buttons = driver.find_elements(By.CSS_SELECTOR, "button")
    for btn in all_buttons:
        try:
            text = btn.text.strip()
            if text and len(text) < 30:
                print(f"Button: '{text}'")
        except:
            pass
except Exception as e:
    print(f"Method 3 error: {e}")

# Now get the page source and save it
page_source = driver.page_source
with open("debug_consumables_wait.html", "w", encoding="utf-8") as f:
    f.write(page_source)
print("\nSaved to debug_consumables_wait.html")

# Now parse to find tables
soup = BeautifulSoup(page_source, 'html.parser')
tables = soup.find_all('table')
print(f"\n=== FOUND {len(tables)} TABLES ===")

for i, table in enumerate(tables):
    rows = table.find_all('tr')
    if len(rows) > 0:
        print(f"\n--- Table {i+1} ---")
        first_row = rows[0]
        cells = first_row.find_all(['td', 'th'])
        for cell in cells[:5]:
            imgs = cell.find_all('img')
            for img in imgs:
                alt = img.get('alt', '')[:50]
                src = img.get('src', '')[:50]
                print(f"  img: alt='{alt}', src={src}...")

driver.quit()