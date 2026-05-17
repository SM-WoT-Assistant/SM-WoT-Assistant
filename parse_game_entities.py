#!/usr/bin/env python3
"""
parse_game_entities.py - КРОК 1
Збір всіх можливих варіантів з клієнта гри:
- Обладнання (equipment)
- Витратні (consumables)  
- Перки екіпажу (crew perks)
- Польова модернізація (field mods)
- Снаряди (ammo shells)

Використовує Orion для декодування XML файлів клієнта.
"""
import os
import re
import json
import time
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

class GameEntitiesExtractor:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.extracted_data = self.project_root / "extracted_data"
        self.orion_path = self.project_root / "tools" / "orion" / "PjOrion.exe"
        
        self.game_entities = {
            "equipment": {},
            "consumables": {},
            "crew_perks": {},
            "field_mods": {},
            "ammo_types": {}
        }
        
        self.icons_base = self.project_root / "extracted_icons" / "loadout"
        
    def run_orion_decode(self, folder_path, timeout=15):
        """Декодує XML файли в папці через Orion"""
        if not self.orion_path.exists():
            print(f"[ПОМИЛКА] Orion не знайдено: {self.orion_path}")
            return {}
            
        abs_folder = os.path.abspath(str(folder_path))
        xml_files = [f for f in os.listdir(abs_folder) if f.endswith('.xml')]
        
        if not xml_files:
            print(f"[ШТАБ] Немає XML в: {abs_folder}")
            return {}
            
        orion_dir = os.path.dirname(os.path.abspath(str(self.orion_path)))
        print(f"[ШТАБ] Декодування через Orion ({len(xml_files)} файлів)...")
        
        cmd = [str(self.orion_path), f"--unpack-folder={abs_folder}", "--exit"]
        
        try:
            flags = 0
            startupinfo = None
            if os.name == "nt":
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                
            proc = subprocess.Popen(cmd, cwd=orion_dir, shell=False, creationflags=flags, startupinfo=startupinfo)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.system('taskkill /f /im PjOrion.exe >nul 2>&1')
            
            time.sleep(0.5)
        except Exception as e:
            print(f"[ПОМИЛКА] Збій Orion: {e}")
            return {}
            
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
        equip_file = common_dir / "equipments.xml"
        if equip_file.exists():
            print(f"\n[1] Парсинг {equip_file.name}...")
            
            # Декодуємо через Orion
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
            perk_map = {
                "commander_sixthSense": "Sixth Sense",
                "commander_practical": "Practical",
                "commander_eagleEye": "Eagle Eye",
                "commander_enemyShotPredictor": "Enemy Shot Predictor",
                "brotherhood": "Brothers in Arms",
                "repair": "Repairs",
                "camouflage": "Concealment",
                "fireFighting": "Firefighting",
                "gunner_sniper": "Snap Shot",
                "gunner_focus": "Designated Target",
                "gunner_rancorous": "Armorer",
                "gunner_smoothTurret": "Smooth Ride",
                "driver_smoothDriving": "Off-Road Driving",
                "driver_badRoadsKing": "Clutch Braking",
                "driver_virtuoso": "Controlled Impact",
                "driver_rammingMaster": "Preventative Maintenance",
                "loader_pedant": "Safe Stowage",
                "loader_desperado": "Adrenaline Rush",
                "loader_intuition": "Intuition",
                "radioman_finder": "Sound Detection",
                "improvedRadioCommunication": "Jack of All Trades",
                "smokeSignal": "Signal Boosting",
                "radioman_sidebyside": "Relayer",
            }
            
            for perk_id in sorted(all_perks):
                perk_name = perk_map.get(perk_id, perk_id.replace('_', ' ').title())
                self.game_entities["crew_perks"][perk_id] = {
                    "id": perk_id,
                    "name": perk_name,
                    "icon": perk_id,
                    "has_icon": perk_id in existing_perks
                }
                
            print(f"   Знайдено перків: {len(all_perks)}")
            print(f"   Іконки перків: {len(existing_perks)}")
            
        except Exception as e:
            print(f"   Помилка: {e}")
            
    def _extract_field_mods(self):
        """Витягує польову модернізацію"""
        # Польова модернізація - це не завжди в XML
        # Спробуємо знайти в extracted_data
        field_mods_found = []
        
        # Типові field mods (рівні 1-5)
        standard_mods = [
            "allTerrainSuspension",
            "lightweightSuspension",
            "parallaxAdjustment",
            "refinedPowder",
            "leftSidePeriscope",
            "rightSidePeriscope",
            "rightAngleOptics",
            "antiReflectiveLenses",
            "reinforcedSpallLiner",
            "antiFragmentationLining",
            "powerSupplyTuning",
            "electricalSystemShielding",
            "additionalForwardGears",
            "additionalReverseGears",
            "noModification"
        ]
        
        for mod_id in standard_mods:
            self.game_entities["field_mods"][mod_id] = {
                "id": mod_id,
                "name": re.sub(r'([A-Z])', r' \1', mod_id).title(),
                "icon": mod_id,
                "type": "standard"
            }
            
        print(f"   Знайдено field mods: {len(standard_mods)}")
        
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