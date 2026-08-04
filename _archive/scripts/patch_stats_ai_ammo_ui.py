import re

with open('stats_ai.py', 'r', encoding='utf-8') as f:
    src = f.read()

new_render_items = """        def render_items(parent, items, category, size=(48, 48)):
            slots = []
            for name in items:
                photo = self.get_loadout_icon(category, name, size)
                slot = tk.Frame(parent, bg="#111111", bd=0, relief="flat")
                icon_box = tk.Frame(slot, bg="#1d2a1a" if category == "artefacts" else "#1a1d2a", bd=1, relief="flat", width=size[0]+6, height=size[1]+6)
                icon_box.pack(side="top")
                icon_box.pack_propagate(False)
                lbl = tk.Label(icon_box, bg="#1d2a1a" if category == "artefacts" else "#1a1d2a", padx=0, pady=0)
                if photo:
                    lbl.config(image=photo)
                    lbl.image = photo
                else:
                    lbl.config(width=4, height=2, bg="#2a3a28" if category == "artefacts" else "#272a3a")
                lbl.pack(expand=True, fill="both")
                slots.append(slot)
            self._layout_tile_row(parent, slots, gap=0)
            return slots
            
        def render_ammo_items(parent, items, category="ammo", size=(48, 48)):
            slots = []
            for item in items:
                if isinstance(item, tuple) and len(item) == 2:
                    name, count = item
                else:
                    name, count = item, 0
                    
                photo = self.get_loadout_icon(category, name, size)
                slot = tk.Frame(parent, bg="#111111", bd=0, relief="flat")
                icon_box = tk.Frame(slot, bg="#1a1d2a", bd=1, relief="flat", width=size[0]+6, height=size[1]+6)
                icon_box.pack(side="top")
                icon_box.pack_propagate(False)
                
                # Image Label
                lbl = tk.Label(icon_box, bg="#1a1d2a", padx=0, pady=0)
                if photo:
                    lbl.config(image=photo)
                    lbl.image = photo
                else:
                    lbl.config(width=4, height=2, bg="#272a3a")
                lbl.pack(expand=True, fill="both")
                
                # Text Label with black background for contrast
                if count > 0:
                    t_lbl = tk.Label(icon_box, text=str(count), fg="#ffffff", bg="#0a0b12", font=("Arial", 8, "bold"), padx=2, pady=0)
                    t_lbl.place(relx=1.0, rely=1.0, anchor="se")
                    
                slots.append(slot)
            self._layout_tile_row(parent, slots, gap=0)
            return slots"""

# Replace `def render_items` to `render_items(ammo_body`
start_str = "        def render_items(parent, items, category, size=(48, 48)):"
end_str = "        render_items(equip_body, build_data.get(\"equipment_1\", []), \"artefacts\")"

parts = src.split(start_str)
if len(parts) >= 2:
    before = parts[0]
    subparts = parts[1].split(end_str)
    after = end_str + subparts[1]
    
    with open('stats_ai.py', 'w', encoding='utf-8') as f:
        f.write(before + new_render_items + "\n        " + after)
    print("Patched render functions.")
else:
    print("Could not find render_items block.")

# Replace `render_items(ammo_body...` with `render_ammo_items(ammo_body...`
with open('stats_ai.py', 'r', encoding='utf-8') as f:
    src = f.read()
    
src = src.replace('render_items(ammo_body, build_data.get("ammo", []), "ammo")', 'render_ammo_items(ammo_body, build_data.get("ammo", []), "ammo")')

with open('stats_ai.py', 'w', encoding='utf-8') as f:
    f.write(src)
    print("Patched ammo calls.")
