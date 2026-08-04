import json
import re

# Load the full page data from Selenium
with open('tomato_is7_full.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find __NEXT_DATA__ script
print("=== LOOKING FOR __NEXT_DATA__ ===")
match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if match:
    next_data = json.loads(match.group(1))
    props = next_data.get('props', {}).get('pageProps', {})

    # Print all keys
    print(f"\nAll keys in pageProps: {list(props.keys())}")

    # Search deeper for any consumable-related data
    print("\n=== DEEP SEARCH FOR CONSUMABLES ===")

    def search_for_consumables(obj, path="", depth=0):
        if depth > 4:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if 'consum' in k.lower():
                    print(f"KEY FOUND: {path}.{k}")
                    print(f"  Value: {str(v)[:200]}")
                search_for_consumables(v, f"{path}.{k}", depth+1)
        elif isinstance(obj, list) and obj:
            if isinstance(obj[0], dict):
                # Check first item keys
                first = obj[0]
                if isinstance(first, dict):
                    keys = list(first.keys())
                    if any('consum' in k.lower() for k in keys):
                        print(f"LIST with consumables keys: {path}, keys: {keys}")

    search_for_consumables(props)
else:
    print("No __NEXT_DATA__ found")

# Also look for any data in window variable
print("\n=== LOOKING FOR WINDOW DATA ===")
window_match = re.search(r'window\.(\w+)\s*=\s*({.*?});', html)
if window_match:
    print(f"Found window variable: {window_match.group(1)}")

# Look for any JSON in scripts
print("\n=== LOOKING FOR JSON IN SCRIPTS ===")
script_matches = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
for i, script in enumerate(script_matches):
    if 'consum' in script.lower() and '{' in script:
        # Find JSON-like content
        print(f"Script {i}: Found 'consum'")
        # Try to extract JSON
        try:
            if '{' in script:
                start = script.find('{')
                # Find matching brace
                depth = 0
                for j in range(start, len(script)):
                    if script[j] == '{': depth += 1
                    elif script[j] == '}': depth -= 1
                    if depth == 0:
                        json_str = script[start:j+1]
                        data = json.loads(json_str)
                        print(f"  JSON keys: {list(data.keys())[:10]}")
                        break
        except:
            pass