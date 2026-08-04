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
time.sleep(10)

# Check localStorage
print("\n=== LOCAL STORAGE ===")
js_code = """
(function() {
    var keys = [];
    for (var i = 0; i < localStorage.length; i++) {
        keys.push(localStorage.key(i));
    }
    return keys;
})()
"""
keys = driver.execute_script(js_code)
print(f"LocalStorage keys: {keys}")

# Check specific keys
for key in keys[:10]:
    value = driver.execute_script(f"return localStorage.getItem('{key}')")
    if value and ('consum' in value.lower() or 'repair' in value.lower()):
        print(f"\nKey '{key}' has consumables data:")
        print(value[:500])

# Also check sessionStorage
print("\n=== SESSION STORAGE ===")
js_session = """
(function() {
    var keys = [];
    for (var i = 0; i < sessionStorage.length; i++) {
        keys.push(sessionStorage.key(i));
    }
    return keys;
})()
"""
s_keys = driver.execute_script(js_session)
print(f"SessionStorage keys: {s_keys}")

driver.quit()