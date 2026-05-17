import json

data = json.load(open('tomato_next_data.json', 'r', encoding='utf-8'))
props = data['props']['pageProps']

# Check tankData
print("=== tankData ===")
tank_data = props.get('tankData', {})
for k, v in tank_data.items():
    print(f"  {k}: {type(v).__name__}")

# Check tankDetails
print("\n=== tankDetails ===")
tank_details = props.get('tankDetails', {})
for k, v in tank_details.items():
    print(f"  {k}: {type(v).__name__}")

# Try to find in more places - maybe in a different format
print("\n=== FULL SEARCH FOR 'repairkit' ===")
def search_all(obj, path="", depth=0):
    if depth > 6:
        return
    try:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    if 'repairkit' in v.lower() or 'medkit' in v.lower():
                        print(f"  {path}.{k} = {v}")
                search_all(v, f"{path}.{k}", depth+1)
        elif isinstance(obj, list) and obj and isinstance(obj[0], str):
            for s in obj:
                if isinstance(s, str) and ('repairkit' in s.lower() or 'medkit' in s.lower()):
                    print(f"  {path} = {obj}")
    except:
        pass

search_all(props)