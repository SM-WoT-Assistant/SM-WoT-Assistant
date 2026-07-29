import os
import re
import json
import config

EQUIP_MAP = {}
CONS_MAP = {}
CREW_SKILL_MAP = {}

EQUIP_SLOT_TAGS = {
    "rammer": ["firepower"],
    "aimingStabilizer": ["firepower"],
    "enhancedAimDrives": ["firepower"],
    "improvedSights": ["firepower"],
    "turbocharger": ["mobility"],
    "modernizedTurbochargerRotationMechanism": ["mobility"],
    "grousers": ["mobility"],
    "improvedRotationMechanism": ["mobility"],
    "extraHealthReserve": ["survivability"],
    "antifragmentationLining": ["survivability"],
    "improvedConfiguration": ["survivability"],
    "additionalInvisibilityDevice": ["stealth"],
    "camouflageNet": ["stealth", "camouflage"],
    "stereoscope": ["reconnaissance"],
    "coatedOptics": ["reconnaissance"],
    "commandersView": ["reconnaissance"],
    "improvedVentilation": ["universal"],
}

SLOT_TYPE_NAMES = {
    1: "universal",
    2: "mobility",
    3: "stealth",
    4: "firepower",
    5: "survivability",
}

SLOT2_DEFAULT = {
    "HT": "survivability",
    "MT": "firepower",
    "TD": "survivability",
    "LT": "firepower",
    "SPG": "survivability",
}

_CACHED_LANG = None


def _mo_cache_path(lang):
    return os.path.join(config.USER_DATA_DIR, f"mo_maps_{lang}.json")


def _category_map():
    """Read game_entities_english.json for category membership (which IDs are equipment vs consumables)."""
    path = os.path.join(config.BASE_DIR, "game_entities_english.json")
    if not os.path.exists(path):
        return set(), set()
    try:
        with open(path, encoding="utf-8") as f:
            ge = json.load(f)
        equip_ids = set(ge.get("equipment", {}).keys())
        cons_ids = set(ge.get("consumables", {}).keys())
        return equip_ids, cons_ids
    except Exception:
        return set(), set()


def generate_mo_maps(lm, lang="en"):
    """Build EQUIP_MAP, CONS_MAP, CREW_SKILL_MAP from LanguageModule .mo data.

    Call after language_module.setup() finishes parsing .mo files.
    Maps are stored in module-level dicts + cached to disk per language.
    """
    global EQUIP_MAP, CONS_MAP, CREW_SKILL_MAP, _CACHED_LANG
    _CACHED_LANG = lang

    equip_ids, cons_ids = _category_map()

    equip_map = {}
    cons_map = {}
    crew_map = {}

    artefacts = lm.dictionaries.get("artefacts", {})
    seen_base_names = set()

    for msgid, raw_name in artefacts.items():
        if not msgid.endswith("/name"):
            continue
        name = raw_name.strip()
        if not name or "/" in name or name.startswith("#") or name == "?empty?":
            continue
        if msgid.startswith("#PluralForms") or msgid == "n_a/name":
            continue

        if msgid.startswith("archetype/"):
            base_id = msgid.split("/")[1]
        else:
            base_id = msgid.replace("/name", "")

        if not base_id or base_id in ("n_a", "reserved"):
            continue

        if base_id in cons_ids:
            cons_map[name] = base_id
        elif base_id in equip_ids:
            equip_map[name] = base_id
        else:
            equip_map[name] = base_id

        clean = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
        if clean != name and clean not in seen_base_names:
            seen_base_names.add(clean)
            base = re.sub(r'_tier\d+$', '', base_id) if '_tier' in base_id else base_id
            if base in cons_ids:
                cons_map[clean] = base
            else:
                equip_map[clean] = base

    crew_perks = lm.dictionaries.get("crew_perks", {})
    for msgid, raw_name in crew_perks.items():
        if not msgid.endswith("/name"):
            continue
        name = raw_name.strip()
        if not name or "/" in name or name.startswith("#") or name == "?empty?":
            continue
        perk_id = msgid.replace("/name", "")
        if perk_id in ("n_a", "reserved", "armorPatching"):
            continue
        crew_map[name] = perk_id

    EQUIP_MAP.clear()
    CONS_MAP.clear()
    CREW_SKILL_MAP.clear()
    EQUIP_MAP.update(equip_map)
    CONS_MAP.update(cons_map)
    CREW_SKILL_MAP.update(crew_map)

    _save_cache(equip_map, cons_map, crew_map, lang)


def load_from_cache(lang="en"):
    """Load maps from disk cache. Returns True if loaded successfully."""
    global EQUIP_MAP, CONS_MAP, CREW_SKILL_MAP, _CACHED_LANG
    path = _mo_cache_path(lang)
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        EQUIP_MAP = data.get("equip_map", {})
        CONS_MAP = data.get("cons_map", {})
        CREW_SKILL_MAP = data.get("crew_skill_map", {})
        _CACHED_LANG = lang
        return True
    except Exception:
        return False


def _save_cache(equip_map, cons_map, crew_map, lang):
    try:
        with open(_mo_cache_path(lang), "w", encoding="utf-8") as f:
            json.dump({
                "equip_map": equip_map,
                "cons_map": cons_map,
                "crew_skill_map": crew_map,
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_maps(lang=None):
    """Ensure maps are loaded for the given language. Call at startup after .mo ready."""
    if _CACHED_LANG == lang and EQUIP_MAP:
        return
    if lang and load_from_cache(lang):
        return
    if lang and lang != "en" and load_from_cache("en"):
        return
