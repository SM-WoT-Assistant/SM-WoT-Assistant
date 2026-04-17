import json
import os
import re
from collections import Counter
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
TANK_DB_PATH = os.path.join(BASE_DIR, "tank_db.json")
VEH_SKILL_DIR = os.path.join(
    BASE_DIR, "extracted_data", "common", "post_progression", "veh_skill_configs"
)
EXTRACTED_DATA_DIR = os.path.join(BASE_DIR, "extracted_data")
OUT_DIR = os.path.join(BASE_DIR, "tmp", "reports")
OUT_JSON = os.path.join(OUT_DIR, "field_mods_all_tanks.json")
OUT_MD = os.path.join(OUT_DIR, "field_mods_all_tanks.md")

TOKEN_ICON_MAP = {
    "enginePower": "improvedEnginePower",
    "gunDispersion": "improvedAimingHandling",
    "aimingTime": "improvedAimingHandling",
    "gunStabilizationFromTurret": "improvedTurretRingStability",
    "gunStabilizationFromHull": "improvedChassisStability",
    "hitPoints": "reinforcedStructure",
    "chassisHP": "reinforcedStructure",
    "hullTraverseSpeed": "betterFriction",
    "turretTraverseSpeed": "improvedTurretTurningWheels",
    "turretTraverse": "improvedTurretTurningWheels",
    "specialShellPenetration": "improvedSharpnessVisor",
    "standardShellVelocity": "improvedMuzzleBreak",
    "allShellDamage": "improvedGunBreech",
    "shellModuleDamage": "improvedGunBreech",
    "additionalShellAmmoCapacity": "improvedLightFilters",
    "gunDepression": "improvedScope",
    "viewRange": "improvedObservationDevice",
    "ammoRackHP": "reinforcedInteriorModules",
    "ammoRackPenalty": "reinforcedInteriorModules",
    "chassisRepairSpeed": "improvedSelfRepairingTracks",
    "crewProtection": "improvedSpallingResistance",
    "enginePenalty": "reinforcedInteriorModules",
}

KPI_KEYS = sorted(TOKEN_ICON_MAP.keys(), key=len, reverse=True)
KPI_PATTERN = re.compile("|".join(re.escape(k) for k in KPI_KEYS))
ROLE_PATTERN = re.compile(r"role_[A-Za-z0-9_]+")


def load_tank_db():
    with open(TANK_DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    if not isinstance(db, dict):
        raise ValueError("tank_db.json has unexpected format")
    return db


def find_vehicle_xml(tag):
    for nation in os.listdir(EXTRACTED_DATA_DIR):
        nation_dir = os.path.join(EXTRACTED_DATA_DIR, nation)
        if not os.path.isdir(nation_dir):
            continue
        candidate = os.path.join(nation_dir, f"{tag}.xml")
        if os.path.exists(candidate):
            return candidate
    return None


def read_latin1(path):
    try:
        with open(path, "rb") as f:
            return f.read().decode("latin1", errors="ignore")
    except Exception:
        return ""


def extract_role(tag):
    veh_xml = find_vehicle_xml(tag)
    if not veh_xml:
        return None
    raw = read_latin1(veh_xml)
    if not raw:
        return None
    # Prefer a role marker near postProgressionTree when possible.
    pos = raw.find("postProgressionTree")
    if pos >= 0:
        win = raw[pos : pos + 300]
        m = ROLE_PATTERN.search(win)
        if m:
            return m.group(0)
    m = ROLE_PATTERN.search(raw)
    if m:
        return m.group(0)
    return None


def extract_pairs_from_mod_file(tag):
    path = os.path.join(VEH_SKILL_DIR, f"{tag}_modifications.xml")
    if not os.path.exists(path):
        return []

    raw = read_latin1(path)
    if not raw:
        return []

    seen_tokens = []
    for m in KPI_PATTERN.finditer(raw):
        token = m.group(0)
        if token not in seen_tokens:
            seen_tokens.append(token)

    icons = []
    for token in seen_tokens:
        icon = TOKEN_ICON_MAP.get(token)
        if icon and icon not in icons:
            icons.append(icon)

    pairs = []
    i = 0
    while i + 1 < len(icons):
        pairs.append([icons[i], icons[i + 1]])
        i += 2
    return pairs


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tank_db = load_tank_db()

    records = []
    with_mod_file = 0
    with_pairs = 0
    role_counter = Counter()

    for tag in sorted(tank_db.keys()):
        data = tank_db.get(tag) or {}
        mod_path = os.path.join(VEH_SKILL_DIR, f"{tag}_modifications.xml")
        has_mod_file = os.path.exists(mod_path)
        pairs = extract_pairs_from_mod_file(tag)
        role = extract_role(tag)
        if role:
            role_counter[role] += 1

        if has_mod_file:
            with_mod_file += 1
        if pairs:
            with_pairs += 1

        records.append(
            {
                "tag": tag,
                "name": data.get("name", ""),
                "tier": data.get("tier", ""),
                "nation": data.get("nation", ""),
                "role": role,
                "has_modifications_file": has_mod_file,
                "pairs": pairs,
                "pairs_count": len(pairs),
            }
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "total_tanks": len(records),
            "tanks_with_modifications_file": with_mod_file,
            "tanks_with_pairs_extracted": with_pairs,
            "unique_roles_detected": len(role_counter),
        },
        "roles_top": role_counter.most_common(30),
        "tanks": records,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = []
    lines.append("# FIELD MODS coverage report")
    lines.append("")
    lines.append(f"Generated: {payload['generated_at']}")
    lines.append("")
    lines.append(f"- Total tanks: {payload['summary']['total_tanks']}")
    lines.append(f"- Tanks with *_modifications.xml: {payload['summary']['tanks_with_modifications_file']}")
    lines.append(f"- Tanks with extracted pairs: {payload['summary']['tanks_with_pairs_extracted']}")
    lines.append(f"- Unique roles detected: {payload['summary']['unique_roles_detected']}")
    lines.append("")
    lines.append("## Tanks with extracted pairs")
    lines.append("")

    for rec in records:
        if not rec["pairs"]:
            continue
        pairs_txt = "; ".join(f"{a} + {b}" for a, b in rec["pairs"])
        lines.append(
            f"- {rec['tag']} | {rec['name']} | role={rec['role']} | pairs={pairs_txt}"
        )

    lines.append("")
    lines.append("## Tanks without extracted pairs")
    lines.append("")
    for rec in records:
        if rec["pairs"]:
            continue
        reason = "no *_modifications.xml" if not rec["has_modifications_file"] else "no KPI tokens"
        lines.append(f"- {rec['tag']} | {rec['name']} | role={rec['role']} | {reason}")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Saved: {OUT_JSON}")
    print(f"Saved: {OUT_MD}")
    print(
        f"Summary: total={len(records)}, with_mod_file={with_mod_file}, with_pairs={with_pairs}"
    )


if __name__ == "__main__":
    main()
