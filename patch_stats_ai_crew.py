with open('stats_ai.py', 'r', encoding='utf-8') as f:
    src = f.read()

target = '''        crew_slots = []
        ai_crew = {}
        for role, skills in build_data.get("crew", []):
            ai_crew[role.lower()] = skills'''

replacement = '''        crew_slots = []
        ai_crew = {}
        for role, skills in build_data.get("crew", []):
            r_lower = role.lower()
            if "radio" in r_lower or "radioman" in r_lower: r_lower = "radioman"
            elif "loader" in r_lower: r_lower = "loader"
            elif "gunner" in r_lower: r_lower = "gunner"
            elif "driver" in r_lower: r_lower = "driver"
            elif "commander" in r_lower: r_lower = "commander"
            ai_crew[r_lower] = skills'''

src = src.replace(target, replacement)
with open('stats_ai.py', 'w', encoding='utf-8') as f:
    f.write(src)
print("Patched ai_crew mapping")
