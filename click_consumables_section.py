import sys
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

tank_code = 'R45_IS-7'
tank_id = '7169'
tank_slug = 'is-7'

chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

service = Service()
driver = webdriver.Chrome(service=service, options=chrome_options)

url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"
print(f"Loading: {url}")

try:
    driver.get(url)
    time.sleep(10)

    # Scroll down to find Consumables section
    print("\n=== SCROLLING TO FIND CONSUMABLES ===")
    for i in range(5):
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(1)

    # Try to find "Consumables" text and click on it
    print("\n=== CLICKING ON CONSUMABLES ===")
    
    # Find any element that contains "Consumables"
    all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Consumables')]")
    print(f"Found {len(all_elements)} elements with 'Consumables' text")
    
    for elem in all_elements:
        try:
            print(f"Element: {elem.tag_name} - {elem.text[:50]}")
            elem.click()
            print("Clicked!")
            time.sleep(5)
            break
        except Exception as e:
            print(f"Error clicking: {e}")

    # After clicking, wait and get data
    print("\n=== WAITING FOR CONSUMABLES DATA ===")
    time.sleep(5)

    # Get page source
    html = driver.page_source
    
    # Get all text
    body = driver.find_element(By.TAG_NAME, "body")
    text = body.text
    
    print(f"Text length: {len(text)}")
    
    # Save
    with open('tomato_consumables_clicked.html', 'w', encoding='utf-8') as f:
        f.write(html)
    with open('tomato_consumables_clicked.txt', 'w', encoding='utf-8', errors='ignore') as f:
        f.write(text)
    print("Saved!")

    # Search for consumables with percentages
    print("\n=== SEARCHING FOR CONSUMABLES WITH % ===")
    for line in text.split('\n'):
        line = line.strip()
        if len(line) > 5:
            if any(w in line for w in ['Repair Kit', 'First Aid', 'Extinguisher', 'Ration']) and '%' in line:
                print(f"  FOUND: {line[:150]}")

finally:
    driver.quit()

print("Done")