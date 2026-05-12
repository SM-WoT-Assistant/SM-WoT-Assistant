"""
Extract equipment loadouts from WoT client (optional_devices_usage.csv)
This data contains popular equipment builds for all tanks.

Auto-update: runs only when game client version changes.

Run:
    python extract_equipment_loadouts.py
"""
import zipfile
import csv
import io
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EQUIPMENT_MAP = {
    "ventilation": "Improved Ventilation",
    "aimingStabilizer": "Vertical Stabilizer",
    "rammer": "Gun Rammer",
    "coatedOptics": "Coated Optics",
    "enhancedAimDrives": "Enhanced Gun Laying Drives",
    "improvedSights": "Improved Aiming",
    "turbocharger": "Turbocharger",
    "extraHealthReserve": "Improved Hardening",
    "additionalInvisibilityDevice": "Low-Noise Exhaust System",
    "commandersView": "Commander's Vision System",
    "stereoscope": "Binocular Telescope",
    "camouflageNet": "Camouflage Net",
    "antifragmentationLining": "Spall Liner",
    "improvedConfiguration": "Modified Configuration",
    "improvedRotationMechanism": "Improved Rotation Mechanisms",
    "improvedAiming": "Improved Aiming",
}

NATION_MAP = {
    "china": "China",
    "czech": "Czechoslovakia",
    "france": "France",
    "germany": "Germany",
    "japan": "Japan",
    "poland": "Poland",
    "sweden": "Sweden",
    "uk": "UK",
    "usa": "USA",
    "ussr": "USSR",
}


def extract_loadouts(pkg_path, output_path):
    """Extract equipment loadouts from scripts.pkg."""
    if not os.path.exists(pkg_path):
        print(f"[ERROR] scripts.pkg not found at {pkg_path}")
        return False

    print(f"[INFO] Extracting equipment loadouts from {pkg_path}")

    loadouts_data = {}

    with zipfile.ZipFile(pkg_path, 'r') as z:
        data = z.read('scripts/item_defs/optional_devices_assistance/optional_devices_usage.csv')
        text = data.decode('utf-8', errors='ignore')

        reader = csv.DictReader(io.StringIO(text), delimiter=';')

        for row in reader:
            tank_id = row.get('VEHICLE_NAME', '')
            dev1 = row.get('DEV_1', '')
            dev2 = row.get('DEV_2', '')
            dev3 = row.get('DEV_3', '')
            usage = row.get('SETUP_USAGE_PERCENT', '0')

            if not tank_id:
                continue

            nation, tank_name = tank_id.split(':', 1) if ':' in tank_id else ('', tank_id)

            eq1 = EQUIPMENT_MAP.get(dev1, dev1)
            eq2 = EQUIPMENT_MAP.get(dev2, dev2)
            eq3 = EQUIPMENT_MAP.get(dev3, dev3)

            loadout = {
                "equipment": [eq1, eq2, eq3],
                "usage_percent": float(usage) if usage else 0
            }

            if tank_id not in loadouts_data:
                loadouts_data[tank_id] = []

            loadouts_data[tank_id].append(loadout)

    for tank_id, loadouts in loadouts_data.items():
        loadouts.sort(key=lambda x: x['usage_percent'], reverse=True)
        loadouts_data[tank_id] = loadouts[:3]

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(loadouts_data, f, ensure_ascii=False, indent=2)

    print(f"[OK] Extracted {len(loadouts_data)} tanks to {output_path}")
    return True


if __name__ == "__main__":
    pkg_path = r"C:\Games\World_of_Tanks_EU\res\packages\scripts.pkg"
    output_path = "equipment_loadouts.json"

    if os.path.exists(pkg_path):
        extract_loadouts(pkg_path, output_path)
    else:
        print(f"[ERROR] scripts.pkg not found at {pkg_path}")
        print("Please check your WoT installation path")