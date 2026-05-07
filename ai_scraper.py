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
Standard: Gun Rammer, Improved Ventilation, Vertical Stabilizer, Turbocharger, Improved Hardening, Low-Noise Exhaust System, Coated Optics, Binocular Telescope, Camouflage Net, Spall Liner, Modified Configuration, Improved Rotation Mechanisms, Enhanced Gun Laying Drives, Improved Aiming.

Experimental: Experimental Turbocharger, Experimental Hardening, Experimental Optics.

2. AMMO CAPACITY & TYPES (Distribute exact piece count, sum must equal max ammo):
Armor Piercing (AP), Armor Piercing Composite Rigid (APCR), High Explosive Anti-Tank (HEAT), High Explosive (HE)

3. CONSUMABLES (Select EXACTLY 3 items from this list):
Small Repair Kit, Large Repair Kit, Small First Aid Kit, Large First Aid Kit, Manual Fire Extinguisher, Automatic Fire Extinguisher, Extra Rations, Case of Cola, Chocolate, Pudding and Tea, Strong Coffee, Improved Rations, Bread with Lard, Smoked Lard, Buchty, Spaghetti with Meat Sauce, Onigiri, Coffee with Cinnamon.

4. CREW PERKS (Select EXACTLY 4 major perks and EXACTLY 2 situational perks from this list for each role):
Brothers in Arms, Repairs, Concealment, Firefighting, Sixteenth Sense, Eagle Eye, Sound Detection, Jack of All Trades, Armorer, Snap Shot, Designated Target, Smooth Ride, Off-Road Driving, Clutch Braking, Controlled Impact, Preventative Maintenance, Safe Stowage, Adrenaline Rush, Intuition, Situational Awareness, Call for Vengeance.

5. FIELD MODIFICATION (Select EXACTLY one option per level from this list):
Level II: "All-Terrain Suspension" OR "Lightweight Suspension" OR "No Modification"

Level IV: "Parallax Adjustment" OR "Refined Powder" OR "No Modification"

Level VI: "Right-Angle Optics" OR "Anti-Reflective Lenses" OR "No Modification"

Level VIII: "Power Supply Tuning" OR "Electrical System Shielding" OR "No Modification"
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
