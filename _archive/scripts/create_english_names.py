#!/usr/bin/env python3
"""
create_english_names.py
Мапінг українських назв на англійські для промту
Стандартні назви WoT використовуються на всіх серверах
"""
import json

# Мапінг system_id -> English name (standard WoT names)
ENGLISH_NAMES = {
    # === EQUIPMENT ===
    # Standard Equipment
    "rammer": "Gun Rammer",
    "improvedVentilation": "Improved Ventilation",
    "improvedVentilation_class1": "Improved Ventilation Class 1",
    "improvedVentilation_class2": "Improved Ventilation Class 2", 
    "improvedVentilation_class3": "Improved Ventilation Class 3",
    "coatedOptics": "Coated Optics",
    "binocularTelescope": "Binocular Telescope",
    "camouflageNet": "Camouflage Net",
    "spallLiner": "Spall Liner",
    "improvedConfiguration": "Improved Configuration",
    "improvedRotationMechanisms": "Improved Rotation Mechanisms",
    "enhancedGunLayingDrives": "Enhanced Gun Laying Drives",
    "improvedAiming": "Improved Aiming",
    "grousers": "Grousers",
    "additionalGrousers": "Additional Grousers",
    "lowNoiseExhaustSystem": "Low-Noise Exhaust System",
    
    # Deluxe/Experimental Equipment
    "deluxRammer": "Experimental Gun Rammer",
    "deluxImprovedVentilation": "Deluxe Ventilation",
    "deluxCoatedOptics": "Deluxe Optics",
    "deluxeTurbocharger": "Improved Turbocharger",
    "deluxAimingStabilizer": "Advanced Stabilizer",
    
    # Trophy Equipment
    "trophyBasicTankRammer": "Trophy Gun Rammer",
    "trophyUpgradedTankRammer": "Trophy Gun Rammer (Improved)",
    "trophyBasicImprovedVentilation": "Trophy Ventilation",
    "trophyUpgradedImprovedVentilation": "Trophy Ventilation (Improved)",
    "trophyBasicCoatedOptics": "Trophy Optics",
    "trophyUpgradedCoatedOptics": "Trophy Optics (Improved)",
    "trophyBasicTurbocharger": "Trophy Turbocharger",
    "trophyUpgradedTurbocharger": "Trophy Turbocharger (Improved)",
    "trophyBasicAimingStabilizer": "Trophy Stabilizer",
    "trophyUpgradedAimingStabilizer": "Trophy Stabilizer (Improved)",
    
    # Modernized Equipment
    "modernizedTurbochargerRotationMechanism1": "Mobility System I",
    "modernizedTurbochargerRotationMechanism2": "Mobility System II",
    "modernizedTurbochargerRotationMechanism3": "Mobility System III",
    "modernizedAimDrivesAimingStabilizer1": "Fire Control System I",
    "modernizedAimDrivesAimingStabilizer2": "Fire Control System II",
    "modernizedAimDrivesAimingStabilizer3": "Fire Control System III",
    
    # Classes
    "tankRammer_tier1": "Gun Rammer Class 1",
    "tankRammer_tier2": "Gun Rammer Class 2",
    "turbocharger_tier1": "Turbocharger Class 1",
    "turbocharger_tier2": "Turbocharger Class 2",
    "turbocharger_tier3": "Turbocharger Class 3",
    
    # === CONSUMABLES ===
    "handExtinguishers": "Manual Fire Extinguisher",
    "autoExtinguishers": "Automatic Fire Extinguisher",
    "smallRepairkit": "Small Repair Kit",
    "largeRepairkit": "Large Repair Kit",
    "smallMedkit": "Small First Aid Kit",
    "largeMedkit": "Large First Aid Kit",
    "chocolate": "Chocolate",
    "cocacola": "Cola",
    "ration": "Extra Rations",
    "hotCoffee": "Strong Coffee",
    "afterburning": "Rechargeable Nitro",
    
    # === CREW PERKS ===
    "commander_sixthSense": "Sixth Sense",
    "commander_practical": "Eagle Eye",
    "commander_smoothDriving": "Smooth Ride",
    "commander_brotherhood": "Brothers in Arms",
    "commander_expert": "Expert",
    "commander_mentor": "Mentor",
    "commander_intuition": "Intuition",
    "commander_recon": "Reconnaissance",
    "commander_situationalAwareness": "Situational Awareness",
    
    "gunner_sniper": "Snap Shot",
    "gunner_focus": "Designated Target",
    "gunner_rancorous": "Rancorous",
    
    "driver_smoothDriving": "Smooth Driving",
    "driver_badRoadsKing": "Off-Road Driving",
    "driver_vitality": "Clutch Braking",
    
    "loader_intuition": "Intuition",
    "loader_pedant": "Safe Stowage",
    "loader_practical": "Adrenaline Rush",
    
    "radioman_lastEffort": "Signal Boosting",
    "radioman_finder": "Relayer",
    "radioman_invention": "Voice of Warning",
    
    # === FIELD MODIFICATIONS ===
    "allTerrainSuspension": "All-Terrain Suspension",
    "lightweightSuspension": "Lightweight Suspension",
    "parallaxAdjustment": "Parallax Adjustment",
    "refinedPowder": "Refined Powder",
    "leftSidePeriscope": "Left-Side Periscope",
    "rightSidePeriscope": "Right-Side Periscope",
    "rightAngleOptics": "Right-Angle Optics",
    "antiReflectiveLenses": "Anti-Reflective Lenses",
    "reinforcedSpallLiner": "Reinforced Spall Liner",
    "antiFragmentationLining": "Anti-Fragmentation Lining",
    "powerSupplyTuning": "Power Supply Tuning",
    "electricalSystemShielding": "Electrical System Shielding",
    "additionalForwardGears": "Additional Forward Gears",
    "additionalReverseGears": "Additional Reverse Gears",
    
    # === AMMO TYPES ===
    "armorPiercing": "Armor Piercing (AP)",
    "armorPiercingCompositeRigid": "Armor Piercing Composite Rigid (APCR)",
    "highExplosiveAntiTank": "High Explosive Anti-Tank (HEAT)",
    "highExplosive": "High Explosive (HE)",
}

def load_game_entities():
    with open("game_entities.json", "r", encoding="utf-8") as f:
        return json.load(f)

def create_english_mapping():
    game_data = load_game_entities()
    
    result = {
        "equipment": {},
        "consumables": {},
        "crew_perks": {},
        "field_mods": {},
        "ammo_types": {}
    }
    
    # Map equipment
    for item_id, item_data in game_data.get("equipment", {}).items():
        english_name = ENGLISH_NAMES.get(item_id, item_id)
        result["equipment"][item_id] = {
            "name": english_name,
            "icon": item_data.get("icon", ""),
            "original_ukr": item_data.get("name", "")
        }
    
    # Map consumables
    for item_id, item_data in game_data.get("consumables", {}).items():
        english_name = ENGLISH_NAMES.get(item_id, item_id)
        result["consumables"][item_id] = {
            "name": english_name,
            "icon": item_data.get("icon", ""),
            "original_ukr": item_data.get("name", "")
        }
    
    # Map crew perks (simplified)
    for item_id, item_data in game_data.get("crew_perks", {}).items():
        english_name = ENGLISH_NAMES.get(item_id, item_id)
        result["crew_perks"][item_id] = {
            "name": english_name,
            "tags": item_data.get("tags", "")
        }
    
    # Map field mods
    for item_id, item_data in game_data.get("field_mods", {}).items():
        english_name = ENGLISH_NAMES.get(item_id, item_id)
        result["field_mods"][item_id] = {
            "name": english_name,
            "type": item_data.get("type", "")
        }
    
    # Save
    with open("game_entities_english.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Equipment: {len(result['equipment'])}")
    print(f"Consumables: {len(result['consumables'])}")
    print(f"Crew perks: {len(result['crew_perks'])}")
    print(f"Field mods: {len(result['field_mods'])}")
    print("\nSaved to game_entities_english.json")

if __name__ == "__main__":
    create_english_mapping()