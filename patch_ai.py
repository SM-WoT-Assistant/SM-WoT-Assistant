import re

with open('stats_ai.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if '# Equipment items' in line and start_idx == -1:
        start_idx = i
    if 'crew_body.bind("<Configure>"' in line:
        end_idx = i

if start_idx != -1 and end_idx != -1:
    new_logic = """
        # Row 2 frames
        equip_body_2 = tk.Frame(self.ai_equipment_frame_2, bg="#111111")
        equip_body_2.pack(side="top", fill="x", pady=3)
        cons_body_2 = tk.Frame(self.ai_consumables_frame_2, bg="#111111")
        cons_body_2.pack(side="top", fill="x", pady=3)
        ammo_body_2 = tk.Frame(self.ai_ammo_frame_2, bg="#111111")
        ammo_body_2.pack(side="top", fill="x", pady=3)
        
        # Show loading placeholders
        loading_labels = []
        for body in [equip_body, cons_body, ammo_body, crew_body, fm_body]:
            lbl = tk.Label(body, text="ШІ Аналізує Сетап...", fg="#888888", bg="#111111", font=("Arial", 10))
            lbl.pack(pady=20, expand=True)
            loading_labels.append(lbl)
            
        tank_name = data.get("name", tag)
        def on_build_ready(build_data, is_cached):
            if not self.ai_equipment_frame.winfo_exists(): return
            self.ai_equipment_frame.after(0, lambda: self._update_ai_setup_ui(
                build_data, equip_body, cons_body, ammo_body, crew_body, fm_body,
                equip_body_2, cons_body_2, ammo_body_2, loading_labels
            ))
            
        ai_engine_instance.fetch_build_async(tag, tank_name, on_build_ready)
"""
    
    new_methods = """
    def _map_ai_fm_text_to_icon(self, text):
        mapping = {
            "All-Terrain Suspension": "additionalGrousers",
            "Lightweight Suspension": "betterFriction",
            "Parallax Adjustment": "improvedAimingHandling",
            "Refined Powder": "improvedScope",
            "Right-Angle Optics": "improvedObservationDevice",
            "Anti-Reflective Lenses": "improvedSpallingResistance",
            "Power Supply Tuning": "improvedTurretTurningWheels", 
            "Electrical System Shielding": "improvedLightFilters"
        }
        return mapping.get(text, "glow")

    def _update_ai_setup_ui(self, build_data, equip_body, cons_body, ammo_body, crew_body, fm_body, equip_body_2, cons_body_2, ammo_body_2, loading_labels):
        for lbl in loading_labels:
            if lbl.winfo_exists(): lbl.destroy()
            
        for body in [equip_body, cons_body, ammo_body, crew_body, fm_body, equip_body_2, cons_body_2, ammo_body_2]:
            for w in body.winfo_children(): w.destroy()
            
        def render_items(parent, items, category, size=(48, 48)):
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
                lbl.pack(expand=True)
                slots.append(slot)
            self._layout_tile_row(parent, slots, gap=0)
            return slots
            
        render_items(equip_body, build_data.get("equipment_1", []), "artefacts")
        render_items(equip_body_2, build_data.get("equipment_2", []), "artefacts")
        render_items(cons_body, build_data.get("consumables", []), "artefacts")
        # Don't show consumables on second row, they are usually the same
        render_items(ammo_body, build_data.get("ammo", []), "ammo")
        
        # Crew section
        crew_slots = []
        for role, skills in build_data.get("crew", []):
            slot = tk.Frame(crew_body, bg="#111111", bd=0, relief="flat")
            row = tk.Frame(slot, bg="#111111")
            row.pack(side="top", pady=(0, 3))
            
            r_icon = role.lower()
            if "loader" in r_icon: r_icon = "loader"
            if "radioman" in r_icon: r_icon = "radioman"
            if "gunner" in r_icon: r_icon = "gunner"
            if "driver" in r_icon: r_icon = "driver"
            if "commander" in r_icon: r_icon = "commander"
            
            role_box = tk.Frame(row, bg="#111111", bd=0, relief="flat", width=40, height=40)
            role_box.pack(side="left", padx=(0, 3))
            role_box.pack_propagate(False)
            role_photo = self.get_loadout_icon("crew_roles", r_icon, (24, 24))
            role_lbl = tk.Label(role_box, bg="#111111")
            if role_photo:
                role_lbl.config(image=role_photo)
                role_lbl.image = role_photo
            role_lbl.pack(expand=True)
            
            for sk in skills:
                sk_box = tk.Frame(row, bg="#2a1a1a", bd=1, relief="flat", width=40, height=40)
                sk_box.pack(side="left", padx=(0, 3))
                sk_box.pack_propagate(False)
                sk_photo = self.get_loadout_icon("artefacts", sk, (24, 24))
                sk_lbl = tk.Label(sk_box, bg="#2a1a1a")
                if sk_photo:
                    sk_lbl.config(image=sk_photo)
                    sk_lbl.image = sk_photo
                sk_lbl.pack(expand=True)
            crew_slots.append(slot)
            
        self._layout_tile_grid(crew_body, crew_slots, min_cell=9999, gap=0, stretch=False)
        crew_body.bind("<Configure>", lambda e, c=crew_body, s=crew_slots: self._layout_tile_grid(c, s, min_cell=9999, gap=0, stretch=False))
        
        # Field mods section
        fm_slots = []
        for fm_text in build_data.get("field_mods", []):
            slot = tk.Frame(fm_body, bg="#111111", bd=0, relief="flat")
            icon_box = tk.Frame(slot, bg="#1a242a", bd=1, relief="flat", width=64, height=64)
            icon_box.pack(side="left", padx=0)
            icon_box.pack_propagate(False)
            fm_icon = self._map_ai_fm_text_to_icon(fm_text)
            photo = self.get_loadout_icon('field_mods', fm_icon, (64, 64))
            lbl = tk.Label(icon_box, bg="#1a242a", padx=0, pady=0)
            if photo:
                lbl.config(image=photo)
                lbl.image = photo
            else:
                lbl.config(width=3, height=2, bg="#1e2d35")
            lbl.pack(expand=True)
            fm_slots.append(slot)
            
        self._layout_tile_row(fm_body, fm_slots, gap=0)
"""

    lines = lines[:start_idx] + [new_logic] + [new_methods] + lines[end_idx+1:]
    with open('stats_ai.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"Patched stats_ai.py successfully (lines {start_idx}-{end_idx})")
else:
    print(f"Failed to find indices: start={start_idx}, end={end_idx}")
