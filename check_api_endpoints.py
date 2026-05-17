import requests
import json

tank_id = 7169

endpoints = [
    f"https://tomato.gg/api/tanks/{tank_id}/loadouts",
    f"https://tomato.gg/api/tanks/{tank_id}/consumables",
    f"https://tomato.gg/api/tanks/{tank_id}/loadout-analytics",
    f"https://tomato.gg/api/tanks/{tank_id}/popular-loadouts",
    f"https://tomato.gg/tanks/{tank_id}/is-7/EU/loadouts",
]

for url in endpoints:
    try:
        r = requests.get(url, timeout=10)
        print(f"\n{url}")
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())[:10]}")
            elif isinstance(data, list):
                print(f"  List length: {len(data)}")
    except Exception as e:
        print(f"\n{url}")
        print(f"  Error: {e}")