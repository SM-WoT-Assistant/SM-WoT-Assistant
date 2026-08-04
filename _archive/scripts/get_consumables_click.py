import sys
import time
import re
import json
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU?tab=loadouts"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(12)

print("\n=== CLICKING CONSUMABLES TAB ===")
consumables_clicked = False

all_elements = driver.find_elements(By.CSS_SELECTOR, "a, button, span, div")
for elem in all_elements:
    try:
        text = elem.text.strip()
        if text and 'Consumables' in text and len(text) < 20:
            print(f"Found: '{text}'")
            elem.click()
            print("Clicked!")
            time.sleep(8)
            consumables_clicked = True
            break
    except:
        pass

if not consumables_clicked:
    print("Trying JavaScript click...")
    script = """
    const elements = document.querySelectorAll('button, a, span, div');
    for (const el of elements) {
        if (el.textContent.trim() === 'Consumables') {
            el.click();
            return true;
        }
    }
    return false;
    """
    result = driver.execute_script(script)
    print(f"JS click result: {result}")
    time.sleep(8)

html = driver.page_source

print("\n=== SAVING HTML ===")
with open('tomato_consumables_clicked_final.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Saved to tomato_consumables_clicked_final.html")

print("\n=== SEARCHING FOR CONSUMABLES WITH PERCENTAGES ===")
text = driver.find_element("tag name", "body").text

consumable_names = [
    'Repair Kit', 'First Aid Kit', 'Fire Extinguisher', 'Food Rations',
    'Small Repair Kit', 'Large Repair Kit', 'Medkit', 'Antidote',
    'Coffee', 'Chocolate', ' Cola', 'Ice Cream'
]

for name in consumable_names:
    if name in text:
        idx = text.find(name)
        context = text[max(0,idx-30):idx+100]
        if '%' in context:
            print(f"\n{name}:")
            print(f"  {context.strip()}")
        else:
            print(f"Found {name} but no %")

print("\n=== CHECKING __NEXT_DATA__ ===")
match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if match:
    next_data = json.loads(match.group(1))
    props = next_data.get('props', {}).get('pageProps', {})
    print(f"Keys in pageProps: {list(props.keys())}")
    
    if 'consumables' in props:
        print(f"Found consumables in pageProps!")
        print(json.dumps(props['consumables'], indent=2)[:500])

driver.quit()