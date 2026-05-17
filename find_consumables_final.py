import re

with open('tomato_scroll.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# Get clean text
all_text = re.sub(r'<[^>]+>', ' ', html)
all_text = re.sub(r'\s+', ' ', all_text)

# Look for any text that contains specific consumable names with percentages
print('=== FINDING CONSUMABLE NAMES WITH PERCENTAGES ===')

# Look for lines that have these exact phrases
phrases = [
    'Small Repair Kit',
    'Large Repair Kit',
    'Small First Aid Kit',
    'Large First Aid Kit',
    'Automatic Fire Extinguisher',
    'Manual Fire Extinguisher',
    'Improved Combat Rations'
]

for phrase in phrases:
    # Find all instances of phrase and check if within 200 chars there's a percentage
    pattern = rf'{re.escape(phrase)}.{{0,200}}?\d+\.?\d+%'
    matches = re.findall(pattern, all_text, re.IGNORECASE)
    if matches:
        print(f'\n{phrase}: {len(matches)} matches')
        for m in matches[:3]:
            print(f'  {m[:150]}')

# Check for any JSON structure that might have consumable data
print('\n=== LOOKING FOR JSON STRUCTURE ===')
# Find any structure that looks like it has consumables
json_like = re.findall(r'\{[^{}]*(?:Repair|Kit|Extinguisher|Ration)[^{}]*\d+\.?\d+[^{}]*\}', html, re.IGNORECASE)
print(f'Found {len(json_like)} JSON-like structures')
for j in json_like[:5]:
    print(f'  {j[:150]}')