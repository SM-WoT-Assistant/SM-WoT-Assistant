import json
import os


def safe_merge_tth_from_extracted(extract_dir, parse_tth_func, tth_path="tank_tth.json"):
    base = {}
    if os.path.exists(tth_path):
        try:
            with open(tth_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                base = loaded
        except Exception:
            base = {}

    discovered = 0
    updated = 0

    if not os.path.isdir(extract_dir):
        return False, discovered, updated, len(base)

    for nation in os.listdir(extract_dir):
        nation_path = os.path.join(extract_dir, nation)
        if not os.path.isdir(nation_path):
            continue

        for fname in os.listdir(nation_path):
            if not fname.endswith(".xml") or fname == "list.xml":
                continue

            tag = fname[:-4]
            fpath = os.path.join(nation_path, fname)
            tth = parse_tth_func(fpath)
            if not tth:
                continue

            discovered += 1
            prev = base.get(tag)
            if not isinstance(prev, dict) or prev != tth:
                base[tag] = tth
                updated += 1

    if not base:
        return False, discovered, updated, 0

    with open(tth_path, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)

    return True, discovered, updated, len(base)


def safe_merge_tth_from_file_list(file_paths, parse_tth_func, tth_path="tank_tth.json", force_update_tags=None):
    """Інкрементальний merge: оновлює лише передані XML-файли."""
    base = {}
    if os.path.exists(tth_path):
        try:
            with open(tth_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                base = loaded
        except Exception:
            base = {}

    checked = 0
    discovered = 0
    updated = 0
    force_set = set(force_update_tags or [])

    for fpath in file_paths or []:
        if not isinstance(fpath, str) or not fpath.endswith(".xml") or not os.path.isfile(fpath):
            continue
        checked += 1

        tag = os.path.basename(fpath)[:-4]
        tth = parse_tth_func(fpath)
        if not tth:
            continue

        discovered += 1
        prev = base.get(tag)
        if tag in force_set:
            base[tag] = tth
            updated += 1
        elif not isinstance(prev, dict) or prev != tth:
            base[tag] = tth
            updated += 1

    if not base:
        return False, checked, discovered, updated, 0

    with open(tth_path, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)

    return True, checked, discovered, updated, len(base)
