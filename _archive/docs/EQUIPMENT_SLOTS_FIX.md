# Equipment Slots Fix Documentation

## Problem
The script `create_tank_slots_db.py` was incorrectly calculating equipment slots from XML `<supplySlots>` data.

### Original (Wrong) Logic
```python
result["equipment_slots"] = slots.count('1')
```

This only counted '1' in the supplySlots string, missing other equipment slot types (2, 3, 4, 5).

### Examples of Incorrect Calculation
| supplySlots | Old Logic (count '1') | Actual Slots |
|-------------|----------------------|--------------|
| `5 1 1 6 6 6 7 8 8 8` | 2 | 3 |
| `2 1 1 6 6 6 7 8 8 8` | 2 | 3 |
| `4 1 1 6 6 6 7 8 8 8` | 2 | 3 |

## Root Cause Analysis
The `<supplySlots>` XML field contains:
- Equipment slots (codes 1, 2, 3, 4, 5)
- Consumable slots (codes 6, 7, 8)

The first occurrence of 6, 7, or 8 marks the start of consumable slots.

## Correct Logic
Count all numbers BEFORE the first occurrence of 6, 7, or 8:

```python
def count_equipment_slots(supply_slots_str):
    slots = supply_slots_str.strip().split()
    equipment_count = 0
    for s in slots:
        if s in ['6', '7', '8']:
            break
        equipment_count += 1
    return equipment_count
```

### Verification by Tier
According to WoT official documentation:
- Tier I: 0 slots (no equipment)
- Tier II: 1 slot
- Tier III: 2 slots
- Tier IV+: 3 slots

| XML supplySlots | Calculation | Tier | Expected | Result |
|-----------------|-------------|------|----------|--------|
| `1 6 8 8 8` | 1 before 6 | 2 | 1 | ✓ |
| `1 1 6 6 8 8 8` | 2 before 6 | 3 | 2 | ✓ |
| `1 1 1 6 6 6 7 8 8 8` | 3 before 6 | 5+ | 3 | ✓ |
| `5 1 1 6 6 6 7 8 8 8` | 3 before 6 | 8 | 3 | ✓ |
| `2 1 1 6 6 6 7 8 8 8` | 3 before 6 | 8 | 3 | ✓ |

## Files Affected
1. `create_tank_slots_db.py` - Line 37 needs fix
2. `tank_slots_full.json` - needs regeneration
3. `generate_prompt.py` - needs dynamic slot count
4. `generate_prompt_is7.py` - needs update for 3 slots
5. `prompt_is7.txt` - needs regeneration

## Fix Timeline
1. Fix `create_tank_slots_db.py`
2. Run script to regenerate `tank_slots_full.json`
3. Update prompt generators to use dynamic slot count
4. Regenerate prompts with correct slot count