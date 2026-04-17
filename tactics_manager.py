import json
from tkinter import filedialog, messagebox

def export_tactic(parent, map_id, map_name, drawings):
    if not map_id or map_id not in drawings or not drawings[map_id]:
        messagebox.showinfo("Експорт", "На цій карті немає малюнків для експорту.", parent=parent)
        return
    
    file_path = filedialog.asksaveasfilename(
        parent=parent,
        title=f"Експорт тактики: {map_name}",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        initialfile=f"tactic_{map_id}.json"
    )
    
    if file_path:
        data = {
            "map_id": map_id,
            "map_name": map_name,
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
            
            # Валідація
            if not isinstance(data, dict) or "drawings" not in data:
                messagebox.showerror("Помилка", "Некоректний формат файлу тактики.", parent=parent)
                return
            
            import_map_id = data.get("map_id")
            if import_map_id and import_map_id != current_map_id:
                confirm = messagebox.askyesno(
                    "Попередження", 
                    f"Ця тактика була створена для мапи '{data.get('map_name', import_map_id)}'.\n"
                    f"Ви впевнені, що хочете імпортувати її на поточну мапу '{current_map_name}'?",
                    parent=parent
                )
                if not confirm: return

            # Питаємо як імпортувати
            choice = messagebox.askyesnocancel(
                "Імпорт", 
                "Бажаєте ЗАМІНИТИ існуючі малюнки (Так) чи ДОДАТИ нові до поточних (Ні)?",
                parent=parent
            )
            
            if choice is None: return # Скасовано
            
            if current_map_id not in drawings: drawings[current_map_id] = []
            
            if choice: # Так = Замінити
                drawings[current_map_id] = data["drawings"]
            else: # Ні = Додати
                drawings[current_map_id].extend(data["drawings"])
            
            on_success()
            messagebox.showinfo("Імпорт", "Тактику успішно імпортовано!", parent=parent)
            
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося прочитати файл: {e}", parent=parent)
