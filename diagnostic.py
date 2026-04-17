#!/usr/bin/env python3
"""Diagnostic check for tank_db and tank_tth without GUI."""
import json
import os

print("=" * 60)
print("DIAGNOSTIC: Tank Database Status")
print("=" * 60)

# Check tank_db.json
if os.path.exists("tank_db.json"):
    with open("tank_db.json") as f:
        db = json.load(f)
    print(f"\n✓ tank_db.json: {len(db)} танків")
    
    # Check nation distribution
    nations = {}
    for v in db.values():
        n = v.get("nation", "Unknown")
        nations[n] = nations.get(n, 0) + 1
    
    print("  Рацион по країнам:")
    for nation, count in sorted(nations.items()):
        print(f"    - {nation}: {count}")
else:
    print("\n✗ tank_db.json не знайдено")

# Check tank_tth.json
if os.path.exists("tank_tth.json"):
    with open("tank_tth.json") as f:
        tth = json.load(f)
    print(f"\n✓ tank_tth.json: {len(tth)} ТТХ записів")
else:
    print("\n✗ tank_tth.json не знайдено")

print("\n" + "=" * 60)
