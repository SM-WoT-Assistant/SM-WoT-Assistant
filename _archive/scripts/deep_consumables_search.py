import re
import json

with open('tomato_is7_with_interaction.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Look for Consumables section specifically
print("=== FINDING CONSUMABLES SECTION IN HTML ===")
idx = html.lower().find('consumables')
if idx >= 0:
    section = html[idx:idx+3000]
    print(section[:1500])

# Look for any data in script tags that might contain consumables with percentages
print("\n=== SEARCHING IN SCRIPTS ===")
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
for i, script in enumerate(scripts):
    if 'repairkit' in script.lower() or 'medkit' in script.lower():
        print(f"\nScript {i} has consumable data:")
        # Try to find JSON-like data
        matches = re.findall(r'\{[^{}]*\}', script, re.DOTALL)
        for m in matches[:3]:
            if 'repairkit' in m.lower() or 'medkit' in m.lower():
                print(f"  {m[:300]}")

# Look for any data attributes that might contain percentages
print("\n=== LOOKING FOR DATA ATTRIBUTES ===")
data_attrs = re.findall(r'data-[a-z-]+="[^"]*"', html)
consumable_attrs = [a for a in data_attrs if 'kit' in a.lower() or 'medkit' in a.lower() or 'repair' in a.lower() or 'ration' in a.lower()]
print(f"Found {len(consumable_attrs)} consumable-related data attributes")
for a in consumable_attrs[:10]:
    print(f"  {a}")

# Try to find any JSON that might contain consumable usage data
print("\n=== LOOKING FOR JSON STRINGS WITH PERCENTAGES ===")
json_patterns = [
    r'"(repairkit|medkit|extinguisher|ration)[^"]*":\s*\d+\.?\d*',
    r'(repairkit|medkit|extinguisher|ration)[^}]*\d+\.\d+%',
]
for pattern in json_patterns:
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f"Pattern '{pattern}': {matches[:5]}")

# Look for any element that contains both name and percentage
print("\n=== LOOKING FOR ELEMENTS WITH NAME AND PERCENTAGE ===")
# Find any text that has both a consumable name and a percentage within 200 chars
for name in ['Repair Kit', 'First Aid', 'Extinguisher', 'Rations', 'Kit']:
    pattern = rf'{re.escape(name)}.{{0,200}}\d+\.?\d+%'
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f"\n{name}: {len(matches)} matches")
        for m in matches[:3]:
            clean = re.sub(r'<[^>]+>', ' ', m)
            clean = re.sub(r'\s+', ' ', clean).strip()
            print(f"  {clean[:150]}")