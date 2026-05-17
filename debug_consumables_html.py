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

# Try to find and click "Consumables"
print("\n=== LOOKING FOR CONSUMABLES ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    try:
        text = btn.text.strip()
        if "Consumable" in text:
            print(f"Found button: '{text}'")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(5)
            break
    except:
        continue

# Get page source
page_source = driver.page_source
with open("debug_consumables.html", "w", encoding="utf-8") as f:
    f.write(page_source)
print("Saved to debug_consumables.html")

driver.quit()

# Now parse to find tables with consumables
from bs4 import BeautifulSoup
soup = BeautifulSoup(page_source, 'html.parser')

# Find all tables
tables = soup.find_all('table')
print(f"\n=== FOUND {len(tables)} TABLES ===")

for i, table in enumerate(tables[:5]):
    rows = table.find_all('tr')
    if rows:
        print(f"\n--- Table {i+1} has {len(rows)} rows ---")
        # Check first row for img elements
        first_row = rows[0]
        imgs = first_row.find_all('img')
        for img in imgs:
            alt = img.get('alt', '')
            src = img.get('src', '')
            print(f"  Img alt: '{alt}', src: {src[:50]}...")