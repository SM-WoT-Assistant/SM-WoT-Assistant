import requests
import json

# Try additional endpoints
endpoints = [
    'https://tomato.gg/tanks/7169/loadouts',
    'https://tomato.gg/tanks/7169/consumables',
    'https://tomato.gg/api/loadouts/is-7',
    'https://tomato.gg/api/tank/is-7/loadouts',
]

for url in endpoints:
    print(f"=== {url} ===")
    try:
        r = requests.get(url, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                print(f"Keys: {list(data.keys())[:15]}")
                # Save
                with open('tomato_api_test.json', 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print("Saved!")
            except:
                print(f"Content (first 500): {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    print()