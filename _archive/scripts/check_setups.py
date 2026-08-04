import json

data = json.load(open('tomato_next_data.json', 'r', encoding='utf-8'))
props = data['props']['pageProps']

print('=== CHECK popularSetups DETAILED ===')
equip = props.get('equipment', {}).get('data', {})
setups = equip.get('popularSetups', [])

# Show first 5 setups with all details
for i, setup in enumerate(setups[:5]):
    items = setup[0]
    stats = setup[1]
    print(f'\nSetup {i+1}:')
    print(f'  Items: {items} (count: {len(items)})')
    print(f'  Stats: {stats}')

# Check if any setup has more than 3 items
print('\n=== CHECK FOR MORE THAN 3 ITEMS ===')
for i, setup in enumerate(setups[:20]):
    items = setup[0]
    if len(items) > 3:
        print(f'Setup {i+1} has {len(items)} items: {items}')

# Check all unique item names across all setups
print('\n=== ALL UNIQUE ITEMS IN SETUPS ===')
all_items = set()
for setup in setups:
    for item in setup[0]:
        all_items.add(item)
print(sorted(all_items))