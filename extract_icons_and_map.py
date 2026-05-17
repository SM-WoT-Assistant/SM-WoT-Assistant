import os
import json
import zipfile
import shutil

BASE_DIR = os.getcwd()
GUI_PKG = r"C:\Games\World_of_Tanks_EU\res\packages\gui-part1.pkg"
ICONS_OUTPUT = os.path.join(BASE_DIR, "extracted_icons", "artefacts")

def extract_artefact_icons():
    os.makedirs(ICONS_OUTPUT, exist_ok=True)
    
    with zipfile.ZipFile(GUI_PKG, 'r') as z:
        for entry in z.infolist():
            if 'gui/maps/icons/artefact/' in entry.filename and entry.filename.endswith('.png'):
                filename = os.path.basename(entry.filename)
                out_path = os.path.join(ICONS_OUTPUT, filename)
                with open(out_path, 'wb') as f:
                    f.write(z.read(entry.filename))
                print(f"Extracted: {filename}")

def load_game_entities():
    with open(os.path.join(BASE_DIR, "game_entities.json"), 'r', encoding='utf-8') as f:
        return json.load(f)

def build_icon_mapping():
    game_data = load_game_entities()
    
    mapping = {
        "equipment": {},
        "consumables": {},
        "crew_perks": {},
        "field_mods": {}
    }
    
    for item_id, item_data in game_data.get("equipment", {}).items():
        mapping["equipment"][item_id] = {
            "name": item_data.get("name", item_id),
            "icon": item_data.get("icon", "")
        }
    
    for item_id, item_data in game_data.get("consumables", {}).items():
        mapping["consumables"][item_id] = {
            "name": item_data.get("name", item_id),
            "icon": item_data.get("icon", "")
        }
    
    mapping_file = os.path.join(BASE_DIR, "icon_mapping.json")
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    print(f"\nMapping saved to: {mapping_file}")
    print(f"Equipment: {len(mapping['equipment'])}")
    print(f"Consumables: {len(mapping['consumables'])}")

if __name__ == "__main__":
    print("=" * 60)
    print("STEP 1: Extract artefact icons from gui-part1.pkg")
    print("=" * 60)
    extract_artefact_icons()
    
    print("\n" + "=" * 60)
    print("STEP 2: Build icon mapping")
    print("=" * 60)
    build_icon_mapping()