import json

data = json.load(open('tomato_next_data.json', 'r', encoding='utf-8'))
props = data['props']['pageProps']

# Print all keys with their types and sizes
print("=== ALL pageProps ENTRIES ===")
for k, v in props.items():
    if isinstance(v, dict):
        print(f"{k}: dict with {len(v)} keys")
    elif isinstance(v, list):
        print(f"{k}: list with {len(v)} items")
    else:
        print(f"{k}: {type(v).__name__}")

# Look deeper - maybe consumables are in some nested structure
print("\n=== SEARCH FOR 'consumable' KEY (not in key name, but anywhere) ===")
def find_consumable(obj, path="", depth=0):
    if depth > 4:
        return
    if isinstance(obj, dict):
        # Check values
        for k, v in obj.items():
            if isinstance(v, str) and 'repairkit' in v.lower() or 'medkit' in v.lower() or 'extinguisher' in v.lower() or 'ration' in v.lower():
                print(f"FOUND at {path}.{k}: {v}")
            find_consumable(v, f"{path}.{k}", depth+1)
    elif isinstance(obj, list) and obj:
        if isinstance(obj[0], dict):
            for i, item in enumerate(obj[:3]):
                find_consumable(item, f"{path}[{i}]", depth+1)

find_consumable(props)