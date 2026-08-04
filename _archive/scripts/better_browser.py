import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

tank_id = '7169'
tank_slug = 'is-7'

# More browser options to avoid detection
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

service = Service()
driver = webdriver.Chrome(service=service, options=chrome_options)

# Remove webdriver flag
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
    """
})

url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"
print(f"Loading: {url}")

try:
    driver.get(url)
    time.sleep(15)  # Wait longer for React to load

    # Check page title
    print(f"Title: {driver.title}")
    
    # Get text
    body = driver.find_element(By.TAG_NAME, "body")
    text = body.text
    print(f"Text length: {len(text)}")
    
    # Find all sections - look at HTML structure
    print("\n=== LOOKING FOR ALL SECTIONS ===")
    sections = driver.find_elements(By.CSS_SELECTOR, "h2")
    for sec in sections:
        try:
            t = sec.text.strip()
            if t:
                print(f"  Section: {t[:50]}")
        except:
            pass

    # Save regardless
    html = driver.page_source
    with open('tomato_full_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\nHTML saved: {len(html)} chars")

finally:
    driver.quit()

print("Done")