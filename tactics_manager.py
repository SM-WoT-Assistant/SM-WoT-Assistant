import json
import tkinter as tk
from tkinter import filedialog, messagebox

def _choice_dialog(parent, title, text):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg="#222")
    dlg.resizable(False, False)
    dlg.attributes("-topmost", True)
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
    tk.Button(bf, text="ЗАМІНИТИ", bg="#553333", fg="#ff6666", bd=0,
              font=("Arial", 9, "bold"), padx=12, pady=4, command=on_replace).pack(side="left", padx=4)
    tk.Button(bf, text="ОБ'ЄДНАТИ", bg="#335533", fg="#66cc66", bd=0,
              font=("Arial", 9, "bold"), padx=12, pady=4, command=on_merge).pack(side="left", padx=4)
    tk.Button(bf, text="СКАСУВАТИ", bg="#444", fg="#aaa", bd=0,
              font=("Arial", 9), padx=12, pady=4, command=on_cancel).pack(side="left", padx=4)
    parent.wait_window(dlg)
    return result

def export_tactic(parent, map_id, map_name, drawings):
    if not map_id or map_id not in drawings or not drawings[map_id]:
        messagebox.showinfo("Експорт", "На цій карті немає малюнків для експорту.", parent=parent)
        return
    
    file_path = filedialog.asksaveasfilename(
        parent=parent,
        title=f"Експорт тактики: {map_name}",
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
            messagebox.showinfo("Експорт", "Тактику успішно експортовано!", parent=parent)
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося зберегти файл: {e}", parent=parent)

def import_tactic(parent, current_map_id, current_map_name, drawings, on_success):
    file_path = filedialog.askopenfilename(
        parent=parent,
        title="Імпорт тактики",
        filetypes=[("JSON files", "*.json")]
    )
    
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not isinstance(data, dict) or "drawings" not in data:
                messagebox.showerror("Помилка", "Некоректний формат файлу тактики.", parent=parent)
                return

            if not isinstance(data["drawings"], list):
                messagebox.showerror("Помилка",
                    "Це файл усіх тактик (містить кілька мап).\nВикористайте ALL IMPORT.",
                    parent=parent)
                return

            import_map_id = data.get("map_id")
            if import_map_id and import_map_id != current_map_id:
                dlg = tk.Toplevel(parent)
                dlg.title("Попередження")
                dlg.configure(bg="#222")
                dlg.resizable(False, False)
                dlg.attributes("-topmost", True)
                dlg.grab_set()
                confirm = [False]
                msg = (f"Ця тактика була створена для мапи '{data.get('map_name', import_map_id)}'.\n"
                       f"Імпортувати на поточну мапу '{current_map_name}'?")
                tk.Label(dlg, text=msg, bg="#222", fg="#ccc",
                         font=("Arial", 9), wraplength=380).pack(padx=20, pady=(15, 10))
                bf = tk.Frame(dlg, bg="#222")
                bf.pack(pady=(0, 12))
                tk.Button(bf, text="ТАК", bg="#553333", fg="#ff6666", bd=0,
                          font=("Arial", 9, "bold"), padx=12, pady=4,
                          command=lambda: [confirm.__setitem__(0, True), dlg.destroy()]).pack(side="left", padx=4)
                tk.Button(bf, text="НІ", bg="#444", fg="#aaa", bd=0,
                          font=("Arial", 9), padx=12, pady=4,
                          command=dlg.destroy).pack(side="left", padx=4)
                parent.wait_window(dlg)
                if not confirm[0]:
                    return

            choice = _choice_dialog(parent, "Імпорт",
                "Бажаєте ЗАМІНИТИ існуючі малюнки чи ОБ'ЄДНАТИ з поточними?")

            if choice is None:
                return

            if current_map_id not in drawings:
                drawings[current_map_id] = []

            if choice:
                drawings[current_map_id] = data["drawings"]
            else:
                drawings[current_map_id].extend(data["drawings"])
            
            on_success()
            messagebox.showinfo("Імпорт", "Тактику успішно імпортовано!", parent=parent)
            
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося прочитати файл: {e}", parent=parent)


def export_all_tactics(parent, drawings, map_names=None):
    if not drawings:
        messagebox.showinfo("Експорт", "Немає малюнків для експорту.", parent=parent)
        return

    from datetime import datetime
    import config

    file_path = filedialog.asksaveasfilename(
        parent=parent,
        title="Експорт усіх тактик",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        initialfile="all_tactics.json"
    )
    if not file_path:
        return

    count = sum(len(v) for v in drawings.values())
    export_data = {
        "app": "SM WoT Assistant",
        "version": config.load_version(),
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_maps": len(drawings),
        "total_drawings": count,
        "drawings": dict(drawings),
        "map_names": map_names or {},
    }
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Експорт",
            f"Експортовано {len(drawings)} мап ({count} об'єктів).", parent=parent)
    except Exception as e:
        messagebox.showerror("Помилка", f"Не вдалося зберегти файл: {e}", parent=parent)


def import_all_tactics(parent, drawings, on_success):
    file_path = filedialog.askopenfilename(
        parent=parent,
        title="Імпорт усіх тактик",
        filetypes=[("JSON files", "*.json")]
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            messagebox.showerror("Помилка", "Некоректний формат файлу тактик.", parent=parent)
            return

        if "drawings" not in data:
            src = data
        else:
            src = data["drawings"]
        src_maps = len(src)
        src_items = sum(len(v) for v in src.values())
        dst_maps = len(drawings)
        dst_items = sum(len(v) for v in drawings.values())

        info = (
            f"Файл містить {src_maps} мап ({src_items} об'єктів).\n"
            f"Поточний проект має {dst_maps} мап ({dst_items} об'єктів).\n\n"
        )

        choice = _choice_dialog(parent, "Імпорт",
            info + "Бажаєте ЗАМІНИТИ всі малюнки чи ОБ'ЄДНАТИ з поточними?")
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
        messagebox.showinfo("Імпорт",
            f"Імпортовано {src_maps} мап. Всього: {len(drawings)} мап ({new_total} об'єктів).",
            parent=parent)

    except Exception as e:
        messagebox.showerror("Помилка", f"Не вдалося прочитати файл: {e}", parent=parent)
