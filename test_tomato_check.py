import sys
sys.path.insert(0, '.')
from tomato_scraper import get_tank_info

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
print(f'Tank: {tank_code}')
print(f'Tomato ID: {tank_id}, Slug: {tank_slug}')
print(f'URL: https://tomato.gg/tanks/{tank_id}/{tank_slug}')

print('\n--- CONS_MAP ---')
from stats_ai import CONS_MAP
for k, v in CONS_MAP.items():
    print(f'  {k} -> {v}')