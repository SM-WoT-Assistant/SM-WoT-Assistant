import sys
import time
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(15)

# Just get title and URL
print(f"Page title: {driver.title}")
print(f"Current URL: {driver.current_url}")

# Get all text
all_text = ""
try:
    all_text = driver.find_element("tag name", "body").text
except Exception as e:
    print(f"Error getting text: {e}")

print(f"\nTotal text length: {len(all_text) if all_text else 0}")

# Save to file
if all_text:
    with open('tomato_all_text.txt', 'w', encoding='utf-8') as f:
        f.write(all_text)
    print("Saved to tomato_all_text.txt")

# Search
if all_text:
    for line in all_text.split('\n'):
        line = line.strip()
        if line and any(w in line for w in ['Repair', 'Medkit', 'Extinguisher', 'Ration']) and '%' in line:
            print(f"  {line[:150]}")

driver.quit()