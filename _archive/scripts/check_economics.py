import json

data = json.load(open('tomato_next_data.json', 'r', encoding='utf-8'))
props = data['props']['pageProps']

print('=== ECONOMICS DATA ===')
econ = props.get('economics', {}).get('data', [])
print(f'Found {len(econ)} items')
for item in econ[:3]:
    print(f'  {item}')

print('\n=== FIELD MODS ===')
fm = props.get('fieldMods', {})
print(f'Keys: {fm.keys()}')
fm_data = fm.get('data', {})
print(f'Data keys: {fm_data.keys() if fm_data else "None"}')