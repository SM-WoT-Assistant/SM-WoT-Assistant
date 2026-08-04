# Tank Slots Database - Documentation

## Overview
Created comprehensive database of all 1264 tanks from WoT EU client with slot information.

## Files Created

### 1. tank_slots_full.json
Main database with full information for each tank.

**Structure:**
```json
{
  "tank_id": {
    "name_english": "IS-7",
    "crew_roles": ["commander", "gunner", "driver", "loader", "loader"],
    "equipment_slots": 2,
    "consumable_slots": ["6", "6", "6", "7", "8", "8", "8"],
    "available_equipment": ["camouflageNet", "additionalInvisibilityDevice", ...],
    "has_post_progression": true,
    "post_progression_tree": "role_HT_break",
    "field_mod_name": "Heavy Tank Breakthrough",
    "nation": "ussr"
  }
}
```

### 2. tank_slots_db.json (simpler version)
Basic slot information without available equipment list.

## Field Descriptions

| Field | Description | Values |
|-------|-------------|--------|
| `name_english` | Tank name in English | "IS-7", "T-34", etc. |
| `crew_roles` | Crew positions | commander, gunner, driver, loader, radioman |
| `equipment_slots` | Number of equipment slots | 0, 1, 2, 3 |
| `consumable_slots` | Consumable slot types | "6"=MedKit, "7"=RepairKit, "8"=Extinguisher |
| `available_equipment` | Equipment types allowed | camouflageNet, additionalInvisibilityDevice, etc. |
| `has_post_progression` | Has field modifications | true/false |
| `post_progression_tree` | Field mod tree name | role_HT_break, role_MT_universal, etc. |
| `field_mod_name` | Human-readable field mod | "Heavy Tank Breakthrough" |
| `nation` | Tank nation | ussr, usa, germany, uk, france, china, etc. |

## Consumable Slot Types

| Code | Consumable Type |
|------|-----------------|
| 6 | MedKit (First Aid Kit) |
| 7 | Repair Kit |
| 8 | Fire Extinguisher |

## Equipment Slot Types

| Count | Meaning |
|-------|---------|
| 0 | No equipment slots (special vehicles) |
| 1 | 1 slot (some light tanks) |
| 2 | 2 slots (most tanks) |
| 3 | 3 slots (some tanks) |

## Field Modification Types

| Tree Name | English Name |
|-----------|---------------|
| role_HT_break | Heavy Tank Breakthrough |
| role_HT_sniper | Heavy Tank Sniper |
| role_MT_universal | Medium Tank Universal |
| role_MT_sniper | Medium Tank Sniper |
| role_LT_universal | Light Tank Universal |
| role_LT_scout | Light Tank Scout |
| role_TD_sniper | Tank Destroyer Sniper |
| role_TD_assault | Tank Destroyer Assault |
| role_SPG_sniper | SPG Sniper |
| role_SPG_burst | SPG Burst |

## Available Equipment Types

From `optDevsOverrides` in vehicle XML:
- camouflageNet
- deluxeCamouflageNet
- additionalInvisibilityDevice
- deluxeAdditionalInvisibilityDevice
- trophyBasicAdditionalInvisibilityDevice
- trophyUpgradedAdditionalInvisibilityDevice
- invisibilityBonus (attribute, not equipment)

## Usage Example

```python
import json

with open('tank_slots_full.json', 'r') as f:
    tanks = json.load(f)

# Get IS-7 data
is7 = tanks['R45_IS-7']
print(f"Name: {is7['name_english']}")
print(f"Equipment slots: {is7['equipment_slots']}")
print(f"Crew: {is7['crew_roles']}")
print(f"Field mod: {is7['field_mod_name']}")
```

## Statistics

- Total tanks: 1264
- By nation:
  - Germany: 234
  - USA: 190
  - USSR: 230
  - UK: 152
  - France: 128
  - China: 85
  - Sweden: 56
  - Poland: 44
  - Czech: 42
  - Italy: 38
  - Japan: 65

- Equipment slots distribution:
  - 0 slots: 36 tanks
  - 1 slot: 57 tanks
  - 2 slots: 994 tanks
  - 3 slots: 177 tanks

- Tanks with field modifications: 336

## Source Files

- Source decoded XML: `D:\!WORK\WOT\WOTtraner\WORK\WoT_Assistant_4.0\tmp\tth_work\`
- Original scripts.pkg: `C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg`

## Notes

- Tank names extracted from decoded vehicle XML files
- Some tank names are approximated based on ID patterns
- Post progression (field mods) available for 336 tanks at tier 8+
- Equipment availability shows which equipment categories can be installed