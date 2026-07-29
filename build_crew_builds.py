"""
Build crew_builds.json from decoded WoT vehicle XML files.

Auto-update: runs only when game client version changes.
- Extracts real crew layout (including secondary roles) from extracted_data/<nation>/*.xml
- Fills missing tanks from class defaults
- Stores global perk policy (tier -> perks, secondary-role bonus)
- Stores global role skill pools/defaults

Run:
    python build_crew_builds.py
"""

import os
import re
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted_data")
TTH_WORK_DIR = os.path.join(BASE_DIR, "tmp", "tth_work")
TANK_DB_PATH = os.path.join(BASE_DIR, "tank_db.json")
OUT_PATH = os.path.join(BASE_DIR, "crew_builds.json")

KNOWN_ROLES = {"commander", "gunner", "driver", "loader", "radioman"}

DEFAULT_ROLES_BY_CLASS = {
    "HT": ["commander", "gunner", "driver", "loader"],
    "MT": ["commander", "gunner", "driver", "loader"],
    "LT": ["commander", "gunner", "driver", "loader"],
    "TD": ["commander", "gunner", "driver", "loader"],
    "SPG": ["commander", "gunner", "driver", "loader"],
}

DEFAULT_SKILLS = {
    "commander": ["commander_sixthSense", "commander_practical", "brotherhood"],
    "gunner": ["gunner_sniper", "gunner_focus", "brotherhood"],
    "driver": ["driver_smoothDriving", "driver_badRoadsKing", "brotherhood"],
    "loader": ["loader_pedant", "loader_desperado", "brotherhood"],
    "radioman": ["camouflage", "repair", "brotherhood"],
}

ROLE_SKILL_POOLS = {
    "commander": [
        "commander_sixthSense", "commander_practical", "commander_eagleEye",
        "commander_enemyShotPredictor", "commander_emergency", "commander_tutor",
        "commander_coordination", "commander_holdLine", "commander_staySharp",
        "repair", "camouflage", "brotherhood"
    ],
    "gunner": [
        "gunner_sniper", "gunner_focus", "gunner_rancorous",
        "gunner_smoothTurret", "gunner_armorer", "gunner_loneWolf",
        "gunner_quickAiming", "gunner_pointBlast",
        "repair", "camouflage", "brotherhood", "fireFighting"
    ],
    "driver": [
        "driver_smoothDriving", "driver_badRoadsKing", "driver_virtuoso",
        "driver_rammingMaster", "driver_reliablePlacement", "driver_motorExpert",
        "driver_suspensionRepair", "driver_bulletproof",
        "repair", "camouflage", "brotherhood", "fireFighting"
    ],
    "loader": [
        "loader_pedant", "loader_desperado", "loader_intuition",
        "loader_perfectCharge", "loader_melee", "loader_ammunitionImprove",
        "loader_secondChance", "loader_magMastery",
        "repair", "camouflage", "brotherhood", "fireFighting"
    ],
    "radioman": [
        "radioman_finder", "improvedRadioCommunication", "smokeSignal",
        "radioman_signalInterception", "radioman_interference", "radioman_expert",
        "radioman_sideBySide", "radioman_threatSearch", "radioman_battleTempered",
        "repair", "camouflage", "brotherhood", "fireFighting"
    ],
}

PERK_POLICY = {
    "default_primary_perk_count": 6,
    "primary_perk_count_by_tier": {
        "1": 6, "2": 6, "3": 6, "4": 6,
        "5": 6, "6": 6,
        "7": 6,
        "8": 6,
        "9": 6,
        "10": 6,
        "11": 6,
    },
    "secondary_perk_bonus_per_role": 3,
    "secondary_perk_bonus_by_custom_role_slots": {
        "2 4": 3,
        "3 5": 3
    },
    "max_perks_per_member": 15,
}


def _read_vehicle_source(xml_path):
    with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _parse_vehicle_crew_info(xml_path):
    raw = _read_vehicle_source(xml_path)
    m = re.search(r"<crew>(.*?)</crew>", raw, re.DOTALL)
    if not m:
        return None

    block = m.group(1)
    members = []
    for role, inner in re.findall(r"<(\w+)\s*>(.*?)</\w+>", block, re.DOTALL):
        role = (role or "").strip()
        if role not in KNOWN_ROLES:
            continue

        text = re.sub(r"<.*?>", " ", inner or "", flags=re.DOTALL)
        text = re.sub(r"\s+", " ", text).strip()
        also = []
        if text:
            for token in re.split(r"[\s,;/|]+", text):
                token = token.strip()
                if token in KNOWN_ROLES and token != role and token not in also:
                    also.append(token)

        members.append({"role": role, "also": also})

    if not members:
        return []

    out = []
    role_count = {}
    roles = [m["role"] for m in members]

    for member in members:
        role = member["role"]
        also = member["also"]

        role_count[role] = role_count.get(role, 0) + 1

        if role_count[role] > 1:
            if role == "loader":
                has_radioman = "radioman" in roles or any("radioman" in m.get("also", []) for m in out)
                if not has_radioman:
                    out.append({"role": "loader_radio", "also": ["radioman"]})
                else:
                    out.append({"role": "loader", "also": []})
            else:
                out.append({"role": role + "_" + str(role_count[role]), "also": also})
        else:
            out.append(member)

    slot_match = re.search(r"<customRoleSlotOptions>\s*([^<]+?)\s*</customRoleSlotOptions>", raw, re.DOTALL)
    custom_role_slot_options = None
    if slot_match:
        custom_role_slot_options = re.sub(r"\s+", " ", slot_match.group(1)).strip()

    return {
        "crew_members": out,
        "custom_role_slot_options": custom_role_slot_options,
    }


def _collect_vehicle_sources():
    sources = {}
    skip = {"list.xml", "customization.xml", "Observer.xml"}

    if os.path.isdir(EXTRACT_DIR):
        for nation in sorted(os.listdir(EXTRACT_DIR)):
            npath = os.path.join(EXTRACT_DIR, nation)
            if not os.path.isdir(npath):
                continue
            for fname in sorted(os.listdir(npath)):
                if not fname.endswith(".xml") or fname in skip:
                    continue
                tag = fname[:-4]
                sources[tag] = os.path.join(npath, fname)

    if os.path.isdir(TTH_WORK_DIR):
        for root, _dirs, files in os.walk(TTH_WORK_DIR):
            for fname in files:
                if not fname.endswith('.xml') or fname in skip:
                    continue
                tag = fname[:-4]
                sources[tag] = os.path.join(root, fname)

    return sources


def main():
    print("[INFO] Building crew_builds.json from XML files...")

    with open(TANK_DB_PATH, "r", encoding="utf-8") as f:
        tank_db = json.load(f)

    tank_slots = {}
    try:
        with open("tank_slots_full.json", "r", encoding="utf-8") as f:
            tank_slots = json.load(f)
    except Exception:
        pass

    xml_crew = {}
    sources = _collect_vehicle_sources()
    for tag, path in sources.items():
        parsed = _parse_vehicle_crew_info(path)
        if parsed and parsed.get('crew_members'):
            xml_crew[tag] = parsed

    tanks = {}
    for tag, data in tank_db.items():
        tank_class = str((data or {}).get("class") or "MT").upper()
        parsed = xml_crew.get(tag)
        if parsed:
            members = parsed.get('crew_members') or []
            custom_role_slot_options = parsed.get('custom_role_slot_options')
        else:
            slot_data = tank_slots.get(tag, {})
            slot_roles = slot_data.get('crew_roles') if isinstance(slot_data, dict) else None
            if slot_roles and isinstance(slot_roles, list):
                members = []
                has_radioman = any(r == 'radioman' for r in slot_roles)
                loader_count = sum(1 for r in slot_roles if r == 'loader')
                for role in slot_roles:
                    also = []
                    if role == 'loader' and loader_count >= 2 and not has_radioman:
                        idx = [i for i, m in enumerate(members) if m['role'] == 'loader']
                        if len(idx) >= 1:
                            members.append({"role": "loader", "also": []})
                            continue
                    elif role == 'commander' and not has_radioman:
                        also = ['radioman']
                    members.append({"role": role, "also": also})
                custom_role_slot_options = None
            else:
                defaults = DEFAULT_ROLES_BY_CLASS.get(tank_class, DEFAULT_ROLES_BY_CLASS["MT"])
                members = [{"role": role, "also": []} for role in defaults]
                custom_role_slot_options = None

        tanks[tag] = {
            "crew_members": members,
            "crew": [m["role"] for m in members],
        }
        if custom_role_slot_options:
            tanks[tag]["custom_role_slot_options"] = custom_role_slot_options

    payload = {
        "_comment": "General crew model. Auto-regenerated on XML change.",
        "version": 2,
        "_default_roles": DEFAULT_ROLES_BY_CLASS,
        "_default_skills": DEFAULT_SKILLS,
        "_role_skill_pools": ROLE_SKILL_POOLS,
        "_perk_policy": PERK_POLICY,
        "tanks": tanks,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    xml_real_count = sum(1 for tag in tanks if tag in xml_crew)
    print(f"crew_builds.json regenerated: {len(tanks)} tanks")
    print(f"XML crew (real): {xml_real_count}")
    print(f"Class-default crew: {len(tanks) - xml_real_count}")


if __name__ == "__main__":
    main()