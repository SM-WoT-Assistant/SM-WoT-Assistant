import re

with open('ai_engine.py', 'r', encoding='utf-8') as f:
    src = f.read()

# Define the new robust _normalize_build method
new_normalize = """    def _normalize_build(self, raw_json):
        # Normalize equipment
        equip1 = []
        equip2 = []
        
        # Check title casing for root keys
        eq_root = raw_json.get("equipment") or raw_json.get("Equipment") or raw_json.get("loadouts") or raw_json.get("Loadouts") or {}
        
        if isinstance(eq_root, dict):
            equip1 = eq_root.get("loadout_1") or eq_root.get("Loadout_1") or []
            equip2 = eq_root.get("loadout_2") or eq_root.get("Loadout_2") or []
        elif isinstance(eq_root, list) and len(eq_root) > 0:
            equip1 = eq_root
            
        eq1_mapped = [AI_EQUIP_MAP.get(e, "notFound") for e in equip1 if isinstance(e, str)]
        eq2_mapped = [AI_EQUIP_MAP.get(e, "notFound") for e in equip2 if isinstance(e, str)]
        
        # Normalize consumables
        cons_raw = raw_json.get("consumables") or raw_json.get("Consumables") or []
        cons_mapped = [AI_CONS_MAP.get(c, "notFound") for c in cons_raw if isinstance(c, str)]
        
        # Normalize ammo
        ammo_mapped = []
        ammo_raw = raw_json.get("ammo") or raw_json.get("Ammo") or {}
        if isinstance(ammo_raw, dict):
            for k, v in ammo_raw.items():
                if str(k).lower() == "distribution" and isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            t = str(item.get("type", "")).upper()
                            if "APCR" in t: ammo_mapped.append(AI_AMMO_MAP["APCR"])
                            elif "HEAT" in t: ammo_mapped.append(AI_AMMO_MAP["HEAT"])
                            elif "HESH" in t: ammo_mapped.append(AI_AMMO_MAP["HE"])
                            elif "AP" in t: ammo_mapped.append(AI_AMMO_MAP["AP"])
                            elif "HE" in t: ammo_mapped.append(AI_AMMO_MAP["HE"])
                elif str(k).lower() == "total":
                    continue
                else:
                    k_up = str(k).upper()
                    if isinstance(v, (int, float, str)) and str(v).strip() != "0":
                        if "APCR" in k_up: ammo_mapped.append(AI_AMMO_MAP["APCR"])
                        elif "HEAT" in k_up: ammo_mapped.append(AI_AMMO_MAP["HEAT"])
                        elif "HESH" in k_up: ammo_mapped.append(AI_AMMO_MAP["HE"])
                        elif "AP" in k_up: ammo_mapped.append(AI_AMMO_MAP["AP"])
                        elif "HE" in k_up: ammo_mapped.append(AI_AMMO_MAP["HE"])
        
        # Deduplicate ammo order safely
        seen_ammo = set()
        clean_ammo = []
        for am in ammo_mapped:
            if am not in seen_ammo:
                seen_ammo.add(am)
                clean_ammo.append(am)
                        
        # Normalize crew
        crew_mapped = []
        crew_raw = raw_json.get("crew_perks") or raw_json.get("Crew") or raw_json.get("crew") or {}
        
        if isinstance(crew_raw, dict):
            # Check if it's flat
            k_lower = [k.lower() for k in crew_raw.keys()]
            if "major" in k_lower or "situational" in k_lower:
                mj = crew_raw.get("major") or crew_raw.get("Major") or []
                sit = crew_raw.get("situational") or crew_raw.get("Situational") or []
                all_s = mj + sit
                mapped = [AI_CREW_MAP.get(s, "notFound") for s in all_s if isinstance(s, str)]
                crew_mapped.append(("commander", mapped))
            else:
                for role, skills in crew_raw.items():
                    if isinstance(skills, dict):
                        mj = skills.get("major") or skills.get("Major") or []
                        sit = skills.get("situational") or skills.get("Situational") or []
                        all_s = mj + sit
                    elif isinstance(skills, list):
                        all_s = skills
                    else:
                        all_s = []
                    mapped = [AI_CREW_MAP.get(s, "notFound") for s in all_s if isinstance(s, str)]
                    crew_mapped.append((role, mapped))
                
        # Normalize Field Mods
        fm_raw = raw_json.get("field_modifications") or raw_json.get("Field_Modification") or raw_json.get("field_mod") or {}
        fm_mapped = []
        if isinstance(fm_raw, dict):
            for k, v in fm_raw.items():
                if isinstance(v, str) and "no modification" not in v.lower() and v.strip() != "":
                    fm_mapped.append(v)
        elif isinstance(fm_raw, list):
            for v in fm_raw:
                if isinstance(v, str) and "no modification" not in v.lower() and v.strip() != "":
                    # Usually "Level 2: Name" format from earlier prompt
                    parts = v.split(":")
                    if len(parts) > 1:
                        fm_mapped.append(parts[1].strip())
                    else:
                        fm_mapped.append(v)
                
        return {
            "equipment_1": eq1_mapped[:3],
            "equipment_2": eq2_mapped[:3],
            "consumables": cons_mapped[:3],
            "ammo": clean_ammo[:4],
            "crew": crew_mapped,
            "field_mods": fm_mapped
        }"""

# Replace the block
start_sig = "def _normalize_build(self, raw_json):"
end_sig = "def fetch_build_async(self, tag, tank_name, callback):"

parts = src.split(start_sig)
if len(parts) >= 2:
    before = parts[0]
    rest = parts[1]
    subparts = rest.split(end_sig)
    after = end_sig + subparts[1]
    
    with open('ai_engine.py', 'w', encoding='utf-8') as f:
        f.write(before + new_normalize + "\n\n    " + after)
    print("Patched ai_engine.py successfully.")
else:
    print("Could not find signatures.")
