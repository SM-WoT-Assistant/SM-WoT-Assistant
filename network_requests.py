import sys
import time
import json
sys.path.insert(0, '.')
from tomato_selenium import create_driver, get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

print(f"Loading: {url}")
driver = create_driver()

# Enable performance logging
driver.execute_cdp_cmd('Network.enable', {})

# Collect requests
requests = []
def handle_request(req):
    requests.append(req)

driver.get(url)
time.sleep(10)

# Get logged requests
logs = driver.get_log('performance')
print(f"\n=== NETWORK REQUESTS ===")
for log in logs[:30]:
    try:
        msg = json.loads(log['message'])
        if msg.get('message', {}).get('method') == 'Network.requestWillBeSent':
            url = msg['message']['params'].get('request', {}).get('url', '')
            if 'api' in url.lower() or 'loadout' in url.lower() or 'consumable' in url.lower():
                print(f"  {url}")
    except:
        pass

driver.quit()