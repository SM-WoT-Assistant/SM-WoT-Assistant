import sys
import json
sys.path.insert(0, '.')
from tomato_scraper import scrape_tank_loadouts

print("=== SCRAPING IS-7 FROM TOMATO.GG ===")
result = scrape_tank_loadouts('R45_IS-7')

if result:
    with open('tomato_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("Result saved to tomato_result.json")
    print("\n--- CONSUMABLES ---")
    if result.get('data'):
        print(result['data'].get('consumables', []))
else:
    print("No result returned")