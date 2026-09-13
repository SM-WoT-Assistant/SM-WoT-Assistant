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
    "modernizedAimDrivesAimingStabilizer": ["firepower"],
    "modernizedExtraHealthReserveAntifragmentationLining": ["survivability"],
    "modernizedImprovedSightsEnhancedAimDrives": ["firepower"],
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


def sort_equipment_for_slots(equipment_names, slot_types):
    """Sort equipment list to match tank's slot bonus categories.

    slot_types: [slot1_type_id, slot2_type_id, ...] from tank_slots_full.json
    Returns new sorted list. Items matching earlier slots come first.
    """
    if not slot_types or not equipment_names:
        return equipment_names

    def _slot_score(item):
        tags = EQUIP_SLOT_TAGS.get(item, [])
        if not tags:
            return (len(slot_types), 0)
        for i, st in enumerate(slot_types):
            slot_name = SLOT_TYPE_NAMES.get(st, "universal")
            if slot_name in tags:
                return (i, 0)
        return (len(slot_types), 1)

    return sorted(equipment_names, key=_slot_score)

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
    """Load maps from disk cache. Returns True if loaded successfully.

    If the requested language cache is empty or missing, tries any other
    available mo_maps_*.json in USER_DATA_DIR as fallback.
    """
    global EQUIP_MAP, CONS_MAP, CREW_SKILL_MAP, _CACHED_LANG

    def _try_load(lg):
        path = _mo_cache_path(lg)
        if not os.path.exists(path):
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            em = data.get("equip_map", {})
            cm = data.get("cons_map", {})
            crm = data.get("crew_skill_map", {})
            if em or cm or crm:
                EQUIP_MAP.clear()
                CONS_MAP.clear()
                CREW_SKILL_MAP.clear()
                EQUIP_MAP.update(em)
                CONS_MAP.update(cm)
                CREW_SKILL_MAP.update(crm)
                return True
            return False
        except Exception:
            return False

    if _try_load(lang):
        _CACHED_LANG = lang
        return True
    # Fallback: scan USER_DATA_DIR for any available mo_maps_*.json
    try:
        for fn in os.listdir(config.USER_DATA_DIR):
            if fn.startswith("mo_maps_") and fn.endswith(".json"):
                fallback_lang = fn.replace("mo_maps_", "").replace(".json", "")
                if fallback_lang != lang and _try_load(fallback_lang):
                    _CACHED_LANG = fallback_lang
                    return True
    except Exception:
        pass
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
