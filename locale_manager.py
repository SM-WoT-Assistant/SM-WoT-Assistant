import os
import json
import config
import translations

class LocaleManager:
    def __init__(self, app):
        self.app = app
        self.lang = app.settings.get("language", "en")
        
        self.locales_file = config.LOCALES_FILE
        self.languages = self.load_locales()
        
        # Ensure English base exists
        if "en" not in self.languages:
            self.languages["en"] = translations.TRANSLATIONS["en"]
        
        # Ensure current language exists
        if self.lang not in self.languages:
            self.languages[self.lang] = {"ui": {}}
        
        # Ensure all EN UI keys exist in current language (translate if needed)
        self._ensure_ui_keys()
        
    def _ensure_ui_keys(self):
        """Ensure current language has all EN UI keys (translated or fallback)."""
        en_ui = translations.TRANSLATIONS.get("en", {}).get("ui", {})
        curr_ui = self.languages[self.lang].setdefault("ui", {})
        
        changed = False
        for key, en_val in en_ui.items():
            if key not in curr_ui:
                # Will be translated on demand via t_ui
                curr_ui[key] = en_val  # Fallback to EN initially
                changed = True
        
        if changed:
            self.save_locales()
        
    def load_locales(self):
        if os.path.exists(self.locales_file):
            try:
                with open(self.locales_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[LOCALE] Load error {self.locales_file}: {e}")
        return {}
        
    def save_locales(self):
        try:
            with open(self.locales_file, "w", encoding="utf-8") as f:
                json.dump(self.languages, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[LOCALE] Save error {self.locales_file}: {e}")

    def set_language(self, lang_code):
        self.lang = lang_code
        self.app.settings["language"] = lang_code
        self.app.save_settings()
        # Ensure new language has structure
        if lang_code not in self.languages:
            self.languages[lang_code] = {"ui": {}}
        self._ensure_ui_keys()

    def t_ui(self, key, default=None):
        """Get UI translation with dynamic translation via Google Translate."""
        if default is None:
            default = str(key)
        
        # Get English source value (authoritative from translations.py)
        en_val = translations.TRANSLATIONS.get("en", {}).get("ui", {}).get(key, key)
        
        # 1. Try to get from cache (locales.json)
        val = self.languages.get(self.lang, {}).get("ui", {}).get(key)
        
        # If cached value exists and differs from English source -> already translated, return it
        if val and val != en_val:
            return val
        
        # 2. If language != EN and (no cache or cache equals English) -> translate
        if self.lang != "en":
            try:
                from ui_translator import translate
                translated = translate(en_val, self.lang)
                if translated != en_val:
                    # Save to cache
                    self.languages.setdefault(self.lang, {}).setdefault("ui", {})[key] = translated
                    self.save_locales()
                    return translated
            except Exception as e:
                print(f"[LOCALE] Translation failed for '{key}': {e}")
        
        # 3. Fallback to EN
        return en_val if en_val != key else default
        
    def t_tank(self, tank_id, default_name):
        """Get tank name translation (future use)"""
        return self.languages.get(self.lang, {}).get("tanks", {}).get(tank_id, default_name)

    def t_map(self, eng):
        """Main function for map name translation and formatting."""
        lmaps = self.languages.get(self.lang, {}).get("maps", {})

        if hasattr(self.app, 'custom_names') and eng in self.app.custom_names:
            return self.app.custom_names[eng]

        # Always check extractor_names for consistent naming with game client (both TACTIC and MAPS modes)
        if hasattr(self.app, 'extractor_names') and self.app.extractor_names:
            # For TACTIC mode, eng is English name like "Karelia"
            # For MAPS mode, eng is internal key like "01_karelia"
            lookup_key = eng
            
            # If eng is not directly in extractor_names, try to find internal key via TECH_MAPS_STAGING
            if eng not in self.app.extractor_names:
                # Build reverse mapping from English to internal key
                if not hasattr(self, '_eng_to_internal'):
                    self._eng_to_internal = {}
                    for internal, english in config.TECH_MAPS_STAGING.items():
                        self._eng_to_internal[english] = internal
                lookup_key = self._eng_to_internal.get(eng, eng)
            
            ext = self.app.extractor_names.get(lookup_key)
            if ext and ext != eng:
                # ext is localized name from map_dictionary.json
                return ext

        if eng in lmaps:
            return lmaps[eng]

        if eng in config.TECH_MAPS_STAGING:
            en = config.TECH_MAPS_STAGING[eng]
            if en in lmaps:
                return lmaps[en]
            return en

        for k, v in lmaps.items():
            if k.lower() == eng.lower():
                return v
                
        for sep in [" - ", "-"]:
            if sep in eng:
                pts = eng.split(sep, 1)
                first = pts[0].strip()
                base = None
                if hasattr(self.app, 'custom_names'):
                    base = self.app.custom_names.get(first)
                if not base:
                    for k, v in lmaps.items():
                        if k.lower() == first.lower():
                            base = v
                            break
                if not base and first in config.TECH_MAPS_STAGING:
                    en = config.TECH_MAPS_STAGING[first]
                    base = lmaps.get(en, en)
                if base:
                    second = pts[1].strip()
                    if second.lower() == "assault": second = self.t_ui("assault", "Assault")
                    elif second.lower() == "encounter": second = self.t_ui("encounter", "Encounter")
                    elif second.lower() == "region": second = self.t_ui("region", "Region")
                    return f"{base} ({second})"
        
        for tech_name, en_name in sorted(config.TECH_MAPS_STAGING.items(), key=lambda x: len(x[0]), reverse=True):
            if eng.startswith(tech_name):
                return lmaps.get(en_name, en_name)

        return eng