import re

with open('stats_ai.py', 'r', encoding='utf-8') as f:
    src = f.read()

# 1. Update get_loadout_icon signature and image opening logic
src = src.replace('def get_loadout_icon(self, category, name, size=(40, 40)):', 'def get_loadout_icon(self, category, name, size=(40, 40), disabled=False):')
src = src.replace('cache_key = f"{category}_{name}_{size[0]}"', 'cache_key = f"{category}_{name}_{size[0]}_{disabled}"')

target_enhance = 'img = Image.open(icon_path).convert("RGBA")'
repl_enhance = """img = Image.open(icon_path).convert("RGBA")
            if disabled:
                from PIL import ImageEnhance
                img = ImageEnhance.Brightness(img).enhance(0.3)"""
src = src.replace(target_enhance, repl_enhance)

# 2. Update on_build_ready to pass new args
target_on_build = """        def on_build_ready(build_data, is_cached):
            if not self.ai_equipment_frame.winfo_exists(): return
            self.ai_equipment_frame.after(0, lambda: self._update_ai_setup_ui(
                build_data, equip_body, cons_body, ammo_body, crew_body, fm_body,
                equip_body_2, cons_body_2, ammo_body_2, loading_labels
            ))"""

repl_on_build = """        def on_build_ready(build_data, is_cached):
            if not self.ai_equipment_frame.winfo_exists(): return
            self.ai_equipment_frame.after(0, lambda: self._update_ai_setup_ui(
                build_data, equip_body, cons_body, ammo_body, crew_body, fm_body,
                equip_body_2, cons_body_2, ammo_body_2, loading_labels, data, crew_rows, fm_pairs
            ))"""
src = src.replace(target_on_build, repl_on_build)

# 3. Update _update_ai_setup_ui definition and content
target_def = '    def _update_ai_setup_ui(self, build_data, equip_body, cons_body, ammo_body, crew_body, fm_body, equip_body_2, cons_body_2, ammo_body_2, loading_labels):'
repl_def = '    def _update_ai_setup_ui(self, build_data, equip_body, cons_body, ammo_body, crew_body, fm_body, equip_body_2, cons_body_2, ammo_body_2, loading_labels, data, crew_rows, fm_pairs):'
src = src.replace(target_def, repl_def)

# We will replace everything from "# Force correct ration based on nation" to "self._layout_tile_row(fm_body, fm_slots, gap=0)"
# Since we don't have that comment yet, we replace from "render_items(equip_body, build_data.get(\"equipment_1\", []), \"artefacts\")"

new_ui_logic = """        # Force correct ration based on nation
        ration_map = {
            "ussr": "ration", "usa": "cocacola", "germany": "chocolate", "uk": "ration_uk",
            "france": "hotCoffee", "china": "ration_china", "poland": "ration_poland",
            "czech": "Buchty", "japan": "ration_japan", "italy": "ration_italy", "sweden": "ration_sweden"
        }
        nation = data.get("nation", "")
        correct_ration = ration_map.get(nation)
        if correct_ration:
            cons = build_data.get("consumables", [])
            for i, c in enumerate(cons):
                if c in ration_map.values():
                    cons[i] = correct_ration
            build_data["consumables"] = cons
            
        render_items(equip_body, build_data.get("equipment_1", []), "artefacts")
        render_items(equip_body_2, build_data.get("equipment_2", []), "artefacts")
        render_items(cons_body, build_data.get("consumables", []), "artefacts")
        render_items(cons_body_2, build_data.get("consumables", []), "artefacts")
        render_ammo_items(ammo_body, build_data.get("ammo", []), "ammo")
        render_ammo_items(ammo_body_2, build_data.get("ammo", []), "ammo")

        # Crew section
        crew_slots = []
        ai_crew = {}
        for role, skills in build_data.get("crew", []):
            ai_crew[role.lower()] = skills
            
        for member, _ in crew_rows:
            slot = tk.Frame(crew_body, bg="#111111", bd=0, relief="flat")
            row = tk.Frame(slot, bg="#111111")
            row.pack(side="top", pady=(0, 3))
            
            role_str = member.get("role", "commander")
            primary_r_icon = role_str.lower()
            if "loader" in primary_r_icon: primary_r_icon = "loader"
            if "radio" in primary_r_icon or "radioman" in primary_r_icon: primary_r_icon = "radioman"
            if "gunner" in primary_r_icon: primary_r_icon = "gunner"
            if "driver" in primary_r_icon: primary_r_icon = "driver"
            if "commander" in primary_r_icon: primary_r_icon = "commander"
            
            # Primary role
            role_box = tk.Frame(row, bg="#111111", bd=0, relief="flat", width=40, height=40)
            role_box.pack(side="left", padx=(0, 3))
            role_box.pack_propagate(False)
            role_photo = self.get_loadout_icon("crew_roles", primary_r_icon + "_plus", (24, 24))
            role_lbl = tk.Label(role_box, bg="#111111")
            if role_photo:
                role_lbl.config(image=role_photo)
                role_lbl.image = role_photo
            role_lbl.pack(expand=True)
            
            # Secondary roles
            also_roles = member.get("also") or []
            for sec_role in also_roles:
                sec_icon = sec_role.lower()
                if "loader" in sec_icon: sec_icon = "loader"
                if "radio" in sec_icon or "radioman" in sec_icon: sec_icon = "radioman"
                if "gunner" in sec_icon: sec_icon = "gunner"
                if "driver" in sec_icon: sec_icon = "driver"
                if "commander" in sec_icon: sec_icon = "commander"
                
                sec_box = tk.Frame(row, bg="#111111", bd=0, relief="flat", width=40, height=40)
                sec_box.pack(side="left", padx=(0, 3))
                sec_box.pack_propagate(False)
                sec_photo = self.get_loadout_icon("crew_roles", sec_icon + "_plus", (24, 24))
                sec_lbl = tk.Label(sec_box, bg="#111111")
                if sec_photo:
                    sec_lbl.config(image=sec_photo)
                    sec_lbl.image = sec_photo
                sec_lbl.pack(expand=True)
                
            # Skills for this member (combining primary and secondary roles)
            skills = []
            for r in [primary_r_icon] + [sr.lower() for sr in also_roles]:
                if "radio" in r or "radioman" in r: r = "radioman"
                elif "loader" in r: r = "loader"
                elif "gunner" in r: r = "gunner"
                elif "driver" in r: r = "driver"
                elif "commander" in r: r = "commander"
                skills.extend(ai_crew.get(r, []))
            
            # Deduplicate skills keeping order
            seen_sk = set()
            clean_skills = []
            for sk in skills:
                if sk not in seen_sk:
                    seen_sk.add(sk)
                    clean_skills.append(sk)
                    
            for sk in clean_skills:
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

        # Field mods section
        fm_slots = []
        ai_fm_icons = [self._map_ai_fm_text_to_icon(text) for text in build_data.get("field_mods", [])]
        
        for pair in fm_pairs:
            # pair is [mod1_id, mod2_id]
            if len(pair) != 2: continue
            
            slot = tk.Frame(fm_body, bg="#111111", bd=0, relief="flat")
            
            for mod_id in pair:
                is_selected = mod_id in ai_fm_icons
                
                icon_box = tk.Frame(slot, bg="#1a242a" if is_selected else "#0d1215", bd=1, relief="flat", width=64, height=64)
                icon_box.pack(side="left", padx=2)
                icon_box.pack_propagate(False)
                
                photo = self.get_loadout_icon('field_mods', mod_id, (64, 64), disabled=not is_selected)
                lbl = tk.Label(icon_box, bg="#1a242a" if is_selected else "#0d1215", padx=0, pady=0)
                if photo:
                    lbl.config(image=photo)
                    lbl.image = photo
                else:
                    lbl.config(width=3, height=2, bg="#1e2d35" if is_selected else "#0f161a")
                lbl.pack(expand=True)
                
            fm_slots.append(slot)

        self._layout_tile_row(fm_body, fm_slots, gap=0)"""

start_str = '        render_items(equip_body, build_data.get("equipment_1", []), "artefacts")'
end_str = '        self._layout_tile_row(fm_body, fm_slots, gap=0)'

parts = src.split(start_str)
if len(parts) >= 2:
    before = parts[0]
    subparts = parts[1].split(end_str)
    after = subparts[1]
    with open('stats_ai.py', 'w', encoding='utf-8') as f:
        f.write(before + new_ui_logic + after)
    print("Patched UI logic")
else:
    print("Could not find UI block")
