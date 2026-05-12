import sys
import time
import json
import os
import re
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

TIMEOUT_SECONDS = 120
WAIT_FOR_DATA_MS = 20000

TANK_TO_TOMATO = {
    "Pl15_60TP_Lewandowskiego": ("3473", "60tp"),
    "R45_IS-7": ("7169", "is-7"),
    "R90_IS-4M": ("6145", "is-4"),
    "G42_Maus": ("6929", "maus"),
    "G89_Leopard1": ("2577", "leopard-1"),
    "A69_T110E5": ("5633", "t110e5"),
    "F10_AMX_50B": ("6209", "amx-50-b"),
    "S11_Strv_103B": ("4737", "strv-103b"),
    "Ch19_121": ("4145", "121"),
    "Cz17_Vz_55": ("2929", "vz-55"),
    "It08_Progetto_M40_mod_65": ("2721", "progetto-65"),
    "F18_Bat_Chatillon25t": ("3649", "b-c-25-t"),
    "GB100_Manticore": ("8193", "manticore"),
    "Pl21_CS_63": ("5265", "cs-63"),
}

def get_tank_info(tank_code):
    if tank_code in TANK_TO_TOMATO:
        return TANK_TO_TOMATO[tank_code]
    return None, None

def create_scraper():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    profile = QWebEngineProfile.defaultProfile()
    profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    view = QWebEngineView()
    view.setFixedSize(1280, 900)
    
    settings = view.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
    
    view.show()
    
    return app, view

def scrape_tank_loadouts(tank_code):
    tank_id, tank_slug = get_tank_info(tank_code)
    if not tank_id:
        print(f"[TOMATO] Unknown tank: {tank_code}")
        return None
    
    print(f"[TOMATO] Scraping {tank_code} -> tomato.gg/tanks/{tank_id}/{tank_slug}")
    
    app, view = create_scraper()
    
    result = {"data": None, "error": None}
    loadout_data = {}
    
    def on_load_finished(ok):
        print(f"[TOMATO] Page loaded, ok={ok}")
        if not ok:
            result["error"] = "Failed to load page"
            app.quit()
            return
        
        # Wait for page to fully render
        QTimer.singleShot(10000, lambda: extract_data(app))
    
    def extract_data(app_instance):
        js_code = """
        (function() {
            return {
                text: document.body.innerText,
                title: document.title
            };
        })()
        """
        
        def js_result(data):
            if data and isinstance(data, dict):
                text = data.get("text", "")
                print(f"[TOMATO] Text length: {len(text)}")
                loadout_data["text"] = text
                result["data"] = loadout_data
            app.quit()
        
        view.page().runJavaScript(js_code, js_result)
    
    def on_timeout():
        result["error"] = "Timeout"
        app.quit()
    
    view.loadFinished.connect(on_load_finished)
    
    url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"
    print(f"[TOMATO] Loading: {url}")
    view.setUrl(QUrl(url))
    
    timer = QTimer()
    timer.timeout.connect(on_timeout)
    timer.setSingleShot(True)
    timer.start(TIMEOUT_SECONDS * 1000)
    
    app.exec()
    
    timer.stop()
    view.deleteLater()
    
    return result

def parse_tomato_data(raw_data):
    if not raw_data:
        return None
    
    parsed = {
        "equipment_1": [],
        "equipment_2": [],
        "consumables": [],
        "crew_perks": {},
        "field_mods": [],
        "source": "tomato.gg"
    }
    
    text = raw_data.get("text", "")
    
    if not text:
        return None
    
    print(f"[TOMATO] Parsing text, length: {len(text)}")
    
    equipment_patterns = [
        r'Gun Rammer', r'Improved Ventilation', r'Vertical Stabilizer', r'Turbocharger',
        r'Improved Hardening', r'Coated Optics', r'Camouflage Net', r'Spall Liner',
        r'Enhanced Gun Laying Drives', r'Improved Rotation Mechanisms',
        r'Commander\'s Vision System', r'Binocular Telescope', r'Low-Noise Exhaust',
        r'Improved Aiming', r'Low-Noise Exhaust System'
    ]
    
    equip_found = []
    for pattern in equipment_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            equip_found.append(pattern)
    
    parsed["equipment_1"] = equip_found[:3]
    parsed["equipment_2"] = equip_found[3:6] if len(equip_found) > 3 else equip_found[:3]
    
    consumable_patterns = [
        r'Large Repair Kit', r'Small Repair Kit',
        r'Large First Aid Kit', r'Small First Aid Kit',
        r'Manual Fire Extinguisher', r'Automatic Fire Extinguisher',
        r'Extra Rations', r'100-octane', r'105-octane',
        r'Case of Cola', r'Chocolate', r'Pudding and Tea',
        r'Strong Coffee', r'Improved Rations', r'Coffee with Cinnamon'
    ]
    
    cons_found = []
    for pattern in consumable_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            cons_found.append(pattern)
    
    parsed["consumables"] = cons_found[:3]
    
    skill_patterns = [
        r'Brothers in Arms', r'Repair', r'Concealment', r'Firefighting',
        r'Sixth Sense', r'Recon', r'Mentor', r'Emergency',
        r'Smooth Ride', r'Off-Road Driving', r'Clutch Braking',
        r'Safe Stowage', r'Intuition', r'Adrenaline Rush',
        r'Snap Shot', r'Dead Eye', r'Designated Target'
    ]
    
    skill_found = []
    for pattern in skill_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            skill_found.append(pattern)
    
    parsed["crew_perks"] = {
        "commander": skill_found[:6],
        "gunner": skill_found[:6],
        "driver": skill_found[:6],
        "loader": skill_found[:6]
    }
    
    return parsed

def fetch_build(tank_code):
    print(f"[TOMATO] Fetching build for: {tank_code}")
    
    result = scrape_tank_loadouts(tank_code)
    
    if result.get("error"):
        print(f"[TOMATO] Error: {result['error']}")
        return None
    
    if result.get("data"):
        parsed = parse_tomato_data(result["data"])
        if parsed:
            return parsed
    
    return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tank_code = sys.argv[1]
    else:
        tank_code = "Pl15_60TP_Lewandowskiego"
    
    build = fetch_build(tank_code)
    if build:
        print(json.dumps(build, indent=2))
    else:
        print("Failed to fetch build")