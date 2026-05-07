with open('stats_ai.py', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if 'tank_name = data.get("name"' in line:
        start_idx = i
    if 'self._layout_tile_row(fm_body, fm_slots, gap=0)' in line:
        end_idx = i

if start_idx != -1 and end_idx != -1:
    print(f"Found block: {start_idx} to {end_idx}")
else:
    print("Not found")
