import re
import json

with open('tomato_consumables_section.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f"HTML length: {len(html)}")

# Find all percentages in the HTML
print("\n=== ALL PERCENTAGES ===")
percentages = re.findall(r'\d+\.?\d*%', html)
unique_pcts = sorted(set(percentages), key=lambda x: float(x.replace('%','')), reverse=True)
print(f"Total: {len(percentages)}, Unique: {len(unique_pcts)}")
print("Top 30:", unique_pcts[:30])

# Look for any text around "consumable" or specific consumable names
print("\n=== SEARCHING NEAR CONSUMABLE NAMES ===")

consumable_names = [
    'Small Repair Kit', 'Large Repair Kit',
    'Small First Aid Kit', 'Large First Aid Kit',
    'Automatic Fire Extinguisher', 'Manual Fire Extinguisher',
    'Improved Combat Rations', 'Small First Aid Kit'
]

for name in consumable_names:
    # Look for name followed or preceded by percentage
    pattern = rf'{re.escape(name)}[\s\S{{0,100}}]\d+\.\d+%'
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f"\n{name}:")
        for m in matches[:5]:
            # Clean HTML tags
            clean = re.sub(r'<[^>]+>', ' ', m)
            clean = re.sub(r'\s+', ' ', clean).strip()
            print(f"  {clean[:250]}")

# Also check __NEXT_DATA__
print("\n=== CHECKING __NEXT_DATA__ ===")
match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if match:
    try:
        next_data = json.loads(match.group(1))
        props = next_data.get('props', {}).get('pageProps', {})
        print(f"pageProps is empty: {len(props) == 0}")
        if props:
            print(f"Keys: {list(props.keys())}")
    except Exception as e:
        print(f"Error parsing: {e}")