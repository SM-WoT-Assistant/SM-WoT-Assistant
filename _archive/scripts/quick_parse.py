import re
import json

print("Starting...")
with open('tomato_scroll.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# Find script with consumable data
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"Found {len(scripts)} scripts")

for i, script in enumerate(scripts):
    if 'consumable' in script.lower() and 'repair' in script.lower():
        print(f"Script {i} has consumable data")

        # Find JSON
        if '{' in script:
            start = script.find('{')
            # Just get first 50000 chars
            json_str = script[start:start+50000]
            print(f"JSON sample (first 500 chars): {json_str[:500]}")

            # Try to parse
            try:
                data = json.loads(json_str)
                props = data.get('props', {}).get('pageProps', {})
                print(f"\npageProps keys: {list(props.keys())[:15]}")

                # Save
                with open('tomato_consumables_data.json', 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print("Saved!")
            except Exception as e:
                print(f"Parse error: {e}")
            break

print("Done")