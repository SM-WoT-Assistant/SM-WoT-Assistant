from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1280,900")

driver = webdriver.Chrome(options=chrome_options)

url = "https://tomato.gg/tanks/7169/is-7/EU?tab=loadouts"
print(f"Loading: {url}")
driver.get(url)
time.sleep(10)

# Scroll
driver.execute_script("window.scrollTo(0, 500)")
time.sleep(2)

print("\n=== ALL BUTTONS ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for i, btn in enumerate(buttons):
    try:
        text = btn.text.strip()[:50]
        if text:
            print(f"{i}: '{text}'")
    except:
        pass

print("\n=== ALL LINKS/ANCHORS ===")
links = driver.find_elements(By.TAG_NAME, "a")
for i, link in enumerate(links[:30]):
    try:
        text = link.text.strip()[:50]
        href = link.get_attribute("href") or ""
        if text or "loadout" in href.lower() or "consumable" in href.lower():
            print(f"{i}: text='{text}', href={href[:60]}...")
    except:
        pass

driver.quit()