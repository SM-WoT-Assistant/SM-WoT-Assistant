"""
Build crew_builds.json from decoded WoT vehicle XML files.

This script is version-stable and avoids per-tank hardcoded perk rules:
- Extracts real crew layout (including secondary roles) from extracted_data/<nation>/*.xml
- Fills missing tanks from class defaults
- Stores global perk policy (tier -> perks, secondary-role bonus)
- Stores global role skill pools/defaults

Run after extraction:
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
        "commander_enemyShotPredictor", "repair", "camouflage", "brotherhood"
    ],
    "gunner": [
        "gunner_sniper", "gunner_focus", "gunner_rancorous",
        "gunner_smoothTurret", "repair", "camouflage", "brotherhood"
    ],
    "driver": [
        "driver_smoothDriving", "driver_badRoadsKing", "driver_virtuoso",
        "driver_rammingMaster", "repair", "camouflage", "brotherhood"
    ],
    "loader": [
        "loader_pedant", "loader_desperado", "loader_intuition",
        "repair", "camouflage", "brotherhood", "fireFighting"
    ],
    "radioman": [
        "radioman_finder", "improvedRadioCommunication", "smokeSignal",
        "camouflage", "repair", "brotherhood", "fireFighting"
    ],
}

PERK_POLICY = {
    "default_primary_perk_count": 6,
    "primary_perk_count_by_tier": {
        "1": 1, "2": 1, "3": 1, "4": 1,
        "5": 2, "6": 2,
        "7": 4,
        "8": 6,
        "9": 6,
        "10": 6,
        "11": 6,
    },
    "secondary_perk_bonus_per_role": 3,
    "secondary_perk_bonus_by_custom_role_slots": {
        "2 4": 3,
        "3 5": 1
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

    # Deduplicate same role entries while preserving first appearance.
    out = []
    seen = set()
    for member in members:
        role = member["role"]
        if role in seen:
            continue
        seen.add(role)
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
                sources.setdefault(tag, os.path.join(npath, fname))

    if os.path.isdir(TTH_WORK_DIR):
        for root, _dirs, files in os.walk(TTH_WORK_DIR):
            for fname in files:
                if not fname.endswith('.xml') or fname in skip:
                    continue
                tag = fname[:-4]
                # Prefer decoded tmp/tth_work vehicle XML when available.
                sources[tag] = os.path.join(root, fname)

    return sources


def main():
    with open(TANK_DB_PATH, "r", encoding="utf-8") as f:
        tank_db = json.load(f)

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
        if not parsed:
            defaults = DEFAULT_ROLES_BY_CLASS.get(tank_class, DEFAULT_ROLES_BY_CLASS["MT"])
            members = [{"role": role, "also": []} for role in defaults]
            custom_role_slot_options = None
        else:
            members = parsed.get('crew_members') or []
            custom_role_slot_options = parsed.get('custom_role_slot_options')

        tanks[tag] = {
            "crew_members": members,
            "crew": [m["role"] for m in members],
        }
        if custom_role_slot_options:
            tanks[tag]["custom_role_slot_options"] = custom_role_slot_options

    payload = {
        "_comment": "General crew model. Regenerate on game update with build_crew_builds.py",
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
