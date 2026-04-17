import json
import os
import shutil
import subprocess
import time


NATIONS = ["china", "czech", "france", "germany", "italy", "japan", "poland", "sweden", "uk", "usa", "ussr"]


def _run_orion_unpack(orion_path, folder_path, timeout_sec=45):
    if not os.path.exists(orion_path):
        return False, "orion-not-found"

    orion_dir = os.path.dirname(orion_path)
    cmd = [orion_path, f"--unpack-folder={os.path.abspath(folder_path)}", "--exit"]

    flags = 0
    startupinfo = None
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    try:
        proc = subprocess.Popen(cmd, cwd=orion_dir, shell=False, creationflags=flags, startupinfo=startupinfo)
        proc.wait(timeout=timeout_sec)
        if proc.returncode not in (0, None):
            return False, f"returncode-{proc.returncode}"
        time.sleep(0.7)
        return True, "ok"
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        if os.name == "nt":
            os.system('taskkill /f /im PjOrion.exe >nul 2>&1')
        return False, "timeout"
    except Exception as e:
        return False, f"error-{e}"


def repair_missing_tth_with_orion_batches(
    extract_dir,
    tank_db_path,
    tank_tth_path,
    orion_path,
    parse_tth_func,
    batch_size=25,
    timeout_sec=60,
):
    if not os.path.exists(tank_db_path):
        return False, {"error": "tank_db_not_found"}

    with open(tank_db_path, "r", encoding="utf-8") as f:
        tank_db = json.load(f)
    if not isinstance(tank_db, dict) or not tank_db:
        return False, {"error": "tank_db_invalid"}

    tank_tth = {}
    if os.path.exists(tank_tth_path):
        try:
            with open(tank_tth_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                tank_tth = loaded
        except Exception:
            tank_tth = {}

    missing_tags = [tag for tag in tank_db.keys() if tag not in tank_tth]
    if not missing_tags:
        return True, {
            "missing_before": 0,
            "decoded_files": 0,
            "added": 0,
            "missing_after": 0,
            "skipped": 0,
        }

    # Build file path index from extracted_data nation roots.
    file_index = {}
    for nation in NATIONS:
        nation_path = os.path.join(extract_dir, nation)
        if not os.path.isdir(nation_path):
            continue
        for fname in os.listdir(nation_path):
            if not fname.endswith(".xml") or fname in ("list.xml", "customization.xml"):
                continue
            file_index[fname[:-4]] = os.path.join(nation_path, fname)

    candidates = [file_index[tag] for tag in missing_tags if tag in file_index]
    skipped = len(missing_tags) - len(candidates)
    if not candidates:
        return False, {
            "missing_before": len(missing_tags),
            "decoded_files": 0,
            "added": 0,
            "missing_after": len(missing_tags),
            "skipped": skipped,
            "error": "no_source_xml_for_missing",
        }

    work_root = os.path.join("tmp", "tth_decode_work")
    os.makedirs(work_root, exist_ok=True)

    decoded_files = 0
    added = 0
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        batch_dir = os.path.join(work_root, f"batch_{i // batch_size:03d}")
        if os.path.isdir(batch_dir):
            shutil.rmtree(batch_dir, ignore_errors=True)
        os.makedirs(batch_dir, exist_ok=True)

        for src in batch:
            shutil.copy2(src, os.path.join(batch_dir, os.path.basename(src)))

        ok, _status = _run_orion_unpack(orion_path, batch_dir, timeout_sec=timeout_sec)
        if not ok:
            continue

        for fname in os.listdir(batch_dir):
            if not fname.endswith(".xml"):
                continue
            tag = fname[:-4]
            xml_path = os.path.join(batch_dir, fname)
            tth = parse_tth_func(xml_path)
            if not tth:
                continue
            decoded_files += 1
            prev = tank_tth.get(tag)
            if not isinstance(prev, dict) or prev != tth:
                tank_tth[tag] = tth
                added += 1

    with open(tank_tth_path, "w", encoding="utf-8") as f:
        json.dump(tank_tth, f, ensure_ascii=False, indent=2)

    missing_after = sum(1 for tag in tank_db.keys() if tag not in tank_tth)
    return True, {
        "missing_before": len(missing_tags),
        "decoded_files": decoded_files,
        "added": added,
        "missing_after": missing_after,
        "skipped": skipped,
    }
