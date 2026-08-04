import json
import re

VALID_EQUIPMENT = {
    "Gun Rammer", "Improved Ventilation", "Vertical Stabilizer", "Turbocharger",
    "Improved Hardening", "Low-Noise Exhaust System", "Coated Optics",
    "Commander's Vision System", "Binocular Telescope", "Camouflage Net",
    "Spall Liner", "Modified Configuration", "Improved Rotation Mechanisms",
    "Enhanced Gun Laying Drives", "Improved Aiming",
    "rammer", "improvedVentilation", "aimingStabilizer", "turbocharger",
    "extraHealthReserve", "additionalInvisibilityDevice", "coatedOptics",
    "commandersView", "stereoscope", "camouflageNet", "antifragmentationLining",
    "improvedConfiguration", "improvedRotationMechanism", "enhancedAimDrives",
    "improvedSights"
}

VALID_CONSUMABLES = {
    "Small Repair Kit", "Large Repair Kit", "Small First Aid Kit", "Large First Aid Kit",
    "Manual Fire Extinguisher", "Automatic Fire Extinguisher", "Removed Speed Governor",
    "100-octane Gasoline", "105-octane Gasoline", "Extra Rations (USSR)",
    "Case of Cola (USA)", "Chocolate (Germany)", "Pudding and Tea (UK)",
    "Strong Coffee (France)", "Improved Rations (China)", "Bread with Lard (Poland)",
    "Buchty (Czechoslovakia)", "Spaghetti with Meat Sauce (Italy)",
    "Onigiri (Japan)", "Coffee with Cinnamon (Sweden)",
    "smallRepairkit", "largeRepairkit", "smallMedkit", "largeMedkit",
    "handExtinguishers", "autoExtinguishers", "removedRpmLimiter",
    "qualityFuel", "excellentFuel", "ration", "cocacola", "chocolate",
    "ration_uk", "hotCoffee", "ration_china", "ration_poland", "ration_czech",
    "ration_italy", "ration_japan", "ration_sweden"
}

VALID_CREW_SKILLS = {
    "Brothers in Arms", "Repair", "Concealment", "Firefighting",
    "Recon", "Emergency", "Mentor", "Coordination", "Sound Detection",
    "Practicality", "Hold the Line", "Stay Sharp",
    "Snap Shot", "Deadeye", "Designated Target", "Armorer", "Steady Aim",
    "Quick Aiming", "Point Blank", "Lone Wolf",
    "Smooth Ride", "Off-Road Driving", "Clutch Braking", "Controlled Impact",
    "Reliable Placement", "Engineer", "Field Support", "Bulletproof",
    "Adrenaline Rush", "Safe Stowage", "Intuition", "Perfect Charge",
    "Close Combat", "Ammo Tuning", "The Second Chance", "Mag Mastery",
    "Situational Awareness", "Signal Interception", "Jamming",
    "Communications Expert", "Side by Side", "Threat Search", "Battle Tempered",
    "brotherhood", "repair", "camouflage", "fireFighting",
    "commander_eagleEye", "commander_emergency", "commander_tutor",
    "commander_coordination", "commander_enemyShotPredictor", "commander_practical",
    "commander_holdLine", "commander_staySharp",
    "gunner_smoothTurret", "gunner_rancorous", "gunner_sniper",
    "gunner_armorer", "gunner_focus", "gunner_quickAiming", "gunner_pointBlast",
    "gunner_loneWolf",
    "driver_smoothDriving", "driver_badRoadsKing", "driver_virtuoso",
    "driver_rammingMaster", "driver_reliablePlacement", "driver_motorExpert",
    "driver_suspensionRepair", "driver_bulletproof",
    "loader_desperado", "loader_pedant", "loader_intuition", "loader_perfectCharge",
    "loader_melee", "loader_ammunitionImprove", "loader_secondChance", "loader_magMastery",
    "radioman_finder", "radioman_signalInterception", "radioman_interference",
    "radioman_expert", "radioman_sideBySide", "radioman_threatSearch", "radioman_battleTempered"
}

VALID_AMMO_TYPES = {"AP", "APCR", "HEAT", "HE", "HESH",
    "ARMOR_PIERCING", "ARMOR_PIERCING_CR", "HOLLOW_CHARGE",
    "HIGH_EXPLOSIVE", "HIGH_EXPLOSIVE_PREMIUM"}


def _find_key(d, *patterns):
    for p in patterns:
        for k in d:
            if p.lower() == k.lower():
                return d[k]
    for p in patterns:
        for k in d:
            if p.lower() in k.lower():
                return d[k]
    return None


def _normalize_string(s):
    s = str(s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def _parse_ammo(raw):
    result = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            kl = str(k).upper()
            t = None
            if "APCR" in kl or "COMPOSITE" in kl or "CR" in kl: t = "APCR"
            elif "HEAT" in kl or "CHARGE" in kl: t = "HEAT"
            elif "HESH" in kl or "SQUASH" in kl: t = "HESH"
            elif "HE" in kl and "AP" not in kl: t = "HE"
            elif "AP" in kl: t = "AP"
            if t and isinstance(v, (int, float)) and int(v) > 0:
                result.append((t, int(v)))
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                t = _parse_ammo(item.get("type", ""))
                c = int(item.get("count", 0) or item.get("amount", 0))
                if t and c > 0: result.append((t, c))
    return result


def normalize_build(raw_json):
    norm = {
        "tank": _find_key(raw_json, "tank", "Tank", "name", "Name") or "",
        "equipment": {"loadout_1": [], "loadout_2": []},
        "ammo": {"distribution": {}},
        "consumables": [],
        "crew": {},
        "field_mods": []
    }

    # Equipment
    eq_root = _find_key(raw_json, "equipment", "Equipment", "loadouts", "Loadouts",
                       "loadout", "Loadout") or {}
    if isinstance(eq_root, dict):
        # New structure: loadout_1_open_maps / loadout_2_city_corridor_maps
        l1 = _find_key(eq_root, "loadout_1_open_maps", "loadout_1", "Loadout 1 Open",
                       "loadout_open", "open_maps") or []
        l2 = _find_key(eq_root, "loadout_2_city_corridor_maps", "loadout_2", "Loadout 2 City",
                       "loadout_city", "city_maps") or []
        if isinstance(l1, list):
            norm["equipment"]["loadout_1"] = [str(x) for x in l1[:3] if str(x) in VALID_EQUIPMENT]
        if isinstance(l2, list):
            norm["equipment"]["loadout_2"] = [str(x) for x in l2[:3] if str(x) in VALID_EQUIPMENT]
    elif isinstance(eq_root, list):
        norm["equipment"]["loadout_1"] = [str(x) for x in eq_root[:3] if str(x) in VALID_EQUIPMENT]

    # Ammo
    ammo_root = _find_key(raw_json, "ammo", "Ammo", "ammunition", "Ammunition") or {}
    if isinstance(ammo_root, dict):
        dist = _find_key(ammo_root, "distribution", "Distribution", "shells", "Shells") or ammo_root
        if isinstance(dist, dict):
            for k, v in dist.items():
                kl = str(k).upper()
                t = None
                if "APCR" in kl: t = "APCR"
                elif "HEAT" in kl: t = "HEAT"
                elif "HESH" in kl: t = "HESH"
                elif "AP" in kl: t = "AP"
                elif "HE" in kl: t = "HE"
                if t and isinstance(v, (int, float)) and int(v) > 0:
                    norm["ammo"]["distribution"][t] = int(v)
    elif isinstance(ammo_root, list):
        for item in ammo_root:
            if isinstance(item, dict):
                t = str(item.get("type", "")).upper()
                c = int(item.get("count", 0) or item.get("amount", 0))
                if "APCR" in t: norm["ammo"]["distribution"]["APCR"] = c
                elif "HEAT" in t: norm["ammo"]["distribution"]["HEAT"] = c
                elif "HESH" in t: norm["ammo"]["distribution"]["HESH"] = c
                elif "AP" in t: norm["ammo"]["distribution"]["AP"] = c
                elif "HE" in t: norm["ammo"]["distribution"]["HE"] = c

    # Consumables
    cons_root = _find_key(raw_json, "consumables", "Consumables", "consumbles") or []
    if isinstance(cons_root, list) and cons_root:
        valid_cons = [str(x) for x in cons_root[:3] if str(x) in VALID_CONSUMABLES]
        norm["consumables"] = valid_cons
    # Fallback: try to find from any list field
    if not norm["consumables"]:
        for key in ["consumables", "Consumables"]:
            if key in raw_json and isinstance(raw_json[key], list):
                cons_items = [str(x) for x in raw_json[key][:3] if str(x) in VALID_CONSUMABLES]
                if cons_items:
                    norm["consumables"] = cons_items
                    break
        # Last resort: if all results have same consumables, use them
        if not norm["consumables"] and isinstance(cons_root, list) and cons_root:
            norm["consumables"] = [str(x) for x in cons_root[:3]]

    # Crew
    crew_root = _find_key(raw_json, "crew", "Crew", "crew_perks", "Crew Perks", "perks") or {}
    if isinstance(crew_root, dict):
        for role, skills in crew_root.items():
            role_lower = str(role).lower()
            skill_list = []
            if isinstance(skills, dict):
                primary = _find_key(skills, "primary", "Primary", "primary_role")
                secondary = _find_key(skills, "secondary", "Secondary", "secondary_role")
                if isinstance(primary, list): skill_list.extend(primary)
                if isinstance(secondary, list): skill_list.extend(secondary)
            elif isinstance(skills, list):
                skill_list = skills
            valid = [str(s) for s in skill_list if str(s) in VALID_CREW_SKILLS][:6]
            norm["crew"][role] = valid

    # Field Mods
    fm_root = _find_key(raw_json, "field_mods", "field_modifications", "Field Modifications",
                        "Field Mods", "Modifications") or []
    if isinstance(fm_root, list):
        norm["field_mods"] = [str(x) for x in fm_root[:5] if str(x).strip()]

    return norm


def validate_build(norm):
    issues = []
    if len(norm["equipment"]["loadout_1"]) < 3: issues.append("equipment_loadout_1")
    if len(norm["equipment"]["loadout_2"]) < 3: issues.append("equipment_loadout_2")
    if len(norm["consumables"]) < 3: issues.append("consumables")
    if len(norm["ammo"]["distribution"]) < 2: issues.append("ammo")
    if not norm["crew"]: issues.append("crew")
    return issues


# Test normalizer
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))

    if len(sys.argv) > 1:
        result = sys.argv[1]
        try:
            data = json.loads(result)
            n = normalize_build(data)
            issues = validate_build(n)
            print("NORMALIZED:")
            print(json.dumps(n, indent=2, ensure_ascii=False))
            print("ISSUES:", issues)
        except Exception as e:
            print(f"Error: {e}")
    else:
        test1 = '{"tank":"IS-7","equipment":{"loadout_1":["Improved Hardening","Turbocharger","Vertical Stabilizer"],"loadout_2":["Improved Hardening","Improved Ventilation","Vertical Stabilizer"]},"ammo":{"capacity":30,"distribution":{"AP":10,"APCR":18,"HE":2}},"consumables":["Large Repair Kit","Large First Aid Kit","Extra Rations (USSR)"],"crew_perks":{"commander":["Brothers in Arms","Repair","Recon","Sound Detection","Practicality","Hold the Line"],"gunner":["Brothers in Arms","Repair","Snap Shot","Deadeye","Steady Aim","Quick Aiming"],"driver":["Brothers in Arms","Repair","Off-Road Driving","Clutch Braking","Smooth Ride","Controlled Impact"],"loader_1":{"primary_role":["Brothers in Arms","Repair","Safe Stowage","Intuition","Perfect Charge","Adrenaline Rush"],"secondary_role_radio_operator":["Situational Awareness","Signal Interception","Battle Tempered","Communications Expert"]}},"field_modifications":["All-Terrain Suspension","Parallax Adjustment","Periscope Dish","Passive Safety System","Reinforced Suspension"]}'

        test2 = '{"Tank":"IS-7","Equipment":{"Loadout 1":["Improved Hardening","Turbocharger","Vertical Stabilizer"],"Loadout 2":["Improved Ventilation","Turbocharger","Vertical Stabilizer"]},"Ammo":{"AP":10,"APCR":18,"HE":2},"Consumables":["Large Repair Kit","Large First Aid Kit","Extra Rations (USSR)"],"Crew":{"Commander":["Brothers in Arms","Repair","Concealment","Recon","Sound Detection","Practicality"],"Gunner":["Brothers in Arms","Repair","Concealment","Snap Shot","Deadeye","Steady Aim"],"Driver":["Brothers in Arms","Repair","Concealment","Smooth Ride","Off-Road Driving","Clutch Braking"],"Loader_1":["Brothers in Arms","Repair","Concealment","Safe Stowage","Intuition","Adrenaline Rush"]},"Field Modifications":["All-Terrain Suspension","Parallax Adjustment","Periscope Dish","Passive Safety System","Reinforced Suspension"]}'

        test_scraper1 = '{"tank":"IS-7","loadouts":{"loadout_1":["Improved Hardening","Gun Rammer","Turbocharger"],"loadout_2":["Improved Hardening","Gun Rammer","Vertical Stabilizer"]},"ammo":{"max_capacity":30,"distribution":{"AP":10,"APCR":18,"HE":2}},"consumables":["Large Repair Kit","Large First Aid Kit","Extra Rations (USSR)"],"crew_perks":{"commander":["Brothers in Arms","Repair","Recon","Sound Detection","Emergency","Coordination"],"gunner":["Brothers in Arms","Repair","Snap Shot","Deadeye","Steady Aim","Quick Aiming"],"driver":["Brothers in Arms","Repair","Smooth Ride","Off-Road Driving","Clutch Braking","Controlled Impact"],"loader_1":["Brothers in Arms","Repair","Safe Stowage","Intuition","Adrenaline Rush","Perfect Charge"],"loader_2":["Brothers in Arms","Repair","Safe Stowage","Intuition","Close Combat","Ammo Tuning"]},"field_modifications":["All-Terrain Suspension","Parallax Adjustment","Periscope Dish","Passive Safety System","Reinforced Suspension"]}'

        test_scraper2 = '{"tank":"IS-7","loadouts":{"loadout_1":["Improved Hardening","Turbocharger","Vertical Stabilizer"],"loadout_2":["Improved Ventilation","Gun Rammer","Vertical Stabilizer"]},"ammo":{"total_capacity":30,"distribution":{"AP":10,"APCR":18,"HE":2}},"consumables":["Large Repair Kit","Large First Aid Kit","Extra Rations (USSR)"],"crew_perks":{"commander":["Brothers in Arms","Repair","Recon","Emergency","Practicality","Sound Detection"],"gunner":["Brothers in Arms","Repair","Snap Shot","Steady Aim","Deadeye","Armorer"],"driver":["Brothers in Arms","Repair","Smooth Ride","Off-Road Driving","Clutch Braking","Controlled Impact"],"loader_1":["Brothers in Arms","Repair","Safe Stowage","Intuition","Adrenaline Rush","Perfect Charge"],"loader_2":["Brothers in Arms","Repair","Safe Stowage","Intuition","Firefighting","Close Combat"]},"field_modifications":["All-Terrain Suspension","Parallax Adjustment","Periscope Dish","Passive Safety System","Reinforced Suspension"]}'

        test_context1 = '{"tank":"IS-7","equipment":{"loadout_1_open_maps":["Turbocharger","Vertical Stabilizer","Improved Hardening"],"loadout_2_city_corridor_maps":["Improved Hardening","Gun Rammer","Vertical Stabilizer"]},"ammo":{"max_capacity":30,"distribution":{"AP":10,"APCR":18,"HE":2}},"consumables":["Large Repair Kit","Large First Aid Kit","Extra Rations (USSR)"],"crew_perks":{"commander":["Brothers in Arms","Repair","Recon","Sound Detection","Practicality","Coordination"],"gunner":["Brothers in Arms","Repair","Snap Shot","Steady Aim","Deadeye","Armorer"],"driver":["Brothers in Arms","Repair","Off-Road Driving","Smooth Ride","Clutch Braking","Controlled Impact"],"loader_1":["Brothers in Arms","Repair","Safe Stowage","Intuition","Adrenaline Rush","Perfect Charge"]},"field_modifications":["All-Terrain Suspension","Parallax Adjustment","Periscope Electric Drive","Passive Safety System","Reinforced Suspension"]}'

        test_context2 = '{"tank":"IS-7","equipment":{"loadout_1_open_maps":["Turbocharger","Vertical Stabilizer","Coated Optics"],"loadout_2_city_corridor_maps":["Improved Hardening","Gun Rammer","Vertical Stabilizer"]},"ammo":{"total_capacity":30,"distribution":{"AP":10,"APCR":18,"HE":2}},"consumables":["Large Repair Kit","Large First Aid Kit","Extra Rations (USSR)"],"crew_perks":{"commander":["Brothers in Arms","Repair","Recon","Hold the Line","Stay Sharp","Sound Detection"],"gunner":["Brothers in Arms","Repair","Snap Shot","Steady Aim","Deadeye","Quick Aiming"],"driver":["Brothers in Arms","Repair","Smooth Ride","Off-Road Driving","Clutch Braking","Controlled Impact"],"loader_1":["Brothers in Arms","Repair","Safe Stowage","Intuition","Adrenaline Rush","Perfect Charge"]},"field_modifications":["All-Terrain Suspension","Parallax Adjustment","Right-Angle Periscope","Passive Safety System","Reinforced Suspension"]}'

        print("=== Context-Aware Test 1 (Open Maps vs City) ===")
        n1 = normalize_build(json.loads(test_context1))
        print("Loadout 1 (Open Maps):", n1["equipment"]["loadout_1"])
        print("Loadout 2 (City):", n1["equipment"]["loadout_2"])
        print("Consumables:", n1["consumables"])
        print("Validation:", validate_build(n1))

        print("\n=== Context-Aware Test 2 (Open Maps vs City) ===")
        n2 = normalize_build(json.loads(test_context2))
        print("Loadout 1 (Open Maps):", n2["equipment"]["loadout_1"])
        print("Loadout 2 (City):", n2["equipment"]["loadout_2"])
        print("Consumables:", n2["consumables"])
        print("Validation:", validate_build(n2))

        print("\n=== Comparison ===")
        print("Loadout 2 (City) match:", n1["equipment"]["loadout_2"] == n2["equipment"]["loadout_2"])
        print("Consumables match:", n1["consumables"] == n2["consumables"])
