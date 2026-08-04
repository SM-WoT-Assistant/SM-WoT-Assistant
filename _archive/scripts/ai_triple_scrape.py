import json
import sys
import os
import subprocess
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from ai_normalizer import normalize_build, validate_build, VALID_EQUIPMENT, VALID_CREW_SKILLS, VALID_CONSUMABLES


def scrape_tank(tank_name, timeout=60):
    """Run scraper and return raw JSON or None"""
    try:
        result = subprocess.run(
            ["python", "ai_scraper_strict.py", tank_name],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            timeout=timeout
        )
        for line in result.stdout.split("\n"):
            if line.startswith("JSON_RESULT:"):
                json_str = line.replace("JSON_RESULT:", "", 1).strip()
                return json.loads(json_str)
    except Exception as e:
        print(f"Scraper error: {e}")
    return None


def _score_equipment(items, valid_set):
    """Score how many valid items in the list"""
    return len([x for x in items if x in valid_set])


def _pick_most_common(items_list, max_items=3, valid_set=None):
    """Pick most common items from multiple lists"""
    counter = Counter()
    for items in items_list:
        for item in items:
            if valid_set is None or item in valid_set:
                counter[item] += 1
    return [item for item, _ in counter.most_common(max_items)]


def _pick_most_common_consumables(cons_lists, max_items=3):
    """Pick most common consumables"""
    counter = Counter()
    for items in cons_lists:
        for item in items:
            if item in VALID_CONSUMABLES:
                counter[item] += 1
    result = [item for item, _ in counter.most_common(max_items)]
    # If we got less than max_items, fill with first valid
    if len(result) < max_items:
        for items in cons_lists:
            for item in items:
                if item not in result:
                    result.append(item)
                    if len(result) >= max_items:
                        break
            if len(result) >= max_items:
                break
    return result[:max_items]


def _pick_most_common_skills(skills_by_role, max_skills=6):
    """Pick most common skills per role from multiple results"""
    result = {}
    for role in ["commander", "gunner", "driver", "loader_1"]:
        counter = Counter()
        for skills in skills_by_role.get(role, []):
            for skill in skills:
                if skill in VALID_CREW_SKILLS:
                    counter[skill] += 1
        result[role] = [s for s, _ in counter.most_common(max_skills)]
    return result


def average_results(results, tank_name):
    """Average 3 results into one build"""
    if not results:
        return None

    # Normalize all results
    normalized = []
    for r in results:
        if r and "error" not in r:
            n = normalize_build(r)
            if not validate_build(n):
                normalized.append(n)

    if len(normalized) < 2:
        return normalized[0] if normalized else None

    # Collect equipment for averaging
    l1_lists = [n["equipment"]["loadout_1"] for n in normalized]
    l2_lists = [n["equipment"]["loadout_2"] for n in normalized]
    cons_lists = [n["consumables"] for n in normalized]
    crew_lists = {role: [n["crew"].get(role, []) for n in normalized] for role in ["commander", "gunner", "driver", "loader_1"]}

    # Build averaged result
    avg = {
        "tank": tank_name,
        "equipment": {
            "loadout_1": _pick_most_common(l1_lists, 3, VALID_EQUIPMENT),
            "loadout_2": _pick_most_common(l2_lists, 3, VALID_EQUIPMENT)
        },
        "ammo": normalized[0]["ammo"],
        "consumables": _pick_most_common_consumables(cons_lists, 3),
        "crew": _pick_most_common_skills(crew_lists, 6),
        "field_mods": normalized[0]["field_mods"]
    }

    return avg


def run_triple_scrape(tank_name):
    print(f"[AI] Scraping 3x builds for: {tank_name}")
    results = []

    for i in range(1, 4):
        print(f"[AI] Attempt {i}/3...")
        r = scrape_tank(tank_name)
        if r and "error" not in r:
            results.append(r)
            print(f"[AI] Got result {i}: OK")
        else:
            print(f"[AI] Attempt {i} failed")
        if i < 3:
            time.sleep(1)

    if not results:
        print("[AI] All attempts failed")
        return {"error": "All scraper attempts failed"}

    print(f"[AI] Normalizing {len(results)} results...")
    averaged = average_results(results, tank_name)

    if averaged:
        issues = validate_build(averaged)
        if issues:
            print(f"[AI] Averaged result has issues: {issues}")
        else:
            print(f"[AI] Averaged result VALID")
    else:
        print("[AI] Averaging failed, using first valid result")
        for r in results:
            n = normalize_build(r)
            if not validate_build(n):
                averaged = n
                break

    return averaged


if __name__ == "__main__":
    tank = sys.argv[1] if len(sys.argv) > 1 else "IS-7"
    result = run_triple_scrape(tank)

    print("\n" + "="*60)
    print("FINAL AVERAGED RESULT:")
    print("="*60)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    issues = validate_build(result) if result else []
    print(f"\nValidation: {issues if issues else 'PASSED'}")

    # Store in cache
    if result and "error" not in result:
        cache_file = "ai_cache.json"
        cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
            except:
                pass
        cache[tank] = result
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
        print(f"\n[CACHE] Saved to {cache_file}")
