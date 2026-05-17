import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

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

    # Scroll to bottom to load all content
    print("\n=== SCROLLING DOWN ===")
    for i in range(10):
        driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(0.5)

    # Use JavaScript to find and click on element containing "Consumables"
    print("\n=== CLICKING CONSUMABLES VIA JS ===")
    js_click = """
    (function() {
        // Find all elements with Consumables text
        var elements = document.querySelectorAll('h2, h3, div, span, a, button');
        for (var i = 0; i < elements.length; i++) {
            if (elements[i].textContent && elements[i].textContent.includes('Consumables')) {
                console.log('Found: ' + elements[i].tagName + ' - ' + elements[i].textContent.substring(0, 50));
                // Try to find parent button or clickable element
                var parent = elements[i].parentElement;
                while (parent) {
                    if (parent.tagName === 'BUTTON' || parent.getAttribute('role') === 'button') {
                        parent.click();
                        console.log('Clicked parent button!');
                        return true;
                    }
                    parent = parent.parentElement;
                }
            }
        }
        return false;
    })()
    """
    result = driver.execute_script(js_click)
    print(f"JS result: {result}")

    time.sleep(5)

    # Now look for any expandable/collapsible sections
    print("\n=== LOOKING FOR EXPANDABLE SECTIONS ===")
    js_expand = """
    (function() {
        var buttons = document.querySelectorAll('button');
        var found = [];
        for (var i = 0; i < buttons.length; i++) {
            var text = buttons[i].textContent.trim();
            if (text && text.length < 50) {
                found.push(text);
            }
        }
        return found;
    })()
    """
    buttons_text = driver.execute_script(js_expand)
    print(f"Buttons found: {buttons_text[:20]}")

    # Get text content after all interactions
    body = driver.find_element(By.TAG_NAME, "body")
    text = body.text
    
    print(f"\n=== TEXT LENGTH: {len(text)} ===")
    
    # Save
    with open('tomato_final.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)
    with open('tomato_final.txt', 'w', encoding='utf-8', errors='ignore') as f:
        f.write(text)
    print("Saved!")

    # Print all lines with Consumable + %
    print("\n=== CONSUMABLE LINES ===")
    for line in text.split('\n'):
        line = line.strip()
        if 'Consum' in line or 'Repair' in line or 'Kit' in line or 'Extinguisher' in line or 'Ration' in line:
            print(f"  {line[:100]}")

finally:
    driver.quit()

print("Done")