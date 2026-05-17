import json

data = json.load(open('tomato_next_data.json', 'r', encoding='utf-8'))
props = data['props']['pageProps']
crew = props.get('crew', {}).get('data', {})

print("=== CREW DATA ===")
print(f"Keys: {crew.keys() if crew else 'None'}")

crew_info = crew.get('crew', [])
print(f"Crew members: {len(crew_info)}")
for i, member in enumerate(crew_info[:2]):
    print(f"\nMember {i+1}:")
    for k, v in member.items():
        print(f"  {k}: {v}")

# Also check equipment data more carefully
print("\n=== EQUIPMENT DATA FULL ===")
equip = props.get('equipment', {}).get('data', {})
print(f"Keys: {equip.keys()}")

# Maybe there's a section for consumables that we missed
for k in equip.keys():
    v = equip[k]
    if isinstance(v, list):
        print(f"  {k}: {len(v)} items")
    elif isinstance(v, dict):
        print(f"  {k}: dict with {len(v)} keys")