import sys
import time
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()

# Enable network logging
driver.execute_cdp_cmd('Network.enable', {})

# Collect network requests
requests_log = []

def handle_request(req):
    requests_log.append(req)

# Use performance logging instead
driver.get(url)
time.sleep(15)  # Wait longer for everything to load

# Get all performance logs
logs = driver.get_log('browser')
print(f"\n=== BROWSER LOGS (first 20) ===")
for log in logs[:20]:
    msg = log.get('message', '')
    if 'error' not in msg.lower() and 'warning' not in msg.lower():
        print(f"  {msg[:150]}")

# Get the page source after full load
html = driver.page_source

# Save full HTML
with open('tomato_is7_full_loaded.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("\nSaved full HTML")

# Now check if percentages are present
print("\n=== CHECKING FOR PERCENTAGES WITH CONSUMABLES ===")
import re
for name in ['Repair Kit', 'First Aid Kit', 'Extinguisher', 'Rations']:
    pattern = rf'{re.escape(name)}.{{0,100}}\d+\.?\d+%'
    matches = re.findall(pattern, html, re.IGNORECASE)
    print(f"  {name}: {len(matches)} matches")
    if matches:
        for m in matches[:2]:
            clean = re.sub(r'<[^>]+>', ' ', m)
            clean = re.sub(r'\s+', ' ', clean).strip()
            print(f"    {clean[:150]}")

# Check for any new network requests
print("\n=== CHECKING NETWORK REQUESTS ===")
for req in requests_log:
    print(f"  {req}")

driver.quit()