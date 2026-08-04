import sys
import time
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)

url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU?tab=loadouts"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(10)

# Try scrolling down to trigger lazy loading
print("\n=== SCROLLING TO LOAD CONTENT ===")
for i in range(5):
    driver.execute_script("window.scrollBy(0, 1000);")
    time.sleep(2)
    print(f"Scroll {i+1}")

# Also try clicking on sections to expand them
print("\n=== LOOKING FOR CLICKABLE SECTIONS ===")

# Get all buttons and try clicking ones that might expand data
buttons = driver.find_elements("tag name", "button")
for btn in buttons[:20]:
    try:
        text = btn.text.strip()
        if text and len(text) < 30:
            print(f"Button: {text[:30]}")
            # Try clicking
            btn.click()
            time.sleep(1)
    except:
        pass

# Get HTML source
html = driver.page_source
print(f"\nHTML length: {len(html)}")

# Get text
text = driver.find_element("tag name", "body").text
print(f"Text length after scrolling: {len(text)}")

# Save
with open('tomato_scroll.html', 'w', encoding='utf-8') as f:
    f.write(html)
with open('tomato_scroll.txt', 'w', encoding='utf-8', errors='ignore') as f:
    f.write(text)

print("Saved HTML and text")

# Search for consumables
print("\n=== SEARCHING ===")
for line in text.split('\n')[:50]:
    if any(w in line for w in ['Repair', 'Medkit', 'Extinguisher', 'Ration', 'Equipment']):
        print(f"  {line[:80]}")

driver.quit()