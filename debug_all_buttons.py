from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1280,1400")

driver = webdriver.Chrome(options=chrome_options)

url = "https://tomato.gg/tanks/7169/is-7/EU?tab=loadouts"
print(f"Loading: {url}")
driver.get(url)
time.sleep(15)

# Scroll down to see more content
print("Scrolling...")
driver.execute_script("window.scrollTo(0, 1000)")
time.sleep(3)

# Find ALL buttons and print their text
print("\n=== ALL BUTTONS ON PAGE ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for i, btn in enumerate(buttons):
    try:
        text = btn.text.strip()
        if text and len(text) < 50:
            # Get parent info
            parent = btn.find_element(By.XPATH, "..")
            parent_class = parent.get_attribute("class") or ""
            print(f"{i}: '{text}' | parent class: {parent_class[:50]}")
    except:
        pass

# Also find elements with role="tab"
print("\n=== ELEMENTS WITH role=tab ===")
tabs = driver.find_elements(By.CSS_SELECTOR, "[role='tab']")
for i, tab in enumerate(tabs):
    try:
        text = tab.text.strip()
        print(f"{i}: '{text}'")
    except:
        pass

# Try to find any element containing "Consumable" text
print("\n=== SEARCHING FOR 'Consumable' TEXT ===")
all_elements = driver.find_elements(By.CSS_SELECTOR, "*")
consumable_elements = []
for elem in all_elements:
    try:
        text = elem.text
        if "Consumable" in text:
            consumable_elements.append((elem.tag_name, text[:100]))
    except:
        pass

for tag, text in consumable_elements[:10]:
    print(f"  {tag}: {text}")

driver.quit()