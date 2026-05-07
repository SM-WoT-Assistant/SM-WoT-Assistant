import os
import json
import threading
import subprocess

CACHE_FILE = "ai_cache.json"

AI_EQUIP_MAP = {
    "Gun Rammer": "rammer",
    "Improved Ventilation": "improvedVentilation",
    "Vertical Stabilizer": "aimingStabilizer",
    "Turbocharger": "turbocharger",
    "Improved Hardening": "extraHealthReserve",
    "Low-Noise Exhaust System": "additionalInvisibilityDevice",
    "Coated Optics": "coatedOptics",
    "Binocular Telescope": "stereoscope",
    "Camouflage Net": "camouflageNet",
    "Spall Liner": "antifragmentationLining",
    "Modified Configuration": "improvedConfiguration",
    "Improved Rotation Mechanisms": "improvedRotationMechanism",
    "Enhanced Gun Laying Drives": "enhancedAimDrives",
    "Improved Aiming": "improvedSights",
    "Experimental Turbocharger": "modernizedTurbochargerRotationMechanism",
    "Experimental Hardening": "modernizedExtraHealthReserveAntifragmentationLining",
    "Experimental Optics": "modernizedImprovedSightsEnhancedAimDrives"
}

AI_AMMO_MAP = {
    "AP": "ARMOR_PIERCING",
    "APCR": "ARMOR_PIERCING_CR",
    "HEAT": "HOLLOW_CHARGE",
    "HE": "HIGH_EXPLOSIVE"
}

AI_CONS_MAP = {
    "Small Repair Kit": "smallRepairkit",
    "Large Repair Kit": "largeRepairkit",
    "Small First Aid Kit": "smallMedkit",
    "Large First Aid Kit": "largeMedkit",
    "Manual Fire Extinguisher": "handExtinguishers",
    "Automatic Fire Extinguisher": "autoExtinguishers",
    "Extra Rations": "ration",
    "Case of Cola": "cocacola",
    "Chocolate": "chocolate",
    "Pudding and Tea": "ration_uk",
    "Strong Coffee": "hotCoffee",
    "Improved Rations": "ration_china",
    "Bread with Lard": "ration_poland",
    "Smoked Lard": "ration_czech",
    "Buchty": "Buchty",
    "Spaghetti with Meat Sauce": "ration_italy",
    "Onigiri": "ration_japan",
    "Coffee with Cinnamon": "ration_sweden"
}

AI_CREW_MAP = {
    "Brothers in Arms": "brotherhood",
    "Repairs": "repair",
    "Concealment": "camouflage",
    "Firefighting": "fireFighting",
    "Sixteenth Sense": "commander_sixthSense",
    "Eagle Eye": "commander_eagleEye",
    "Sound Detection": "commander_enemyShotPredictor",
    "Jack of All Trades": "commander_tutor",
    "Armorer": "gunner_rancorous",
    "Snap Shot": "gunner_smoothTurret",
    "Designated Target": "gunner_sniper",
    "Smooth Ride": "driver_smoothDriving",
    "Off-Road Driving": "driver_badRoadsKing",
    "Clutch Braking": "driver_virtuoso",
    "Controlled Impact": "driver_rammingMaster",
    "Preventative Maintenance": "loader_pedant", 
    "Safe Stowage": "loader_intuition",
    "Adrenaline Rush": "loader_desperado",
    "Intuition": "loader_intuition",
    "Situational Awareness": "radioman_finder",
    "Call for Vengeance": "radioman_finder"
}

class AIEngine:
    def __init__(self):
        self.cache = self._load_cache()
        self._lock = threading.Lock()
        
    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}
        
    def _save_cache(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=4)
            
    def _normalize_build(self, raw_json):
        # Normalize equipment
        equip1 = []
        equip2 = []
        
        # Check title casing for root keys
        eq_root = raw_json.get("equipment") or raw_json.get("Equipment") or raw_json.get("loadouts") or raw_json.get("Loadouts") or {}
        
        if isinstance(eq_root, dict):
            equip1 = eq_root.get("loadout_1") or eq_root.get("Loadout_1") or []
            equip2 = eq_root.get("loadout_2") or eq_root.get("Loadout_2") or []
        elif isinstance(eq_root, list) and len(eq_root) > 0:
            equip1 = eq_root
            
        eq1_mapped = [AI_EQUIP_MAP.get(e, "notFound") for e in equip1 if isinstance(e, str)]
        eq2_mapped = [AI_EQUIP_MAP.get(e, "notFound") for e in equip2 if isinstance(e, str)]
        
        # Normalize consumables
        cons_raw = raw_json.get("consumables") or raw_json.get("Consumables") or []
        cons_mapped = [AI_CONS_MAP.get(c, "notFound") for c in cons_raw if isinstance(c, str)]
        
        # Normalize ammo
        ammo_mapped = []
        ammo_raw = raw_json.get("ammo") or raw_json.get("Ammo") or {}
        if isinstance(ammo_raw, dict):
            for k, v in ammo_raw.items():
                if str(k).lower() == "distribution" and isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            t = str(item.get("type", "")).upper()
                            count = 0
                            try: count = int(item.get("count", 0))
                            except: pass
                            
                            icon = None
                            if "APCR" in t: icon = AI_AMMO_MAP["APCR"]
                            elif "HEAT" in t: icon = AI_AMMO_MAP["HEAT"]
                            elif "HESH" in t: icon = AI_AMMO_MAP["HE"]
                            elif "AP" in t: icon = AI_AMMO_MAP["AP"]
                            elif "HE" in t: icon = AI_AMMO_MAP["HE"]
                            
                            if icon and count > 0:
                                ammo_mapped.append((icon, count))
                elif str(k).lower() == "total":
                    continue
                else:
                    k_up = str(k).upper()
                    count = 0
                    if isinstance(v, (int, float, str)) and str(v).strip() != "0":
                        try: count = int(v)
                        except: pass
                        
                        icon = None
                        if "APCR" in k_up: icon = AI_AMMO_MAP["APCR"]
                        elif "HEAT" in k_up: icon = AI_AMMO_MAP["HEAT"]
                        elif "HESH" in k_up: icon = AI_AMMO_MAP["HE"]
                        elif "AP" in k_up: icon = AI_AMMO_MAP["AP"]
                        elif "HE" in k_up: icon = AI_AMMO_MAP["HE"]
                        
                        if icon and count > 0:
                            ammo_mapped.append((icon, count))

        # Deduplicate ammo order safely
        seen_ammo = set()
        clean_ammo = []
        for am, count in ammo_mapped:
            if am not in seen_ammo:
                seen_ammo.add(am)
                clean_ammo.append((am, count))

        # Normalize crew
        crew_mapped = []
        crew_raw = raw_json.get("crew_perks") or raw_json.get("Crew") or raw_json.get("crew") or {}
        
        if isinstance(crew_raw, dict):
            # Check if it's flat
            k_lower = [k.lower() for k in crew_raw.keys()]
            if "major" in k_lower or "situational" in k_lower:
                mj = crew_raw.get("major") or crew_raw.get("Major") or []
                sit = crew_raw.get("situational") or crew_raw.get("Situational") or []
                all_s = mj + sit
                mapped = [AI_CREW_MAP.get(s, "notFound") for s in all_s if isinstance(s, str)]
                crew_mapped.append(("commander", mapped))
            else:
                for role, skills in crew_raw.items():
                    if isinstance(skills, dict):
                        mj = skills.get("major") or skills.get("Major") or []
                        sit = skills.get("situational") or skills.get("Situational") or []
                        all_s = mj + sit
                    elif isinstance(skills, list):
                        all_s = skills
                    else:
                        all_s = []
                    mapped = [AI_CREW_MAP.get(s, "notFound") for s in all_s if isinstance(s, str)]
                    crew_mapped.append((role, mapped))
                
        # Normalize Field Mods
        fm_raw = raw_json.get("field_modifications") or raw_json.get("Field_Modification") or raw_json.get("field_mod") or {}
        fm_mapped = []
        if isinstance(fm_raw, dict):
            for k, v in fm_raw.items():
                if isinstance(v, str) and "no modification" not in v.lower() and v.strip() != "":
                    fm_mapped.append(v)
        elif isinstance(fm_raw, list):
            for v in fm_raw:
                if isinstance(v, str) and "no modification" not in v.lower() and v.strip() != "":
                    # Usually "Level 2: Name" format from earlier prompt
                    parts = v.split(":")
                    if len(parts) > 1:
                        fm_mapped.append(parts[1].strip())
                    else:
                        fm_mapped.append(v)
                
        return {
            "equipment_1": eq1_mapped[:3],
            "equipment_2": eq2_mapped[:3],
            "consumables": cons_mapped[:3],
            "ammo": clean_ammo[:4],
            "crew": crew_mapped,
            "field_mods": fm_mapped
        }

    def fetch_build_async(self, tag, tank_name, callback):
        # Always check cache first to return immediately if available
        with self._lock:
            if tag in self.cache:
                callback(self._normalize_build(self.cache[tag]), True) # True = from cache
                return
                
        def run_scraper():
            try:
                proc = subprocess.run(["python", "ai_scraper.py", tank_name], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                json_str = None
                for line in proc.stdout.split("\n"):
                    if line.startswith("JSON_RESULT:"):
                        json_str = line.replace("JSON_RESULT:", "", 1).strip()
                        break
                        
                if json_str:
                    data = json.loads(json_str)
                    if "error" not in data:
                        with self._lock:
                            self.cache[tag] = data
                            self._save_cache()
                            norm = self._normalize_build(data)
                        callback(norm, False) # False = fresh
                    else:
                        print(f"AI Error: {data['error']}")
                        callback({}, False)
                else:
                    print("AI Error: No JSON string found.")
                    callback({}, False)
            except Exception as e:
                print(f"AI Exception: {e}")
                callback({}, False)
                
        threading.Thread(target=run_scraper, daemon=True).start()

ai_engine_instance = AIEngine()
