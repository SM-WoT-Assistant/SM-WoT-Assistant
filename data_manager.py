# data_manager.py
import os
import json
import re
import config

class DataManager:
    def __init__(self):
        self.drawings_file = os.path.join(os.path.dirname(config.SETTINGS_FILE), "map_drawings.json")

    def load_json(self, file_path, default_data=None):
        if default_data is None:
            default_data = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return default_data

    def save_json(self, file_path, data):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"[DATA] Error saving {file_path}: {e}")

    def load_drawings(self):
        return self.load_json(self.drawings_file)

    def save_drawings(self, data):
        self.save_json(self.drawings_file, data)

    def load_tank_db(self):
        try:
            def _estimate_tier_from_tth(tag, tth_db):
                rec = tth_db.get(tag) if isinstance(tth_db, dict) else None
                if not isinstance(rec, dict):
                    return 5
                hp = rec.get("hp")
                try:
                    hp = int(hp)
                except Exception:
                    return 5
                if hp <= 260: return 1
                if hp <= 360: return 2
                if hp <= 500: return 3
                if hp <= 700: return 4
                if hp <= 900: return 5
                if hp <= 1100: return 6
                if hp <= 1300: return 7
                if hp <= 1500: return 8
                if hp <= 1750: return 9
                return 10

            if os.path.exists(os.path.join(config.BASE_DIR, "tank_db.json")):
                with open(os.path.join(config.BASE_DIR, "tank_db.json"), "r", encoding="utf-8") as f:
                    db = json.load(f)
                    clean_db = {}
                    # Технічні / евентові / видалені з гри танки
                    bad_tags = [
                        "_7x7", "_fallout", "_fl", "_sh", "_bootcamp", "_igr", "_test",
                        "_training", "tutorial", "observer", "r05_kv", "r70_t_50_2",
                        "sherman_crab", "g00_", "_cfe", "auto_s", "auto_test",
                        "_shxxi", "_bomber", "pillbox", "env_artillery",  # Тех об'єкти
                        "a08_t23", "a26_t18", "a15_t57",  # USA вилучені танки
                        "_newonboarding", "_storymode",   # Тренувальні
                    ]
                    icons_dir = os.path.join(config.BASE_DIR, "extracted_icons")
                    for k, v in db.items():
                        if any(b in k.lower() for b in bad_tags) or any(b in v["name"].lower() for b in bad_tags):
                            continue
                        icon_path = os.path.join(icons_dir, v.get("icon", ""))
                        if not os.path.exists(icon_path):
                            v = dict(v)
                            v["icon"] = ""
                        clean_db[k] = v
                    if clean_db:
                        return clean_db

            tth_path = os.path.join(config.BASE_DIR, "tank_tth.json")
            tth_db = {}
            if os.path.exists(tth_path):
                with open(tth_path, "r", encoding="utf-8") as f:
                    tth_db = json.load(f)
                if isinstance(tth_db, dict) and tth_db:
                    nation_map = {
                        "A": "USA", "R": "USSR", "G": "Germany", "F": "France", "GB": "UK",
                        "Ch": "China", "J": "Japan", "Cz": "Czech", "Pl": "Poland", "S": "Sweden", "It": "Italy"
                    }
                    clean_db = {}
                    for tag in tth_db.keys():
                        if not isinstance(tag, str):
                            continue
                        m = re.match(r'''^([A-Za-z]+)\d{1,4}_(.+)$''', tag)
                        pref = m.group(1) if m else ""
                        name_part = m.group(2) if m else tag
                        nation = nation_map.get(pref, "Unknown")
                        display_name = name_part.replace("_", " ").replace("-", "-").strip()
                        clean_db[tag] = {
                            "name": display_name,
                            "tier": _estimate_tier_from_tth(tag, tth_db),
                            "class": "Unknown",
                            "nation": nation,
                            "icon": "",
                            "is_premium": False,
                            "compact_descr": None,
                        }
                    if clean_db:
                        print(f"[DB] Fallback: завантажено {len(clean_db)} танків із tank_tth.json")
                        return clean_db

            extracted_root = os.path.join(config.BASE_DIR, "extracted_data")
            if os.path.isdir(extracted_root):
                nation_map_folder = {
                    "usa": "USA", "ussr": "USSR", "germany": "Germany", "france": "France", "uk": "UK",
                    "china": "China", "japan": "Japan", "czech": "Czech", "poland": "Poland", "sweden": "Sweden", "italy": "Italy"
                }
                rough_db = {}
                for nation_folder in os.listdir(extracted_root):
                    npath = os.path.join(extracted_root, nation_folder)
                    if not os.path.isdir(npath):
                        continue
                    if nation_folder.lower() not in nation_map_folder:
                        continue
                    for fname in os.listdir(npath):
                        if not fname.endswith('.xml'):
                            continue
                        if fname in ("list.xml", "customization.xml"):
                            continue
                        tag = fname[:-4]
                        low = tag.lower()
                        if any(b in low for b in ["_7x7", "_fallout", "_fl", "_sh", "_bootcamp", "_igr", "_test", "_training", "tutorial", "observer", "_newonboarding", "_storymode"]):
                            continue
                        m = re.match(r'''^[A-Za-z]+\d{1,4}_(.+)$''', tag)
                        name_part = m.group(1) if m else tag
                        rough_db[tag] = {
                            "name": name_part.replace("_", " ").strip(),
                            "tier": _estimate_tier_from_tth(tag, tth_db),
                            "class": "Unknown",
                            "nation": nation_map_folder[nation_folder.lower()],
                            "icon": "",
                            "is_premium": False,
                            "compact_descr": None,
                        }
                if rough_db:
                    try:
                        with open(os.path.join(config.USER_DATA_DIR, "tank_db.json"), "w", encoding="utf-8") as f:
                            json.dump(rough_db, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        print(f"[DB] Попередження: не вдалося зберегти fallback tank_db.json: {e}")
                    print(f"[DB] Last-resort fallback: завантажено {len(rough_db)} танків із extracted_data")
                    return rough_db
        except Exception as e:
            print(f"[DB] load_tank_db error: {e}")
            import service_messages
            service_messages.log_event("data_update", f"load_tank_db failed: {e}", level="error")
        return {}