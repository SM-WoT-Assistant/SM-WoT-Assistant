import json

data = json.load(open('tomato_next_data.json', 'r', encoding='utf-8'))
props = data['props']['pageProps']

print('=== ALL KEYS IN pageProps ===')
for k in props.keys():
    print(f'  {k}')

print('\n=== LOOKING FOR CONSUMABLES ===')
def search(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if 'consum' in k.lower():
                print(f"FOUND KEY: {path}.{k}")
            search(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:5]):
            search(item, f"{path}[{i}]")

search(props)

print('\n=== CHECK popularSetups STRUCTURE ===')
equip = props.get('equipment', {}).get('data', {})
setups = equip.get('popularSetups', [])
if setups:
    print(f'Found {len(setups)} setups')
    print('First setup:', setups[0])
    print('Setup keys:', setups[0][1].keys() if len(setups) > 0 else 'N/A')