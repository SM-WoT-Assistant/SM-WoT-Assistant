import json

data = json.load(open('tomato_next_data.json', 'r', encoding='utf-8'))
props = data['props']['pageProps']

print('=== FULL SEARCH FOR CONSUMABLES ===')

# Search everywhere for any mention of consumables-related keywords
keywords = ['consumable', 'repair', 'medkit', 'kit', 'extinguisher', 'ration', 'cola', 'chocolate', 'coffee', 'fuel', 'food']

def deep_search(obj, path="", depth=0):
    if depth > 5:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            lower_k = k.lower()
            # Check key name
            for kw in keywords:
                if kw in lower_k:
                    print(f"KEY: {path}.{k}")
            deep_search(v, f"{path}.{k}", depth+1)
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], str):
            # Check string list values
            for s in obj:
                for kw in keywords:
                    if kw in s.lower():
                        print(f"STRING LIST: {path} = {obj[:5]}")
                        break
        else:
            for i, item in enumerate(obj[:3]):
                deep_search(item, f"{path}[{i}]", depth+1)
    elif isinstance(obj, str):
        for kw in keywords:
            if kw in obj.lower():
                print(f"STRING: {path} = {obj[:80]}")
                break

deep_search(props)

print('\n=== CHECK tankData ===')
tank_data = props.get('tankData', {})
print(f'tankData keys: {tank_data.keys() if tank_data else "None"}')

print('\n=== CHECK tankDetails ===')
tank_details = props.get('tankDetails', {})
print(f'tankDetails: {str(tank_details)[:500]}')