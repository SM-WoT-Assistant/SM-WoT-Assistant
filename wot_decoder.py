# НЕ СКОРОЧУВАТИ І НЕ ОПТИМІЗУВАТИ КОД ЯКИЙ НЕ СТОСУЄТЬСЯ ВИПРАВЛЕНЬ!
# wot_decoder.py 2_14
import os
import time
import subprocess
import re
import xml.etree.ElementTree as ET

class WotXmlDecoder:
    def __init__(self):
        self.orion_path = os.path.abspath(os.path.join(os.getcwd(), "tools", "orion", "PjOrion.exe"))

    def decode_folder(self, folder_path, timeout=10):
        if not os.path.exists(self.orion_path):
            print(f"[ПОМИЛКА] Не знайдено PjOrion за шляхом: {self.orion_path}")
            return {}

        abs_folder_path = os.path.abspath(folder_path)
        xml_files = [n for n in os.listdir(abs_folder_path) if n.endswith('.xml')]
        if not xml_files:
            print("[ШТАБ] Немає XML для декодування, запуск PjOrion пропущено.")
            return {}
        orion_dir = os.path.dirname(self.orion_path)
        
        print(f"[ШТАБ] Запуск PjOrion (Тайм-аут: {timeout} сек)...")
        cmd = [self.orion_path, f"--unpack-folder={abs_folder_path}", "--exit"]
        
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
            
            time.sleep(1.5)
        except Exception as e:
            print(f"[ПОМИЛКА] Збій запуску декодера: {e}")
            return {}
            
        map_data = {}
        for file_name in xml_files:
            
            xml_path = os.path.join(abs_folder_path, file_name)
            data = self._parse_xml(xml_path, file_name)
            
            if data and file_name != '_list_.xml':
                map_name = file_name.replace('.xml', '')
                map_data[map_name] = data
                
        return map_data

    def _parse_xml(self, xml_path, file_name):
        try:
            with open(xml_path, 'r', encoding='utf-8', errors='ignore') as f:
                xml_text = f.read().strip()
            
            if not xml_text: return None

            # ВИПРАВЛЕННЯ ТЕГІВ: Тепер враховуємо цифри, крапки та ПІДКРЕСЛЕННЯ (_)
            if re.match(r'^<[0-9\._]', xml_text):
                xml_text = re.sub(r'^<[^>]+>', '<root>', xml_text, count=1)
                xml_text = re.sub(r'</[^>]+>\s*$', '</root>', xml_text)

            root = ET.fromstring(xml_text)
            
            if file_name == '_list_.xml':
                return {}

            bb_dict = {"bottomLeft": [-500.0, -500.0], "upperRight": [500.0, 500.0]}
            bbox = root.find("boundingBox")
            if bbox is not None:
                bl = bbox.findtext("bottomLeft")
                ur = bbox.findtext("upperRight")
                # Обов'язковий .strip() для координат
                if bl: bb_dict["bottomLeft"] = [float(x) for x in bl.strip().split()]
                if ur: bb_dict["upperRight"] = [float(x) for x in ur.strip().split()]
                
            gameplay_types = {}
            gpt = root.find("gameplayTypes")
            if gpt is not None:
                for mode in gpt:
                    mode_name = mode.tag
                    mode_data = {"bases": [], "spawns": []}
                    
                    bases = mode.find("teamBasePositions")
                    if bases is not None:
                        for team in bases:
                            for pos in team:
                                if pos.text: 
                                    mode_data["bases"].append([float(x) for x in pos.text.strip().split()])
                                    
                    cp = mode.find("controlPoint")
                    if cp is not None and cp.text:
                        mode_data["bases"].append([float(x) for x in cp.text.strip().split()])
                        
                    spawns = mode.find("teamSpawnPoints")
                    if spawns is not None:
                        for team in spawns:
                            for pos in team:
                                if pos.text: 
                                    mode_data["spawns"].append([float(x) for x in pos.text.strip().split()])
                                    
                    if mode_data["bases"] or mode_data["spawns"]:
                        gameplay_types[mode_name] = mode_data
                        
            return {"boundingBox": bb_dict, "gameplayTypes": gameplay_types}
            
        except Exception:
            return None
# wot_decoder.py 2_14
# НЕ СКОРОЧУВАТИ І НЕ ОПТИМІЗУВАТИ КОД ЯКИЙ НЕ СТОСУЄТЬСЯ ВИПРАВЛЕНЬ!