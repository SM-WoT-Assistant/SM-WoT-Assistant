import sys
import time
import json
import os
import urllib.parse
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from collections import Counter

DELAY_BETWEEN_REQUESTS = 20

TANK_DB = None
def load_tank_names():
    global TANK_DB
    if TANK_DB is None:
        try:
            with open("tank_db.json", "r", encoding="utf-8") as f:
                TANK_DB = json.load(f)
        except:
            TANK_DB = {}
    return TANK_DB

def get_tank_display_name(tank_code):
    db = load_tank_names()
    full_name = db.get(tank_code, {}).get("name", tank_code)
    
    # Use short name from tank_db - it's already in English
    return full_name

def build_prompt(tank_name):
    current_date = time.strftime("%Y-%m-%d")
    return f"""Current date: {current_date}.

[INSTRUCTION CONTEXT & PURPOSE]
This instruction acts as a configuration generator for the game World of Tanks. Its purpose is to process the requested tank name and output a highly precise, machine-readable competitive build. This output will be directly parsed by a downstream Python application.

Generate the optimal competitive build data for the tank: {tank_name}.
You must ONLY use the exact names and terms provided in the lists below. Begin your response exactly with the phrase "Build Generated:" followed immediately by a markdown code block containing the requested JSON data. Do not include any other conversational text or explanations outside or inside the code block.

1. EQUIPMENT (Create TWO loadouts: Loadout 1 (Main) and Loadout 2 (Alternate). Select EXACTLY 3 items for each from this list):
Gun Rammer, Improved Ventilation, Vertical Stabilizer, Turbocharger, Improved Hardening, Low-Noise Exhaust System, Coated Optics, Commander's Vision System, Binocular Telescope, Camouflage Net, Spall Liner, Modified Configuration, Improved Rotation Mechanisms, Enhanced Gun Laying Drives, Improved Aiming.

2. AMMO CAPACITY & TYPES (You MUST list ALL shell types this tank can use. Most tanks have 3 types. Distribute the exact piece count for each type, the sum must equal the tank's max ammo capacity. Output as JSON object with type abbreviation as key and count as value):
Types: Armor Piercing (AP), Armor Piercing Composite Rigid (APCR), High Explosive Anti-Tank (HEAT), High Explosive (HE), High Explosive Squash Head (HESH)

3. CONSUMABLES (Select EXACTLY 3 items from this list, use the correct nation-specific ration):
Small Repair Kit, Large Repair Kit, Small First Aid Kit, Large First Aid Kit, Manual Fire Extinguisher, Automatic Fire Extinguisher, Removed Speed Governor, 100-octane Gasoline, 105-octane Gasoline, Extra Rations (USSR), Case of Cola (USA), Chocolate (Germany), Pudding and Tea (UK), Strong Coffee (France), Improved Rations (China), Bread with Lard (Poland), Buchty (Czechoslovakia), Spaghetti with Meat Sauce (Italy), Onigiri (Japan), Coffee with Cinnamon (Sweden).

4. CREW PERKS — Select EXACTLY 6 perks for each crew member's primary role. If a crew member has a secondary role (e.g. Loader+Radio Operator), add 4 bonus perks from that secondary role. Use ONLY names from this list:
- Shared (all roles): Brothers in Arms, Repair, Concealment, Firefighting.
- Commander: Recon, Emergency, Mentor, Coordination, Sound Detection, Practicality, Hold the Line, Stay Sharp.
- Gunner: Snap Shot, Deadeye, Designated Target, Armorer, Steady Aim, Quick Aiming, Point Blank, Lone Wolf.
- Driver: Smooth Ride, Off-Road Driving, Clutch Braking, Controlled Impact, Reliable Placement, Engineer, Field Support, Bulletproof.
- Loader: Adrenaline Rush, Safe Stowage, Intuition, Perfect Charge, Close Combat, Ammo Tuning, The Second Chance, Mag Mastery.
- Radio Operator: Situational Awareness, Signal Interception, Jamming, Communications Expert, Side by Side, Threat Search, Battle Tempered.

5. FIELD MODIFICATIONS:
List the exact in-game names of the recommended field modifications for this tank. Output them as a list of strings. Do not invent names. Only include the ones that you actually recommend picking.
"""

def single_request(app, view, prompt):
    url = f"https://www.google.com/search?q={urllib.parse.quote(prompt)}&udm=50"
    result = {"data": None, "error": None}
    
    extract_attempts = 0
    max_attempts = 45
    
    def check_result():
        nonlocal extract_attempts
        extract_attempts += 1
        
        def js_callback(page_content):
            text = str(page_content)
            if "Build Generated:" in text:
                try:
                    if "```json" in text:
                        json_str = text.split("```json")[1].split("```")[0]
                    elif "```" in text:
                        json_str = text.split("```")[1].split("```")[0]
                    else:
                        json_str = text[text.find("{"):text.rfind("}")+1]
                    data = json.loads(json_str.strip())
                    result["data"] = data
                    app.quit()
                    return
                except Exception as e:
                    pass
            
            if extract_attempts >= max_attempts:
                result["error"] = "Timeout"
                app.quit()
            else:
                QTimer.singleShot(1500, check_result)
                
        view.page().runJavaScript("document.body.innerText", js_callback)
    
    def on_load_finished(ok):
        if not ok:
            result["error"] = "Load failed"
            app.quit()
            return
        QTimer.singleShot(3000, check_result)
    
    view.loadFinished.connect(on_load_finished)
    view.load(QUrl(url))
    QTimer.singleShot(60000, app.quit)
    app.exec()
    return result

def run_triple_scraper(tank_name):
    # Single request mode (instead of 3)
    print(f"[SCRAPER] Request for {tank_name}...")
    
    app = QApplication(sys.argv)
    view = QWebEngineView()
    view.resize(800, 600)
    
    prompt = build_prompt(tank_name)
    result = single_request(app, view, prompt)
    
    if result["data"] and "error" not in result["data"]:
        data = result["data"]
        save_to_cache(tank_name, data)
        print("JSON_RESULT:" + json.dumps(data, ensure_ascii=False))
    else:
        print(f"JSON_RESULT:{{\"error\": \"{result.get('error', 'Failed')}\"}}")

VALID_EQUIPMENT = {
    "Gun Rammer", "Improved Ventilation", "Vertical Stabilizer", "Turbocharger",
    "Improved Hardening", "Low-Noise Exhaust System", "Coated Optics",
    "Commander's Vision System", "Binocular Telescope", "Camouflage Net",
    "Spall Liner", "Modified Configuration", "Improved Rotation Mechanisms",
    "Enhanced Gun Laying Drives", "Improved Aiming"
}

VALID_CONSUMABLES = {
    "Small Repair Kit", "Large Repair Kit", "Small First Aid Kit", "Large First Aid Kit",
    "Manual Fire Extinguisher", "Automatic Fire Extinguisher", "Removed Speed Governor",
    "100-octane Gasoline", "105-octane Gasoline", "Extra Rations (USSR)",
    "Case of Cola (USA)", "Chocolate (Germany)", "Pudding and Tea (UK)",
    "Strong Coffee (France)", "Improved Rations (China)", "Bread with Lard (Poland)",
    "Buchty (Czechoslovakia)", "Spaghetti with Meat Sauce (Italy)",
    "Onigiri (Japan)", "Coffee with Cinnamon (Sweden)"
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
    "Communications Expert", "Side by Side", "Threat Search", "Battle Tempered"
}

def validate_build(data):
    issues = []
    
    loadouts = data.get("loadouts", {})
    l1 = loadouts.get("loadout_1", [])
    l2 = loadouts.get("loadout_2", [])
    
    if len(l1) != 3:
        issues.append(f"Loadout 1 has {len(l1)} items (need 3)")
    if len(l2) != 3:
        issues.append(f"Loadout 2 has {len(l2)} items (need 3)")
    
    for item in l1 + l2:
        if item and item not in VALID_EQUIPMENT:
            issues.append(f"Invalid equipment: {item}")
    
    consumables = data.get("consumables", [])
    if len(consumables) != 3:
        issues.append(f"Consumables has {len(consumables)} items (need 3)")
    
    for item in consumables:
        if item and item not in VALID_CONSUMABLES:
            issues.append(f"Invalid consumable: {item}")
    
    crew = data.get("crew_perks", {})
    for role, skills in crew.items():
        if isinstance(skills, list):
            valid_count = sum(1 for s in skills if s in VALID_CREW_SKILLS)
            if valid_count != 6:
                issues.append(f"{role} has {valid_count} valid perks (need 6)")
    
    return issues

def average_results(results, tank_name):
    if len(results) == 1:
        result = results[0]
        issues = validate_build(result)
        if issues:
            print(f"[VALIDATION] Issues: {issues}")
        else:
            print(f"[VALIDATION] PASSED")
        return result
    
    def pick_most_common(items_list, max_items=3):
        counter = Counter()
        for items in items_list:
            if isinstance(items, list):
                for item in items:
                    counter[item] += 1
        return [item for item, count in counter.most_common(max_items) if count > 0]
    
    def get_loadout_items(result):
        """Extract equipment from different JSON structures."""
        # Try "loadouts" key
        loadouts = result.get("loadouts", {})
        if loadouts.get("loadout_1") or loadouts.get("loadout_2"):
            return loadouts.get("loadout_1", []), loadouts.get("loadout_2", [])
        # Try "equipment" key (T110E5 format)
        equipment = result.get("equipment", {})
        if equipment.get("loadout_1") or equipment.get("loadout_2"):
            return equipment.get("loadout_1", []), equipment.get("loadout_2", [])
        return [], []
    
    l1_lists = []
    l2_lists = []
    for r in results:
        l1, l2 = get_loadout_items(r)
        l1_lists.append(l1)
        l2_lists.append(l2)
    
    cons_lists = [r.get("consumables", []) for r in results]
    
    crew_results = {}
    for role in ["commander", "gunner", "driver", "loader", "loader_radio_operator"]:
        role_lists = []
        for r in results:
            cp = r.get("crew_perks", {})
            if role in cp:
                val = cp[role]
                if isinstance(val, list):
                    role_lists.append(val)
        if role_lists:
            crew_results[role] = pick_most_common(role_lists, 6)
    
    avg_loadout_1 = pick_most_common(l1_lists, 3)
    avg_loadout_2 = pick_most_common(l2_lists, 3)
    avg_consumables = pick_most_common(cons_lists, 3)
    
    ammo = results[0].get("ammo", {})
    field_mods = results[0].get("field_modifications", [])
    
    averaged = {
        "tank": tank_name,
        "loadouts": {
            "loadout_1": avg_loadout_1,
            "loadout_2": avg_loadout_2
        },
        "ammo": ammo,
        "consumables": avg_consumables,
        "crew_perks": crew_results,
        "field_modifications": field_mods
    }
    
    issues = validate_build(averaged)
    if issues:
        print(f"[VALIDATION] Averaged result issues: {issues}")
    else:
        print(f"[VALIDATION] Averaged result PASSED")
    
    return averaged

def save_to_cache(tank_name, data):
    cache_file = "ai_builds_cache.json"
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except:
            pass
    
    cache[tank_name] = data
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"[CACHE] Saved {tank_name}")

if __name__ == "__main__":
    tank_code = sys.argv[1] if len(sys.argv) > 1 else "T110E5"
    display_name = get_tank_display_name(tank_code)
    print(f"[TANK] Code: {tank_code} -> Display: {display_name}")
    run_triple_scraper(display_name)