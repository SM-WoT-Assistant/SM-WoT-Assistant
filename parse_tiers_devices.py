import os
import sys
import json
import zipfile
import xml.etree.ElementTree as ET
import config

_TIERS_RAW = os.path.join(
    "temp_scripts2", "scripts", "item_defs", "vehicles",
    "common", "optional_devices", "tiers_devices.xml"
)
_TIERS_DECODED = os.path.join(
    "temp_scripts", "decoded", "tiers_devices_decoded.xml"
)
_PKG_ENTRY = "scripts/item_defs/vehicles/common/optional_devices/tiers_devices.xml"
_BW_SIG = b'\x45\x4e\xa1\x62'

ALL_CLASSES = ["SPG", "LT", "MT", "HT", "TD"]


def _try_client_pkg():
    """Читає tiers_devices.xml з scripts.pkg клієнта гри (ZIP) в писемний кеш.

    Повертає шлях до кешованої сирої копії або None."""
    try:
        if not os.path.exists(config.SETTINGS_FILE):
            return None
        with open(config.SETTINGS_FILE, "r", encoding="utf-8") as f:
            wot_path = (json.load(f) or {}).get("wot_path", "")
        if not wot_path:
            return None
        pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
        if not os.path.exists(pkg_path):
            return None
        raw_path = os.path.join(config.USER_DATA_DIR, "tiers_devices_raw.xml")
        with zipfile.ZipFile(pkg_path, "r") as z:
            with open(raw_path, "wb") as f:
                f.write(z.read(_PKG_ENTRY))
        return raw_path
    except Exception:
        return None


def _ensure_decoded(xml_path, base_dir):
    """If xml_path is binary BigWorld format, decode it and return decoded path.
    If already text XML, return the path as-is."""
    try:
        with open(xml_path, 'rb') as f:
            header = f.read(4)
        if header == _BW_SIG:
            decoded_path = os.path.join(config.USER_DATA_DIR, "tiers_devices_decoded.xml")
            os.makedirs(os.path.dirname(decoded_path), exist_ok=True)
            from decode_xml import WotXmlParser
            parser = WotXmlParser()
            root_name = os.path.basename(xml_path).split('.')[0]
            with open(xml_path, 'rb') as f:
                data = f.read()
            parser.data = data
            parser.offset = 5
            parser.dictionary = []
            while True:
                s_start = parser.offset
                while parser.offset < len(parser.data) and parser.data[parser.offset] != 0:
                    parser.offset += 1
                s = parser.data[s_start:parser.offset].decode('utf-8', errors='ignore')
                parser.offset += 1
                if not s:
                    break
                parser.dictionary.append(s)
            xml_content = parser.read_element(root_name, 0)
            with open(decoded_path, 'w', encoding='utf-8') as f:
                f.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
                f.write(xml_content)
            return decoded_path
    except Exception:
        pass
    return xml_path


def _extract_tier_suffix(user_string):
    if "_tier" not in user_string:
        return 0
    part = user_string.split("_tier")[-1].split("/")[0].split("_")[0]
    try:
        return int(part)
    except ValueError:
        return 0


def _extract_archetype(user_string):
    if ":" in user_string:
        base = user_string.split(":")[-1].split("/")[0]
        for suffix in ["_tier1", "_tier2", "_tier3", "_tier4", "_tier5"]:
            base = base.replace(suffix, "")
        return base
    return user_string


def _tag_to_class(tag_string):
    """Map a BigWorld tag pattern to a WoT class code.
    Only maps unambiguous direct class tags, NOT compound vehicle tags.
    Returns None if no safe mapping (caller should keep raw tag)."""
    t = tag_string.lower().strip()
    # Direct class tags only — no compound tags like "wheeledVehicle lightTank"
    if t in ("spg", "sau", "artillery"):
        return "SPG"
    if t in ("lighttank", "light_tank"):
        return "LT"
    if t in ("mediumtank", "medium_tank"):
        return "MT"
    if t in ("heavytank", "heavy_tank"):
        return "HT"
    if t in ("at-spg", "atspg", "tank_destroyer"):
        return "TD"
    return None


def load_tiers_devices(xml_path=None):
    """Парсить tiers_devices.xml і повертає словники обладнання.

    xml_path: шлях до DECODED XML. Якщо None, шукає в стандартних місцях.
    Якщо файл в BigWorld форматі, декодує автоматично.

    Returns:
        dict with keys:
            'by_tier': {tier_number: [device_key, ...]}
            'exclude_by_class': {class_code: [device_key, ...]}
            'exclude_by_tags': {tag_pattern: [device_key, ...]}
            'categories': {device_key: category_name}
            'device_info': {device_key: {id, archetype, tier, minLevel, maxLevel, ...}}
        або {} при помилці.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if xml_path is None:
        pkg_raw = _try_client_pkg()
        candidates = []
        if pkg_raw:
            candidates.append(pkg_raw)
        candidates.extend([
            os.path.join(base_dir, _TIERS_DECODED),
            os.path.join(base_dir, _TIERS_RAW),
        ])
    else:
        candidates = [xml_path]

    xml_path_actual = None
    for c in candidates:
        if os.path.exists(c):
            xml_path_actual = c
            break

    if xml_path_actual is None:
        return {}

    xml_path_actual = _ensure_decoded(xml_path_actual, base_dir)

    try:
        tree = ET.parse(xml_path_actual)
        root = tree.getroot()
    except Exception:
        return {}

    devices = list(root)

    by_tier = {t: [] for t in range(1, 12)}
    exclude_by_class = {}
    exclude_by_tags = {}
    categories = {}
    device_info = {}
    tierless_devices = []

    for dev in devices:
        us_el = dev.find("userString")
        if us_el is None or not us_el.text:
            continue
        user_string = us_el.text.strip()

        arch_el = dev.find("archetype")
        archetype = arch_el.text.strip() if arch_el is not None and arch_el.text else ""

        id_el = dev.find("id")
        dev_id = id_el.text.strip() if id_el is not None and id_el.text else "0"

        cat_el = dev.find("categories")
        cat = cat_el.text.strip() if cat_el is not None and cat_el.text else ""

        tags_el = dev.find("tags")
        tags = tags_el.text.strip() if tags_el is not None and tags_el.text else ""

        tier_suffix = _extract_tier_suffix(user_string)
        dev_key_base = _extract_archetype(user_string)
        dev_key = f"{dev_key_base}_tier{tier_suffix}" if tier_suffix else dev_key_base

        vf = dev.find("vehicleFilter")
        min_level = None
        max_level = None
        excl_list = []

        if vf is not None:
            incl = vf.find("include")
            if incl is not None:
                for v in list(incl):
                    ml = v.find("minLevel")
                    xl = v.find("maxLevel")
                    if ml is not None and ml.text:
                        try:
                            min_level = int(ml.text.strip())
                        except ValueError:
                            pass
                    if xl is not None and xl.text:
                        try:
                            max_level = int(xl.text.strip())
                        except ValueError:
                            pass

            excl_el = vf.find("exclude")
            if excl_el is not None:
                for v in list(excl_el):
                    mt = v.find("mandatoryTags")
                    if mt is not None and mt.text:
                        excl_list.append(mt.text.strip())

        info = {
            "id": dev_id,
            "archetype": archetype,
            "user_string": user_string,
            "dev_key": dev_key,
            "tier_suffix": tier_suffix,
            "min_level": min_level,
            "max_level": max_level,
            "tags": tags,
            "categories": cat,
            "excludes": excl_list,
        }
        device_info[dev_key] = info
        categories[dev_key] = cat

        if excl_list:
            for tag_pattern in excl_list:
                if tag_pattern not in exclude_by_tags:
                    exclude_by_tags[tag_pattern] = []
                exclude_by_tags[tag_pattern].append(dev_key)

                wot_class = _tag_to_class(tag_pattern)
                if wot_class:
                    if wot_class not in exclude_by_class:
                        exclude_by_class[wot_class] = []
                    exclude_by_class[wot_class].append(dev_key)

        if min_level is not None and max_level is not None:
            for t in range(min_level, max_level + 1):
                if t in by_tier:
                    by_tier[t].append(dev_key)
        else:
            tierless_devices.append(dev_key)

    for t in range(1, 12):
        by_tier[t].extend(tierless_devices)

    if not any(by_tier[t] for t in range(1, 12)):
        return {}

    return {
        "by_tier": by_tier,
        "exclude_by_class": exclude_by_class,
        "exclude_by_tags": exclude_by_tags,
        "categories": categories,
        "device_info": device_info,
    }
