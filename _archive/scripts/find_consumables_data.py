import re
import json

with open('tomato_full_page.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# Look for any JSON structure that has consumables with count/percentage
print('=== SEARCHING FOR CONSUMABLES COUNT DATA ===')

# Try to find patterns like: [["consumable1", {"count": 123}]]
consumable_patterns = [
    r'\["[^"]*repairkit[^"]*"\],\{"count":\d+',
    r'\["[^"]*medkit[^"]*"\],\{"count":\d+',
    r'\["[^"]*ration[^"]*"\],\{"count":\d+',
    r'\["[^"]*extinguisher[^"]*"\],\{"count":\d+',
]

for pattern in consumable_patterns:
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f'\nFound pattern: {pattern[:40]}')
        for m in matches[:5]:
            print(f'  {m[:100]}')

# Alternative - look for any array with consumable names and numbers
print('\n=== LOOKING FOR CONSUMABLES ARRAYS ===')
# Find any array that contains both consumable name and a number
arrays_with_kits = re.findall(r'\[[^\]]*(?:repairkit|medkit|ration|extinguisher)[^\]]*\]', html, re.IGNORECASE)
print(f'Found {len(arrays_with_kits)} arrays with consumable names')
for a in arrays_with_kits[:10]:
    print(f'  {a[:150]}')

# Look for any "consumables" key in any JSON
print('\n=== LOOKING FOR CONSUMABLES KEY ===')
consumables_keys = re.findall(r'"consumables"\s*:\s*\{[^}]+\}', html, re.IGNORECASE)
print(f'Found {len(consumables_keys)} consumables keys')
for k in consumables_keys[:5]:
    print(f'  {k[:200]}')