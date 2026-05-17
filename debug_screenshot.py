from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

# Wait for page to load
time.sleep(15)

# Scroll to load all content
print("Scrolling...")
for i in range(3):
    driver.execute_script("window.scrollTo(0, {});".format((i+1) * 800))
    time.sleep(2)

# Take screenshot
driver.save_screenshot("debug_page.png")
print("Screenshot saved to debug_page.png")

# Try to find element with specific class from user selector
print("\n=== Looking for tableComponents element ===")
try:
    # Try to find using CSS selector from user
    elem = driver.find_element(By.CSS_SELECTOR, ".tableComponents__TableContainer-sc-6483777a-2")
    print(f"Found element!")
    print(f"Tag: {elem.tag_name}")
    print(f"Text: {elem.text[:500]}")
except Exception as e:
    print(f"Not found: {e}")

# Try to find by partial class name
print("\n=== Looking for elements with 'TableContainer' ===")
try:
    elements = driver.find_elements(By.CSS_SELECTOR, "[class*='TableContainer']")
    for i, el in enumerate(elements[:5]):
        print(f"{i}: {el.tag_name} - {el.get_attribute('class')[:100]}")
except Exception as e:
    print(f"Error: {e}")

driver.quit()
print("\nDone")