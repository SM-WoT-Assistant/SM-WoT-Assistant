import requests
import json

# Try tomato.gg API
tank_id = "7169"
server = "EU"

# Try different API endpoints
endpoints = [
    f"https://tomato.gg/api/tanks/{tank_id}/loadouts",
    f"https://tomato.gg/api/tank/{tank_id}",
    f"https://tomato.gg/api/loadouts/{tank_id}",
]

for url in endpoints:
    try:
        r = requests.get(url, timeout=10)
        print(f"\n=== {url} ===")
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            # Save to file
            with open(f'tomato_api_{tank_id}.json', 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("Saved to tomato_api_{tank_id}.json")
    except Exception as e:
        print(f"Error: {e}")