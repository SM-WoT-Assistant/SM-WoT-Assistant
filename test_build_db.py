#!/usr/bin/env python3
"""Test tank database building without GUI."""
import sys
import json
sys.path.insert(0, '.')

# Remove tank_db.json to force rebuild
import os
if os.path.exists("tank_db.json"):
    os.remove("tank_db.json")
    print("[TEST] Deleted old tank_db.json for fresh build")

# Test TankExtractor.build_database()
from tank_extractor import TankExtractor

try:
    with open("settings.json") as f:
        config = json.load(f)
except:
    config = {}

wot_path = config.get("wot_path", "")
print(f"[TEST] WoT path: {wot_path}")

extractor = TankExtractor(wot_path)
print("[TEST] Running build_database()...")
result = extractor.build_database()

print(f"[TEST] build_database() returned: {result}")

# Check final result
if os.path.exists("tank_db.json"):
    with open("tank_db.json") as f:
        db = json.load(f)
    print(f"[TEST] Final tank_db.json: {len(db)} tanks saved")
else:
    print("[TEST] tank_db.json not created")
