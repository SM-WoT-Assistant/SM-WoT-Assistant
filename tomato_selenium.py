import sys
import json
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

TANK_TO_TOMATO = {
    # Poland
    "Pl15_60TP_Lewandowskiego": ("3473", "60tp"),
    "Pl21_CS_63": ("5265", "cs-63"),
    # USSR
    "R45_IS-7": ("7169", "is-7"),
    "R90_IS-4M": ("6145", "is-4"),
    "R97_Object_140": ("5633", "object-140"),
    "R148_Object_430_U": ("36609", "obj-430u"),
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
    "Cz04_T50_51": ("2417", "tvp-t-50-51"),
    "S16_Kranvagn": ("2433", "kranvagn"),
    "It13_Progetto_M35_mod_46": ("2289", "progett-46"),
    "R97_Object_140": ("5633", "object-140"),
    "R148_Object_430_U": ("36609", "obj-430u"),
}

def get_tank_info(tank_code):
    if tank_code in TANK_TO_TOMATO:
        return TANK_TO_TOMATO[tank_code]
    # Try partial match
    for key in TANK_TO_TOMATO:
        if key in tank_code or tank_code in key:
            return TANK_TO_TOMATO[key]
    return None, None

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,900")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    
    return driver

def click_loadout_tab(driver):
    """Click on Loadout Analytics tab."""
    try:
        # Try to find and click the Loadout tab
        tabs = driver.find_elements(By.TAG_NAME, "button")
        for tab in tabs:
            text = tab.text.lower()
            if "loadout" in text or "equipment" in text or "analytics" in text:
                print(f"[TOMATO] Clicking tab: {tab.text}")
                tab.click()
                time.sleep(3)
                return True
    except Exception as e:
        print(f"[TOMATO] Error clicking tab: {e}")
    return False

def scrape_tank_loadouts(tank_code):
    tank_id, tank_slug = get_tank_info(tank_code)
    if not tank_id:
        print(f"[TOMATO] Unknown tank: {tank_code}")
        return None
    
    print(f"[TOMATO] Scraping {tank_code} -> tomato.gg/tanks/{tank_id}/{tank_slug}")
    
    driver = None
    try:
        driver = create_driver()
        
        url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"
        print(f"[TOMATO] Loading: {url}")
        driver.get(url)
        
        # Wait for page to load
        time.sleep(5)
        
        # Try to click Loadout tab
        click_loadout_tab(driver)
        
        # Wait for content to load
        time.sleep(8)
        
        # Scroll to trigger lazy loading
        driver.execute_script("window.scrollTo(0, 500)")
        time.sleep(2)
        
        # Get page text
        text = driver.find_element(By.TAG_NAME, "body").text
        print(f"[TOMATO] Got text, length: {len(text)}")
        
        # Extract __NEXT_DATA__ JSON
        page_source = driver.page_source
        
        # Try to extract data from page source
        if "__NEXT_DATA__" in page_source:
            print("[TOMATO] Found __NEXT_DATA__")
            import re
            match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>([^<]+)</script>', page_source)
            if match:
                try:
                    import json as json_module
                    data = json_module.loads(match.group(1))
                    next_data = data.get("props", {}).get("pageProps", {})
                    print(f"[TOMATO] pageProps keys: {list(next_data.keys())}")
                    
                    # Extract ALL pageProps data (we'll parse it later)
                    loadout_data = {}
                    
                    # Save full next_data for debugging
                    loadout_data["_full_page_props"] = next_data
                    
                    if "equipment" in next_data:
                        equip = next_data["equipment"]
                        if isinstance(equip, dict) and "data" in equip:
                            equip_data = equip["data"]
                            if "equipmentDist" in equip_data:
                                loadout_data["equipment_dist"] = equip_data["equipmentDist"]
                                print(f"[TOMATO] Equipment dist count: {len(equip_data['equipmentDist'])}")
                            # Check for loadouts
                            if "loadouts" in equip_data:
                                loadout_data["loadouts"] = equip_data["loadouts"]
                                print(f"[TOMATO] Loadouts found: {len(equip_data['loadouts'])}")
                    
                    if "crew" in next_data:
                        crew = next_data["crew"]
                        if isinstance(crew, dict) and "data" in crew:
                            loadout_data["crew"] = crew["data"]
                            print(f"[TOMATO] Crew data extracted")
                    
                    if "fieldMods" in next_data:
                        fm = next_data["fieldMods"]
                        if isinstance(fm, dict) and "data" in fm:
                            loadout_data["field_mods"] = fm["data"]
                            print(f"[TOMATO] Field mods extracted")
                    
                    return loadout_data
                    
                except Exception as e:
                    print(f"[TOMATO] JSON parse error: {e}")
        
        return {"text": text}
        
    except Exception as e:
        print(f"[TOMATO] Error: {e}")
        return None
    finally:
        if driver:
            driver.quit()

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
    
    # Parse equipment from popularSetups (with usage percentages)
    full_data = raw_data.get("_full_page_props", {})
    equip_data = full_data.get("equipment", {}).get("data", {})
    popular_setups = equip_data.get("popularSetups", [])
    
    if popular_setups:
        print(f"[TOMATO] Found {len(popular_setups)} popular setups")
        # Sort by count (most popular first)
        sorted_setups = sorted(popular_setups, key=lambda x: x[1].get("count", 0) if isinstance(x[1], dict) else 0, reverse=True)
        
        # Get top 2 setups
        setup_1 = sorted_setups[0][0] if len(sorted_setups) > 0 else []
        setup_2 = sorted_setups[1][0] if len(sorted_setups) > 1 else []
        
        # Map equipment IDs to names
        equip_id_to_name = {
            "rammer": "Gun Rammer",
            "turbocharger": "Turbocharger",
            "aimingStabilizer": "Vertical Stabilizer",
            "extraHealthReserve": "Improved Hardening",
            "improvedVentilation": "Improved Ventilation",
            "coatedOptics": "Coated Optics",
            "enhancedAimDrives": "Enhanced Gun Laying Drives",
            "additionalGrousers": "Additional Grousers",
            "grousers": "Additional Grousers",
            "experimentalGunLaying": "Innovative Loading System",
            "improvedSights": "Improved Aiming",
            "improvedConfiguration": "Modified Configuration",
            "improvedRotationMechanism": "Improved Rotation Mechanisms",
            "additionalInvisibilityDevice": "Low-Noise Exhaust System",
            "camouflageNet": "Camouflage Net",
            "antifragmentationLining": "Spall Liner",
            "commandersView": "Commander's Vision System",
            "stereoscope": "Binocular Telescope",
            "modernizedTurbochargerRotationMechanism": "Experimental Turbocharger",
        }
        
        parsed["equipment_1"] = [equip_id_to_name.get(e, e) for e in setup_1[:3]]
        parsed["equipment_2"] = [equip_id_to_name.get(e, e) for e in setup_2[:3]]
        
        # Show usage percentages - use totalLoadouts for correct calculation
        total_loadouts = equip_data.get("totalLoadouts", 0)
        count_1 = sorted_setups[0][1].get("count", 0) if len(sorted_setups) > 0 else 0
        count_2 = sorted_setups[1][1].get("count", 0) if len(sorted_setups) > 1 else 0
        pct_1 = (count_1 / total_loadouts * 100) if total_loadouts > 0 else 0
        pct_2 = (count_2 / total_loadouts * 100) if total_loadouts > 0 else 0
        
        print(f"[TOMATO] Equipment 1: {parsed['equipment_1']} ({pct_1:.1f}%)")
        print(f"[TOMATO] Equipment 2: {parsed['equipment_2']} ({pct_2:.1f}%)")
    else:
        # Fallback to old method
        equip_dist = raw_data.get("equipment_dist", [])
        if equip_dist:
            print(f"[TOMATO] Parsing {len(equip_dist)} equipment items")
            equip_names = [item[0].replace(" Class 1", "").replace(" Class 2", "").replace(" Class 3", "") for item in equip_dist]
            parsed["equipment_1"] = equip_names[:3]
            parsed["equipment_2"] = equip_names[3:6] if len(equip_names) > 3 else equip_names[:3]
            print(f"[TOMATO] Equipment 1: {parsed['equipment_1']}")
            print(f"[TOMATO] Equipment 2: {parsed['equipment_2']}")
    
    # Parse crew from crew data
    crew_data = raw_data.get("crew", {})
    if crew_data and isinstance(crew_data, dict):
        crew_info = crew_data.get("crew", [])
        if crew_info:
            print(f"[TOMATO] Parsing crew, roles: {len(crew_info)}")
            # Format: [{"role": "commander", "skills": [[skill_name, {stats}], ...]}, ...]
            skill_map = {
                "brotherhood": "Brothers in Arms",
                "repair": "Repair",
                "camouflage": "Concealment",
                "fireFighting": "Firefighting",
                "commander_eagleEye": "Sixth Sense",
                "commander_tutor": "Mentor",
                "commander_emergency": "Emergency",
                "commander_coordination": "Coordination",
                "commander_enemyShotPredictor": "Recon",
                "commander_practical": "Practicality",
                "driver_smoothDriving": "Smooth Ride",
                "driver_badRoadsKing": "Off-Road Driving",
                "driver_virtuoso": "Clutch Braking",
                "loader_desperado": "Adrenaline Rush",
                "loader_pedant": "Safe Stowage",
                "loader_intuition": "Intuition",
                "gunner_smoothTurret": "Snap Shot",
                "gunner_sniper": "Dead Eye",
                "gunner_focus": "Steady Aim"
            }
            
            for role_data in crew_info:
                role = role_data.get("role", "")
                skills = role_data.get("skills", [])
                
                # Get top skills by count
                skill_counts = []
                for skill in skills:
                    if isinstance(skill, list) and len(skill) >= 2:
                        skill_name = skill[0]
                        stats = skill[1] if len(skill) > 1 else {}
                        count = stats.get("count", 0)
                        skill_counts.append((skill_name, count))
                
                # Sort by count and get top 6 primary skills
                skill_counts.sort(key=lambda x: x[1], reverse=True)
                top_skills = [skill_map.get(s[0], s[0]) for s in skill_counts[:6]]
                
                # Parse secondarySkills for radio operator (loader with secondarySkills = loader_radio)
                secondary = role_data.get("secondarySkills", [])
                if secondary and len(secondary) > 0:
                    sec_counts = []
                    for skill in secondary:
                        if isinstance(skill, list) and len(skill) >= 2:
                            skill_name = skill[0]
                            stats = skill[1] if len(skill) > 1 else {}
                            count = stats.get("count", 0)
                            sec_counts.append((skill_name, count))
                    sec_counts.sort(key=lambda x: x[1], reverse=True)
                    # Take top 4 secondary skills (radio operator)
                    sec_skills = [skill_map.get(s[0], s[0]) for s in sec_counts[:4]]
                    
                    # Store as loader_radio (radio operator - 5th crew member)
                    parsed["crew_perks"]["loader_radio"] = top_skills + sec_skills
                    print(f"[TOMATO] Found loader_radio with {len(sec_skills)} secondary skills")
                else:
                    parsed["crew_perks"][role] = top_skills
            
            print(f"[TOMATO] Crew perks: {parsed['crew_perks']}")
    
    # Field mods from field_mods data
    field_mods = raw_data.get("field_mods", {})
    if field_mods:
        # Field mods format depends on structure
        print(f"[TOMATO] Field mods: {type(field_mods)}")
        parsed["field_mods"] = field_mods
    
    return parsed

def fetch_build(tank_code):
    print(f"[TOMATO] Fetching build for: {tank_code}")
    
    result = scrape_tank_loadouts(tank_code)
    
    if result:
        parsed = parse_tomato_data(result)
        # Include raw data for debugging
        parsed["_raw_data"] = result
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