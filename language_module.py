"""
language_module.py — Parse .mo files from WoT game client (any language).
Detects language, builds dictionaries, exports locale JSON for website.
"""
import os
import json
import struct
import xml.etree.ElementTree as ET
import config


class LanguageModule:
    def __init__(self, wot_path=None):
        self.wot_path = wot_path
        self.dictionaries = {}
        self.language = ""
        self._cache_dir = None

    def detect_language(self):
        """Detect game client language from game_info.xml <localization> tag."""
        if not self.wot_path:
            print("[LANG] detect: no wot_path")
            return "en"

        gi_path = os.path.join(self.wot_path, "game_info.xml")
        if os.path.exists(gi_path):
            try:
                tree = ET.parse(gi_path)
                loc_el = tree.find(".//localization")
                if loc_el is not None and loc_el.text:
                    lang = loc_el.text.strip().lower()
                    if lang:
                        self.language = lang
                        print(f"[LANG] detect: {lang} from game_info.xml")
                        return lang
            except Exception as e:
                print(f"[LANG] detect: parse error {e}")

        self.language = "en"
        print("[LANG] detect: fallback to en")
        return "en"

    def get_available_languages(self):
        """Return list of language codes available for this game installation."""
        if not self.wot_path:
            return ["en"]

        gi_path = os.path.join(self.wot_path, "game_info.xml")
        if not os.path.exists(gi_path):
            return ["en"]

        try:
            tree = ET.parse(gi_path)
            langs = []
            for el in tree.findall(".//language_id"):
                if el.text and el.text.strip():
                    langs.append(el.text.strip().lower())
            return langs if langs else ["en"]
        except Exception:
            return ["en"]

    def build_all_dictionaries(self, language=None):
        """Parse all .mo files from game client. Replaces old caches."""
        if not self.wot_path:
            return False

        if language:
            self.language = language
        else:
            self.detect_language()
        self._cache_dir = os.path.join(config.USER_DATA_DIR, "localization", self.language)

        if os.path.isdir(self._cache_dir):
            import shutil
            shutil.rmtree(self._cache_dir, ignore_errors=True)
        os.makedirs(self._cache_dir, exist_ok=True)

        mo_dir = os.path.join(self.wot_path, "res", "text", "lc_messages")
        if not os.path.isdir(mo_dir):
            return False

        categories = {
            "artefacts": "artefacts.mo",
            "crew_perks": "crew_perks.mo",
            "item_types": "item_types.mo",
            "arenas": "arenas.mo",
            "tooltips": "tooltips.mo",
            "menu": "menu.mo",
            "ingame_gui": "ingame_gui.mo",
            "tank_setup": "tank_setup.mo",
            "settings": "settings.mo",
            "common": "common.mo",
            "dialogs": "dialogs.mo",
            "manual": "manual.mo",
            "crew": "crew.mo",
            "battle_results": "battle_results.mo",
            "system_messages": "system_messages.mo",
            "veh_post_progression": "veh_post_progression.mo",
            "hangar": "hangar.mo",
            "prebattle": "prebattle.mo",
            "veh_compare": "veh_compare.mo",
        }

        for name, fname in categories.items():
            mo_path = os.path.join(mo_dir, fname)
            if os.path.exists(mo_path):
                data = self._parse_mo(mo_path)
                if data:
                    self.dictionaries[name] = data
                    self._save_cache(name, data)

        self._build_vehicles_dict(mo_dir)
        self._build_crew_dict(mo_dir)
        return len(self.dictionaries) > 0

    def _parse_mo(self, path):
        try:
            with open(path, "rb") as f:
                raw = f.read()

            magic = struct.unpack("<I", raw[:4])[0]
            if magic != 0x950412DE:
                return {}

            n = struct.unpack("<I", raw[8:12])[0]
            ot = struct.unpack("<I", raw[12:16])[0]
            tt = struct.unpack("<I", raw[16:20])[0]

            result = {}
            for i in range(n):
                ol = struct.unpack("<I", raw[ot + i * 8: ot + i * 8 + 4])[0]
                oo = struct.unpack("<I", raw[ot + i * 8 + 4: ot + i * 8 + 8])[0]
                tl = struct.unpack("<I", raw[tt + i * 8: tt + i * 8 + 4])[0]
                to = struct.unpack("<I", raw[tt + i * 8 + 4: tt + i * 8 + 8])[0]

                if ol == 0 or tl == 0:
                    continue

                msgid = raw[oo: oo + ol].decode("utf-8", errors="ignore")
                msgstr = raw[to: to + tl].decode("utf-8", errors="ignore")

                if msgid and msgstr and not msgid.startswith("Project-Id"):
                    result[msgid] = msgstr

            return result
        except Exception:
            return {}

    def _build_vehicles_dict(self, mo_dir):
        vehicle_files = [f for f in os.listdir(mo_dir) if f.endswith("_vehicles.mo")]
        combined = {}
        for fname in vehicle_files:
            mo_path = os.path.join(mo_dir, fname)
            data = self._parse_mo(mo_path)
            if data:
                combined.update(data)
        if combined:
            self.dictionaries["vehicles"] = combined
            self._save_cache("vehicles", combined)

    def _build_crew_dict(self, mo_dir):
        crew_files = [f for f in os.listdir(mo_dir) if f.endswith("_crew.mo")]
        combined = {}
        for fname in crew_files:
            mo_path = os.path.join(mo_dir, fname)
            data = self._parse_mo(mo_path)
            if data:
                combined.update(data)
        if combined:
            self.dictionaries["crew_nations"] = combined
            self._save_cache("crew_nations", combined)

    def _save_cache(self, name, data):
        try:
            path = os.path.join(self._cache_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            pass

    def load_cache(self):
        if not self.language:
            self.detect_language()
        self._cache_dir = os.path.join(config.USER_DATA_DIR, "localization", self.language)
        if not os.path.isdir(self._cache_dir):
            return False
        loaded = False
        for fname in os.listdir(self._cache_dir):
            if fname.endswith(".json"):
                name = fname[:-5]
                try:
                    path = os.path.join(self._cache_dir, fname)
                    with open(path, "r", encoding="utf-8") as f:
                        self.dictionaries[name] = json.load(f)
                    loaded = True
                except Exception:
                    pass
        return loaded

    def t(self, msgid, default=None):
        if not msgid:
            return default or msgid
        for cat_data in self.dictionaries.values():
            if msgid in cat_data:
                val = cat_data[msgid]
                if val and not val.startswith("#"):
                    val = val.strip()
                    return val if val and val != "?empty?" else (default or msgid)
        return default or msgid

    def export_locale_json(self, output_path=None):
        result = {"ui": {}, "items": {}, "maps": {}}
        import translations
        result["ui"] = translations.TRANSLATIONS.get("en", {}).get("ui", {})

        for name, data in self.dictionaries.items():
            if name in ("vehicles", "crew_nations"):
                continue
            for k, v in data.items():
                if "/name" in k and v and not v.startswith("#"):
                    short_key = k.replace("/name", "")
                    result["items"][short_key] = v

        try:
            maps_path = os.path.join(config.BASE_DIR, "extracted_maps", "map_dictionary.json")
            if os.path.exists(maps_path):
                with open(maps_path, "r", encoding="utf-8") as f:
                    result["maps"] = json.load(f)
        except Exception:
            pass

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        try:
            import firebase_reporter
            firebase_reporter.push_locale(self.language, result)
        except Exception:
            pass

        return result

    def get_all_names(self):
        result = {}
        for cat_data in self.dictionaries.values():
            for k, v in cat_data.items():
                if "/name" in k and v and not v.startswith("#") and v.strip() != "?empty?":
                    result[k] = v.strip()
        return result

    def build_value_index(self):
        """Build reverse lookup {value_lower: msgid} for common UI terms."""
        self._value_index = {}
        for cat_data in self.dictionaries.values():
            for k, v in cat_data.items():
                if not v or v.startswith("#") or v.strip() == "?empty?":
                    continue
                val = v.strip()
                if len(val) < 3 or len(val) > 80:
                    continue
                val_lower = val.lower()
                if val_lower not in self._value_index:
                    self._value_index[val_lower] = k

    def t_by_value(self, value, default=None):
        """Find a msgid whose translation equals the given value, then return its translation."""
        if not hasattr(self, '_value_index') or not self._value_index:
            self.build_value_index()
        msgid = self._value_index.get(value.lower())
        if msgid:
            result = self.t(msgid)
            if result and result != msgid:
                return result
        return default or value

    def _get_en_value_index(self):
        """Load English .mo dictionaries and build reverse value index.
        Used for reverse lookups: English name → system_id → localized name.
        Prefers keys ending with '/value' or '/name' for better translations."""
        if hasattr(self, '_en_value_index') and self._en_value_index:
            return self._en_value_index
        self._en_value_index = {}
        en_dir = os.path.join(config.USER_DATA_DIR, "localization", "en")
        if not os.path.isdir(en_dir):
            return self._en_value_index
        try:
            for fn in os.listdir(en_dir):
                if fn.endswith('.json'):
                    with open(os.path.join(en_dir, fn), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for k, v in data.items():
                        if not v or v.startswith("#") or len(v.strip()) < 2:
                            continue
                        val_lower = v.strip().lower()
                        existing = self._en_value_index.get(val_lower)
                        if existing is None:
                            self._en_value_index[val_lower] = k
                        elif ('/' + val_lower) in k.lower() and ('/' + val_lower) not in existing.lower():
                            self._en_value_index[val_lower] = k
        except Exception:
            pass
            pass
        return self._en_value_index


_lang_module = None


def get_lang_module(wot_path=None):
    global _lang_module
    if _lang_module is None:
        _lang_module = LanguageModule(wot_path)
        if not _lang_module.load_cache():
            if wot_path:
                _lang_module.wot_path = wot_path
                _lang_module.build_all_dictionaries()
                print(f"[get_lang_module] built from .mo, lang={_lang_module.language}")
        else:
            print(f"[get_lang_module] loaded from cache, lang={_lang_module.language}, dicts={len(_lang_module.dictionaries)}")
    return _lang_module


def reset_lang_module():
    global _lang_module
    _lang_module = None


def setup(wot_path, settings, save_callback):
    """Called on app startup. Detects language, rebuilds if changed."""
    global _lang_module
    print(f"[LANG SETUP] wot_path={wot_path}")
    lm = LanguageModule(wot_path)
    lang = lm.detect_language()
    
    saved = settings.get("language", "")
    print(f"[LANG SETUP] detected={lang}, saved={saved}")

    if lang != saved or not saved or not os.path.isdir(
        os.path.join(config.USER_DATA_DIR, "localization", lang)
    ):
        print("[LANG SETUP] rebuilding dictionaries...")
        lm.build_all_dictionaries(language=lang)
        print(f"[LANG SETUP] built {len(lm.dictionaries)} categories, lang={lm.language}")
        locale_dir = os.path.join(config.BASE_DIR, "public", "locale")
        if os.path.isdir(locale_dir):
            import shutil
            shutil.rmtree(locale_dir, ignore_errors=True)
        lm.export_locale_json(
            os.path.join(config.BASE_DIR, "public", "locale", f"{lang}.json")
        )
        print(f"[LANG SETUP] exported locale/{lang}.json")
        regenerate_game_entities(lm)
        settings["language"] = lang
        try:
            with open(config.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            print(f"[LANG SETUP] settings saved, language={lang}")
        except Exception as e:
            print(f"[LANG SETUP] settings save error: {e}")
        reset_lang_module()
        try:
            import firebase_reporter
            firebase_reporter.set_app_language(lang)
            print(f"[LANG SETUP] RTDB lang={lang}")
        except Exception:
            pass
    else:
        print("[LANG SETUP] no change, skipping rebuild")

    if _lang_module is None:
        _lang_module = LanguageModule(wot_path)
        _lang_module._cache_dir = os.path.join(config.USER_DATA_DIR, "localization", lang)
        _lang_module.load_cache()
    # Always regenerate map dictionary to match current game language
    regenerate_map_dictionary(_lang_module)
    return lang


def check_for_language_change(wot_path, settings, save_callback=None):
    """Called from map_manager when game version changes."""
    return setup(wot_path, settings, save_callback or (lambda: None))


def regenerate_map_dictionary(lm):
    """Regenerate map_dictionary.json from arenas.mo."""
    arenas = lm.dictionaries.get("arenas", {})
    dict_path = os.path.join(config.BASE_DIR, "extracted_maps", "map_dictionary.json")
    old_dict = {}
    if os.path.exists(dict_path):
        with open(dict_path, "r", encoding="utf-8") as f:
            old_dict = json.load(f)

    new_dict = {}
    for msgid, name in arenas.items():
        if "/name" in msgid and name and not name.startswith("#"):
            map_id = msgid.replace("/name", "")
            if len(name) > 2 and name.strip() != "?empty?":
                new_dict[map_id] = name.strip()

    for kid in old_dict:
        if kid not in new_dict:
            new_dict[kid] = old_dict[kid]

    with open(dict_path, "w", encoding="utf-8") as f:
        json.dump(new_dict, f, indent=2, ensure_ascii=False)


def regenerate_game_entities(lm):
    """Add new entities from game_entities.json to game_entities_english.json.
    Preserves existing English names — never overwrites with current-language text."""
    ge_path = os.path.join(config.BASE_DIR, "game_entities.json")
    ge_en_path = os.path.join(config.BASE_DIR, "game_entities_english.json")
    if not os.path.exists(ge_path):
        return

    ge = json.load(open(ge_path, "r", encoding="utf-8"))

    if os.path.exists(ge_en_path):
        existing = json.load(open(ge_en_path, "r", encoding="utf-8"))
    else:
        existing = {}

    cat_map = {
        "equipment": "equipment", "consumables": "consumables",
        "crew_perks": "crew_perks", "field_mods": "field_mods",
        "ammo_types": "ammo_types"
    }

    added = 0
    for cat_key, edata in ge.items():
        out_cat = cat_map.get(cat_key)
        if not out_cat:
            continue

        existing_cat = existing.setdefault(out_cat, {})

        for eid, data in edata.items():
            if eid in existing_cat:
                continue

            original_ref = data.get("name", "")
            if isinstance(original_ref, str):
                original_ref = original_ref.strip()

            existing_cat[eid] = {
                "name": eid,
                "icon": data.get("icon", ""),
                "original_ukr": original_ref,
            }
            added += 1

    if added > 0:
        with open(ge_en_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"[LANG] game_entities_english.json: added {added} new entities")
