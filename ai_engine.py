import os
import json
import threading
import subprocess
import time
from collections import Counter

CACHE_FILE = "ai_cache.json"

# Cache expiry: 30 days
CACHE_EXPIRY_DAYS = 30

# ============================================================
# Cache management
# ============================================================

def _is_cache_valid(cache_entry):
    """Check if cache entry is less than CACHE_EXPIRY_DAYS old."""
    if not isinstance(cache_entry, dict):
        return False
    timestamp = cache_entry.get("_timestamp", 0)
    if not timestamp:
        return False
    age_days = (time.time() - timestamp) / (24 * 3600)
    return age_days < CACHE_EXPIRY_DAYS

# Equipment ID to internal name mapping
EQUIP_ID_MAP = {
    "healthReserve": "extraHealthReserve",
    "modernizedExtraHealthReserveAntifragmentationLining": "extraHealthReserve",
    "ventilation": "improvedVentilation",
    "aimingStabilizer": "aimingStabilizer",
    "rammer": "rammer",
    "coatedOptics": "coatedOptics",
    "turbocharger": "turbocharger",
    "enhancedAimDrives": "enhancedAimDrives",
    "improvedSights": "improvedSights",
    "improvedRotationMechanism": "improvedRotationMechanism",
    "modernizedTurbochargerRotationMechanism": "turbocharger",
    "commandersView": "commandersView",
    "stereoscope": "stereoscope",
    "camouflageNet": "camouflageNet",
    "antifragmentationLining": "antifragmentationLining",
    "additionalInvisibilityDevice": "additionalInvisibilityDevice",
}

# ============================================================
# VALIDATION SETS - для фільтрації невалідних даних від ШІ
# ============================================================
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

AI_EQUIP_MAP = {
    "Gun Rammer": "rammer",
    "Improved Ventilation": "improvedVentilation",
    "Vertical Stabilizer": "aimingStabilizer",
    "Turbocharger": "turbocharger",
    "Improved Hardening": "extraHealthReserve",
    "Low-Noise Exhaust System": "additionalInvisibilityDevice",
    "Coated Optics": "coatedOptics",
    "Commander's Vision System": "commandersView",
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
    "HE": "HIGH_EXPLOSIVE",
    "HESH": "HIGH_EXPLOSIVE_PREMIUM"
}

AI_CONS_MAP = {
    "Small Repair Kit": "smallRepairkit",
    "Large Repair Kit": "largeRepairkit",
    "Small First Aid Kit": "smallMedkit",
    "Large First Aid Kit": "largeMedkit",
    "Manual Fire Extinguisher": "handExtinguishers",
    "Automatic Fire Extinguisher": "autoExtinguishers",
    "Removed Speed Governor": "removedRpmLimiter",
    "100-octane Gasoline": "qualityFuel",
    "105-octane Gasoline": "excellentFuel",
    "Extra Rations": "ration",
    "Extra Rations (USSR)": "ration",
    "Extra Rations (Soviet)": "ration",
    "Case of Cola": "cocacola",
    "Case of Cola (USA)": "cocacola",
    "Chocolate": "chocolate",
    "Chocolate (Germany)": "chocolate",
    "Pudding and Tea": "ration_uk",
    "Pudding and Tea (UK)": "ration_uk",
    "Strong Coffee": "hotCoffee",
    "Strong Coffee (France)": "hotCoffee",
    "Improved Rations": "ration_china",
    "Improved Rations (China)": "ration_china",
    "Bread with Lard": "ration_poland",
    "Bread with Lard (Poland)": "ration_poland",
    "Smoked Lard": "ration_czech",
    "Buchty": "ration_czech",
    "Buchty (Czechoslovakia)": "ration_czech",
    "Spaghetti with Meat Sauce": "ration_italy",
    "Spaghetti with Meat Sauce (Italy)": "ration_italy",
    "Onigiri": "ration_japan",
    "Onigiri (Japan)": "ration_japan",
    "Coffee with Cinnamon": "ration_sweden",
    "Coffee with Cinnamon (Sweden)": "ration_sweden"
}

AI_CREW_MAP = {
    # ── Shared (all roles) ──
    "Brothers in Arms": "brotherhood",
    "Repair": "repair",
    "Repairs": "repair",
    "Concealment": "camouflage",
    "Firefighting": "fireFighting",
    # ── Commander ──
    "Recon": "commander_eagleEye",
    "Emergency": "commander_emergency",
    "Mentor": "commander_tutor",
    "Coordination": "commander_coordination",
    "Sound Detection": "commander_enemyShotPredictor",
    "Practicality": "commander_practical",
    "Hold the Line": "commander_holdLine",
    "Stay Sharp": "commander_staySharp",
    # ── Gunner ──
    "Snap Shot": "gunner_smoothTurret",
    "Deadeye": "gunner_rancorous",
    "Designated Target": "gunner_sniper",
    "Armorer": "gunner_armorer",
    "Steady Aim": "gunner_focus",
    "Snap-to-Target": "gunner_quickAiming",
    "Quick Aiming": "gunner_quickAiming",
    "Point Blank": "gunner_pointBlast",
    "Lone Wolf": "gunner_loneWolf",
    # ── Driver ──
    "Smooth Ride": "driver_smoothDriving",
    "Off-Road Driving": "driver_badRoadsKing",
    "Clutch Braking": "driver_virtuoso",
    "Controlled Impact": "driver_rammingMaster",
    "Reliable Placement": "driver_reliablePlacement",
    "Engineer": "driver_motorExpert",
    "Field Support": "driver_suspensionRepair",
    "Bulletproof": "driver_bulletproof",
    # ── Loader ──
    "Adrenaline Rush": "loader_desperado",
    "Safe Stowage": "loader_pedant",
    "Intuition": "loader_intuition",
    "Perfect Charge": "loader_perfectCharge",
    "Close Combat": "loader_melee",
    "Ammo Tuning": "loader_ammunitionImprove",
    "The Second Chance": "loader_secondChance",
    "Mag Mastery": "loader_magMastery",
    # ── Radio Operator ──
    "Situational Awareness": "radioman_finder",
    "Signal Interception": "radioman_signalInterception",
    "Jamming": "radioman_interference",
    "Communications Expert": "radioman_expert",
    "Side by Side": "radioman_sideBySide",
    "Threat Search": "radioman_threatSearch",
    "Battle Tempered": "radioman_battleTempered",
    # ── Legacy aliases (AI may still return old names) ──
    "Sixth Sense": "commander_enemyShotPredictor",
    "Preventative Maintenance": "armorPatching",
    "Eagle Eye": "commander_eagleEye",
    "Jack of All Trades": "commander_tutor",
    "Call for Vengeance": "radioman_finder",
    "Signal Boosting": "radioman_finder",
    "Relaying": "radioman_finder"
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
            
    def _find_key(self, d, *patterns):
        """Find first key in dict matching any pattern (case-insensitive)."""
        for p in patterns:
            for k in d:
                if p.lower() == k.lower():
                    return d[k]
        # Fuzzy: partial match
        for p in patterns:
            for k in d:
                if p.lower() in k.lower():
                    return d[k]
        return None

    def _normalize_build(self, raw_json):
        """Нормалізація JSON від ШІ до стандартної структури."""

        norm = {
            "tank": self._find_key(raw_json, "tank", "Tank", "name") or "",
            "equipment_1": [], "equipment_2": [],
            "consumables": [],
            "ammo": [],
            "crew": [],
            "field_mods": []
        }

        # ── EQUIPMENT ──
        eq_root = self._find_key(raw_json, "equipment", "Equipment", "loadouts", "Loadouts") or {}
        if isinstance(eq_root, dict):
            # Нова структура: loadout_1_open_maps / loadout_2_city_corridor_maps
            l1 = self._find_key(eq_root, "loadout_1_open_maps", "loadout_1", "Loadout 1 Open") or []
            l2 = self._find_key(eq_root, "loadout_2_city_corridor_maps", "loadout_2", "Loadout 2 City") or []
            if isinstance(l1, list):
                for e in l1[:3]:
                    s = str(e)
                    if s in VALID_EQUIPMENT:
                        mapped = AI_EQUIP_MAP.get(s, s)
                        norm["equipment_1"].append(mapped)
            if isinstance(l2, list):
                for e in l2[:3]:
                    s = str(e)
                    if s in VALID_EQUIPMENT:
                        mapped = AI_EQUIP_MAP.get(s, s)
                        norm["equipment_2"].append(mapped)
        elif isinstance(eq_root, list):
            for e in eq_root[:3]:
                s = str(e)
                if s in VALID_EQUIPMENT:
                    norm["equipment_1"].append(AI_EQUIP_MAP.get(s, s))

        # ── CONSUMABLES ──
        cons_root = self._find_key(raw_json, "consumables", "Consumables") or []
        if isinstance(cons_root, list):
            for c in cons_root[:3]:
                s = str(c)
                if s in VALID_CONSUMABLES:
                    mapped = AI_CONS_MAP.get(s, s)
                    norm["consumables"].append(mapped)

        # ── AMMO ──
        def _parse_ammo_type(text):
            t = str(text).upper()
            if "APCR" in t: return AI_AMMO_MAP["APCR"]
            if "HEAT" in t: return AI_AMMO_MAP["HEAT"]
            if "HESH" in t or "SQUASH" in t: return AI_AMMO_MAP["HESH"]
            if "AP" in t: return AI_AMMO_MAP["AP"]
            if "HE" in t: return AI_AMMO_MAP["HE"]
            return None

        ammo_root = self._find_key(raw_json, "ammo", "Ammo", "ammunition") or {}
        if isinstance(ammo_root, dict):
            dist = self._find_key(ammo_root, "distribution", "Distribution") or ammo_root
            if isinstance(dist, dict):
                for k, v in dist.items():
                    t = _parse_ammo_type(k)
                    if t and isinstance(v, (int, float)) and int(v) > 0:
                        norm["ammo"].append((t, int(v)))
        elif isinstance(ammo_root, list):
            for item in ammo_root:
                if isinstance(item, dict):
                    t = _parse_ammo_type(item.get("type", ""))
                    c = int(item.get("count", 0) or item.get("amount", 0))
                    if t and c > 0:
                        norm["ammo"].append((t, c))

        # ── CREW ──
        crew_raw = self._find_key(raw_json, "crew_perks", "crew", "Crew", "perks") or {}
        if isinstance(crew_raw, dict):
            for role, skills in crew_raw.items():
                skill_list = []
                if isinstance(skills, dict):
                    primary = self._find_key(skills, "primary", "Primary")
                    secondary = self._find_key(skills, "secondary", "Secondary")
                    if isinstance(primary, list): skill_list.extend(primary)
                    if isinstance(secondary, list): skill_list.extend(secondary)
                elif isinstance(skills, list):
                    skill_list = skills
                if skill_list:
                    mapped = []
                    for s in skill_list:
                        ss = str(s)
                        if ss in VALID_CREW_SKILLS:
                            mapped.append(AI_CREW_MAP.get(ss, ss))
                    if mapped:
                        norm["crew"].append((role, mapped))

        # ── FIELD MODS ──
        fm_root = self._find_key(raw_json, "field_modifications", "field_mods", "Field Modifications") or []
        if isinstance(fm_root, list):
            for v in fm_root[:5]:
                if isinstance(v, str) and v.strip() and "no modification" not in v.lower():
                    norm["field_mods"].append(v)

        return norm

    def _validate_build(self, norm):
        """Check if normalized build has minimum required data."""
        issues = []
        eq1 = norm.get("equipment_1", [])
        if len(eq1) < 3:
            issues.append("equipment_1")
        eq2 = norm.get("equipment_2", [])
        if len(eq2) < 3:
            issues.append("equipment_2")
        cons = norm.get("consumables", [])
        if len(cons) < 3:
            issues.append("consumables")
        ammo = norm.get("ammo", [])
        if len(ammo) < 2:
            issues.append("ammo")
        crew = norm.get("crew", [])
        if len(crew) < 1:
            issues.append("crew")
        else:
            for role, skills in crew:
                invalid = [s for s in skills if s not in VALID_CREW_SKILLS and not s.startswith("commander_") and not s.startswith("gunner_") and not s.startswith("driver_") and not s.startswith("loader_") and not s.startswith("radioman_")]
                if len(invalid) > len(skills) * 0.5:
                    issues.append(f"crew_{role}")
        return issues

    def _pick_most_common(self, items_list, max_items=3, valid_set=None):
        """Pick most common items from multiple lists."""
        counter = Counter()
        for items in items_list:
            for item in items:
                if valid_set is None or item in valid_set:
                    counter[item] += 1
        return [item for item, _ in counter.most_common(max_items)]

    def _pick_most_common_skills(self, skills_by_role, max_skills=6):
        """Pick most common skills per role from multiple results."""
        result = {}
        for role in ["commander", "gunner", "driver", "loader_1", "loader_2"]:
            counter = Counter()
            for skills in skills_by_role.get(role, []):
                for skill in skills:
                    if skill in VALID_CREW_SKILLS:
                        counter[skill] += 1
            result[role] = [s for s, _ in counter.most_common(max_skills)]
        return result

    def _run_single_scrape(self, tank_name):
        """Run scraper via tomato_selenium.py - gets real data from tomato.gg"""
        try:
            # Try tomato.gg first
            proc = subprocess.run(
                ["python", "tomato_selenium.py", tank_name],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=180
            )
            for line in proc.stdout.split("\n"):
                if line.startswith("{"):
                    data = json.loads(line)
                    if "equipment_1" in data:
                        # Convert tomato format to ai_engine format
                        return self._convert_tomato_format(data, tank_name)
            # Fallback to Google AI if tomato fails
            print(f"[AI Engine] Tomato failed, trying Google AI...")
        except Exception as e:
            print(f"[AI Engine] Scraper error: {e}")
        return None
    
    def _convert_tomato_format(self, tomato_data, tank_name):
        """Convert tomato_selenium format to ai_engine format."""
        result = {
            "tank": tank_name,
            "equipment": {
                "loadout_1": tomato_data.get("equipment_1", []),
                "loadout_2": tomato_data.get("equipment_2", [])
            },
            "ammo": {"capacity": 30, "distribution": {"AP": 10, "APCR": 18, "HE": 2}},
            "consumables": tomato_data.get("consumables", []),
            "crew_perks": {},
            "field_modifications": []
        }
        
        # Convert crew perks
        crew = tomato_data.get("crew_perks", {})
        for role, skills in crew.items():
            result["crew_perks"][role] = skills
        
        return result

    def _average_results(self, results, tank_name):
        """Average 3 results into one build."""
        if not results:
            return None

        normalized = []
        for r in results:
            if r and "error" not in r:
                n = self._normalize_build(r)
                if not self._validate_build(n):
                    normalized.append(n)

        if len(normalized) < 2:
            return normalized[0] if normalized else None

        l1_lists = [n["equipment_1"] for n in normalized]
        l2_lists = [n["equipment_2"] for n in normalized]
        cons_lists = [n["consumables"] for n in normalized]
        
        # Extract crew skills from list format [(role, skills), ...]
        crew_by_role = {}
        for n in normalized:
            crew = n.get("crew", [])
            if isinstance(crew, list):
                for role, skills in crew:
                    if role not in crew_by_role:
                        crew_by_role[role] = []
                    crew_by_role[role].append(skills if isinstance(skills, list) else [])
        
        crew_lists = {role: crew_by_role.get(role, []) for role in ["commander", "gunner", "driver", "loader_1", "loader_2"]}

        avg = {
            "tank": tank_name,
            "equipment_1": self._pick_most_common(l1_lists, 3),
            "equipment_2": self._pick_most_common(l2_lists, 3),
            "consumables": self._pick_most_common(cons_lists, 3),
            "ammo": normalized[0]["ammo"],
            "crew": self._pick_most_common_skills(crew_lists, 6),
            "field_mods": normalized[0]["field_mods"]
        }

        return avg

    def fetch_build_async(self, tag, tank_name, callback):
        # Check cache first - show cached data immediately, then check for updates in background
        cache_valid = False
        with self._lock:
            if tag in self.cache:
                cache_entry = self.cache[tag]
                # Check cache is valid and not expired (30 days)
                if _is_cache_valid(cache_entry):
                    norm = self._normalize_build(cache_entry)
                    issues = self._validate_build(norm)
                    if not issues:
                        callback(norm, True)  # is_cached=True
                        cache_valid = True
                    else:
                        print(f"[AI Engine] Cache for {tag} invalid ({issues}), re-fetching...")
                        del self.cache[tag]
                        self._save_cache()
                else:
                    age_days = (time.time() - cache_entry.get("_timestamp", 0)) / (24 * 3600)
                    print(f"[AI Engine] Cache for {tag} expired ({age_days:.1f} days), re-fetching...")
                    del self.cache[tag]
                    self._save_cache()

        def run_single_scrape():
            print(f"[AI Engine] Fetching build for {tank_name}...")
            r = self._run_single_scrape(tank_name)
            
            if not r or "error" in r:
                print(f"[AI Engine] Request failed for {tag}")
                callback({}, False)
                return

            print(f"[AI Engine] Got result for {tank_name}")
            norm = self._normalize_build(r)
            
            issues = self._validate_build(norm)
            if issues:
                print(f"[AI Engine] Result has issues: {issues}")
                callback({}, False)
                return

            # Save to cache with timestamp
            if isinstance(norm, dict):
                norm["_timestamp"] = time.time()
            with self._lock:
                self.cache[tag] = norm
                self._save_cache()

            callback(norm, False)

        threading.Thread(target=run_single_scrape, daemon=True).start()

ai_engine_instance = AIEngine()

