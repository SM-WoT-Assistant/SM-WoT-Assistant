import json

with open('tank_db.json', encoding='utf-8') as f:
    db = json.load(f)

for tag, data in db.items():
    name = data.get('name', '')
    if '140' in name or '430' in name:
        print(tag + ': ' + name + ' -> ' + data.get('icon', ''))
