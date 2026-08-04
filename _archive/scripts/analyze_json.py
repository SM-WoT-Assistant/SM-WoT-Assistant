import re
import json

with open('tomato_scroll.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# Find script 173
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
script = scripts[173]

# Find JSON
start = script.find('{')
depth = 0
json_str = ''
for i in range(start, len(script)):
    c = script[i]
    if c == '{':
        depth += 1
    elif c == '}':
        depth -= 1
    json_str += c
    if depth == 0:
        break

data = json.loads(json_str)
props = data.get('props', {}).get('pageProps', {})

print('=== ALL KEYS IN pageProps ===')
for k in props.keys():
    print(f'  {k}')

# Search deeper
print('\n=== SEARCHING FOR CONSUMABLES ===')
def search(obj, path='', depth=0):
    if depth > 4:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if 'consum' in k.lower():
                print(f'FOUND: {path}.{k}')
                print(f'  Value: {str(v)[:500]}')
            search(v, f'{path}.{k}', depth+1)

search(props)

# Also check equipment which might contain consumables
print('\n=== CHECKING EQUIPMENT ===')
equip = props.get('equipment', {})
if equip:
    print(f'Equipment keys: {list(equip.keys())[:10]}')
    equip_data = equip.get('data', {})
    if equip_data:
        print(f'Equipment data keys: {list(equip_data.keys())[:10]}')

# Save the JSON for reference
with open('tomato_loadouts_json.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print('\nSaved JSON to tomato_loadouts_json.json')