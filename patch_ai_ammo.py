import re

with open('ai_engine.py', 'r', encoding='utf-8') as f:
    src = f.read()

new_ammo_logic = """        # Normalize ammo
        ammo_mapped = []
        ammo_raw = raw_json.get("ammo") or raw_json.get("Ammo") or {}
        if isinstance(ammo_raw, dict):
            for k, v in ammo_raw.items():
                if str(k).lower() == "distribution" and isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            t = str(item.get("type", "")).upper()
                            count = 0
                            try: count = int(item.get("count", 0))
                            except: pass
                            
                            icon = None
                            if "APCR" in t: icon = AI_AMMO_MAP["APCR"]
                            elif "HEAT" in t: icon = AI_AMMO_MAP["HEAT"]
                            elif "HESH" in t: icon = AI_AMMO_MAP["HE"]
                            elif "AP" in t: icon = AI_AMMO_MAP["AP"]
                            elif "HE" in t: icon = AI_AMMO_MAP["HE"]
                            
                            if icon and count > 0:
                                ammo_mapped.append((icon, count))
                elif str(k).lower() == "total":
                    continue
                else:
                    k_up = str(k).upper()
                    count = 0
                    if isinstance(v, (int, float, str)) and str(v).strip() != "0":
                        try: count = int(v)
                        except: pass
                        
                        icon = None
                        if "APCR" in k_up: icon = AI_AMMO_MAP["APCR"]
                        elif "HEAT" in k_up: icon = AI_AMMO_MAP["HEAT"]
                        elif "HESH" in k_up: icon = AI_AMMO_MAP["HE"]
                        elif "AP" in k_up: icon = AI_AMMO_MAP["AP"]
                        elif "HE" in k_up: icon = AI_AMMO_MAP["HE"]
                        
                        if icon and count > 0:
                            ammo_mapped.append((icon, count))

        # Deduplicate ammo order safely
        seen_ammo = set()
        clean_ammo = []
        for am, count in ammo_mapped:
            if am not in seen_ammo:
                seen_ammo.add(am)
                clean_ammo.append((am, count))"""

# Replace the block
start_str = "        # Normalize ammo"
end_str = "        # Normalize crew"
parts = src.split(start_str)
if len(parts) >= 2:
    before = parts[0]
    subparts = parts[1].split(end_str)
    after = end_str + subparts[1]
    
    with open('ai_engine.py', 'w', encoding='utf-8') as f:
        f.write(before + new_ammo_logic + "\n\n" + after)
    print("Patched ai_engine.py ammo logic.")
else:
    print("Could not find ammo block.")
