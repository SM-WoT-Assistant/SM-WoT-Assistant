# НЕ СКОРОЧУВАТИ І НЕ ОПТИМІЗУВАТИ КОД ЯКИЙ НЕ СТОСУЄТЬСЯ ВИПРАВЛЕНЬ!
# map_extractor.py 2_09
import os
import shutil
import zipfile
import json
import re
import xml.etree.ElementTree as ET
import wot_decoder

class MapExtractor:
    def __init__(self):
        self.settings_path = "settings.json"
        self.settings = self.load_json(self.settings_path)
        self.wot_path = self.settings.get("wot_path", "")
        self.temp_path = os.path.join("extracted_maps", "temp_xml")
        self.out_path = "extracted_maps"
        self.manifest_path = os.path.join(self.out_path, ".map_extract_manifest.json")
        self.decoder = wot_decoder.WotXmlDecoder()

    def load_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    def get_version(self):
        if not self.wot_path: return None
        v_path = os.path.join(self.wot_path, "version.xml")
        if os.path.exists(v_path):
            try:
                tree = ET.parse(v_path)
                return tree.getroot().findtext("version")
            except: pass
        return None

    def _entry_fingerprint(self, info):
        return {
            "size": int(getattr(info, "file_size", 0)),
            "crc": int(getattr(info, "CRC", 0)),
            "mtime": list(getattr(info, "date_time", (0, 0, 0, 0, 0, 0))),
        }

    def _load_manifest(self):
        manifest = self.load_json(self.manifest_path)
        return manifest if isinstance(manifest, dict) else {}

    def _save_manifest(self, manifest):
        os.makedirs(self.out_path, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def extract(self, callback_status=None, force_full=False):
        if not self.wot_path:
            return False

        pkg_path = os.path.join(self.wot_path, "res", "packages", "scripts.pkg")
        if not os.path.exists(pkg_path):
            return False

        os.makedirs(self.out_path, exist_ok=True)
        if not os.path.exists(self.temp_path):
            os.makedirs(self.temp_path)

        # Працюємо тільки з файлами поточного циклу, щоб декодувати лише змінені.
        for name in os.listdir(self.temp_path):
            fp = os.path.join(self.temp_path, name)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass

        print("[ЕКСТРАКТОР] Витягуємо XML...")
        if callback_status:
            callback_status("Аналіз scripts.pkg...")

        manifest = self._load_manifest()
        new_manifest = {}
        changed_targets = []
        try:
            with zipfile.ZipFile(pkg_path, 'r') as z:
                for file in z.namelist():
                    if not (file.startswith("scripts/arena_defs/") and file.endswith(".xml")):
                        continue

                    # У _list_.xml немає підкреслення, але він потрібен для словника назв.
                    if "_" not in file and not file.endswith("_list_.xml"):
                        continue

                    info = z.getinfo(file)
                    fp = self._entry_fingerprint(info)
                    new_manifest[file] = fp
                    base_name = os.path.basename(file)
                    target = os.path.join(self.temp_path, base_name)
                    prev = manifest.get(file)

                    if not force_full and prev == fp:
                        continue

                    z.extract(file, self.temp_path)
                    src = os.path.join(self.temp_path, file)
                    os.replace(src, target)
                    changed_targets.append(target)
        except Exception as e:
            print(f"[ЕКСТРАКТОР] Помилка zip: {e}")
            return False

        self._save_manifest(new_manifest)

        if not changed_targets and not force_full:
            print("[ЕКСТРАКТОР] Змін у XML мап не виявлено. Пропускаю декодування.")
            if callback_status:
                callback_status("Мапи актуальні, змін не знайдено")
            return True

        if callback_status:
            callback_status(f"Декодування XML: {len(changed_targets)} файлів")

        all_map_data = self.decoder.decode_folder(self.temp_path, timeout=60)

        # Мерджимо тільки змінені мапи, щоб не втратити попередні дані.
        existing_map_data_path = os.path.join(self.out_path, "map_data.json")
        existing_map_data = self.load_json(existing_map_data_path)
        if not isinstance(existing_map_data, dict):
            existing_map_data = {}
        existing_map_data.update(all_map_data)

        # ПОКРАЩЕНИЙ МОДУЛЬ ПЕРЕКЛАДУ
        dictionary = {}
        list_xml = os.path.join(self.temp_path, "_list_.xml")
        saved_dict = self.load_json(os.path.join(self.out_path, "map_dictionary.json"))
        if isinstance(saved_dict, dict):
            dictionary.update(saved_dict)

        if os.path.exists(list_xml):
            try:
                with open(list_xml, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read().strip()

                text = re.sub(r'^<[^>?!][^>]+>', '<root>', text, count=1)
                text = re.sub(r'</[^>]+>\s*$', '</root>', text)

                list_root = ET.fromstring(text)
                for map_node in list_root:
                    name_raw = map_node.findtext("name")
                    loc_raw = map_node.findtext("userString")

                    if name_raw:
                        name_eng = name_raw.strip()
                        if loc_raw:
                            # Переклад: очищуємо від технічного сміття
                            clean_loc = loc_raw.strip().replace("#arenas:", "").split("/")[-1]
                            if not clean_loc or clean_loc == "name":
                                clean_loc = loc_raw.split(":")[-1].split("/")[0]
                            dictionary[name_eng] = clean_loc.capitalize()
                        else:
                            dictionary[name_eng] = name_eng.capitalize()
            except Exception as e:
                print(f"[ЕКСТРАКТОР] Помилка словника: {e}")

        # Збереження
        with open(os.path.join(self.out_path, "map_data.json"), "w", encoding="utf-8") as f:
            json.dump(existing_map_data, f, indent=4)

        with open(os.path.join(self.out_path, "map_dictionary.json"), "w", encoding="utf-8") as f:
            json.dump(dictionary, f, indent=4, ensure_ascii=False)

        if callback_status:
            callback_status(f"Оновлено {len(all_map_data)} мап")

        print("[ЕКСТРАКТОР] Тимчасові файли ЗАЛИШЕНО.")

        print("[ЕКСТРАКТОР] Успішно завершено!")
        return True
# map_extractor.py 2_09
# НЕ СКОРОЧУВАТИ І НЕ ОПТИМІЗУВАТИ КОД ЯКИЙ НЕ СТОСУЄТЬСЯ ВИПРАВЛЕНЬ!