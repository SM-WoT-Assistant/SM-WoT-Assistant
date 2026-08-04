import re

with open('tomato_is7_full.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the Consumables section in HTML
print("=== FINDING CONSUMABLES SECTION ===")

# Find all sections with 'consum' in them
idx = html.lower().find('consumable')
if idx >= 0:
    print(f"Found 'consumable' at position {idx}")
    section = html[max(0,idx-200):idx+2000]
    print("\n=== CONSUMABLES SECTION HTML (first 2000 chars) ===")
    print(section[:2000])

# Also look for any percentage data
print("\n=== ALL PERCENTAGE VALUES IN HTML ===")
percentages = re.findall(r'\d+\.?\d*%', html)
unique_pcts = sorted(set(percentages), key=lambda x: float(x.replace('%','')), reverse=True)
print(f"Total unique percentages: {len(unique_pcts)}")
print("Top 30:", unique_pcts[:30])

# Search for data that might be in JSON format
print("\n=== LOOKING FOR JSON WITH CONSUMABLES ===")
json_patterns = [
    r'"consumables"\s*:\s*\[.*?\]',
    r'"consumable".*?\d+\.\d+',
]

for pattern in json_patterns:
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f"Pattern {pattern}: {len(matches)} matches")
        for m in matches[:3]:
            print(f"  {m[:200]}")