import re
import json

# Use already saved page
filename = "debug_equipment_page.html"
if not os.path.exists(filename):
    print("File not found")
    exit(1)

with open(filename, "r", encoding="utf-8") as f:
    page_source = f.read()

match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>([^<]+)</script>', page_source)
if not match:
    print("No __NEXT_DATA__")
    exit()

data = json.loads(match.group(1))
next_data = data.get("props", {}).get("pageProps", {})

# Check crew section in detail
crew = next_data.get("crew", {})
print(f"\n=== CREW SECTION DETAIL ===")
crew_data = crew.get("data", {})
if isinstance(crew_data, dict):
    crew_list = crew_data.get("crew", [])
    print(f"Crew list length: {len(crew_list)}")

    for i, member in enumerate(crew_list[:2]):
        print(f"\n--- Crew member {i+1} ---")
        print(f"Type: {type(member)}")
        if isinstance(member, dict):
            print(f"Keys: {list(member.keys())}")
            print(json.dumps(member, indent=2)[:2000])