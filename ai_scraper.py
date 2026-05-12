import sys
import time
import json
import urllib.parse
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView

def run_scraper(tank_name):
    app = QApplication(sys.argv)
    
    # Hide the window entirely (no show method called)
    view = QWebEngineView()
    view.resize(800, 600)
    
    current_date = time.strftime("%Y-%m-%d")
    
    prompt = f"""Current date: {current_date}.

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
    
    url = f"https://www.google.com/search?q={urllib.parse.quote(prompt)}&udm=50"
    
    extract_attempts = 0
    max_attempts = 30
    
    def check_result():
        nonlocal extract_attempts
        extract_attempts += 1
        
        def js_callback(result):
            if result and "Build Generated:" in str(result):
                text = str(result)
                try:
                    # Extract the JSON part
                    if "```json" in text:
                        json_str = text.split("```json")[1].split("```")[0]
                    elif "```" in text:
                        json_str = text.split("```")[1].split("```")[0]
                    else:
                        json_str = text[text.find("{"):text.rfind("}")+1]
                        
                    data = json.loads(json_str.strip())
                    print("JSON_RESULT:" + json.dumps(data))
                    app.quit()
                    return
                except Exception as e:
                    pass
            
            if extract_attempts >= max_attempts:
                print("JSON_RESULT:{\"error\": \"Timeout waiting for AI response\"}")
                app.quit()
            else:
                QTimer.singleShot(1000, check_result)
                
        view.page().runJavaScript("document.body.innerText", js_callback)

    def on_load_finished(ok):
        if not ok:
            print("JSON_RESULT:{\"error\": \"Failed to load Google Search\"}")
            app.quit()
            return
            
        # Start polling for the result
        QTimer.singleShot(2000, check_result)
        
    view.loadFinished.connect(on_load_finished)
    view.load(QUrl(url))
    
    # Absolute timeout 45s
    QTimer.singleShot(45000, app.quit)
    app.exec()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_scraper(sys.argv[1])
    else:
        run_scraper("IS-7")
