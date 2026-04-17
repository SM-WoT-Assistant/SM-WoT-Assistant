import os
import zipfile
import subprocess
import time
import json
import xml.etree.ElementTree as ET
import re
import shutil
import tempfile
import ctypes
from tth_updater import safe_merge_tth_from_extracted, safe_merge_tth_from_file_list
from tth_orion_batch import repair_missing_tth_with_orion_batches

# Шляхи
BASE_DIR = os.getcwd()
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted_data")
ICONS_DIR = os.path.join(BASE_DIR, "extracted_icons")
ORION_PATH = os.path.join(BASE_DIR, "tools", "orion", "PjOrion.exe")

class TankExtractor:
    def __init__(self, wot_path):
        self.wot_path = wot_path
        self.pkg_dir = os.path.join(wot_path, "res", "packages")
        self.meta_manifest_path = os.path.join(BASE_DIR, ".tank_extract_manifest.json")
        self.icon_manifest_path = os.path.join(BASE_DIR, ".icon_extract_manifest.json")
        self.changed_vehicle_dirs = set()
        self.changed_vehicle_files = set()
        self.removed_vehicle_tags = set()
        self.changed_metadata_count = 0
        os.makedirs(EXTRACT_DIR, exist_ok=True)
        os.makedirs(ICONS_DIR, exist_ok=True)

    def _is_vehicle_nation_dir(self, path):
        try:
            rel = os.path.relpath(path, EXTRACT_DIR)
        except Exception:
            return False
        root = rel.split(os.sep, 1)[0].lower()
        return root in {"usa", "ussr", "germany", "france", "uk", "china", "japan", "czech", "poland", "sweden", "italy"}

    def _get_tth_decode_dirs(self):
        roots = set()
        for path in self.changed_vehicle_dirs:
            if not os.path.isdir(path) or not self._is_vehicle_nation_dir(path):
                continue
            rel = os.path.relpath(path, EXTRACT_DIR)
            root = rel.split(os.sep, 1)[0]
            roots.add(os.path.join(EXTRACT_DIR, root))
        return sorted(roots)

    def _get_tth_decode_files(self):
        files = []
        for fpath in sorted(self.changed_vehicle_files):
            if not os.path.isfile(fpath):
                continue
            if not self._is_vehicle_nation_dir(os.path.dirname(fpath)):
                continue
            files.append(fpath)
        return files

    def _get_all_vehicle_xml_files(self):
        files = []
        if not os.path.isdir(EXTRACT_DIR):
            return files
        for nation in os.listdir(EXTRACT_DIR):
            nation_path = os.path.join(EXTRACT_DIR, nation)
            if not os.path.isdir(nation_path):
                continue
            for root, _dirs, fnames in os.walk(nation_path):
                for fname in fnames:
                    if not fname.endswith(".xml") or fname == "list.xml":
                        continue
                    files.append(os.path.join(root, fname))
        return sorted(files)

    def _run_orion_unpack_folder(self, folder_path, timeout_sec):
        if not os.path.exists(ORION_PATH):
            print("[ERROR] PjOrion.exe не знайдено!")
            return False

        abs_folder = os.path.abspath(folder_path)
        orion_abs = os.path.abspath(ORION_PATH)
        try:
            # Критично: у цій збірці Orion стабільно декодує через cmd/start/wait (як у старих робочих ревізіях).
            # /MIN флаг — приховує вікно (мінімізує), щоб користувач не бачив спливаючого вікна.
            cmd = f'cmd /c start /MIN /wait "" "{orion_abs}" --unpack-folder="{abs_folder}" --exit'
            rc = subprocess.call(cmd, cwd=os.path.dirname(orion_abs), shell=True, timeout=max(30, timeout_sec))
            if rc not in (0, None):
                print(f"[WARN] Orion повернув код {rc} ({folder_path})")
                return False
            # Даємо ОС завершити flush файлів після закриття Orion.
            time.sleep(1.0)
            return True
        except subprocess.TimeoutExpired:
            print(f"[ERROR] Таймаут декодування ({folder_path}), примусово завершую PjOrion...")
            self._kill_orion_processes()
            return False
        except Exception as e:
            print(f"[ERROR] Помилка запуску декодера ({folder_path}): {e}")
            self._kill_orion_processes()
            return False

    def _kill_orion_processes(self):
        if os.name == "nt":
            os.system('taskkill /f /im PjOrion.exe >nul 2>&1')

    def _hide_window_for_pid(self, pid):
        if os.name != "nt" or not pid:
            return
        try:
            user32 = ctypes.windll.user32
            SW_HIDE = 0

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def enum_cb(hwnd, lparam):
                proc_id = ctypes.c_ulong(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                if proc_id.value == pid:
                    user32.ShowWindow(hwnd, SW_HIDE)
                return True

            user32.EnumWindows(enum_cb, 0)
        except Exception:
            pass

    def _hide_orion_windows(self):
        if os.name != "nt":
            return
        try:
            user32 = ctypes.windll.user32
            SW_HIDE = 0

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def enum_cb(hwnd, lparam):
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = (buf.value or "").lower()
                if "orion" in title or "pjorion" in title:
                    user32.ShowWindow(hwnd, SW_HIDE)
                return True

            user32.EnumWindows(enum_cb, 0)
        except Exception:
            pass

    def _decode_files_batched(self, xml_files, timeout_sec=60, batch_size=24, fail_fast=True):
        if not xml_files:
            return True

        work_root = os.path.join(tempfile.gettempdir(), "wot_orion_autodecode")
        os.makedirs(work_root, exist_ok=True)

        total = len(xml_files)
        ok_batches = 0
        for idx in range(0, total, batch_size):
            batch = xml_files[idx:idx + batch_size]
            batch_dir = os.path.join(work_root, f"batch_{idx // batch_size:03d}")
            if os.path.isdir(batch_dir):
                shutil.rmtree(batch_dir, ignore_errors=True)
            os.makedirs(batch_dir, exist_ok=True)

            backmap = {}
            for src in batch:
                bn = os.path.basename(src)
                dst = os.path.join(batch_dir, bn)
                try:
                    shutil.copy2(src, dst)
                    backmap[bn] = src
                except Exception as e:
                    print(f"[WARN] Не вдалося підготувати XML для декодування: {src} ({e})")

            if not backmap:
                if fail_fast:
                    return False
                continue

            print(f"[DECODER] Orion job {(idx // batch_size) + 1}/{(total + batch_size - 1) // batch_size}: {batch_dir}")
            ok = self._run_orion_unpack_folder(batch_dir, timeout_sec=max(120, timeout_sec))

            copied_back = 0
            for bn, orig in backmap.items():
                decoded = os.path.join(batch_dir, bn)
                if not os.path.exists(decoded):
                    continue
                try:
                    if self._is_probably_plain_xml(decoded):
                        shutil.copy2(decoded, orig)
                        copied_back += 1
                except Exception as e:
                    print(f"[WARN] Не вдалося повернути декодований XML: {orig} ({e})")

            if copied_back > 0:
                ok_batches += 1
            elif not ok and fail_fast:
                return False

        if not fail_fast:
            print(f"[DECODER] Батч-декодування завершено: успішно {ok_batches}/{(total + batch_size - 1) // batch_size}")
            return ok_batches > 0
        return ok_batches > 0

    def _entry_fingerprint(self, info):
        return {
            "size": int(getattr(info, "file_size", 0)),
            "crc": int(getattr(info, "CRC", 0)),
            "mtime": list(getattr(info, "date_time", (0, 0, 0, 0, 0, 0))),
        }

    def _fingerprint_equal(self, old_fp, new_fp):
        """Стабільне порівняння змін: враховуємо тільки size+crc.
        mtime у pkg може змінюватись без зміни контенту і давати false-positive.
        """
        if not isinstance(old_fp, dict) or not isinstance(new_fp, dict):
            return False
        return (
            int(old_fp.get("size", -1)) == int(new_fp.get("size", -2))
            and int(old_fp.get("crc", -1)) == int(new_fp.get("crc", -2))
        )

    def _is_probably_plain_xml(self, fpath):
        """Швидкий pre-check без повного парсингу файлу."""
        try:
            with open(fpath, "rb") as f:
                head = f.read(256)
            if not head:
                return False
            if b"\x00" in head:
                return False
            # Для текстового XML очікуємо '<' на початку (може бути з пробілами/BOM)
            stripped = head.lstrip(b"\xef\xbb\xbf\r\n\t ")
            return stripped.startswith(b"<")
        except Exception:
            return False

    def _load_json_file(self, path):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    def _save_json_file(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _log_changes_by_nation(self):
        """Логує детальні зміни файлів по країнах."""
        if not self.changed_vehicle_files:
            return
        
        by_nation = {}
        for fpath in self.changed_vehicle_files:
            try:
                rel = os.path.relpath(fpath, EXTRACT_DIR)
                nation = rel.split(os.sep, 1)[0].lower()
                if nation not in by_nation:
                    by_nation[nation] = []
                by_nation[nation].append(os.path.basename(fpath))
            except Exception:
                pass
        
        if by_nation:
            print("[EXTRACTION] Зміни по країнах:")
            for nation in sorted(by_nation.keys()):
                count = len(by_nation[nation])
                samples = by_nation[nation][:2]
                print(f"  {nation.upper()}: {count} файлів ({', '.join(samples)}...)")

    def extract_metadata(self, force_full=False):
        print("[EXTRACTION] Витягую метадані з scripts.pkg...")
        pkg_path = os.path.join(self.pkg_dir, "scripts.pkg")
        if not os.path.exists(pkg_path):
            print(f"[ERROR] Не знайдено scripts.pkg за шляхом: {pkg_path}")
            return False

        old_manifest = self._load_json_file(self.meta_manifest_path)
        new_manifest = {}
        changed_files = 0
        self.changed_vehicle_dirs = set()
        self.changed_vehicle_files = set()
        self.removed_vehicle_tags = set()

        with zipfile.ZipFile(pkg_path, 'r') as z:
            for info in z.infolist():
                name = info.filename
                if "item_defs/vehicles/" in name and name.endswith(".xml"):
                    # Зберігаємо шлях зі структурою папок націй
                    target_path = os.path.join(EXTRACT_DIR, name.replace("scripts/item_defs/vehicles/", ""))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)

                    fp = self._entry_fingerprint(info)
                    new_manifest[name] = fp
                    if not force_full and self._fingerprint_equal(old_manifest.get(name), fp) and os.path.exists(target_path):
                        continue

                    try:
                        with open(target_path, "wb") as f:
                            f.write(z.read(name))
                        self.changed_vehicle_dirs.add(os.path.dirname(target_path))
                        self.changed_vehicle_files.add(target_path)
                        changed_files += 1
                    except PermissionError:
                        print(f"[WARN] Пропущено (нема доступу на запис): {target_path}")

        removed_files = 0
        for old_name in old_manifest.keys():
            if old_name in new_manifest:
                continue
            if "item_defs/vehicles/" not in old_name or not old_name.endswith(".xml"):
                continue
            rel = old_name.replace("scripts/item_defs/vehicles/", "")
            old_target = os.path.join(EXTRACT_DIR, rel)
            tag = os.path.basename(old_target)[:-4]
            if tag:
                self.removed_vehicle_tags.add(tag)
            removed_files += 1
            try:
                if os.path.isfile(old_target):
                    os.remove(old_target)
            except Exception:
                pass

        self._save_json_file(self.meta_manifest_path, new_manifest)
        self.changed_metadata_count = changed_files
        print(f"[EXTRACTION] Змінені XML техніки: {changed_files}")
        if removed_files:
            print(f"[EXTRACTION] Видалені XML техніки: {removed_files}")
        self._log_changes_by_nation()
        return True

    def extract_icons(self):
        print("[EXTRACTION] Витягую активи для UI (іконки, прапори, рівні)...")
        
        extracted_count = 0
        pkg_state = {}
        for i in range(1, 5):
            pkg_path = os.path.join(self.pkg_dir, f"gui-part{i}.pkg")
            if os.path.exists(pkg_path):
                pkg_state[f"gui-part{i}.pkg"] = {
                    "size": os.path.getsize(pkg_path),
                    "mtime": int(os.path.getmtime(pkg_path)),
                }

        icon_manifest = self._load_json_file(self.icon_manifest_path)
        if icon_manifest.get("pkg_state") == pkg_state:
            print("[EXTRACTION] GUI-пакети без змін, витяг іконок пропущено.")
            return True

        # Директорії для нових активів всередині ICONS_DIR
        os.makedirs(os.path.join(ICONS_DIR, "nations"), exist_ok=True)
        os.makedirs(os.path.join(ICONS_DIR, "classes"), exist_ok=True)
        os.makedirs(os.path.join(ICONS_DIR, "levels"), exist_ok=True)
        os.makedirs(os.path.join(ICONS_DIR, "tth"), exist_ok=True)
        os.makedirs(os.path.join(ICONS_DIR, "loadout", "artefacts"), exist_ok=True)
        os.makedirs(os.path.join(ICONS_DIR, "loadout", "ammo"), exist_ok=True)
        os.makedirs(os.path.join(ICONS_DIR, "loadout", "crew_skills"), exist_ok=True)
        os.makedirs(os.path.join(ICONS_DIR, "loadout", "crew_roles"), exist_ok=True)
        os.makedirs(os.path.join(ICONS_DIR, "loadout", "field_mods"), exist_ok=True)
        
        # Перевіряємо всі gui-part пакети
        for i in range(1, 5):
            pkg_path = os.path.join(self.pkg_dir, f"gui-part{i}.pkg")
            if not os.path.exists(pkg_path): continue
            
            print(f"      - Обробка {os.path.basename(pkg_path)}...")
            with zipfile.ZipFile(pkg_path, 'r') as z:
                for name in z.namelist():
                    # 1. Великі ангарні іконки танків
                    if "gui/maps/icons/vehicle/x380x304/" in name and name.endswith(".png"):
                        icon_name = os.path.basename(name).lower()
                        with open(os.path.join(ICONS_DIR, icon_name), "wb") as f:
                            f.write(z.read(name))
                        extracted_count += 1
                        
                    # 2. Прапори націй (для кнопок та фону)
                    elif "gui/maps/icons/nations/" in name and name.endswith(".png"):
                        if any(size in name for size in ["131x31", "155x31", "160x100"]):
                            flag_name = os.path.basename(name).lower()
                            with open(os.path.join(ICONS_DIR, "nations", flag_name), "wb") as f:
                                f.write(z.read(name))
                    
                    # 3. Іконки класів
                    elif "gui/maps/icons/vehicleTypes/48x48/" in name and name.endswith(".png"):
                        if "_elite" not in name:
                            class_name = os.path.basename(name).lower()
                            with open(os.path.join(ICONS_DIR, "classes", class_name), "wb") as f:
                                f.write(z.read(name))
                                
                    # 4. Рівні (римські цифри)
                    elif "gui/maps/icons/levels/tank_level_" in name and name.endswith(".png"):
                        if "small" not in name:
                            level_name = os.path.basename(name).lower()
                            with open(os.path.join(ICONS_DIR, "levels", level_name), "wb") as f:
                                f.write(z.read(name))

                    # 5. Іконки основних параметрів ТТХ (як у клієнті)
                    elif "gui/maps/icons/hangar/ttc/paramsType/x24x24/" in name and name.endswith(".png"):
                        tth_name = os.path.basename(name)
                        with open(os.path.join(ICONS_DIR, "tth", tth_name), "wb") as f:
                            f.write(z.read(name))

                    # 6. Loadout: обладнання/витратні/директиви
                    elif name.startswith("gui/maps/icons/artefact/") and name.endswith(".png"):
                        rel = name[len("gui/maps/icons/artefact/"):]
                        if "/" not in rel:
                            out_name = os.path.basename(rel)
                            with open(os.path.join(ICONS_DIR, "loadout", "artefacts", out_name), "wb") as f:
                                f.write(z.read(name))

                    # 7. Loadout: іконки снарядів (без _TRAY та NO_)
                    elif name.startswith("gui/maps/icons/ammopanel/ammo/") and name.endswith(".png"):
                        out_name = os.path.basename(name)
                        if "_TRAY" in out_name or out_name.startswith("NO_"):
                            continue
                        with open(os.path.join(ICONS_DIR, "loadout", "ammo", out_name), "wb") as f:
                            f.write(z.read(name))

                    # 8. Loadout: навички екіпажу (з папки icons для сучасних іконок)
                    elif name.startswith("gui/maps/icons/tankmen/icons/204x256/") and name.endswith(".png"):
                        out_name = os.path.basename(name)
                        with open(os.path.join(ICONS_DIR, "loadout", "crew_skills", out_name), "wb") as f:
                            f.write(z.read(name))

                    # 8.1 Loadout: ролі екіпажу (white role icons)
                    elif name.startswith("gui/maps/icons/tankmen/roles/opaque/white/") and name.endswith(".png"):
                        out_name = os.path.basename(name)
                        with open(os.path.join(ICONS_DIR, "loadout", "crew_roles", out_name), "wb") as f:
                            f.write(z.read(name))

                    # 9. Loadout: польова модернізація (спеціалізації)
                    elif name.startswith("gui/maps/icons/specialization/") and name.endswith(".png"):
                        rel = name[len("gui/maps/icons/specialization/"):]
                        # Беремо лише базові іконки гілок (без extra_large/large/medium/filter).
                        if "/" in rel:
                            continue
                        if rel.startswith(("extra_large_", "large_", "medium_")):
                            continue
                        if rel.endswith("_filter.png"):
                            continue
                        out_name = os.path.basename(rel)
                        with open(os.path.join(ICONS_DIR, "loadout", "field_mods", out_name), "wb") as f:
                            f.write(z.read(name))
        
        print("[SUCCESS] Додаткові активи витягнуто")
        self._save_json_file(self.icon_manifest_path, {"pkg_state": pkg_state})
        return True

    def _clean_xml(self, content):
        content = content.strip()
        content = re.sub(r'^<[^>]+>', '<root>', content, count=1)
        content = re.sub(r'</[^>]+>\s*$', '</root>', content)
        content = re.sub(r'\s*<xmlns:[^>]+>[^<]*</xmlns:[^>]+>', '', content)
        content = re.sub(r'\s*xmlns:[a-zA-Z0-9_]+="[^"]*"', '', content)
        content = re.sub(r'\s+xmlns="[^"]*"', '', content)
        return content

    def _parse_xml_root_safe(self, content):
        content = (content or "").strip()
        if not content:
            return None
        candidates = [
            content,
            self._clean_xml(content),
            re.sub(r'<\?xml[^>]*\?>', '', content).strip(),
        ]
        for cand in candidates:
            try:
                return ET.fromstring(cand)
            except Exception:
                continue
        return None

    def _parse_tth_from_vehicle_xml(self, xml_path):
        try:
            with open(xml_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if not content.strip() or '<' not in content:
                return None

            root = self._parse_xml_root_safe(content)
            if root is None:
                return None
            tth = {}

            def _num_to_int(text_val):
                try:
                    token = str(text_val).strip().split()[0]
                    return int(round(float(token)))
                except Exception:
                    return None

            def _extract_primary_armor(node):
                armor_el = node.find('armor') if node is not None else None
                prim_txt = node.findtext('primaryArmor', '').strip().split() if node is not None else []
                vals = []
                if armor_el is None or not prim_txt:
                    return vals
                for pa in prim_txt[:3]:
                    el = armor_el.find(pa)
                    if el is not None and el.text:
                        v = _num_to_int(el.text)
                        if v is not None:
                            vals.append(v)
                return vals

            speed = root.find('speedLimits')
            if speed is not None:
                fwd = speed.findtext('forward')
                if fwd:
                    tth['speed_fwd'] = int(float(fwd.strip()))
                bwd = speed.findtext('backward')
                if bwd:
                    tth['speed_bwd'] = int(float(bwd.strip()))

            hull = root.find('hull')
            if hull is not None:
                hp_txt = hull.findtext('maxHealth')
                if hp_txt:
                    tth['hp'] = int(hp_txt.strip())

                vals = _extract_primary_armor(hull)
                if vals:
                    tth['hull_armor'] = vals[:3]

            turret_groups = []
            turrets = root.find('turrets')
            if turrets is not None:
                turret_groups.append(turrets)
            for child in root:
                if isinstance(child.tag, str) and child.tag.lower().startswith('turrets'):
                    turret_groups.append(child)

            for turret_group in turret_groups:
                for turret_el in list(turret_group):
                    vals = _extract_primary_armor(turret_el)
                    if vals and 'turret_armor' not in tth:
                        tth['turret_armor'] = vals[:3]

                    if 'view_range' not in tth:
                        vr = turret_el.findtext('circularVisionRadius')
                        if vr:
                            try:
                                tth['view_range'] = int(float(vr.strip()))
                            except Exception:
                                pass

                    guns_el = turret_el.find('guns')
                    if guns_el is None:
                        for sub in list(turret_el):
                            if isinstance(sub.tag, str) and sub.tag.lower().startswith('guns'):
                                guns_el = sub
                                break

                    if guns_el is None:
                        continue

                    for gun_el in list(guns_el):
                        if 'reload' not in tth:
                            reload_txt = gun_el.findtext('reloadTime')
                            if reload_txt:
                                try:
                                    tth['reload'] = round(float(reload_txt.strip()), 1)
                                except Exception:
                                    pass

                        shots_el = gun_el.find('shots')
                        if shots_el is None:
                            continue

                        shell_list = []
                        for shot in list(shots_el):
                            s_type = shot.findtext('kind', '').strip() or shot.tag
                            dmg_el = shot.find('damage')
                            pen_el = shot.find('piercingPower')

                            dmg = _num_to_int(dmg_el.text) if dmg_el is not None and dmg_el.text else 0
                            pen = _num_to_int(pen_el.text) if pen_el is not None and pen_el.text else 0

                            if s_type and (dmg or pen):
                                shell_list.append({
                                    'type': s_type,
                                    'damage': dmg,
                                    'piercing': pen,
                                })

                        if shell_list and 'shells' not in tth:
                            tth['shells'] = shell_list

            return tth if tth else None
        except Exception:
            return None

    def build_tth_database(self):
        print("[DATABASE] Формую tank_tth.json (основні ТТХ з клієнта)...")
        out = {}

        for nation in os.listdir(EXTRACT_DIR):
            nation_path = os.path.join(EXTRACT_DIR, nation)
            if not os.path.isdir(nation_path):
                continue

            for fname in os.listdir(nation_path):
                if not fname.endswith('.xml') or fname == 'list.xml':
                    continue
                tag = fname[:-4]
                fpath = os.path.join(nation_path, fname)
                tth = self._parse_tth_from_vehicle_xml(fpath)
                if tth:
                    out[tag] = tth

        # Не підміняємо реальні ТТХ синтетичними значеннями.
        # Якщо новий парсинг порожній, залишаємо існуючий tank_tth.json як стабільний fallback.
        if not out:
            try:
                if os.path.exists('tank_tth.json'):
                    with open('tank_tth.json', 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                    if isinstance(existing, dict) and existing:
                        print(f"[DATABASE] TTH парсинг порожній, залишаю поточний tank_tth.json: {len(existing)} записів")
                        return True
            except Exception as e:
                print(f"[WARN] Не вдалося прочитати існуючий tank_tth.json: {e}")

        if not out:
            print("[ERROR] tank_tth порожній після побудови. Збереження скасовано.")
            return False

        with open('tank_tth.json', 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[SUCCESS] tank_tth.json створено: {len(out)} танків")
        return True

    def update_tth_database_safe(self, allow_decode_retry=False, force_single_file_refresh=False):
        print("[DATABASE] Оновлюю tank_tth.json (безпечний merge, без перезапису tank_db)...")

        all_files = self._get_all_vehicle_xml_files()
        changed_files = self._get_tth_decode_files()
        changed_files_count = len(changed_files)
        force_update_tags = set()

        # Тестовий режим: навіть без змін проганяємо 1 файл, щоб перевірити pipeline end-to-end.
        if force_single_file_refresh and changed_files_count == 0 and all_files:
            preferred = [
                os.path.join(EXTRACT_DIR, "ussr", "R45_IS-7.xml"),
                os.path.join(EXTRACT_DIR, "uk", "GB86_Centurion_Action_X.xml"),
                os.path.join(EXTRACT_DIR, "usa", "A120_M48A5.xml"),
            ]
            candidate = None
            for p in preferred:
                if os.path.isfile(p):
                    candidate = p
                    break
            if candidate is None:
                for p in all_files:
                    rel = os.path.relpath(p, EXTRACT_DIR).replace("\\", "/").lower()
                    if rel.startswith("common/"):
                        continue
                    candidate = p
                    break
            if candidate is None:
                for p in all_files:
                    if self._is_probably_plain_xml(p):
                        candidate = p
                        break
            if candidate is None:
                candidate = all_files[0]
                print("[TTH-TEST] Увага: текстовий XML не знайдено, тестовий файл може вимагати декодування")

            changed_files = [candidate]
            changed_files_count = 1
            force_update_tags.add(os.path.basename(candidate)[:-4])
            print(f"[TTH-TEST] Примусове тест-оновлення одного файлу: {os.path.basename(candidate)}")

        print(
            "[TTH-CHECK] "
            f"checked_all={len(all_files)}, changed={changed_files_count}, unchanged={max(0, len(all_files) - changed_files_count)}"
        )

        # 1) Інкрементальна перевірка/парс тільки змінених XML без декодування.
        parseable_changed = []
        decode_candidates = []
        parsed_without_decode = 0
        for idx, fpath in enumerate(changed_files, start=1):
            # Швидкий pre-check: якщо файл не схожий на текстовий XML, одразу в decode-чергу.
            if not self._is_probably_plain_xml(fpath):
                decode_candidates.append(fpath)
            else:
                tth = self._parse_tth_from_vehicle_xml(fpath)
                if tth:
                    parsed_without_decode += 1
                    parseable_changed.append(fpath)
                else:
                    decode_candidates.append(fpath)
            if idx == changed_files_count or (idx % 25 == 0):
                print(
                    "[PROGRESS] "
                    f"checked {idx}/{changed_files_count}, parsed={parsed_without_decode}, decode_queue={len(decode_candidates)}"
                )

        print(
            "[TTH-CHECK] "
            f"changed_checked={changed_files_count}, parsed_without_decode={parsed_without_decode}, needs_decode={len(decode_candidates)}"
        )

        # 2) Merge лише тих змінених, що вже парсяться без декодування.
        ok = True
        checked_inc = 0
        discovered = 0
        updates = 0
        total = 0

        if parseable_changed:
            ok, checked_inc, discovered, updates, total = safe_merge_tth_from_file_list(
                parseable_changed,
                self._parse_tth_from_vehicle_xml,
                "tank_tth.json",
                force_update_tags=force_update_tags,
            )

        # 3) Вибіркове декодування лише проблемних змінених XML.
        decoded_files_count = 0
        decoded_parsed = 0
        decoded_updates = 0
        if decode_candidates and allow_decode_retry:
            print(f"[DECODER] Вибіркове декодування змінених XML: {len(decode_candidates)}")
            decoded = self.decode_all(target_files=decode_candidates, timeout_sec=60, fail_fast=False)
            if decoded:
                d_ok, d_checked, d_discovered, d_updated, d_total = safe_merge_tth_from_file_list(
                    decode_candidates,
                    self._parse_tth_from_vehicle_xml,
                    "tank_tth.json",
                )
                decoded_files_count = d_checked
                decoded_parsed = d_discovered
                decoded_updates = d_updated
                ok = ok and d_ok
                total = max(total, d_total)
        elif decode_candidates and not allow_decode_retry:
            print("[DECODER] Вимкнено: авто-декодування не запущено (tth_decode_retry_enabled=false)")

        # 4) Видаляємо TTH для файлів, які зникли з scripts.pkg.
        removed_tth = 0
        if self.removed_vehicle_tags:
            try:
                with open("tank_tth.json", "r", encoding="utf-8") as f:
                    tth_base = json.load(f)
                if isinstance(tth_base, dict):
                    for tag in self.removed_vehicle_tags:
                        if tag in tth_base:
                            del tth_base[tag]
                            removed_tth += 1
                    if removed_tth:
                        with open("tank_tth.json", "w", encoding="utf-8") as f:
                            json.dump(tth_base, f, ensure_ascii=False, indent=2)
                        total = len(tth_base)
            except Exception as e:
                print(f"[WARN] Не вдалося видалити застарілі TTH: {e}")

        if total == 0:
            try:
                with open("tank_tth.json", "r", encoding="utf-8") as f:
                    cur_tth = json.load(f)
                if isinstance(cur_tth, dict):
                    total = len(cur_tth)
            except Exception:
                pass

        if changed_files_count == 0:
            print("[DATABASE] Змінених XML немає: інкрементальне оновлення пропущено.")
        print(
            "[DATABASE] ІНКРЕМЕНТАЛЬНО: "
            f"checked_changed={changed_files_count}, parsed_no_decode={parsed_without_decode}, "
            f"decoded_checked={decoded_files_count}, decoded_parsed={decoded_parsed}, "
            f"updated={updates + decoded_updates}, removed={removed_tth}"
        )
        if decoded_parsed > 0 and (updates + decoded_updates) == 0:
            print("[DATABASE] Декодування виконано, але нові ТТХ збігаються з поточною базою (оновлення не потрібне).")

        if not ok:
            print("[ERROR] Безпечне TTH-оновлення не має даних для збереження.")
            return False

        # Інформативний статус: parsed=0 не означає відсутність TTH, це лише відсутність НОВИХ парсів.
        try:
            with open("tank_db.json", "r", encoding="utf-8") as f:
                db = json.load(f)
            with open("tank_tth.json", "r", encoding="utf-8") as f:
                tth = json.load(f)
            if isinstance(db, dict) and isinstance(tth, dict):
                missing = [k for k in db.keys() if k not in tth]
                coverage = len(tth) / len(db) * 100 if len(db) > 0 else 0
                print(
                    "[DATABASE] TTH coverage: "
                    f"db={len(db)}, tth={len(tth)} ({coverage:.1f}%), "
                    f"missing={len(missing)}, updates={updates}"
                )
                if missing:
                    print(f"[DATABASE] TTH missing sample: {missing[:5]}")
        except Exception as e:
            print(f"[WARN] Не вдалося порахувати TTH coverage: {e}")

        print(
            "[SUCCESS] TTH merge завершено: "
            f"parsed={discovered + decoded_parsed}, updated={updates + decoded_updates}, total={total}"
        )
        return True

    def repair_missing_tth_with_orion(self, batch_size=25, timeout_sec=60):
        print("[DATABASE] Ремонтую відсутні TTH через Orion батчами...")
        ok, stats = repair_missing_tth_with_orion_batches(
            extract_dir=EXTRACT_DIR,
            tank_db_path="tank_db.json",
            tank_tth_path="tank_tth.json",
            orion_path=ORION_PATH,
            parse_tth_func=self._parse_tth_from_vehicle_xml,
            batch_size=batch_size,
            timeout_sec=timeout_sec,
        )
        if ok:
            print(
                "[SUCCESS] Orion TTH repair: "
                f"missing_before={stats.get('missing_before', 0)}, "
                f"decoded={stats.get('decoded_files', 0)}, "
                f"added={stats.get('added', 0)}, "
                f"missing_after={stats.get('missing_after', 0)}, "
                f"skipped={stats.get('skipped', 0)}"
            )
            return True
        print(f"[ERROR] Orion TTH repair failed: {stats}")
        return False

    def decode_all(self, progress_cb=None, target_dirs=None, target_files=None, timeout_sec=45, fail_fast=True):
        if target_files is not None:
            files = [p for p in sorted(target_files) if os.path.isfile(p)]
            if not files:
                print("[DECODER] Немає валідних XML-файлів, декодування пропущено.")
                return True
            print(f"[DECODER] Тихий батч-декод Orion для {len(files)} XML...")
            # Для GUI-бінарника Orion лишаємо більше часу навіть на малому батчі.
            return self._decode_files_batched(files, timeout_sec=max(180, timeout_sec), batch_size=24, fail_fast=fail_fast)

        targets = sorted(target_dirs if target_dirs is not None else self.changed_vehicle_dirs)
        if not targets:
            print("[DECODER] Немає змінених XML, декодування пропущено.")
            return True

        print("[DECODER] Запуск PjOrion для розкодування XML...")
        if not os.path.exists(ORION_PATH):
            print("[ERROR] PjOrion.exe не знайдено!")
            return False

        orion_dir = os.path.dirname(ORION_PATH)

        flags = 0
        startupinfo = None
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        # Декодуємо лише директорії зі зміненими XML; запуск на корені може перевести Orion у REPL.
        decode_jobs = [p for p in targets if os.path.isdir(p)]
        if not decode_jobs:
            print("[DECODER] Немає валідних директорій для декодування.")
            return True
        success_count = 0
        total = len(decode_jobs)
        for idx, folder_path in enumerate(decode_jobs, start=1):
            cmd = [ORION_PATH, f"--unpack-folder={folder_path}", "--exit"]
            try:
                if progress_cb:
                    progress_cb(idx, total, folder_path)
                proc = subprocess.Popen(
                    cmd,
                    cwd=orion_dir,
                    shell=False,
                    creationflags=flags,
                    startupinfo=startupinfo,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                proc.wait(timeout=timeout_sec)
                if proc.returncode not in (0, None):
                    print(f"[ERROR] Декодер повернув код {proc.returncode} ({folder_path})")
                    if fail_fast:
                        return False
                    continue
                success_count += 1
                time.sleep(1)
            except subprocess.TimeoutExpired:
                print(f"[ERROR] Таймаут декодування ({folder_path}), примусово завершую PjOrion...")
                try:
                    proc.kill()
                except Exception:
                    pass
                if os.name == "nt":
                    os.system('taskkill /f /im PjOrion.exe >nul 2>&1')
                if fail_fast:
                    return False
                continue
            except Exception as e:
                print(f"[ERROR] Помилка декодера ({folder_path}): {e}")
                if fail_fast:
                    return False
                continue
        if not fail_fast:
            print(f"[DECODER] Декодування завершено: успішно {success_count}/{total}")
        return success_count > 0 if not fail_fast else True

    def build_database(self):
        print("[DATABASE] Формую tank_db.json...")
        import re
        NATION_IDS = {
            "ussr": 0, "germany": 1, "usa": 2, "china": 3,
            "france": 4, "uk": 5, "japan": 6, "czech": 7,
            "sweden": 8, "poland": 9, "italy": 10,
        }
        tank_db = {}
        for nation in os.listdir(EXTRACT_DIR):
            nation_path = os.path.join(EXTRACT_DIR, nation)
            if not os.path.isdir(nation_path): continue

            nation_mapping = {"usa": "USA", "ussr": "USSR", "uk": "UK"}
            display_nation = nation_mapping.get(nation.lower(), nation.capitalize())
            nation_id = NATION_IDS.get(nation.lower(), -1)

            def _upsert_tank(tag, level_text, tags_text, id_text="", is_premium_hint=False):
                if not tag:
                    return
                # ФІЛЬТРАЦІЯ: Пропускаємо технічні танки та ботів
                technical_tags = ["mapstraining", "igr", "bot", "dummy", "tutorial", "observer"]
                if any(tt in tag.lower() for tt in technical_tags):
                    return

                clean_name = re.sub(r'^[A-Z][a-z]?\d{1,3}_', '', tag)
                clean_name = clean_name.replace("_", " ")
                clean_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean_name)
                clean_name = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', clean_name)
                clean_name = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', clean_name)

                tags_text_l = (tags_text or "").lower()
                v_class = "Unknown"
                if "lighttank" in tags_text_l: v_class = "LT"
                elif "mediumtank" in tags_text_l: v_class = "MT"
                elif "heavytank" in tags_text_l: v_class = "HT"
                elif "at-spg" in tags_text_l: v_class = "TD"
                elif "spg" in tags_text_l: v_class = "SPG"

                is_premium = bool(is_premium_hint)
                if "premium" in tags_text_l or "special" in tags_text_l:
                    is_premium = True

                icon_file = f"{tag}.png".lower()
                if not os.path.exists(os.path.join(ICONS_DIR, icon_file)):
                    icon_file = f"{nation}-{tag}.png".lower()

                compact_descr = None
                id_text = (id_text or "").strip()
                if nation_id >= 0 and id_text.isdigit():
                    compact_descr = (int(id_text) << 8) | (nation_id << 4) | 1

                try:
                    tier_val = int(level_text) if str(level_text).strip() else 0
                except Exception:
                    tier_val = 0

                tank_db[tag] = {
                    "name": clean_name,
                    "tier": tier_val,
                    "class": v_class,
                    "nation": display_nation,
                    "icon": icon_file,
                    "is_premium": is_premium,
                    "compact_descr": compact_descr,
                }
            
            list_xml = os.path.join(nation_path, "list.xml")
            if not os.path.exists(list_xml): continue

            try:
                with open(list_xml, "r", encoding="utf-8", errors="ignore") as f:
                    xml_text = f.read().strip()
                
                # ВИПРАВЛЕННЯ: Видаляємо проблемні xmlns теги та огортаємо в root
                xml_text = re.sub(r'<xmlns:xmlref>.*?</xmlns:xmlref>', '', xml_text, flags=re.DOTALL)
                if xml_text.startswith("<"):
                    xml_text = re.sub(r'^<[^>]+>', '<root>', xml_text, count=1)
                    xml_text = re.sub(r'</[^>]+>\s*$', '</root>', xml_text)

                root = ET.fromstring(xml_text)
                for tank in root:
                    tag = tank.tag
                    if tag == "xmlns:xmlref":
                        continue
                    level = tank.findtext("level")
                    tags_text = tank.findtext("tags", "").lower()
                    is_premium = False
                    price_node = tank.find("price")
                    if price_node is not None and "gold" in ET.tostring(price_node).decode().lower():
                        is_premium = True
                    id_text = tank.findtext("id", "").strip()
                    _upsert_tank(tag, level, tags_text, id_text, is_premium)
            except Exception as e:
                print(f"[WARN] Помилка парсингу {list_xml}: {e}")
                # Fallback без list.xml: збираємо мінімальну БД напряму з XML танків
                recovered = 0
                for fname in os.listdir(nation_path):
                    if not fname.endswith('.xml') or fname in ('list.xml', 'customization.xml'):
                        continue
                    tag = fname[:-4]
                    fpath = os.path.join(nation_path, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        root = self._parse_xml_root_safe(content)
                        if root is None:
                            continue
                        level = root.findtext('level', '')
                        tags_text = root.findtext('tags', '')
                        id_text = root.findtext('id', '')
                        price_node = root.find('price')
                        is_premium = False
                        if price_node is not None and 'gold' in ET.tostring(price_node, encoding='unicode').lower():
                            is_premium = True
                        _upsert_tank(tag, level, tags_text, id_text, is_premium)
                        recovered += 1
                    except Exception:
                        continue
                        # Більш короткий таймаут для батчів
                        decoded = self.decode_all(target_dirs=tth_decode_dirs, timeout_sec=60, fail_fast=False)
                if recovered:
                    print(f"[DATABASE] Fallback з XML ({nation}): +{recovered} танків")

        # Last-resort fallback: якщо tank_db все ще порожній, сканимо імена файлів у extracted_data
        if not tank_db:
            nation_folder_map = {
                "usa": "USA", "ussr": "USSR", "germany": "Germany", "france": "France", "uk": "UK",
                "china": "China", "japan": "Japan", "czech": "Czech", "poland": "Poland", "sweden": "Sweden", "italy": "Italy"
            }
            for nation_folder in os.listdir(EXTRACT_DIR):
                npath = os.path.join(EXTRACT_DIR, nation_folder)
                if not os.path.isdir(npath) or nation_folder.lower() not in nation_folder_map:
                    continue
                for fname in os.listdir(npath):
                    if not fname.endswith('.xml') or fname in ('list.xml', 'customization.xml'):
                        continue
                    tag = fname[:-4]
                    low = tag.lower()
                    if any(b in low for b in ["_7x7", "_fallout", "_fl", "_sh", "_bootcamp", "_igr", "_test", "_training", "tutorial", "observer", "_newonboarding", "_storymode"]):
                        continue
                    m = re.match(r'^[A-Za-z]+\d{1,4}_(.+)$', tag)
                    name_part = m.group(1) if m else tag
                    tank_db[tag] = {
                        "name": name_part.replace("_", " ").strip(),
                        "tier": 5,  # За замовчуванням середній рівень
                        "class": "Unknown",
                        "nation": nation_folder_map[nation_folder.lower()],
                        "icon": f"{tag}.png".lower(),
                        "is_premium": False,
                        "compact_descr": None,
                    }
            if tank_db:
                print(f"[DATABASE] Last-resort fallback: +{len(tank_db)} танків із імен XML")

        if not tank_db:
            print("[ERROR] tank_db порожній після побудови. Збереження скасовано.")
            return False

        with open("tank_db.json", "w", encoding="utf-8") as f:
            json.dump(tank_db, f, ensure_ascii=False, indent=4)
        print(f"[SUCCESS] База створена: {len(tank_db)} танків")
        
        # Крок 2: підставляємо реальні назви з .mo локалізації гри
        try:
            from name_localizer import localize_tank_db
            print("[LOCALIZER] Підставляємо реальні назви з клієнта гри...")
            localize_tank_db(self.wot_path)
        except Exception as e:
            print(f"[WARN] Не вдалося підтягнути локалізовані назви: {e}")
        return True

if __name__ == "__main__":
    # Тестовий запуск з шляху в settings.json
    try:
        with open("settings.json", "r") as f:
            settings = json.load(f)
            wot_p = settings.get("wot_path")
            if wot_p:
                extractor = TankExtractor(wot_p)
                if extractor.extract_metadata() and extractor.extract_icons():
                    if extractor.decode_all():
                        extractor.build_database()  # локалізація вже всередині
                        extractor.build_tth_database()
            else:
                print("[ERROR] Не знайдено wot_path у settings.json")
    except Exception as e:
        print(f"[ERROR] Помилка запуску: {e}")
