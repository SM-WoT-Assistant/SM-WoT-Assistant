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

# Try JavaScript to find any data about consumable usage
print("\n=== JAVASCRIPT: SEARCH FOR CONSUMABLE DATA ===")

js_code = """
(function() {
    var results = [];

    // Look for any element that contains both consumable name and percentage
    var allElements = document.querySelectorAll('div, span, td, tr');
    for (var i = 0; i < allElements.length; i++) {
        var text = allElements[i].innerText || '';
        if ((text.includes('Repair Kit') || text.includes('First Aid') ||
             text.includes('Extinguisher') || text.includes('Ration')) &&
            text.includes('%')) {
            results.push(text.trim());
        }
    }

    return {
        textMatches: results.slice(0, 10)
    };
})()
"""

result = driver.execute_script(js_code)
print(f"Text matches: {len(result.get('textMatches', []))}")
for m in result.get('textMatches', []):
    print(f"  {m[:200]}")

driver.quit()