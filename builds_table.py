#!/usr/bin/env python3
"""Upload all tank builds + prompts + popular tanks to Firebase RTDB.
Run once to seed Firebase, then at build time to update.

Usage:
    python builds_table.py
"""
import json, os, sys, hashlib, time

FIREBASE_PROJECT_ID = "sm-wot-assistant"
FIREBASE_API_KEY = "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"
_RTDB_BASE = f"https://{FIREBASE_PROJECT_ID}-default-rtdb.europe-west1.firebasedatabase.app"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _rtdb_url(path):
    return f"{_RTDB_BASE}/{path}.json?auth={FIREBASE_API_KEY}"

def _put(path, data, timeout=15):
    try:
        import requests
        url = _rtdb_url(path)
        r = requests.put(url, json=data, timeout=timeout)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"  [FAIL] PUT {path}: {e}")
        return False

def _patch(path, data, timeout=15):
    try:
        import requests
        url = _rtdb_url(path)
        r = requests.patch(url, json=data, timeout=timeout)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"  [FAIL] PATCH {path}: {e}")
        return False

def main():
    print("=== Firebase Builds Table Upload ===\n")

    # 1. Load all data files
    builds_path = os.path.join(BASE_DIR, "ai_builds_cache.json")
    prompts_path = os.path.join(BASE_DIR, "prompts_cache.json")
    popular_path = os.path.join(BASE_DIR, "popular_tanks_cache.json")
    manifest_path = os.path.join(BASE_DIR, ".tank_extract_manifest.json")

    ai_builds = json.load(open(builds_path, "r", encoding="utf-8"))
    prompts = json.load(open(prompts_path, "r", encoding="utf-8"))
    popular = json.load(open(popular_path, "r", encoding="utf-8"))
    manifest = json.load(open(manifest_path, "r", encoding="utf-8"))

    builds = ai_builds.get("builds", {})
    updated = ai_builds.get("updated", {})
    print(f"Builds: {len(builds)} tanks")
    print(f"Prompts: {len(prompts)} tanks")
    print(f"Popular: {len(popular.get('tanks',[]))} tanks")
    print(f"Manifest: {len(manifest)} entries")

    # 2. Compute scripts fingerprint from manifest
    fp_str = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    scripts_fingerprint = hashlib.md5(fp_str.encode('utf-8')).hexdigest()
    print(f"Scripts fingerprint: {scripts_fingerprint}")

    # 3. Build popular tanks data (just tags as list)
    popular_tags = [t["tag"] for t in popular.get("tanks", []) if t.get("tag")]
    print(f"Popular tags: {popular_tags[:5]}... ({len(popular_tags)} total)")

    # 4. Popular tanks prompt
    popular_prompt = (
        "In World of Tanks, compile a list of the 50 most popular tanks "
        "for tiers 8-11, using the exact tank names as they appear in the game client. "
        "List only the tank names, one per line."
    )

    # 5. Upload builds to Firebase
    print("\nUploading builds...")
    version = 1
    batch_size = 50
    tank_keys = sorted(builds.keys())
    ok = 0
    fail = 0
    for i in range(0, len(tank_keys), batch_size):
        batch = tank_keys[i:i+batch_size]
        batch_data = {}
        for tag in batch:
            if tag in builds and tag in updated:
                batch_data[tag] = {
                    "data": builds[tag],
                    "updated": updated[tag]
                }
        path = f"builds/tanks"
        if _patch(path, batch_data):
            ok += len(batch)
        else:
            fail += len(batch)
        print(f"  {i+len(batch)}/{len(tank_keys)} uploaded (ok={ok}, fail={fail})", end="\r")

    # Set builds version + fingerprint
    _patch("builds", {"version": version, "scripts_fingerprint": scripts_fingerprint})
    print(f"\nBuilds version: {version}")

    # 6. Upload prompts
    print("\nUploading prompts...")
    prompt_keys = sorted(prompts.keys())
    ok_p = 0
    fail_p = 0
    for i in range(0, len(prompt_keys), batch_size):
        batch = prompt_keys[i:i+batch_size]
        batch_data = {}
        for tag in batch:
            if tag in prompts:
                batch_data[tag] = prompts[tag]
        path = f"prompts/tanks"
        if _patch(path, batch_data):
            ok_p += len(batch)
        else:
            fail_p += len(batch)
        print(f"  {i+len(batch)}/{len(prompt_keys)} uploaded (ok={ok_p}, fail={fail_p})", end="\r")

    # Upload popular tanks prompt
    _put("prompts/popular_tanks", popular_prompt)
    _patch("prompts", {"version": version})
    print(f"\nPrompts version: {version}")

    # 7. Upload popular tanks
    print(f"\nUploading popular tanks...")
    _put("popular_tanks", {
        "version": version,
        "data": popular_tags,
        "updated": popular.get("updated", time.strftime("%Y-%m-%dT%H:%M:%S"))
    })
    print(f"Popular tanks: {len(popular_tags)} tags")

    # 8. Init pending_updates
    print("\nInitializing pending_updates...")
    _put("pending_updates/popular_tanks", {
        "status": "idle",
        "version": version,
        "message": ""
    })
    _put("pending_updates/builds", {
        "status": "idle",
        "version": version,
        "queue": [],
        "current_tag": "",
        "progress": "0/0",
        "message": ""
    })

    print(f"\n=== DONE ===")
    print(f"Builds: {ok} uploaded, {fail} failed")
    print(f"Prompts: {ok_p} uploaded, {fail_p} failed")
    print(f"Popular tanks: {len(popular_tags)} uploaded")
    print(f"Version: {version}")

if __name__ == "__main__":
    main()
