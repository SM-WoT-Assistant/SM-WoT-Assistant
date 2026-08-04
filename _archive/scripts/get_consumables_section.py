import sys
import time
import re
import json
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info
from selenium.webdriver.common.by import By

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(10)

# Find and click on "Consumables" section or tab
print("\n=== LOOKING FOR CONSUMABLES SECTION ===")

# First, let's get all links and try to find "Consumables" navigation
links = driver.find_elements(By.TAG_NAME, "a")
nav_items = []
for link in links:
    try:
        text = link.text.strip()
        href = link.get_attribute("href") or ""
        if text and ('consumable' in text.lower() or '/consumable' in href.lower()):
            nav_items.append((text, href))
    except:
        pass

print(f"Found {len(nav_items)} Consumables-related links:")
for item in nav_items[:10]:
    print(f"  {item[0]}: {item[1]}")

# Let's navigate directly to the Consumables section
# Try URL pattern: /tanks/{id}/{slug}/consumables or similar
consumables_urls = [
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU/consumables",
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU?tab=consumables",
]

for test_url in consumables_urls:
    print(f"\nTrying: {test_url}")
    driver.get(test_url)
    time.sleep(5)
    
    # Check if we're on consumables page
    html = driver.page_source
    if 'consumable' in html.lower():
        # Save the HTML
        with open('tomato_consumables_section.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Saved to tomato_consumables_section.html")
        
        # Search for percentages
        print("\n=== SEARCHING FOR PERCENTAGES ===")
        for word in ['Repair Kit', 'First Aid', 'Extinguisher', 'Rations']:
            pattern = rf'.{{0,100}}{re.escape(word)}.{{0,100}}\d+\.?\d*%'
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                print(f"\n{word} - Found {len(matches)}:")
                for m in matches[:5]:
                    clean = re.sub(r'<[^>]+>', ' ', m)
                    clean = re.sub(r'\s+', ' ', clean).strip()
                    print(f"  {clean[:200]}")
        
        # Check __NEXT_DATA__
        match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            next_data = json.loads(match.group(1))
            props = next_data.get('props', {}).get('pageProps', {})
            print(f"\n__NEXT_DATA__ pageProps keys: {list(props.keys())}")
            
            # Save the JSON
            with open('tomato_consumables_json.json', 'w', encoding='utf-8') as f:
                json.dump(next_data, f, indent=2, ensure_ascii=False)
            print("Saved JSON to tomato_consumables_json.json")
        
        break

driver.quit()