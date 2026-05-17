import re

print("Starting...")
with open('tomato_scroll.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# Search for "consumables" as a key in JSON
print("=== SEARCHING FOR 'consumables' KEY ===")
pattern = r'"consumables"\s*:'
matches = list(re.finditer(pattern, html, re.IGNORECASE))
print(f"Found {len(matches)} 'consumables:' patterns")

for i, match in enumerate(matches[:5]):
    start = max(0, match.start() - 50)
    end = match.end() + 200
    context = html[start:end]
    print(f"\nMatch {i+1}:")
    print(f"  Context: {context}")

# Also search for patterns that look like consumable data
print("\n=== SEARCHING FOR REPAIR KIT WITH PERCENTAGE ===")
pattern2 = r'repair[^\s]{0,30}\d{2}\.\d{2}%'
matches2 = re.findall(pattern2, html, re.IGNORECASE)
print(f"Found {len(matches2)} matches")
for m in matches2[:5]:
    print(f"  {m[:50]}")

# Try finding the actual data section
print("\n=== LOOKING FOR LOADOUT STRUCTURE ===")
loadout_patterns = [
    r'"loadouts"\s*:\s*\{',
    r'"popularSetups"\s*:\s*\[',
    r'"consumables"\s*:\s*\[',
]
for p in loadout_patterns:
    matches = re.findall(p, html)
    print(f"Pattern '{p}': {len(matches)} matches")