import json
import tkinter as tk
from tkinter import filedialog
import dialog_utils

def _choice_dialog(parent, title, text, _t=None):
    _t = _t or (lambda k, d: d)
    dlg, hdr = dialog_utils.make_custom_dialog(parent, title)
    dialog_utils._DragHelper(dlg, hdr)
    dlg.grab_set()
    result = None
    tk.Label(dlg, text=text, bg="#222", fg="#ccc",
             font=("Arial", 9), wraplength=380, justify="left").pack(padx=20, pady=(15, 15))
    bf = tk.Frame(dlg, bg="#222")
    bf.pack(pady=(0, 12))
    def on_replace():
        nonlocal result; result = True; dlg.destroy()
    def on_merge():
        nonlocal result; result = False; dlg.destroy()
    def on_cancel():
        nonlocal result; result = None; dlg.destroy()
    tk.Button(bf, text=_t('tactic_replace', 'Replace'), bg="#553333", fg="#ff6666", bd=0,
              font=("Arial", 9, "bold"), padx=12, pady=4, command=on_replace).pack(side="left", padx=4)
    tk.Button(bf, text=_t('tactic_merge', 'Merge'), bg="#335533", fg="#66cc66", bd=0,
              font=("Arial", 9, "bold"), padx=12, pady=4, command=on_merge).pack(side="left", padx=4)
    tk.Button(bf, text=_t('tactic_choice_cancel', 'Cancel'), bg="#444", fg="#aaa", bd=0,
              font=("Arial", 9), padx=12, pady=4, command=on_cancel).pack(side="left", padx=4)
    parent.wait_window(dlg)
    return result

def export_tactic(parent, map_id, map_name, drawings, _t=None):
    _t = _t or (lambda k, d: d)
    if not map_id or map_id not in drawings or not drawings[map_id]:
        dialog_utils.dark_messagebox(parent, _t('export_no_drawings', 'Export'), _t('export_no_drawings', 'No drawings'))
        return

    file_path = filedialog.asksaveasfilename(
        parent=parent,
        title=_t('export_success', 'Export tactic'),
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        initialfile=f"{map_name}.json"
    )

    if file_path:
        data = {
            "map_id": map_id,
            "map_name": map_name,
            "title": "",
            "comment": "",
            "drawings": drawings[map_id]
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            dialog_utils.dark_messagebox(parent, _t('export_success', 'Export'), _t('export_success', 'Exported!'))
        except Exception as e:
            dialog_utils.dark_messagebox(parent, _t('export_save_error', 'Error'), _t('export_save_error', 'Save failed: {error}').format(error=e), is_error=True)

def import_tactic(parent, current_map_id, current_map_name, drawings, on_success, _t=None):
    _t = _t or (lambda k, d: d)
    file_path = filedialog.askopenfilename(
        parent=parent,
        title=_t('import_success', 'Import tactic'),
        filetypes=[("JSON files", "*.json")]
    )

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "drawings" not in data:
                dialog_utils.dark_messagebox(parent, _t('import_error_format', 'Error'), _t('import_error_format', 'Invalid format'), is_error=True)
                return

            if not isinstance(data["drawings"], list):
                dialog_utils.dark_messagebox(parent, _t('import_error_all_maps', 'Error'),
                    _t('import_error_all_maps', 'All-maps file.\nUse Import All.'),
                    is_error=True)
                return

            import_map_id = data.get("map_id")
            if import_map_id and import_map_id != current_map_id:
                msg = _t('import_warning_msg', "Created for '{src}'.\nImport to '{dst}'?").format(src=data.get('map_name', import_map_id), dst=current_map_name)
                if not dialog_utils.dark_confirmbox(parent, _t('import_warning_title', 'Map mismatch'), msg, yes_text=_t('btn_yes', 'Yes'), no_text=_t('btn_no', 'No')):
                    return

            choice = _choice_dialog(parent, _t('import_choice_msg', 'Import'),
                _t('import_choice_msg', 'Replace or merge?'), _t=_t)

            if choice is None:
                return

            if current_map_id not in drawings:
                drawings[current_map_id] = []

            if choice:
                drawings[current_map_id] = data["drawings"]
            else:
                drawings[current_map_id].extend(data["drawings"])

            on_success()
            dialog_utils.dark_messagebox(parent, _t('import_success', 'Import'), _t('import_success', 'Imported!'))

        except Exception as e:
            dialog_utils.dark_messagebox(parent, _t('import_read_error', 'Error'), _t('import_read_error', 'Read failed: {error}').format(error=e), is_error=True)


import os
import time
import uuid
import re as _re
import config


def migrate_legacy_elements(items, cw, ch, org_x, org_y, img_w, img_h):
    """One-time conversion of pre-02.10 scheme coords into the image-rect space.

    Commit 8085639 (02.10.2026) changed the scheme coordinate space from
    canvas fractions (x/canvas) to image-rect fractions ((x-org)/img_size).
    Legacy elements render ~5-10% toward the map centre (border inset) and
    their pixel error scales with the window — the reported "schemes shift
    with edit-window size". Restore the drawn position with the exact
    inverse: u_new = (u_old * canvas - org) / img_size. No clamping.
    Idempotent: elements already stamped norm:"img" are skipped.
    Returns the number of converted elements."""
    if not items or img_w < 10 or img_h < 10 or cw < 10 or ch < 10:
        return 0

    def _conv_pair_list(vals):
        out = list(vals)
        for i in range(0, len(out) - 1, 2):
            out[i] = (out[i] * cw - org_x) / img_w
            out[i + 1] = (out[i + 1] * ch - org_y) / img_h
        return out

    n = 0
    for obj in items:
        if not isinstance(obj, dict) or obj.get("norm"):
            continue
        changed = False
        c = obj.get("coords")
        if isinstance(c, list) and len(c) >= 2:
            obj["coords"] = _conv_pair_list(c)
            changed = True
        elif not c and "x1" in obj:
            # ancient x1/y1/x2/y2 format (normalized to coords at painter load)
            x1 = (obj.get("x1", 0.0) * cw - org_x) / img_w
            y1 = (obj.get("y1", 0.0) * ch - org_y) / img_h
            x2 = (obj.get("x2", obj.get("x1", 0.0)) * cw - org_x) / img_w
            y2 = (obj.get("y2", obj.get("y1", 0.0)) * ch - org_y) / img_h
            obj["coords"] = [x1, y1, x2, y2]
            changed = True
        tc = obj.get("text_coords")
        if isinstance(tc, list) and len(tc) >= 2:
            obj["text_coords"] = _conv_pair_list(tc)
            changed = True
        cic = obj.get("class_icon_coords")
        if isinstance(cic, list) and len(cic) >= 2:
            obj["class_icon_coords"] = _conv_pair_list(cic)
            changed = True
        if changed:
            obj["norm"] = "img"
            n += 1
    return n


def migrate_schemes_db(db_path, cw, ch, org_x, org_y, img_w, img_h):
    """File-level migration of saved_schemes.json (one-shot, idempotent).

    Creates <db_path>.bak_pre_norm once before the first rewrite — the
    rollback point. Elements already carrying norm:"img" are skipped, so
    re-running is a no-op. Returns (schemes_touched, elements_converted)."""
    db = _load_db(db_path)
    if not db:
        return 0, 0
    total_els = 0
    touched = 0
    for scheme in db.values():
        if not isinstance(scheme, dict):
            continue
        els = scheme.get("elements")
        if not isinstance(els, list):
            continue
        n = migrate_legacy_elements(els, cw, ch, org_x, org_y, img_w, img_h)
        if n:
            total_els += n
            touched += 1
    if not touched:
        return 0, 0
    import shutil
    bak = db_path + ".bak_pre_norm"
    try:
        if os.path.isfile(db_path) and not os.path.isfile(bak):
            shutil.copy2(db_path, bak)
    except Exception as e:
        print(f"[NORM] backup failed ({e}) — schemes DB NOT migrated")
        return 0, 0
    if not _save_db(db_path, db):
        return 0, 0
    return touched, total_els


def _load_db(db_path):
    """Load the saved_schemes.json database. Returns dict of schemes keyed by drawing_id."""
    import safe_io
    data = safe_io.read_json(db_path, {})
    if isinstance(data, dict):
        return data
    return {}


def _save_db(db_path, db):
    """Save the saved_schemes.json database."""
    import safe_io
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    except Exception:
        pass
    return safe_io.write_json(db_path, db, indent=2)


def save_scheme_to_db(db_path, map_id, map_name, mode, drawings, scheme_name=None, description="", source="local", section="maps"):
    """Save current map's drawings into the single JSON DB.
    Upserts by (map_id, mode, scheme_name) — replaces if same name exists for same map+mode.
    Returns (ok, display_name)."""
    if not map_id or map_id not in drawings:
        return False, "No drawings"
    if not drawings[map_id] and not scheme_name:
        return False, "No drawings"

    db = _load_db(db_path)
    name = scheme_name or f"{map_name} [{mode}]"

    existing_id = None
    for did, s in db.items():
        if (s.get("map_id") == map_id and s.get("battle_mode") == mode
                and s.get("scheme_name", "") == name):
            existing_id = did
            break

    drawing_id = existing_id or str(uuid.uuid4())[:8]
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    old = db.get(drawing_id, {})

    db[drawing_id] = {
        "drawing_id": drawing_id,
        "map_id": map_id,
        "map_name": map_name,
        "battle_mode": mode,
        "scheme_name": name,
        "description": description,
        "elements": drawings[map_id],
        "source": source,
        # "maps" | "tactic": recorded on create, PRESERVED on update;
        # the minimap mod never shows section=="tactic" (user spec 09.10)
        "section": old.get("section") or section,
        "is_base": old.get("is_base", False),
        "is_default": old.get("is_default", False),
        "saved_at": old.get("saved_at", now),
        "updated_at": now,
    }

    ok = _save_db(db_path, db)
    action = "Updated" if existing_id else "Saved"
    return ok, f"{action}: {name}" if ok else "Save failed"


def list_schemes_from_db(db_path, mode=None, source=None):
    """List schemes from DB. Returns list of scheme dicts, optionally filtered by mode/source."""
    db = _load_db(db_path)
    result = []
    for drawing_id, scheme in db.items():
        if mode and scheme.get("battle_mode", "Standard") != mode:
            continue
        if source and scheme.get("source", "local") != source:
            continue
        result.append(scheme)
    result.sort(key=lambda s: s.get("saved_at", ""), reverse=True)
    return result


def load_scheme_from_db(db_path, drawing_id):
    """Load a single scheme by drawing_id. Returns (map_id, elements) or None."""
    db = _load_db(db_path)
    scheme = db.get(drawing_id)
    if not scheme or "elements" not in scheme:
        return None
    return scheme.get("map_id", ""), scheme["elements"]


def delete_scheme_from_db(db_path, drawing_id):
    """Delete a scheme from DB by drawing_id."""
    db = _load_db(db_path)
    if drawing_id in db:
        del db[drawing_id]
        return _save_db(db_path, db)
    return False


def toggle_base_scheme(db_path, drawing_id):
    """Toggle is_base flag on a scheme. Returns new is_base value or None if not found."""
    db = _load_db(db_path)
    scheme = db.get(drawing_id)
    if not scheme:
        return None
    current = scheme.get("is_base", False)
    scheme["is_base"] = not current
    _save_db(db_path, db)
    return scheme["is_base"]


def toggle_default_scheme(db_path, drawing_id):
    """Set is_default=True for this scheme and clear it from others with same map_id+battle_mode.
    If already default, removes the default flag. Returns new is_default value or None if not found."""
    db = _load_db(db_path)
    scheme = db.get(drawing_id)
    if not scheme:
        return None
    map_id = scheme.get("map_id", "")
    mode = scheme.get("battle_mode", "")
    current = scheme.get("is_default", False)
    if current:
        scheme["is_default"] = False
        _save_db(db_path, db)
        return False
    for did, s in db.items():
        if did != drawing_id and s.get("map_id") == map_id and s.get("battle_mode") == mode:
            s["is_default"] = False
    scheme["is_default"] = True
    _save_db(db_path, db)
    return True


def get_default_scheme(db_path, map_id, battle_mode):
    """Get the default scheme for a given map_id+battle_mode. Returns scheme dict or None."""
    db = _load_db(db_path)
    for did, s in db.items():
        if (s.get("is_default") and s.get("map_id") == map_id
                and s.get("battle_mode") == battle_mode):
            return s
    return None


def get_scheme_count(db_path):
    """Return number of schemes in DB."""
    return len(_load_db(db_path))


def rename_scheme_in_db(db_path, drawing_id, new_name, new_desc):
    """Rename a scheme and update its description. Returns (ok, message)."""
    db = _load_db(db_path)
    scheme = db.get(drawing_id)
    if not scheme:
        return False, "Scheme not found"
    scheme["scheme_name"] = new_name
    scheme["description"] = new_desc
    scheme["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    ok = _save_db(db_path, db)
    return ok, f"Renamed: {new_name}" if ok else "Rename failed"


def save_scheme(map_id, map_name, mode, drawings, _t=None):
    """Legacy wrapper — saves to JSON DB."""
    db_path = config.SCHEMES_FILE
    return save_scheme_to_db(db_path, map_id, map_name, mode, drawings)


def list_schemes(mode=None):
    """Legacy wrapper — lists from JSON DB."""
    return list_schemes_from_db(config.SCHEMES_FILE, mode=mode)


def load_scheme(file_path):
    """Legacy wrapper — unused, kept for backward compat."""
    return None


def delete_scheme(file_path):
    """Legacy wrapper — unused, kept for backward compat."""
    return False


def migrate_tactik_folder():
    """One-time migration: convert Tactik_Shemi/ files into saved_schemes.json."""
    db_path = config.SCHEMES_FILE
    if os.path.isfile(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and len(data) > 0:
                return False
        except Exception:
            pass

    tactik_dir = os.path.join(config.BASE_DIR, "Tactik_Shemi")
    if not os.path.isdir(tactik_dir):
        return False

    db = {}
    migrated = 0
    for fname in os.listdir(tactik_dir):
        if not fname.endswith(".json") or fname == "all_maps.json":
            continue
        fpath = os.path.join(tactik_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            map_id = data.get("map_id", "")
            map_name = data.get("map_name", "")
            elements = data.get("drawings", data.get("elements", []))
            if not map_id or not elements:
                continue
            drawing_id = str(uuid.uuid4())[:8]
            db[drawing_id] = {
                "drawing_id": drawing_id,
                "map_id": map_id,
                "map_name": map_name,
                "battle_mode": "Standard",
                "elements": elements,
                "source": "local",
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            migrated += 1
        except Exception:
            continue

    all_maps_path = os.path.join(tactik_dir, "all_maps.json")
    if os.path.isfile(all_maps_path):
        try:
            with open(all_maps_path, "r", encoding="utf-8") as f:
                am_data = json.load(f)
            if isinstance(am_data, dict) and "drawings" in am_data:
                am_drawings = am_data["drawings"]
                if isinstance(am_drawings, dict):
                    for map_id, elements in am_drawings.items():
                        if not elements:
                            continue
                        drawing_id = str(uuid.uuid4())[:8]
                        db[drawing_id] = {
                            "drawing_id": drawing_id,
                            "map_id": map_id,
                            "map_name": map_id,
                            "battle_mode": "Standard",
                            "elements": elements,
                            "source": "local",
                            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        migrated += 1
                elif isinstance(am_drawings, list):
                    drawing_id = str(uuid.uuid4())[:8]
                    db[drawing_id] = {
                        "drawing_id": drawing_id,
                        "map_id": am_data.get("map_id", ""),
                        "map_name": am_data.get("map_name", ""),
                        "battle_mode": "Standard",
                        "elements": am_drawings,
                        "source": "local",
                        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    migrated += 1
        except Exception:
            pass

    if db:
        _save_db(db_path, db)
    print(f"[MIGRATE] Tactik_Shemi: {migrated} schemes migrated to saved_schemes.json")
    return migrated > 0


def export_all_tactics(parent, drawings, map_names=None, _t=None):
    _t = _t or (lambda k, d: d)
    if not drawings:
        dialog_utils.dark_messagebox(parent, _t('export_no_drawings', 'Export'), _t('export_no_drawings', 'No drawings'))
        return

    from datetime import datetime
    import config

    file_path = filedialog.asksaveasfilename(
        parent=parent,
        title=_t('export_all_success', 'Export all tactics'),
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        initialfile="all_maps.json"
    )
    if not file_path:
        return

    count = sum(len(v) for v in drawings.values())
    export_data = {
        "type": "all_maps",
        "app": "SM WoT Assistant",
        "version": config.load_version(),
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_maps": len(drawings),
        "total_drawings": count,
        "drawings": dict(drawings),
        "map_names": {k: config.MAP_NAMES_EN.get(k, k) for k in drawings} if map_names is None else map_names,
    }
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        dialog_utils.dark_messagebox(parent, _t('export_all_success', 'Export'),
            _t('export_all_success', 'Exported {maps} maps ({count} items)').format(maps=len(drawings), count=count))
    except Exception as e:
        dialog_utils.dark_messagebox(parent, _t('export_save_error', 'Error'), _t('export_save_error', 'Save failed: {error}').format(error=e), is_error=True)


def import_all_tactics(parent, drawings, on_success, _t=None):
    _t = _t or (lambda k, d: d)
    file_path = filedialog.askopenfilename(
        parent=parent,
        title=_t('import_all_success', 'Import all tactics'),
        filetypes=[("JSON files", "*.json")]
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            dialog_utils.dark_messagebox(parent, _t('import_all_error_format', 'Error'), _t('import_all_error_format', 'Invalid all-maps format'), is_error=True)
            return

        if "drawings" not in data:
            src = data
        else:
            src = data["drawings"]
        src_maps = len(src)
        src_items = sum(len(v) for v in src.values())
        dst_maps = len(drawings)
        dst_items = sum(len(v) for v in drawings.values())

        info = _t('import_all_info', "File: {src_m} maps ({src_o} items)\nCurrent: {dst_m} maps ({dst_o} items)").format(src_m=src_maps, src_o=src_items, dst_m=dst_maps, dst_o=dst_items)

        choice = _choice_dialog(parent, _t('import_all_choice_msg', 'Import'),
            info + "\n\n" + _t('import_all_choice_msg', 'Replace all or merge?'), _t=_t)
        if choice is None:
            return

        if choice:
            drawings.clear()
            drawings.update(src)
        else:
            for map_id, items in src.items():
                if map_id not in drawings:
                    drawings[map_id] = []
                drawings[map_id].extend(items)

        on_success()
        new_total = sum(len(v) for v in drawings.values())
        dialog_utils.dark_messagebox(parent, _t('import_all_success', 'Import'),
            _t('import_all_success', 'Imported {src_m} maps.\nTotal: {total} items.').format(src_m=src_maps, total=new_total))

    except Exception as e:
        dialog_utils.dark_messagebox(parent, _t('import_read_error', 'Error'), _t('import_read_error', 'Read failed: {error}').format(error=e), is_error=True)


def import_unified(parent, current_map_id, current_map_name, drawings, on_success, _t=None):
    """Auto-detect single-map or all-maps format and import."""
    _t = _t or (lambda k, d: d)
    file_path = filedialog.askopenfilename(
        parent=parent,
        title=_t('unified_error_format', 'Import tactic'),
        filetypes=[("JSON files", "*.json")]
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            dialog_utils.dark_messagebox(parent, _t('unified_error_format', 'Error'), _t('unified_error_format', 'Invalid file format'), is_error=True)
            return

        # Detect all_maps type: has "type":"all_maps" OR "drawings" is a dict
        is_all_maps = data.get("type") == "all_maps" or \
                      ("drawings" in data and isinstance(data["drawings"], dict))

        if is_all_maps:
            src = data.get("drawings", data)
            if not isinstance(src, dict):
                src = {}
            src_maps = len(src)
            src_items = sum(len(v) for v in src.values() if isinstance(v, list))
            dst_maps = len(drawings)
            dst_items = sum(len(v) for v in drawings.values() if isinstance(v, list))

            info = _t('import_all_info', "File: {src_m} maps ({src_o} items)\nCurrent: {dst_m} maps ({dst_o} items)").format(src_m=src_maps, src_o=src_items, dst_m=dst_maps, dst_o=dst_items)
            choice = _choice_dialog(parent, _t('import_all_choice_msg', 'Import'),
                info + "\n\n" + _t('import_all_choice_msg', 'Replace all or merge?'), _t=_t)
            if choice is None:
                return

            if choice:
                drawings.clear()
                drawings.update(src)
            else:
                for map_id, items in src.items():
                    if map_id not in drawings:
                        drawings[map_id] = []
                    if isinstance(items, list):
                        drawings[map_id].extend(items)

            on_success()
            new_total = sum(len(v) for v in drawings.values() if isinstance(v, list))
            dialog_utils.dark_messagebox(parent, _t('import_all_success', 'Import'),
                _t('import_all_success', 'Imported {src_m} maps.\nTotal: {total} items.').format(src_m=src_maps, total=new_total))
        else:
            # Single-map import
            if "drawings" not in data or not isinstance(data["drawings"], list):
                dialog_utils.dark_messagebox(parent, _t('unified_single_format_error', 'Error'),
                    _t('unified_single_format_error', 'Invalid format:\nexpected array of drawings'),
                    is_error=True)
                return

            import_map_id = data.get("map_id")
            if import_map_id and import_map_id != current_map_id:
                msg = _t('import_warning_msg', "Created for '{src}'.\nImport to '{dst}'?").format(src=data.get('map_name', import_map_id), dst=current_map_name)
                if not dialog_utils.dark_confirmbox(parent, _t('import_warning_title', 'Map mismatch'), msg, yes_text=_t('btn_yes', 'Yes'), no_text=_t('btn_no', 'No')):
                    return

            choice = _choice_dialog(parent, _t('import_choice_msg', 'Import'),
                _t('import_choice_msg', 'Replace or merge?'), _t=_t)
            if choice is None:
                return

            if current_map_id not in drawings:
                drawings[current_map_id] = []

            if choice:
                drawings[current_map_id] = data["drawings"]
            else:
                drawings[current_map_id].extend(data["drawings"])

            on_success()
            dialog_utils.dark_messagebox(parent, _t('import_success', 'Import'), _t('import_success', 'Imported!'))

    except Exception as e:
        dialog_utils.dark_messagebox(parent, _t('import_read_error', 'Error'), _t('import_read_error', 'Read failed: {error}').format(error=e), is_error=True)
