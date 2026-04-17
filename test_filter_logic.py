#!/usr/bin/env python3
"""Test the filter logic with actual tank_db."""
import json

# Load tank_db
with open("tank_db.json") as f:
    tank_db = json.load(f)

print(f"Total tanks loaded: {len(tank_db)}")

# Simulate filter values
def _normalize_nation(nation_value):
    if nation_value is None:
        return ""
    return str(nation_value).strip().lower()

def _normalize_tier(tier_value):
    try:
        return int(tier_value)
    except:
        return None

def _normalize_class(class_value):
    if class_value is None:
        return ""
    return str(class_value).strip().upper()

# Test: simulate clicking "USA" nation filter
nation_filters = {
    "USA": {"active": True},  # Only USA active
    "USSR": {"active": False},
    "Germany": {"active": False},
    "France": {"active": False},
    "UK": {"active": False},
    "China": {"active": False},
    "Japan": {"active": False},
    "Czech": {"active": False},
    "Poland": {"active": False},
    "Sweden": {"active": False},
    "Italy": {"active": False},
}

# Build active nation set (same as _active_filter_values)
active_n = {_normalize_nation(n) for n, v in nation_filters.items() if v["active"]}
print(f"\nActive filters: {active_n}")

# Count matching tanks
matching = 0
non_matching = 0
for tag, data in tank_db.items():
    if not isinstance(data, dict):
        continue
    data_nation = _normalize_nation(data.get("nation"))
    
    # This is the logic from refresh_ai_view
    if active_n and data_nation not in active_n:
        non_matching += 1
        continue
    
    matching += 1
    if matching <= 5:  # Show first 5
        print(f"  ✓ {tag}: {data.get('name')} - nation={data.get('nation')} (normalized: {data_nation})")

print(f"\n=== Result ===")
print(f"Matching tanks with USA filter: {matching}")
print(f"Non-matching tanks: {non_matching}")
print(f"Total: {matching + non_matching}")
