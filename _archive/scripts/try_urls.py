import sys
import time
import re
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)

# Try different URL patterns
urls_to_try = [
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU/loadouts",
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/loadouts",
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU?tab=loadouts",
    f"https://tomato.gg/loadouts/{tank_id}",
    f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU/analytics",
]

for url in urls_to_try:
    print(f"\n=== TRYING: {url} ===")
    driver = create_driver()
    try:
        driver.get(url)
        time.sleep(10)
        text = driver.find_element("tag name", "body").text
        print(f"Text length: {len(text)}")
        print(f"URL stayed: {driver.current_url}")

        # Save if we got content
        if len(text) > 3000:
            filename = f'tomato_url_{tank_id}.html'.replace(':', '_')
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"Saved! Content has: {text[:500]}")

            # Search for consumables
            for name in ['Repair Kit', 'First Aid', 'Extinguisher']:
                if name in text and '%' in text:
                    print(f"  FOUND: {name}")

        if len(text) > 5000:
            break  # Found a working URL

    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()
        time.sleep(2)