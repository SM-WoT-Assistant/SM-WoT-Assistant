#!/usr/bin/env python3
"""
generate_prompt.py - версія 3
Генерує AI промт з повним маппінгом назв
"""
import json
from datetime import datetime

# Load data
with open('game_entities_english.json', 'r', encoding='utf-8') as f:
    game_entities = json.load(f)

with open('tank_slots_full.json', 'r', encoding='utf-8') as f:
    tank_slots = json.load(f)

with open('crew_builds.json', 'r', encoding='utf-8') as f:
    crew_builds = json.load(f)

# Complete mapping for equipment IDs to human names
EQUIPMENT_MAP = {
    # Standard equipment
    'rammer': 'Gun Rammer',
    'improvedVentilation': 'Improved Ventilation',
    'verticalStabilizer': 'Vertical Stabilizer',
    'coatedOptics': 'Coated Optics',
    'enhancedAimDrives': 'Enhanced Gun Laying Drives',
    'camouflageNet': 'Camouflage Net',
    'additionalInvisibilityDevice': 'Additional Invisibility Device',
    'improvedHardening': 'Improved Hardening',
    'lowNoiseExhaust': 'Low-Noise Exhaust System',
    'turbocharger': 'Turbocharger',
    'binocularTelescope': 'Binocular Telescope',
    'spallLiner': 'Spall Liner',
    'improvedConfiguration': 'Modified Configuration',
    'improvedRotationMechanism': 'Improved Rotation Mechanisms',
    'grousers': 'Grousers',
    'additionalGrousers': 'Additional Grousers',
    'aimingStabilizer': 'Aiming Stabilizer',
    'improvedSights': 'Improved Sights',
    'gunReloadBoost': 'Improved Ventilation',
    'fireStartingChanceFactor': 'Fire Starting Chance Factor',
    'explosiveCapacity': 'Explosive Capacity',
    'gunsDamages': 'Guns Damage',
    
    # Deluxe equipment
    'deluxImprovedVentilation': 'Deluxe Ventilation',
    'deluxCoatedOptics': 'Deluxe Optics', 
    'deluxeExtraHealthReserve': 'Deluxe Extra Health Reserve',
    'deluxeImprovedRotationMechanism': 'Deluxe Improved Rotation Mechanism',
    'deluxeImprovedSights': 'Deluxe Improved Sights',
    'deluxeAdditionalInvisibilityDevice': 'Deluxe Additional Invisibility Device',
    'deluxeStereoscope': 'Deluxe Stereoscope',
    'deluxeCamouflageNet': 'Deluxe Camouflage Net',
    'deluxeAimingStabilizer': 'Deluxe Aiming Stabilizer',
    'deluxEnhancedAimDrives': 'Deluxe Enhanced Gun Laying Drives',
    
    # Trophy equipment
    'trophyBasicAimDrives': 'Trophy Gun Laying Drives',
    'trophyUpgradedAimDrives': 'Trophy Gun Laying Drives (Improved)',
    'trophyBasicTankRammer': 'Trophy Gun Rammer',
    'trophyUpgradedTankRammer': 'Trophy Gun Rammer (Improved)',
    'trophyBasicImprovedVentilation': 'Trophy Ventilation',
    'trophyUpgradedImprovedVentilation': 'Trophy Ventilation (Improved)',
    'trophyBasicAimingStabilizer': 'Trophy Aiming Stabilizer',
    'trophyUpgradedAimingStabilizer': 'Trophy Aiming Stabilizer (Improved)',
    'trophyBasicCoatedOptics': 'Trophy Optics',
    'trophyUpgradedCoatedOptics': 'Trophy Optics (Improved)',
    'trophyBasicImprovedConfiguration': 'Trophy Modified Configuration',
    'trophyUpgradedImprovedConfiguration': 'Trophy Modified Configuration (Improved)',
    'trophyBasicImprovedRotationMechanism': 'Trophy Improved Rotation Mechanism',
    'trophyUpgradedImprovedRotationMechanism': 'Trophy Improved Rotation Mechanism (Improved)',
    'trophyBasicImprovedSights': 'Trophy Improved Sights',
    'trophyUpgradedImprovedSights': 'Trophy Improved Sights (Improved)',
    'trophyBasicAdditionalInvisibilityDevice': 'Trophy Additional Invisibility Device',
    'trophyUpgradedAdditionalInvisibilityDevice': 'Trophy Additional Invisibility Device (Improved)',
    'trophyBasicTurbocharger': 'Trophy Turbocharger',
    'trophyUpgradedTurbocharger': 'Trophy Turbocharger (Improved)',
    'trophyBasicExtraHealthReserve': 'Trophy Extra Health Reserve',
    'trophyUpgradedExtraHealthReserve': 'Trophy Extra Health Reserve (Improved)',
    
    # Battle Boosters
    'improvedConfigurationBattleBooster': 'Improved Configuration',
    'improvedVentilationBattleBooster': 'Improved Ventilation',
    'rammerBattleBooster': 'Gun Rammer',
    'coatedOpticsBattleBooster': 'Coated Optics',
    'aimingStabilizerBattleBooster': 'Aiming Stabilizer',
    'enhancedAimDrivesBattleBooster': 'Enhanced Gun Laying Drives',
    'camouflageBattleBooster': 'Camouflage Net',
    'smoothTurretBattleBooster': 'Smooth Turret',
    'virtuosoBattleBooster': 'Virtuoso',
    'smoothDrivingBattleBooster': 'Smooth Driving',
    'fireFightingBattleBooster': 'Fire Extinguisher',
    'sixthSenseBattleBooster': 'Sixth Sense',
    'turbochargerBattleBooster': 'Turbocharger',
    'improvedSightsBattleBooster': 'Improved Sights',
    'additInvisibilityDeviceBattleBooster': 'Additional Invisibility Device',
}

# Consumables mapping
CONSUMABLE_MAP = {
    'handExtinguishers': 'Manual Fire Extinguisher',
    'autoExtinguishers': 'Automatic Fire Extinguisher',
    'smallMedkit': 'Small First Aid Kit',
    'largeMedkit': 'Large First Aid Kit',
    'smallRepairkit': 'Small Repair Kit',
    'largeRepairkit': 'Large Repair Kit',
    'chocolate': 'Chocolate',
    'cola': 'Cola',
    'ration': 'Extra Rations',
    'coffee': 'Strong Coffee',
    'ration_china': 'Chinese Rations',
    'ration_uk': 'British Rations',
    'ration_japan': 'Japanese Rations',
    'ration_czech': 'Czech Rations',
    'ration_sweden': 'Swedish Rations',
    'ration_poland': 'Polish Rations',
    'ration_italy': 'Italian Rations',
    'builtinRepairkit': 'Built-in Repair Kit',
    'qualityFuel': 'Quality Fuel',
    'excellentFuel': 'Excellent Fuel',
}

# Crew perks mapping  
PERK_MAP = {
    'commander_sixthSense': 'Sixth Sense',
    'commander_practical': 'Practical',
    'commander_eagleEye': 'Eagle Eye',
    'commander_enemyShotPredictor': 'Enemy Shot Predictor',
    'repair': 'Repairs',
    'camouflage': 'Concealment',
    'brotherhood': 'Brothers in Arms',
    'gunner_sniper': 'Sniper',
    'gunner_focus': 'Focus',
    'gunner_rancorous': 'Rancorous',
    'gunner_smoothTurret': 'Smooth Turret',
    'driver_smoothDriving': 'Smooth Driving',
    'driver_badRoadsKing': 'Bad Roads King',
    'driver_virtuoso': 'Virtuoso',
    'driver_rammingMaster': 'Ramming Master',
    'loader_pedant': 'Pedant',
    'loader_desperado': 'Desperado',
    'loader_intuition': 'Intuition',
    'fireFighting': 'Firefighting',
    'radioman_finder': 'Finder',
    'improvedRadioCommunication': 'Improved Radio Communication',
    'smokeSignal': 'Smoke Signal',
    'designatedTarget': 'Designated Target',
    'snapShot': 'Snap Shot',
    'smoothRide': 'Smooth Ride',
    'offRoadDriving': 'Off-Road Driving',
    'clutchBraking': 'Clutch Braking',
    'controlledImpact': 'Controlled Impact',
    'preventativeMaintenance': 'Preventative Maintenance',
    'safeStowage': 'Safe Stowage',
    'adrenalineRush': 'Adrenaline Rush',
    'situationalAwareness': 'Situational Awareness',
    'callForVengeance': 'Call for Vengeance',
    'signalBoosting': 'Signal Boosting',
    'relayer': 'Relayer',
    'expert': 'Expert',
    'mentor': 'Mentor',
}

def get_equipment_list():
    """Отримати обладнання з повним маппінгом"""
    result = []
    for eq_id, eq_data in game_entities.get('equipment', {}).items():
        name = eq_data.get('name', '').strip()
        if not name or name.startswith('#'):
            name = EQUIPMENT_MAP.get(eq_id, eq_id)
        # Skip removed items
        if 'removed' in name.lower():
            continue
        if name not in result:
            result.append(name)
    return result

def get_consumables_list():
    """Отримати витратні з маппінгом"""
    result = []
    for c_id, c_data in game_entities.get('consumables', {}).items():
        name = c_data.get('name', '').strip()
        if not name or name.startswith('#'):
            name = CONSUMABLE_MAP.get(c_id, c_id)
        if name not in result:
            result.append(name)
    return result

def get_crew_perks_list():
    """Отримати перки з маппінгом"""
    perks = set()
    if '_role_skill_pools' in crew_builds:
        for role, pool in crew_builds['_role_skill_pools'].items():
            for skill in pool:
                perks.add(skill)
    if '_default_skills' in crew_builds:
        for role, skills in crew_builds['_default_skills'].items():
            for skill in skills:
                perks.add(skill)
    
    result = []
    for perk in perks:
        name = PERK_MAP.get(perk, perk)
        if name not in result:
            result.append(name)
    return result

def get_field_mods_list():
    return [
        "All-Terrain Suspension", "Lightweight Suspension", "Parallax Adjustment",
        "Refined Powder", "Left-Side Periscope", "Right-Side Periscope",
        "Right-Angle Optics", "Anti-Reflective Lenses", "Reinforced Spall Liner",
        "Anti-Fragmentation Lining", "Power Supply Tuning", "Electrical System Shielding",
        "Additional Forward Gears", "Additional Reverse Gears", "No Modification"
    ]

def generate_prompt(tank_id, tank_name=None):
    tank_data = tank_slots.get(tank_id)
    if not tank_name:
        tank_name = tank_data.get('name_english', tank_id)
    
    equipment = get_equipment_list()
    consumables = get_consumables_list()
    crew_perks = get_crew_perks_list()
    field_mods = get_field_mods_list()
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    equip_slot_count = tank_data.get('equipment_slots', 3) if tank_data else 3
    
    slots_line_main = " | ".join([f"Slot {i+1}: [Item {i+1}]" for i in range(equip_slot_count)])
    slots_line_alt = " | ".join([f"Slot {i+1}: [Item {i+1}]" for i in range(equip_slot_count)])
    
    return f"""Current date: {current_date}.

<system_instruction>
You are an advanced, non-conversational data extraction engine for World of Tanks game configurations. Your sole purpose is to process the vehicle name inside the <target_vehicle> tag, match it against your internal technical database, and generate a competitive setup using ONLY the authorized terms provided in the <allowed_entities> block. 

CRITICAL SAFETY FILTERS:
1. Start your response immediately with the exact string "Build Generated:".
2. Right after the string, open a single markdown text block (```text) and put all configuration data inside it.
3. Do not generate any preface, greetings, meta-commentary, or closing remarks.
4. Any term used in the output that is not physically present in the <allowed_entities> lists will cause a synchronization failure.
</system_instruction>

<allowed_entities>
<equipment>
{", ".join(equipment)}
</equipment>

<ammo>
Armor Piercing (AP), Armor Piercing Composite Rigid (APCR), High Explosive Anti-Tank (HEAT), High Explosive (HE)
</ammo>

<consumables>
{", ".join(consumables)}
</consumables>

<crew_perks>
{", ".join(crew_perks)}
</crew_perks>

<field_modifications>
{", ".join(field_mods)}
</field_modifications>
</allowed_entities>

<target_vehicle>
{tank_name}
</target_vehicle>

<required_output_format>
Build Generated:
```text
1. Equipment:
   * Loadout 1 (Main): {slots_line_main}
   * Loadout 2 (Alternate): {slots_line_alt}
2. Ammo:
   * Loadout 1 (Main): [Type 1]: [Count] shells | [Type 2]: [Count] shells | [Type 3]: [Count] shells
   * Loadout 2 (Alternate): [Type 1]: [Count] shells | [Type 2]: [Count] shells | [Type 3]: [Count] shells
3. Consumables:
   * Loadout 1 (Main): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
   * Loadout 2 (Alternate): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
4. Crew Perks:
   * [Actual Crew Member Role 1]: [Perk 1, Perk 2, Perk 3, ...]
   * [Actual Crew Member Role 2]: [Perk 1, Perk 2, ...]
5. Field Modification:
   * [First Available Level Name/Number]: [Choice]
   * [Second Available Level Name/Number]: [Choice]
```</required_output_format>"""

if __name__ == "__main__":
    prompt = generate_prompt("R45_IS-7", "IS-7")
    
    with open("prompt_is7.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    
    print(f"Equipment: {len(get_equipment_list())}")
    print(f"Consumables: {len(get_consumables_list())}")
    print(f"Crew perks: {len(get_crew_perks_list())}")
    print("Saved to prompt_is7.txt")