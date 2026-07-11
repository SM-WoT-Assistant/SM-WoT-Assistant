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
