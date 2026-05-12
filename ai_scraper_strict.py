import sys
import time
import json
import google.genai as genai

DEFAULT_KEY = "AIzaSyDLm-MXve9ECuE_3uoMurzpV1KQmY6Ql4g"

def run_scraper(tank_name):
    current_date = time.strftime("%Y-%m-%d")

    prompt = f"""Current date: {current_date}.

Generate the optimal competitive build data for the tank: {tank_name}.
Output ONLY a JSON object (no markdown, no extra text). Use EXACT names from these lists:

1. EQUIPMENT (Create TWO loadouts):
   Loadout 1 (Open Maps): 3 items from [Gun Rammer, Improved Ventilation, Vertical Stabilizer, Turbocharger, Improved Hardening, Low-Noise Exhaust System, Coated Optics, Commander's Vision System, Binocular Telescope, Camouflage Net, Spall Liner, Modified Configuration, Improved Rotation Mechanisms, Enhanced Gun Laying Drives, Improved Aiming]
   Loadout 2 (City Maps): 3 items from same list

2. AMMO: List all shell types with count (AP, APCR, HEAT, HE, HESH) - total must equal max ammo capacity

3. CONSUMABLES: 3 items from [Small Repair Kit, Large Repair Kit, Small First Aid Kit, Large First Aid Kit, Manual Fire Extinguisher, Automatic Fire Extinguisher, Removed Speed Governor, 100-octane Gasoline, 105-octane Gasoline, Extra Rations (USSR), Case of Cola (USA), Chocolate (Germany), Pudding and Tea (UK), Strong Coffee (France), Improved Rations (China), Bread with Lard (Poland), Buchty (Czechoslovakia), Spaghetti with Meat Sauce (Italy), Onigiri (Japan), Coffee with Cinnamon (Sweden)]

4. CREW PERKS: 6 perks per role (Commander, Gunner, Driver, Loader, Radio Operator)

5. FIELD MODIFICATIONS: List real in-game names

Output as JSON:
{{
  "tank": "IS-7",
  "equipment": {{"loadout_1_open_maps": [...], "loadout_2_city_corridor_maps": [...]}},
  "ammo": {{"AP": 10, "APCR": 18, "HE": 2}},
  "consumables": [...],
  "crew_perks": {{"commander": [...], "gunner": [...], "driver": [...], "loader": [...], "radio_operator": [...]}},
  "field_modifications": [...]
}}
"""

    try:
        genai.configure(api_key=DEFAULT_KEY)
        client = genai.Client()
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        text = response.text.replace('```json', '').replace('```', '').strip()
        if '{' in text:
            text = text[text.find('{'):text.rfind('}')+1]
        
        data = json.loads(text)
        print("JSON_RESULT:" + json.dumps(data))
        
    except Exception as e:
        print(f"JSON_RESULT:{{\"error\": \"{str(e)}\"}}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_scraper(sys.argv[1])
    else:
        run_scraper("IS-7")
