import os
import json
import config

class LocaleManager:
    def __init__(self, app):
        self.app = app
        self.lang = app.settings.get("language", "ua")
        
        self.locales_file = os.path.join(os.path.dirname(config.SETTINGS_FILE), "locales.json")
        self.languages = self.load_locales()
        
        # Яка немає файлу або він порожній - копіюємо дефолт з config
        if not self.languages:
            self.languages = config.LANG_DATA
            self.save_locales() # одразу створюємо файл для ручного редагування/додавання мов
            
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

        if hasattr(self.app, 'btn_mode_maps_2') and self.app.btn_mode_maps_2.cget("bg") == "#ff4500" and hasattr(self.app, 'extractor_names'):
            ext = self.app.extractor_names.get(eng)
            if ext and ext != eng:
                if ext in lmaps:
                    return lmaps[ext]
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
