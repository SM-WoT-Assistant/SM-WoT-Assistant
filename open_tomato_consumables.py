from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1280,900")

driver = webdriver.Chrome(options=chrome_options)

tank_id = "7169"
tank_slug = "is-7"

url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}"
print(f"Opening: {url}")
driver.get(url)

time.sleep(3)

try:
    loadout_tab = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Loadout') or contains(text(), 'Analytics')]"))
    )
    loadout_tab.click()
    print("Clicked Loadout tab")
    time.sleep(2)
except Exception as e:
    print(f"Could not click Loadout tab: {e}")

try:
    consumables_section = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Consumable')]"))
    )
    consumables_section.click()
    print("Clicked Consumables section")
    time.sleep(2)
except Exception as e:
    print(f"Could not click Consumables: {e}")

print("\n=== PAGE SOURCE (first 5000 chars) ===")
html = driver.page_source
print(html[:5000])

driver.quit()