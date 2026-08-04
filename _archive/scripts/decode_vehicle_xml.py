#!/usr/bin/env python3
"""
decode_vehicle_xml.py - тест парсингу vehicle XML
"""
import os
import xml.etree.ElementTree as ET

def parse_vehicle_for_slots(xml_path):
    if not os.path.exists(xml_path):
        return None
    
    with open(xml_path, 'rb') as f:
        content_bytes = f.read()
    
    # Перевіряємо перші байти
    first_bytes = content_bytes[:4]
    print(f"First bytes: {first_bytes}")
    
    if first_bytes[:2] == b'EN':
        print("File is encoded (ENb format)")
        return None
    
    # Спробуємо як текст
    try:
        content = content_bytes.decode('utf-8')
    except:
        return None
    
    try:
        root = ET.fromstring(content)
    except:
        return None
    
    result = {"equipment_slots": 0, "crew_slots": []}
    
    opt_devs = root.find('.//optDevs')
    if opt_devs is not None:
        result["equipment_slots"] = len(list(opt_devs))
    
    crew = root.findall('.//crew')
    for c in crew:
        role = c.get('role', '')
        if role:
            result["crew_slots"].append(role)
    
    return result

# Test
xml_path = r"D:\!WORK\WOT\WOTtraner\WORK\SETUP S MAPS WoT Assistant_1.00\extracted_data\ussr\R05_KV.xml"
result = parse_vehicle_for_slots(xml_path)
print("Result:", result)