#!/usr/bin/env python3
"""
add_field_mods.py
Додає інформацію про field modifications до танків
"""
import json, os

# Load existing tank data
with open("tank_slots_full.json", "r", encoding="utf-8") as f:
    tanks = json.load(f)

# Field mods are stored in post_progressionTree - the tree name is the field mod
# These are the standard field modifications by role:
field_mods_by_role = {
    "role_HT_break": "Heavy Tank Breakthrough",
    "role_HT_sniper": "Heavy Tank Sniper", 
    "role_MT_universal": "Medium Tank Universal",
    "role_MT_sniper": "Medium Tank Sniper",
    "role_LT_universal": "Light Tank Universal",
    "role_LT_scout": "Light Tank Scout",
    "role_TD_sniper": "Tank Destroyer Sniper",
    "role_TD_assault": "Tank Destroyer Assault",
    "role_SPG_sniper": "SPG Sniper",
    "role_SPG_burst": "SPG Burst"
}

# Update tanks with field mod names
for tank_id, data in tanks.items():
    tree = data.get("post_progression_tree", "")
    if tree in field_mods_by_role:
        data["field_mod_name"] = field_mods_by_role[tree]
    else:
        data["field_mod_name"] = None

# Save updated
with open("tank_slots_full.json", "w", encoding="utf-8") as f:
    json.dump(tanks, f, ensure_ascii=False, indent=2)

print(f"Updated {len(tanks)} tanks with field mod info")

# Show some examples with field mods
with_field = [(k, v) for k, v in tanks.items() if v.get("field_mod_name")]
print(f"Tanks with field mods: {len(with_field)}")
for k, v in with_field[:3]:
    print(f"  {k}: {v.get('field_mod_name')}")