import sys
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

tank_code = 'R45_IS-7'
tank_id = '7169'
tank_slug = 'is-7'

# NOT headless mode
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

# Don't add headless - this allows full JavaScript execution

service = Service()
driver = webdriver.Chrome(service=service, options=chrome_options)

url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"
print(f"Loading: {url}")

try:
    driver.get(url)
    time.sleep(15)  # Wait longer

    # Try clicking on "Consumables" button/section
    print("\n=== LOOKING FOR CONSUMABLES UI ===")

    # Find all buttons
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        try:
            text = btn.text.strip()
            if 'Consumable' in text or 'consumable' in text.lower():
                print(f"Found: {text}")
                btn.click()
                time.sleep(5)
                break
        except:
            pass

    # Get inner text
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print(f"Body text length: {len(body_text)}")

    # Save HTML
    html = driver.page_source
    with open('tomato_not_headless.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Saved HTML")

    # Search for consumables with percentages
    print("\n=== SEARCHING FOR CONSUMABLES ===")
    for line in body_text.split('\n'):
        line = line.strip()
        if any(w in line for w in ['Repair Kit', 'First Aid', 'Extinguisher', 'Ration']) and '%' in line:
            print(f"  {line[:150]}")

finally:
    driver.quit()

print("Done")