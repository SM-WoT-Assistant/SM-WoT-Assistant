#!/usr/bin/env python3
"""
generate_prompt_is7.py - фінальна версія 2
"""
import json
from datetime import datetime

with open('game_entities_english.json', 'r', encoding='utf-8') as f:
    game_entities = json.load(f)

with open('tank_slots_full.json', 'r', encoding='utf-8') as f:
    tank_slots = json.load(f)

with open('crew_builds.json', 'r', encoding='utf-8') as f:
    crew_builds = json.load(f)

# IS-7 data
is7 = tank_slots['R45_IS-7']
tank_name = "IS-7"
equipment_slot_count = is7['equipment_slots']  # 2
crew_roles = is7['crew_roles']

# Equipment - тільки справжнє обладнання (не витратні!)
EQUIPMENT_PROPER = [
    "Gun Rammer", "Improved Ventilation", "Vertical Stabilizer", "Turbocharger",
    "Improved Hardening", "Low-Noise Exhaust System", "Coated Optics",
    "Binocular Telescope", "Camouflage Net", "Spall Liner", "Modified Configuration",
    "Improved Rotation Mechanisms", "Enhanced Gun Laying Drives", "Improved Aiming",
    "Grousers", "Additional Grousers", "Experimental Turbocharger", "Experimental Hardening",
    "Experimental Optics", "Experimental Fire-Control System", "Experimental Mobility System",
    "Experimental Survival Suite", "Additional Invisibility Device", "Deluxe Camouflage Net",
    "Deluxe Additional Invisibility Device", "Trophy Additional Invisibility Device",
    "Trophy Additional Invisibility Device (Improved)", "Trophy Gun Rammer",
    "Trophy Gun Rammer (Improved)", "Trophy Ventilation", "Trophy Ventilation (Improved)",
    "Trophy Aiming Stabilizer", "Trophy Aiming Stabilizer (Improved)", "Trophy Optics",
    "Trophy Optics (Improved)", "Trophy Modified Configuration", "Trophy Modified Configuration (Improved)",
    "Trophy Improved Rotation Mechanism", "Trophy Improved Rotation Mechanism (Improved)",
    "Trophy Improved Sights", "Trophy Improved Sights (Improved)", "Trophy Turbocharger",
    "Trophy Turbocharger (Improved)", "Trophy Extra Health Reserve", "Trophy Extra Health Reserve (Improved)"
]

# Ammo
ammo_list = ["Armor Piercing (AP)", "Armor Piercing Composite Rigid (APCR)", 
             "High Explosive Anti-Tank (HEAT)", "High Explosive (HE)"]

# Consumables
consumables_list = [
    "Small Repair Kit", "Large Repair Kit", "Small First Aid Kit", "Large First Aid Kit",
    "Manual Fire Extinguisher", "Automatic Fire Extinguisher", "Extra Rations",
    "Case of Cola", "Chocolate", "Pudding and Tea", "Strong Coffee", "Improved Rations",
    "Bread with Lard", "Smoked Lard", "Buchty", "Spaghetti with Meat Sauce", "Onigiri",
    "Coffee with Cinnamon", "Sweet Milk", "Boiled Cabbage", "Roasted Turkey",
    "Chinese Rations", "British Rations", "Japanese Rations", "Czech Rations",
    "Swedish Rations", "Polish Rations", "Italian Rations"
]

# Crew perks
all_perks = [
    "Brothers in Arms", "Repairs", "Concealment", "Firefighting", "Sixteenth Sense",
    "Eagle Eye", "Sound Detection", "Jack of All Trades", "Armorer", "Snap Shot",
    "Designated Target", "Smooth Ride", "Off-Road Driving", "Clutch Braking",
    "Controlled Impact", "Preventative Maintenance", "Safe Stowage", 
    "Adrenaline Rush", "Intuition", "Situational Awareness", "Call for Vengeance",
    "Signal Boosting", "Relayer", "Expert", "Mentor", "Camouflage"
]

# Field mods
field_mods_all = [
    "All-Terrain Suspension", "Lightweight Suspension", "Parallax Adjustment",
    "Refined Powder", "Left-Side Periscope", "Right-Side Periscope",
    "Right-Angle Optics", "Anti-Reflective Lenses", "Reinforced Spall Liner",
    "Anti-Fragmentation Lining", "Power Supply Tuning", "Electrical System Shielding",
    "Additional Forward Gears", "Additional Reverse Gears", "No Modification"
]

current_date = datetime.now().strftime("%Y-%m-%d")

# Build output format based on IS-7 data
equipment_slots_line = f"Select EXACTLY {equipment_slot_count} items for each"

# Equipment output lines
if equipment_slot_count == 2:
    equip_output = """   * Loadout 1 (Main): Slot 1: [Item 1] | Slot 2: [Item 2]
   * Loadout 2 (Alternate): Slot 1: [Item 1] | Slot 2: [Item 2]"""
elif equipment_slot_count == 3:
    equip_output = """   * Loadout 1 (Main): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
   * Loadout 2 (Alternate): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]"""
else:
    equip_output = f"   * Loadout 1 (Main): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]"

# Crew output
crew_output = """   * Commander: Major: [Perk 1, Perk 2, Perk 3, Perk 4] | Situational: [Perk 5, Perk 6]
   * Gunner: Major: [Perk 1, Perk 2, Perk 3, Perk 4] | Situational: [Perk 5, Perk 6]
   * Driver: Major: [Perk 1, Perk 2, Perk 3, Perk 4] | Situational: [Perk 5, Perk 6]
   * Loader (Radio Operator): Major: [Perk 1, Perk 2, Perk 3, Perk 4] | Situational: [Perk 5, Perk 6]
   * Loader: Major: [Perk 1, Perk 2, Perk 3, Perk 4] | Situational: [Perk 5, Perk 6]"""

prompt = f"""Current date: {current_date}.

[INSTRUCTION CONTEXT & PURPOSE]
This instruction acts as a configuration generator for the game World of Tanks. Its purpose is to process the requested tank name and output a highly precise, machine-readable competitive build. This output will be directly parsed by a downstream Python application.

Generate the optimal competitive build data for the tank: {tank_name}.

You must ONLY use the exact names and terms provided in the lists below. Begin your response exactly with the phrase "Build Generated:" followed immediately by a markdown code block containing the requested data. Do not include any other conversational text or explanations outside or inside the code block.

1. EQUIPMENT ({equipment_slots_line} from this list):
{', '.join(EQUIPMENT_PROPER)}.

2. AMMO CAPACITY & TYPES (Distribute exact piece count, sum must equal max ammo):
{', '.join(ammo_list)}.

3. CONSUMABLES (Select EXACTLY 3 items from this list):
{', '.join(consumables_list)}.

4. CREW PERKS (Select EXACTLY 4 major perks and EXACTLY 2 situational perks from this list for each role):
{', '.join(all_perks)}.

5. FIELD MODIFICATION (Select EXACTLY one option per level from this list):
Level II: "All-Terrain Suspension" OR "Lightweight Suspension" OR "No Modification"
Level IV: "Parallax Adjustment" OR "Refined Powder" OR "Left-Side Periscope" OR "Right-Side Periscope" OR "No Modification"
Level VI: "Right-Angle Optics" OR "Anti-Reflective Lenses" OR "Reinforced Spall Liner" OR "Anti-Fragmentation Lining" OR "No Modification"
Level VIII: "Power Supply Tuning" OR "Electrical System Shielding" OR "Additional Forward Gears" OR "Additional Reverse Gears" OR "No Modification"

OUTPUT FORMAT:
Build Generated:
```text
1. Equipment:
{equip_output}
2. Ammo: [Type 1]: [Count] shells | [Type 2]: [Count] shells | [Type 3]: [Count] shells
3. Consumables: Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
4. Crew Perks:
{crew_output}
5. Field Modification: Level II: [Choice] | Level IV: [Choice] | Level VI: [Choice] | Level VIII: [Choice]
```"""

with open("prompt_is7.txt", "w", encoding="utf-8") as f:
    f.write(prompt)

print("IS-7 Prompt generated!")
print(f"Equipment: {len(EQUIPMENT_PROPER)} items")
print(f"Consumables: {len(consumables_list)} items")
print(f"Perks: {len(all_perks)} items")
print(f"Equipment slots: {equipment_slot_count}")
print(f"Crew roles: {len(crew_roles)}")
print("\nSaved to prompt_is7.txt")