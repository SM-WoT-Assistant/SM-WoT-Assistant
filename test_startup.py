#!/usr/bin/env python3
"""Simulate main.py startup without GUI to check for errors."""
import sys
import os
sys.path.insert(0, '.')

import json

try:
    with open("settings.json") as f:
        config = json.load(f)
except:
    config = {}

print("[STARTUP] Loading tank databases...")
try:
    if os.path.exists("tank_db.json"):
        with open("tank_db.json") as f:
            tank_db = json.load(f)
        print(f"[STARTUP] ✓ tank_db.json loaded: {len(tank_db)} tanks")
    
    if os.path.exists("tank_tth.json"):
        with open("tank_tth.json") as f:
            tank_tth = json.load(f)
        print(f"[STARTUP] ✓ tank_tth.json loaded: {len(tank_tth)} records")
except Exception as e:
    print(f"[STARTUP] ✗ Database load error: {e}")

print("\n[STARTUP] Complete!")
