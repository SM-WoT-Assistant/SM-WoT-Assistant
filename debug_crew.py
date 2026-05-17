import os
import re
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1280,900")

driver = webdriver.Chrome(options=chrome_options)

tank_id = "7169"
url = f"https://tomato.gg/tanks/{tank_id}/is-7/EU"
print(f"Loading: {url}")
driver.get(url)
time.sleep(3)

# Try to click on Loadout Analytics tab
try:
    loadout_tab = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Loadout') or contains(@href, '/loadout')]"))
    )
    print(f"Found loadout tab: {loadout_tab.text}")
    # Click it
    driver.execute_script("arguments[0].click();", loadout_tab)
    time.sleep(3)
except Exception as e:
    print(f"Could not click loadout tab: {e}")

# Get updated page source
page_source = driver.page_source
driver.quit()

match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>([^<]+)</script>', page_source)
if not match:
    print("No __NEXT_DATA__")
    exit()

data = json.loads(match.group(1))
next_data = data.get("props", {}).get("pageProps", {})

# Check crew section
crew = next_data.get("crew", {})
print(f"\n=== CREW SECTION ===")
print(f"Crew type: {type(crew)}")
if isinstance(crew, dict):
    print(f"Crew keys: {list(crew.keys())}")
    crew_data = crew.get("data", {})
    if isinstance(crew_data, dict):
        print(f"Crew data keys: {list(crew_data.keys())}")
        # Check if there's consumables info in crew data
        for key in crew_data.keys():
            if "consum" in key.lower():
                print(f"\nFound consumables-related key: {key}")
                print(json.dumps(crew_data[key], indent=2)[:2000])