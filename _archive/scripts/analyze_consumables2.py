import re

with open('tomato_full_page.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# Find all consumable buttons (img alt attributes)
print('=== CONSUMABLE BUTTONS ===')
consumable_buttons = re.findall(r'<img alt="([^"]+)"', html)
consumables = [c for c in consumable_buttons if 'kit' in c.lower() or 'extinguisher' in c.lower() or 'ration' in c.lower() or 'fuel' in c.lower()]
print(f'Found: {consumables}')

# Find any data structure that might have usage counts
print('\n=== SEARCHING FOR USAGE DATA ===')

# Look for any number patterns near consumable names
for name in consumables:
    # Look for patterns like: name followed by some number
    pattern = name + r'[^<]{0,50}\d+'
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f'\n{name}:')
        for m in matches[:3]:
            print(f'  {m[:100]}')

# Search for any structure like: {name: count, percentage: x}
print('\n=== LOOKING FOR ANY COUNT/PERCENTAGE DATA ===')
# Find all occurrences of "count" in the HTML
count_occurrences = re.findall(r'.{0,30}count.{0,50}', html)
count_relevant = [c for c in count_occurrences if 'repair' in c.lower() or 'medkit' in c.lower() or 'ration' in c.lower() or 'kit' in c.lower()]
print(f'Found {len(count_relevant)} relevant count occurrences')
for c in count_relevant[:10]:
    print(f'  {c[:100]}')