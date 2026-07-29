#!/usr/bin/env python3
"""
parse_game_entities.py - КРОК 1
Збір всіх можливих варіантів з клієнта гри:
- Обладнання (equipment)
- Витратні (consumables)  
- Перки екіпажу (crew perks)
- Польова модернізація (field mods)
- Снаряди (ammo shells)

Використовує Python декодер для XML файлів клієнта.
"""
import os
import re
import json
import struct
import base64
import xml.etree.ElementTree as ET
from pathlib import Path

class BWXmlDecoder:
    """Native Python BigWorld XML decoder"""
    def __init__(self):
        self.dictionary = []
        self.data = b''
        self.offset = 0
    
    def read_string(self):
        start = self.offset
        while self.offset < len(self.data) and self.data[self.offset] != 0:
            self.offset += 1
        s = self.data[start:self.offset].decode('utf-8', errors='ignore')
        self.offset += 1
        return s
    
    def decode_file(self, input_path, output_path):
        if not os.path.exists(input_path):
            return False
        
        with open(input_path, 'rb') as f:
            self.data = f.read()
        
        if len(self.data) < 4 or self.data[:4] != b'\x45\x4e\xa1\x62':
            return True
        
        self.offset = 5
        self.dictionary = []
        
        while True:
            s = self.read_string()
            if not s:
                break
            self.dictionary.append(s)
        
        root_name = os.path.basename(input_path).split('.')[0]
        xml_content = self._read_element(root_name, 0)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
            f.write(xml_content)
        
        return True
    
    def _read_element(self, name, depth):
        if self.offset + 6 > len(self.data):
            return ""
        
        children_count = struct.unpack_from('<H', self.data, self.offset)[0]
        if children_count > 50000:
            return ""
        self.offset += 2
        struct.unpack_from('<I', self.data, self.offset)[0]
        self.offset += 4
        
        children = []
        for _ in range(children_count):
            if self.offset + 6 > len(self.data):
                break
            child_id = struct.unpack_from('<H', self.data, self.offset)[0]
            self.offset += 2
            data_desc = struct.unpack_from('<I', self.data, self.offset)[0]
            self.offset += 4
            children.append({'id': child_id, 'desc': data_desc})
        
        data_start = self.offset
        
        result = f"{'  ' * depth}<{name}>\n"
        
        for child in children:
            if child['id'] >= len(self.dictionary):
                self.offset = data_start + (child['desc'] & 0x0FFFFFFF)
                continue
            tag_name = self.dictionary[child['id']]
            end_address = child['desc'] & 0x0FFFFFFF
            data_type = child['desc'] >> 28
            
            child_end_offset = data_start + end_address
            if child_end_offset > len(self.data):
                child_end_offset = len(self.data)
            if self.offset > child_end_offset:
                self.offset = child_end_offset
                continue
            length = child_end_offset - self.offset
            
            if data_type == 0:
                if length == 0:
                    result += f"{'  ' * (depth+1)}<{tag_name}></{tag_name}>\n"
                else:
                    result += self._read_element(tag_name, depth + 1)
            else:
                val = ""
                if data_type == 1:
                    val = self.data[self.offset:child_end_offset].decode('utf-8', errors='ignore')
                elif data_type == 2:
                    if length == 1: val = struct.unpack_from('<b', self.data, self.offset)[0]
                    elif length == 2: val = struct.unpack_from('<h', self.data, self.offset)[0]
                    elif length == 4: val = struct.unpack_from('<i', self.data, self.offset)[0]
                    elif length == 8: val = struct.unpack_from('<q', self.data, self.offset)[0]
                    else: val = 0
                elif data_type == 3:
                    num_floats = length // 4
                    floats = struct.unpack_from(f'<{num_floats}f', self.data, self.offset)
                    val = " ".join(f"{f:.6g}" for f in floats)
                elif data_type == 4:
                    val = "true" if (length > 0 and struct.unpack_from('<b', self.data, self.offset)[0]) else "false"
                else:
                    val = base64.b64encode(self.data[self.offset:child_end_offset]).decode('utf-8')
                
                result += f"{'  ' * (depth+1)}<{tag_name}>\t{val}\t</{tag_name}>\n"
            
            self.offset = child_end_offset
        
        result += f"{'  ' * depth}</{name}>\n"
        return result


class GameEntitiesExtractor:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.extracted_data = self.project_root / "extracted_data"
        self.decoder = BWXmlDecoder()
        
        self.game_entities = {
            "equipment": {},
            "consumables": {},
            "crew_perks": {},
            "field_mods": {},
            "ammo_types": {}
        }
        
        self.icons_base = self.project_root / "extracted_icons" / "loadout"
        
    def is_encoded(self, file_path):
        """Перевіряє чи файл закодований (перші байти 'ENb')"""
        try:
            with open(file_path, 'rb') as f:
                first = f.read(4)
                return first == b'ENb' or (first[0] == 69 and first[1] == 78 and first[2] == 161)
        except:
            return False
    
    def decode_xml_file(self, file_path):
        """Декодує один XML файл через Python"""
        if not self.is_encoded(file_path):
            return True
        
        try:
            self.decoder.decode_file(str(file_path), str(file_path))
            return True
        except Exception as e:
            print(f"[ПОМИЛКА] Декодування {file_path}: {e}")
            return False
            return False
    
    def run_orion_decode(self, folder_path):
        """Декодує XML файли в папці через Python декодер"""
        abs_folder = os.path.abspath(str(folder_path))
        xml_files = [f for f in os.listdir(abs_folder) if f.endswith('.xml')]
        
        if not xml_files:
            print(f"[INFO] No XML files in: {abs_folder}")
            return {}
            
        print(f"[INFO] Decoding {len(xml_files)} files via Python...")
        
        for xml_file in xml_files:
            file_path = Path(abs_folder) / xml_file
            self.decode_xml_file(file_path)
            
    def parse_xml_file(self, xml_path):
        """Парсить XML файл"""
        try:
            with open(xml_path, 'r', encoding='utf-8', errors='ignore') as f:
                xml_text = f.read().strip()
            
            if not xml_text:
                return None
            
            # Перевіряємо encoding
            if xml_text.startswith('<equipments.xml>') or '<xmlns:xmlref>' in xml_text:
                # Це WOT XML формат - видаляємо xmlns namespace проблеми
                xml_text = re.sub(r'<\?xml[^>]+\?>', '', xml_text)
                xml_text = re.sub(r'<equipments\.xml>', '<equipments>', xml_text)
                xml_text = re.sub(r'</equipments\.xml>', '</equipments>', xml_text)
                xml_text = re.sub(r'<optional_devices\.xml>', '<optional_devices>', xml_text)
                xml_text = re.sub(r'</optional_devices\.xml>', '</optional_devices>', xml_text)
                
                # Видаляємо тег xmlns:xmlref повністю
                xml_text = re.sub(r'<xmlns:xmlref>[^<]*</xmlns:xmlref>\s*', '', xml_text)
                xml_text = re.sub(r'xmlns:xmlref="[^"]*"', '', xml_text)
                xml_text = re.sub(r'xmlns="[^"]*"', '', xml_text)
                
                # Видаляємо всі xmlns атрибути з тегів
                xml_text = re.sub(r'\s+xmlns:[a-zA-Z0-9_-]+="[^"]*"', '', xml_text)
                
                # Видаляємо пробіли/таби перед xmlns
                xml_text = re.sub(r'[\t ]+xmlns:[a-zA-Z]+', ' xmlns', xml_text)
            
            # Виправляємо теги з цифрами на початку
            if re.match(r'^<[0-9\._]', xml_text):
                xml_text = re.sub(r'^<[^>]+>', '<root>', xml_text, count=1)
                xml_text = re.sub(r'</[^>]+>\s*$', '</root>', xml_text)
            
            return ET.fromstring(xml_text)
        except ET.ParseError as e:
            print(f"[ПОМИЛКА] ET ParseError: {e}")
            print(f"   Рядок: {xml_path}")
            return None
        except Exception as e:
            print(f"[ПОМИЛКА] Парсинг {xml_path}: {e}")
            return None
            
    def extract_equipment_from_xml(self, xml_root):
        """Екстракція обладнання з XML"""
        equipment_list = {}
        
        # Шукаємо обладнання в кореневому елементі
        for elem in xml_root:
            tag_name = elem.tag
            
            # Пропускаємо технічні теги
            if tag_name in ('xmlns:xmlref', 'header', 'version'):
                continue
                
            # Отримуємо базові дані
            item_id = elem.findtext('id', '').strip()
            icon = elem.findtext('icon', '').strip()
            user_string = elem.findtext('userString', '')
            tags = elem.findtext('tags', '')
            
            if not item_id:
                continue
                
            # Визначаємо тип обладнання
            equip_type = "standard"
            if 'deluxe' in tags.lower() or 'improved' in tags.lower():
                equip_type = "deluxe"
            elif 'experimental' in tag_name.lower() or 'experimental' in tags.lower():
                equip_type = "experimental"
            elif 'consumable' in tags.lower() or 'stimulator' in tags.lower():
                equip_type = "consumable"
                
            # Формуємо ім'я з userString
            name = self._clean_user_string(user_string)
            
            equipment_list[tag_name] = {
                "id": tag_name,
                "name": name,
                "icon": icon,
                "type": equip_type,
                "price": elem.findtext('price', '0').strip()
            }
            
        return equipment_list
        
    def extract_consumables_from_xml(self, xml_root):
        """Екстракція витратних з XML"""
        consumables = {}
        
        for elem in xml_root:
            tag_name = elem.tag
            
            if tag_name in ('xmlns:xmlref', 'header', 'version'):
                continue
                
            tags = elem.findtext('tags', '').lower()
            
            # Витратні мають теги: medkit, repairkit, extinguisher, stimulator
            is_consumable = any(t in tags for t in ['medkit', 'repairkit', 'extinguisher', 'stimulator', 'ration'])
            
            if not is_consumable:
                continue
                
            item_id = elem.findtext('id', '').strip()
            icon = elem.findtext('icon', '').strip()
            user_string = elem.findtext('userString', '')
            
            if not item_id:
                continue
                
            name = self._clean_user_string(user_string)
            
            # Визначаємо nation для rations
            nation_filter = None
            if 'germany' in tags:
                nation_filter = "germany"
            elif 'usa' in tags:
                nation_filter = "usa"
            elif 'ussr' in tags:
                nation_filter = "ussr"
            elif 'france' in tags:
                nation_filter = "france"
            elif 'china' in tags:
                nation_filter = "china"
            elif 'uk' in tags:
                nation_filter = "uk"
            elif 'japan' in tags:
                nation_filter = "japan"
                
            consumables[tag_name] = {
                "id": tag_name,
                "name": name,
                "icon": icon,
                "type": "consumable",
                "nation_filter": nation_filter,
                "price": elem.findtext('price', '0').strip()
            }
            
        return consumables
        
    def _clean_user_string(self, user_string):
        """Очищує userString від локалізаційних маркерів"""
        if not user_string:
            return ""
            
        # Видаляємо #artefacts: prefix
        if user_string.startswith('#'):
            parts = user_string.split('/')
            if len(parts) > 1:
                return parts[-1].replace('_name', '').replace('_descr', '')
            return user_string.replace('#artefacts:', '').replace('_name', '')
            
        return user_string
        
    def run_step1(self):
        """КРОК 1: Збір обладнання та витратних"""
        print("\n" + "="*60)
        print("КРОК 1: Збір можливих варіантів обладнання та витратних")
        print("="*60)
        
        common_dir = self.extracted_data / "common"
        if not common_dir.exists():
            print(f"[ПОМИЛКА] Папка common не знайдено: {common_dir}")
            return False
            
        # 1. Парсимо equipments.xml
        equip_file = common_dir / "equipments-1.xml"
        if equip_file.exists():
            print(f"\n[1] Парсинг {equip_file.name}...")
            
            # Декодуємо через Python
            self.run_orion_decode(common_dir)
            
            # Парсимо XML
            xml_root = self.parse_xml_file(equip_file)
            if xml_root is not None:
                # Обладнання
                equipment = self.extract_equipment_from_xml(xml_root)
                self.game_entities["equipment"].update(equipment)
                print(f"   Знайдено обладнання: {len(equipment)}")
                
                # Витратні з того ж файлу
                consumables = self.extract_consumables_from_xml(xml_root)
                self.game_entities["consumables"].update(consumables)
                print(f"   Знайдено витратних: {len(consumables)}")
                
        # 2. Парсимо optional_devices.xml (deluxe/experimental)
        opt_file = common_dir / "optional_devices.xml"
        if opt_file.exists():
            print(f"\n[2] Парсинг {opt_file.name}...")
            
            xml_root = self.parse_xml_file(opt_file)
            if xml_root is not None:
                equipment = self.extract_equipment_from_xml(xml_root)
                self.game_entities["equipment"].update(equipment)
                print(f"   Знайдено додаткового обладнання: {len(equipment)}")
                
        # 3. Збираємо перки екіпажу з crew_builds.json
        print("\n[4] Збір перків екіпажу...")
        self._extract_crew_perks()
        
        # 4. Збираємо field mods
        print("\n[5] Збір польової модернізації...")
        self._extract_field_mods()
        
        # 5. Збираємо всі іконки
        print("\n[6] Перевірка іконок...")
        self._check_icons()
        
        return True
        
    def _extract_crew_perks(self):
        """Витягує перки екіпажу з crew_builds.json"""
        crew_builds_path = self.project_root / "crew_builds.json"
        
        if not crew_builds_path.exists():
            print("   crew_builds.json не знайдено")
            return
            
        try:
            with open(crew_builds_path, 'r', encoding='utf-8') as f:
                crew_data = json.load(f)
                
            all_perks = set()
            
            # Збираємо з _role_skill_pools
            if "_role_skill_pools" in crew_data:
                for role, perks in crew_data["_role_skill_pools"].items():
                    all_perks.update(perks)
                    
            # Збираємо з _default_skills
            if "_default_skills" in crew_data:
                for role, perks in crew_data["_default_skills"].items():
                    all_perks.update(perks)
            
            # Перевіряємо іконки перків
            perks_dir = self.icons_base / "crew_skills"
            existing_perks = set()
            if perks_dir.exists():
                for f in perks_dir.glob("*.png"):
                    existing_perks.add(f.stem)
            
            # Формуємо список перків
            # Назви заповнюються з .mo файлів при runtime через LanguageModule
            # Тут зберігаємо perk_id як name — ніде не використовується для відображення
            
            for perk_id in sorted(all_perks):
                self.game_entities["crew_perks"][perk_id] = {
                    "id": perk_id,
                    "name": perk_id,
                    "icon": perk_id,
                    "has_icon": perk_id in existing_perks
                }
                
            print(f"   Знайдено перків: {len(all_perks)}")
            print(f"   Іконки перків: {len(existing_perks)}")
            
        except Exception as e:
            print(f"   Помилка: {e}")
            
    def _extract_field_mods(self):
        """Витягує польову модернізацію з post_progression XML"""
        parsed = self._parse_field_mods_from_xml()
        if parsed:
            for mod_id in parsed:
                self.game_entities["field_mods"][mod_id] = {
                    "id": mod_id,
                    "name": re.sub(r'([A-Z])', r' \1', mod_id).title(),
                    "icon": mod_id,
                    "type": "standard"
                }
            print(f"   Знайдено field mods: {len(parsed)} (з post_progression XML)")
        else:
            standard_mods = [
                "allTerrainSuspension", "lightweightSuspension",
                "parallaxAdjustment", "refinedPowder",
                "leftSidePeriscope", "rightSidePeriscope",
                "rightAngleOptics", "antiReflectiveLenses",
                "reinforcedSpallLiner", "antiFragmentationLining",
                "powerSupplyTuning", "electricalSystemShielding",
                "additionalForwardGears", "additionalReverseGears",
                "noModification"
            ]
            for mod_id in standard_mods:
                self.game_entities["field_mods"][mod_id] = {
                    "id": mod_id,
                    "name": re.sub(r'([A-Z])', r' \1', mod_id).title(),
                    "icon": mod_id,
                    "type": "standard"
                }
            print(f"   Знайдено field mods: {len(standard_mods)} (fallback)")

    def _parse_field_mods_from_xml(self):
        """Парсить field_modifications.xml і повертає список унікальних imgName.

        Використовує decoded XML з extracted_data/common/post_progression/.
        Повертає [] при помилці."""
        xml_path = self.project_root / "extracted_data" / "common" / "post_progression" / "field_modifications.xml"
        if not xml_path.exists():
            return []

        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(str(xml_path))
            root = tree.getroot()

            img_names = set()
            for elem in root.iter():
                for child in elem:
                    if child.tag == "imgName" and child.text:
                        val = child.text.strip()
                        if val and val != "pairModifications/" and "/" not in val:
                            img_names.add(val)
            return sorted(img_names)
        except Exception as e:
            print(f"[WARN] field_modifications.xml parse error: {e}")
            return []
        
    def _check_icons(self):
        """Перевіряємо існування іконок"""
        artefacts_dir = self.icons_base / "artefacts"
        
        existing = {}
        if artefacts_dir.exists():
            for f in artefacts_dir.glob("*.png"):
                existing[f.stem] = f.name
                
        # Перевіряємо обладнання
        missing_icons = []
        for eq_id, eq_data in self.game_entities.get("equipment", {}).items():
            icon_name = eq_data.get("icon", "").split()[0]  # Беремо першу частину (без координат)
            if icon_name and icon_name not in existing:
                missing_icons.append(icon_name)
                
        if missing_icons:
            print(f"   Іконки не знайдено: {len(missing_icons)}")
            for icon in missing_icons[:10]:
                print(f"      - {icon}")
                
        print(f"   Існуючі іконки: {len(existing)}")
        
    def save_to_json(self):
        """Зберігає результат в JSON"""
        output_file = self.project_root / "game_entities.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.game_entities, f, ensure_ascii=False, indent=2)
            
        print(f"\n[ЗБЕРЕЖЕНО] {output_file}")
        
    def print_summary(self):
        """Виводить підсумок"""
        print("\n" + "="*60)
        print("ПІДСУМОК КРОКУ 1:")
        print("="*60)
        print(f"  Обладнання: {len(self.game_entities['equipment'])}")
        print(f"  Витратні:   {len(self.game_entities['consumables'])}")
        print(f"  Перки:      {len(self.game_entities['crew_perks'])}")
        print(f"  Field mods: {len(self.game_entities['field_mods'])}")
        print(f"  Снаряди:    {len(self.game_entities['ammo_types'])}")
        print("="*60)
        

def main():
    print("КРОК 1: Збір всіх можливих варіантів з клієнта гри")
    print("-" * 60)
    
    extractor = GameEntitiesExtractor()
    
    # Виконуємо КРОК 1
    if extractor.run_step1():
        extractor.print_summary()
        extractor.save_to_json()
        print("\n[OK] КРОК 1 завершено!")
    else:
        print("\n[ПОМИЛКА] КРОК 1 не виконано!")
        
    return 0


if __name__ == "__main__":
    exit(main())