import os, json, re

db = json.load(open('tank_db.json', encoding='utf-8'))
for nation in os.listdir('extracted_data'):
    list_path = os.path.join('extracted_data', nation, 'list.xml')
    if not os.path.exists(list_path): continue
    
    with open(list_path, "r", encoding="utf-8", errors="ignore") as f:
        xml_text = f.read().strip()
    
    xml_text = re.sub(r'<xmlns:xmlref>.*?</xmlns:xmlref>', '', xml_text, flags=re.DOTALL)
    if xml_text.startswith("<"):
        xml_text = re.sub(r'^<[^>]+>', '<root>', xml_text, count=1)
        xml_text = re.sub(r'</[^>]+>\s*$', '</root>', xml_text)

    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text)
        for tank in root:
            tag = tank.tag
            if tag in db:
                is_premium = False
                price_node = tank.find('price')
                tags_node = tank.find('tags')
                
                # Check for gold price
                if price_node is not None:
                    if 'gold' in ET.tostring(price_node).decode().lower():
                        is_premium = True
                
                # Secret tanks, earn_crystals, etc. usually indicates rewards (often considered premium by UI)
                # But actual 'premiumIGR', 'special' are better
                tags = ""
                if tags_node is not None and tags_node.text:
                    tags = tags_node.text.lower()
                    if 'premium' in tags or 'special' in tags:
                        is_premium = True
                
                db[tag]['is_premium'] = is_premium
    except:
        pass

with open('tank_db.json', 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=4)
print("tank_db.json patched with is_premium!")
