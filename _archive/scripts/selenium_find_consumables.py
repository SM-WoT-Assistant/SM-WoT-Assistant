import sys
import time
import re
import json
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()
driver.get(url)
time.sleep(10)

# Get page source
html = driver.page_source

# Look for JSON data in scripts
print("\n=== LOOKING FOR CONSUMABLES IN SCRIPTS ===")

# Find script tags with data
script_pattern = r'<script[^>]*>(.*?)</script>'
scripts = re.findall(script_pattern, html, re.DOTALL)

for i, script in enumerate(scripts[:20]):
    if 'consumable' in script.lower() or 'consumables' in script.lower():
        print(f"\n--- Script {i} has consumables ---")
        # Try to find JSON
        if '{' in script:
            # Look for JSON-like structure
            try:
                # Find JSON in script
                json_match = re.search(r'\{[^{}]*consumable[^{}]*\}', script, re.DOTALL)
                if json_match:
                    print(f"Found JSON: {json_match.group()[:500]}")
            except:
                pass
            # Show context
            idx = script.lower().find('consumable')
            if idx >= 0:
                print(f"Context: {script[max(0,idx-30):idx+100]}")

# Also try to find in page source directly
print("\n=== LOOKING FOR CONSUMABLES IN HTML ===")
# Find the section
idx = html.lower().find('consumables')
if idx >= 0:
    print(f"Found at position {idx}")
    print(f"HTML context:\n{html[idx:idx+500]}")

driver.quit()