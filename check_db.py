#!/usr/bin/env python3
"""Quick diagnostic to check tank_db.json without running full app."""
import json
import os

tank_db_path = "tank_db.json"

if os.path.exists(tank_db_path):
    with open(tank_db_path, "r", encoding="utf-8") as f:
        db = json.load(f)
    
    print(f"✓ tank_db.json найден - {len(db)} танків")
    if len(db) > 0:
        # Show first 5 tanks
        print("\nПервые 5 танков:")
        for i, (tag, info) in enumerate(list(db.items())[:5]):
            print(f"  {i+1}. {tag}: {info['name']} (Уровень {info['tier']}, {info['nation']})")
    else:
        print("❌ tank_db.json пустой!")
else:
    print("❌ tank_db.json не найден")
