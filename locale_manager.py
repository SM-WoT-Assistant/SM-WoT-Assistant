import os
import json
import config
import translations

class LocaleManager:
    def __init__(self, app):
        self.app = app
        self.lang = app.settings.get("language", "ua")
        
        self.locales_file = os.path.join(os.path.dirname(config.SETTINGS_FILE), "locales.json")
        self.languages = self.load_locales()
        
        # Якщо немає файлу або він порожній - копіюємо дефолт з translations
        if not self.languages:
            self.languages = translations.TRANSLATIONS
            self.save_locales()
        else:
            # Додаємо нові ключі з translations.py без перезапису існуючих
            self._merge_missing()
            
    def _merge_missing(self):
        """Add missing keys from translations.py to self.languages (preserves existing)."""
        changed = False
        for lang, lang_data in translations.TRANSLATIONS.items():
            if lang not in self.languages:
                self.languages[lang] = lang_data
                changed = True
                continue
            for section, section_data in lang_data.items():
                if section not in self.languages[lang]:
                    self.languages[lang][section] = section_data
                    changed = True
                    continue
                for key, value in section_data.items():
                    if key not in self.languages[lang][section]:
                        self.languages[lang][section][key] = value
                        changed = True
        if changed:
            self.save_locales()
            
    def load_locales(self):
        if os.path.exists(self.locales_file):
            try:
                with open(self.locales_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ЛОКАЛІЗАЦІЯ] Помилка завантаження {self.locales_file}: {e}")
        return {}
        
    def save_locales(self):
        try:
            with open(self.locales_file, "w", encoding="utf-8") as f:
                json.dump(self.languages, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ЛОКАЛІЗАЦІЯ] Помилка збереження {self.locales_file}: {e}")

    def set_language(self, lang_code):
        self.lang = lang_code
        self.app.settings["language"] = lang_code
        self.app.save_settings()

    def t_ui(self, key, default=None):
        """Отримати переклад UI елементу"""
        if default is None: 
            default = str(key)
        return self.languages.get(self.lang, {}).get("ui", {}).get(key, default)
        
    def t_tank(self, tank_id, default_name):
        """Отримати переклад назви диску (майбутній заділ)"""
        return self.languages.get(self.lang, {}).get("tanks", {}).get(tank_id, default_name)

    def t_map(self, eng):
        """Основна функція для перекладу та форматування назви мапи (заміна translate_map_name)"""
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
                # ext is Ukrainian name from map_dictionary.json
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
                    if second.lower() == "assault": second = self.t_ui("assault", "Штурм")
                    elif second.lower() == "encounter": second = self.t_ui("encounter", "Зустріч")
                    elif second.lower() == "region": second = self.t_ui("region", "Регіон")
                    return f"{base} ({second})"
        
        for tech_name, en_name in sorted(config.TECH_MAPS_STAGING.items(), key=lambda x: len(x[0]), reverse=True):
            if eng.startswith(tech_name):
                return lmaps.get(en_name, en_name)

        return eng
