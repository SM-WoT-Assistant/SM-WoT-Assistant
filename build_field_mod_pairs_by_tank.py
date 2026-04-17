import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

BASE_DIR = os.path.dirname(__file__)
ORION_EXE = os.path.join(BASE_DIR, "tools", "orion", "PjOrion.exe")
POST_PROG_DIR = os.path.join(BASE_DIR, "extracted_data", "common", "post_progression")
FIELD_MOD_BIN = os.path.join(POST_PROG_DIR, "field_modifications.xml")
TMP_DIR = os.path.join(BASE_DIR, "tmp", "field_mod_decode")
FIELD_MOD_XML = os.path.join(TMP_DIR, "field_modifications.xml")
OUT_JSON = os.path.join(POST_PROG_DIR, "field_mod_pairs_by_tank.json")
TANK_DB_PATH = os.path.join(BASE_DIR, "tank_db.json")
EXTRACTED_DATA_DIR = os.path.join(BASE_DIR, "extracted_data")

ROLE_RE = re.compile(r"role_[A-Za-z0-9_]+")
PAIR_TAG_RE = re.compile(r"^(role_[A-Za-z0-9_]+)_pair_(\d+)_([12])$")


def decode_field_modifications_with_orion():
    if not os.path.exists(ORION_EXE):
        raise FileNotFoundError(f"Orion not found: {ORION_EXE}")
    if not os.path.exists(FIELD_MOD_BIN):
        raise FileNotFoundError(f"Missing source: {FIELD_MOD_BIN}")

    if os.path.isdir(TMP_DIR):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    shutil.copy2(FIELD_MOD_BIN, FIELD_MOD_XML)

    cmd = f'cmd /c start /wait "" "{ORION_EXE}" --unpack-folder="{TMP_DIR}" --exit'
    rc = subprocess.call(cmd, cwd=os.path.dirname(ORION_EXE), shell=True, timeout=120)
    if rc not in (0, None):
        raise RuntimeError(f"Orion returned {rc}")

    if not os.path.exists(FIELD_MOD_XML):
        raise FileNotFoundError("Decoded XML not produced")

    with open(FIELD_MOD_XML, "rb") as f:
        head = f.read(16)
    if not head.lstrip().startswith(b"<"):
        raise RuntimeError("Decoded file is not text XML")


def parse_role_pair_icons_from_decoded_xml():
    tree = ET.parse(FIELD_MOD_XML)
    root = tree.getroot()

    role_num_to_icons = {}
    for child in root:
        tag = child.tag.strip()
        m = PAIR_TAG_RE.match(tag)
        if not m:
            continue
        role_key, pair_no, side = m.group(1), int(m.group(2)), m.group(3)
        img = child.findtext("imgName", default="").strip()
        if not img:
            continue

        role_num_to_icons.setdefault(role_key, {}).setdefault(pair_no, {})[side] = img

    role_pairs = {}
    for role_key, by_no in role_num_to_icons.items():
        pairs = {}
        for n in sorted(by_no.keys()):
            sides = by_no[n]
            if "1" in sides and "2" in sides:
                pairs[n] = [sides["1"], sides["2"]]
        if pairs:
            role_pairs[role_key] = pairs
    return role_pairs


def role_base_key(role_norm):
    if not role_norm:
        return None
    if role_norm.startswith("role_MT_"):
        return "role_mediumTank"
    if role_norm.startswith("role_HT_"):
        return "role_heavyTank"
    if role_norm.startswith("role_LT_"):
        return "role_lightTank"
    if role_norm.startswith("role_ATSPG_"):
        return "role_ATSPG"
    if role_norm.startswith("role_SPG_"):
        return "role_SPG"
    return role_norm


def compose_pairs_for_role(role_norm, role_pairs):
    """Compose ordered pair list from base role (1-3) + specialization role (4-5)."""
    if not role_norm:
        return []

    merged = {}
    base_key = role_base_key(role_norm)
    if base_key in role_pairs:
        merged.update(role_pairs[base_key])
    if role_norm in role_pairs:
        merged.update(role_pairs[role_norm])

    ordered = []
    for n in sorted(merged.keys()):
        ordered.append(merged[n])
    return ordered


def find_vehicle_xml(tag):
    for nation in os.listdir(EXTRACTED_DATA_DIR):
        nation_dir = os.path.join(EXTRACTED_DATA_DIR, nation)
        if not os.path.isdir(nation_dir):
            continue
        path = os.path.join(nation_dir, f"{tag}.xml")
        if os.path.exists(path):
            return path
    return None


def extract_role_from_vehicle_xml(tag):
    path = find_vehicle_xml(tag)
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read().decode("latin1", errors="ignore")
    except Exception:
        return None

    pos = raw.find("postProgressionTree")
    if pos >= 0:
        snippet = raw[pos : pos + 320]
        m = ROLE_RE.search(snippet)
        if m:
            return m.group(0)

    m = ROLE_RE.search(raw)
    if m:
        return m.group(0)
    return None


def normalize_role(role):
    if not role:
        return None
    return re.sub(r"\d+$", "", role)


def build_pairs_by_tank(role_pairs):
    with open(TANK_DB_PATH, "r", encoding="utf-8") as f:
        tank_db = json.load(f)

    out = {}
    with_pairs = 0

    for tag in sorted(tank_db.keys()):
        role_raw = extract_role_from_vehicle_xml(tag)
        role_norm = normalize_role(role_raw)
        pairs = compose_pairs_for_role(role_norm, role_pairs)

        if pairs:
            with_pairs += 1

        out[tag] = {
            "role_raw": role_raw,
            "role_normalized": role_norm,
            "pairs": pairs,
        }

    return out, len(tank_db), with_pairs


def main():
    decode_field_modifications_with_orion()
    role_pairs = parse_role_pair_icons_from_decoded_xml()
    by_tank, total, with_pairs = build_pairs_by_tank(role_pairs)

    payload = {
        "source": "decoded field_modifications.xml via Orion + tank postProgressionTree role",
        "role_pair_sets": len(role_pairs),
        "total_tanks": total,
        "tanks_with_pairs": with_pairs,
        "pairs_by_tank": by_tank,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved: {OUT_JSON}")
    print(f"Role pair sets: {len(role_pairs)}")
    print(f"Tanks with pairs: {with_pairs}/{total}")


if __name__ == "__main__":
    main()
