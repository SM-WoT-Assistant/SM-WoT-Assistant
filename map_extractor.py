import os
import shutil
import zipfile
import json
import re
import xml.etree.ElementTree as ET
import wot_decoder
import struct

print("[DEBUG] map_extractor module loaded")


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
            except:
                pass
        return {}

    def get_version(self):
        if not self.wot_path:
            return None
        v_path = os.path.join(self.wot_path, "version.xml")
        if os.path.exists(v_path):
            try:
                tree = ET.parse(v_path)
                return tree.getroot().findtext("version")
            except:
                pass
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

    def _load_ukrainian_map_names_fresh(self):
        """Load Ukrainian map names directly from the game's arenas.mo localization file"""
        ukrainian_names = {}
        try:
            mo_path = os.path.join(self.wot_path, "res", "text", "lc_messages", "arenas.mo")
            if os.path.exists(mo_path):
                with open(mo_path, 'rb') as f:
                    data = f.read()
                magic, version, nstrings, orig_offset, trans_offset = struct.unpack('<IIIII', data[:20])
                if magic != 0x950412de:  # Little endian
                    magic, version, nstrings, orig_offset, trans_offset = struct.unpack('>IIIII', data[:20])
                    if magic != 0x950412de:
                        print("[ЕКСТРАКТОР] Неправильний MO файл")
                        return ukrainian_names

                orig_table = []
                trans_table = []
                for i in range(nstrings):
                    o_len, o_off = struct.unpack_from('<II', data, orig_offset + i*8)
                    t_len, t_off = struct.unpack_from('<II', data, trans_offset + i*8)
                    orig_table.append((o_len, o_off))
                    trans_table.append((t_len, t_off))

                strings = {}
                for i, ((o_len, o_off), (t_len, t_off)) in enumerate(zip(orig_table, trans_table)):
                    orig = data[o_off:o_off+o_len].decode('utf-8')
                    trans = data[t_off:t_off+t_len].decode('utf-8')
                    strings[orig] = trans

                for orig, trans in strings.items():
                    if orig.endswith('/name'):
                        map_key = orig.split('/')[0]  # e.g., '120_graf_zeppelin'
                        ukrainian_names[map_key] = trans

                print(f"[ЕКСТРАКТОР] Завантажено {len(ukrainian_names)} українських назв мап з arenas.mo")
            else:
                print("[ЕКСТРАКТОР] Файл локалізації arenas.mo не знайдено")
        except Exception as e:
            print(f"[ЕКСТРАКТОР] Помилка завантаження українських назв з MO файлу: {e}")
        return ukrainian_names

    def _save_ukrainian_map_names_cache(self, ukrainian_names):
        """Save Ukrainian map names to cache file"""
        try:
            cache_path = os.path.join(self.out_path, "ukrainian_map_names_cache.json")
            os.makedirs(self.out_path, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(ukrainian_names, f, indent=4, ensure_ascii=False)
            print(f"[ЕКСТРАКТОР] Збережено {len(ukrainian_names)} українських назв мап у кеш")
        except Exception as e:
            print(f"[ЕКСТРАКТОР] Помилка збереження кешу українських назв: {e}")

    def _load_ukrainian_map_names_cache(self):
        """Load Ukrainian map names from cache file"""
        try:
            cache_path = os.path.join(self.out_path, "ukrainian_map_names_cache.json")
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    ukrainian_names = json.load(f)
                if isinstance(ukrainian_names, dict) and ukrainian_names:
                    print(f"[ЕКСТРАКТОР] Завантажено {len(ukrainian_names)} українських назв мап з кеш-файлу")
                    return ukrainian_names
                else:
                    print("[ЕКСТРАКТОР] Кеш-файл містить невалідні дані")
            else:
                print("[ЕКСТРАКТОР] Кеш-файл українських назв мап не знайдено")
        except Exception as e:
            print(f"[ЕКСТРАКТОР] Помилка завантаження кешу українських назв: {e}")
        return {}

    def _load_ukrainian_map_names(self):
        """Load Ukrainian map names from the game's arenas.mo localization file with caching"""
        ukrainian_names = self._load_ukrainian_map_names_fresh()
        if ukrainian_names:
            self._save_ukrainian_map_names_cache(ukrainian_names)
            return ukrainian_names

        print("[ЕКСТРАКТОР] Спроба завантажити кешовані українські назви мап...")
        ukrainian_names = self._load_ukrainian_map_names_cache()
        if ukrainian_names:
            print(f"[ЕКСТРАКТОР] Завантажено {len(ukrainian_names)} українських назв мап з кешу")
            return ukrainian_names

        print("[ЕКСТРАКТОР] Не вдалося завантажити українські назви мап ні з MO файлу, ні з кешу")
        return {}

    def extract(self, callback_status=None, force_full=False):
        print("[DEBUG] MapExtractor.extract called")
        if not self.wot_path:
            return False

        pkg_path = os.path.join(self.wot_path, "res", "packages", "scripts.pkg")
        if not os.path.exists(pkg_path):
            return False

        os.makedirs(self.out_path, exist_ok=True)
        if not os.path.exists(self.temp_path):
            os.makedirs(self.temp_path)

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

        existing_map_data_path = os.path.join(self.out_path, "map_data.json")
        existing_map_data = self.load_json(existing_map_data_path)
        if not isinstance(existing_map_data, dict):
            existing_map_data = {}
        existing_map_data.update(all_map_data)

        dictionary = {}

        ukrainian_names = self._load_ukrainian_map_names()

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
                        if name_eng in ukrainian_names:
                            dictionary[name_eng] = ukrainian_names[name_eng]
                        elif loc_raw:
                            clean_loc = loc_raw.strip().replace("#arenas:", "").split("/")[-1]
                            if not clean_loc or clean_loc == "name":
                                clean_loc = loc_raw.split(":")[-1].split("/")[0]
                            dictionary[name_eng] = clean_loc.capitalize()
                        else:
                            dictionary[name_eng] = name_eng.capitalize()
            except Exception as e:
                print(f"[ЕКСТРАКТОР] Помилка словника: {e}")

        with open(os.path.join(self.out_path, "map_data.json"), "w", encoding="utf-8") as f:
            json.dump(existing_map_data, f, indent=4)

        with open(os.path.join(self.out_path, "map_dictionary.json"), "w", encoding="utf-8") as f:
            json.dump(dictionary, f, indent=4, ensure_ascii=False)

        if callback_status:
            callback_status(f"Оновлено {len(all_map_data)} мап")

        print("[ЕКСТРАКТОР] Тимчасові файли ЗАЛИШЕНО.")

        print("[ЕКСТРАКТОР] Успішно завершено!")
        return True