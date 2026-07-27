#!/usr/bin/env python3
"""Admin tool: generate AI tank builds via Selenium + Chrome, upload to Firebase.

Usage:
  python admin_build_generator.py --popular         # Regenerate popular tanks list
  python admin_build_generator.py --builds           # Regenerate ALL tank builds
  python admin_build_generator.py --builds R45_IS-7  # Regenerate specific tank
  python admin_build_generator.py --listen           # Watch pending_updates, auto-run
  python admin_build_generator.py --listen --wot-path="C:/Games/World_of_Tanks_EU"  # With change detection

Requires:
  - Chrome installed (user profile for CAPTCHA-free access)
  - pip install selenium
  - Generate prompts first: python builds_table.py --gen-prompts
"""
import os, sys, json, time, re, random, threading, traceback, hashlib, zipfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_prompt_v2 import generate_prompt
from stats_ai import _save_ai_build_cache, _load_ai_build_cache, _save_ai_build_cache_bulk, StatsAI
_is_build_complete = StatsAI._is_build_complete
from _fill_all_builds import parse_build as _parse_build_response

# ── Config ──────────────────────────────────────────
FIREBASE_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"
API_KEY = "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"

# Chrome profile path — CHANGE to your profile
CHROME_PROFILE = os.environ.get("CHROME_PROFILE",
    r"C:\Users\PRO\AppData\Local\Google\Chrome\User Data")
CHROME_PROFILE_DIR = "Default"

SELENIUM_TIMEOUT = 60       # seconds to wait for AI response
DELAY_MIN, DELAY_MAX = 25, 35  # random delay between prompts

PROGRESS_FILE = "_fill_progress.json"
PROMPTS_FILE = "prompts_cache.json"

# ── Helpers ─────────────────────────────────────────
def _rtdb_url(path):
    return f"{FIREBASE_URL}/{path}.json?auth={API_KEY}"

def _put_json(url, data, timeout=15):
    import requests
    r = requests.put(url, json=data, timeout=timeout)
    return r.status_code in (200, 204)

def _get_json(url, timeout=10):
    import requests
    r = requests.get(url, timeout=timeout)
    return r.json() if r.status_code == 200 else None

def load_tank_db():
    with open("tank_db.json", "r", encoding="utf-8") as f:
        db = json.load(f)
    bad = ["_7x7","_fallout","_fl","_sh","_bootcamp","_igr","_test","_training",
           "tutorial","observer","r05_kv","r70_t_50_2","sherman_crab","g00_",
           "_cfe","auto_s","auto_test","_shxxi","_bomber","pillbox","env_artillery",
           "a08_t23","a26_t18","a15_t57","_newonboarding","_storymode"]
    clean = {}
    for k, v in db.items():
        if any(b in k.lower() for b in bad) or any(b in v.get("name","").lower() for b in bad):
            continue
        tier = v.get("tier", 0)
        if tier < 1 or tier > 11:
            continue
        clean[k] = v
    return clean

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"pass":1,"index":0,"retry":[],"ok_count":0,"fail_count":0}

def save_progress(pass_num, idx, retry, ok_c, fail_c):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"pass":pass_num,"index":idx,"retry":retry,
                    "ok_count":ok_c,"fail_count":fail_c}, f)

def load_prompts():
    if os.path.exists(PROMPTS_FILE):
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# ── Change detection ──────────────────────────────
def _entry_fingerprint(info):
    return {"size": int(getattr(info, "file_size", 0)), "crc": int(getattr(info, "CRC", 0))}

def _fingerprint_equal(a, b):
    if not a or not b:
        return False
    return a.get("size") == b.get("size") and a.get("crc") == b.get("crc")

def detect_changed_tanks(wot_path, manifest_path=".tank_extract_manifest.json"):
    """Return list of tank tags whose vehicle XML changed in scripts.pkg."""
    pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.exists(pkg_path):
        print(f"[DETECT] scripts.pkg not found at {pkg_path}")
        return []
    old = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            old = json.load(f)
    changed = []
    with zipfile.ZipFile(pkg_path, 'r') as z:
        for name in z.namelist():
            if not name.startswith("scripts/item_defs/vehicles/") or not name.endswith(".xml"):
                continue
            if "common/" in name or "components/" in name or "list.xml" in name:
                continue
            info = z.getinfo(name)
            fp = _entry_fingerprint(info)
            prev = old.get(name)
            if prev is None or not _fingerprint_equal(prev, fp):
                tag = os.path.splitext(os.path.basename(name))[0]
                changed.append(tag)
    if changed:
        names = ", ".join(changed[:10])
        print(f"[DETECT] {len(changed)} changed: {names}{'...' if len(changed) > 10 else ''}")
    else:
        print(f"[DETECT] No changed tanks ({len(old)} entries checked)")
    return changed

_WG_API_URL = "https://api.worldoftanks.eu/wot/encyclopedia/info/?application_id=0cc3f254142cf2e40511006d6cd18761&r_realm=eu"

def check_wg_tanks_version():
    """Return tanks_updated_at timestamp from WG API, or None."""
    import requests
    try:
        r = requests.get(_WG_API_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "ok":
                return data["data"].get("tanks_updated_at")
    except Exception:
        pass
    return None

def check_wg_game_version():
    """Return (game_version, tanks_updated_at) from WG API, or (None, None)."""
    import requests
    try:
        r = requests.get(_WG_API_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "ok":
                ver = data["data"].get("game_version")
                ts = data["data"].get("tanks_updated_at")
                return (ver, ts)
    except Exception:
        pass
    return (None, None)

# ── Selenium engine ─────────────────────────────────
def _create_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains

    opts = Options()
    opts.add_argument(f"--user-data-dir={CHROME_PROFILE}")
    opts.add_argument(f"--profile-directory={CHROME_PROFILE_DIR}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--start-maximized")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    # Inject stealth JS
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
        """
    })
    return driver

def _submit_to_ai(driver, prompt, timeout=SELENIUM_TIMEOUT):
    """Submit prompt to Google AI Mode, return response text or None."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains

    # Navigate to Google AI Mode
    driver.get("https://www.google.com/search?q=&udm=50")
    time.sleep(2)

    # Find textarea via multi-selector
    textarea = None
    selectors = [
        "textarea[jsname]",
        "textarea[aria-label]",
        "div[role='dialog'] textarea",
        "div.AgWCw textarea",
        "div.Txyg0d textarea",
        "textarea",
    ]
    for sel in selectors:
        try:
            textarea = driver.find_element(By.CSS_SELECTOR, sel)
            if textarea.is_enabled():
                break
        except:
            continue

    if not textarea:
        print("[AI] textarea not found!")
        return None

    # Paste prompt via clipboard + keyboard
    textarea.click()
    time.sleep(0.3)
    import pyperclip
    pyperclip.copy(prompt)
    time.sleep(0.2)
    ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
    time.sleep(0.5)

    # Submit
    textarea.send_keys(Keys.ENTER)
    print("[AI] Prompt submitted, waiting for response...")

    # Wait and poll for response
    start = time.time()
    response_text = ""
    while time.time() - start < timeout:
        time.sleep(2)
        # Try response container selectors
        containers = driver.find_elements(By.CSS_SELECTOR, "[data-session-thread-id]")
        if not containers:
            containers = driver.find_elements(By.CSS_SELECTOR, "div[aria-label*='AI Overview']")
        if not containers:
            containers = driver.find_elements(By.CSS_SELECTOR, "div.jUiaTd")
        if containers:
            response_text = containers[-1].text.strip()
            if len(response_text) > 100:
                print(f"[AI] Response received ({len(response_text)} chars, {time.time()-start:.0f}s)")
                return response_text
        # Fallback: body text
        if time.time() - start > 30:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if len(body_text) > 200:
                print(f"[AI] Body fallback ({len(body_text)} chars)")
                return body_text
        print(f"[AI] Waiting... ({time.time()-start:.0f}s)")

    print(f"[AI] Timeout ({timeout}s) — no response")
    return None

# ── Response parsing ────────────────────────────────
def _parse_popular_response(text, tank_db):
    """Parse popular tanks list from AI response."""
    lines = text.split('\n')
    names = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        clean = re.sub(r'^[\d\*\-•]+\s*[\.\)\-\s]*\s*', '', line).strip()
        clean = clean.replace('**', '').replace('*', '').replace('__', '')
        skip_words = ['google','sign in','sign up','www.','.com','world of tanks',
                       'note:','here are','here is','the most','popular tanks',
                       'tier 6','tier 7','tier 8','tier 9','tier 10','tier 11']
        low = clean.lower()
        if any(sw in low for sw in skip_words):
            continue
        if len(clean) < 3 or len(clean) > 60:
            continue
        if re.match(r'^[\w\s\'\-\.\/\,]+$', clean):
            names.append(clean)

    # Map names to tags
    from stats_ai import StatsAI
    name_to_tag = {}
    for tag, data in tank_db.items():
        name = data.get("name", "").strip().lower()
        if name:
            name_to_tag[name] = tag
    result = []
    for n in names:
        nl = n.lower().strip()
        if nl in name_to_tag:
            result.append(name_to_tag[nl])
    return result[:30]

# ── Firebase uploads ────────────────────────────────
def _upload_build(tag, build_data):
    if not build_data or not _is_build_complete(build_data):
        return False
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    url = _rtdb_url(f"builds/tanks/{tag}")
    ok = _put_json(url, {"data": build_data, "updated": ts})
    if ok:
        _save_ai_build_cache(tag, build_data, fail_count=0)
    return ok

def _upload_prompt(tag, prompt):
    if not prompt:
        return False
    url = _rtdb_url(f"prompts/tanks/{tag}")
    ok = _put_json(url, prompt)
    if ok:
        print(f"    [PROMPT] uploaded for {tag}")
    return ok

def _upload_popular(tags, tank_db):
    url = _rtdb_url("popular_tanks/data")
    ok1 = _put_json(url, tags)
    # Get current version
    cur = _get_json(_rtdb_url("popular_tanks/version")) or 0
    url2 = _rtdb_url("popular_tanks/version")
    ok2 = _put_json(url2, int(cur) + 1)
    # Save to local cache too
    cache_data = {
        "tanks": [{"tag": t, "name": tank_db.get(t, {}).get("name", t)} for t in tags],
        "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "version": int(cur) + 1
    }
    from stats_ai import _CACHE_PATH
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except:
        pass
    return ok1 and ok2

def _update_builds_version():
    cur = _get_json(_rtdb_url("builds/version")) or 0
    new_ver = int(cur) + 1
    fp_str = json.dumps({"ver": new_ver, "ts": time.time()}, sort_keys=True)
    fp = hashlib.md5(fp_str.encode('utf-8')).hexdigest()
    _put_json(_rtdb_url("builds/version"), new_ver)
    _put_json(_rtdb_url("builds/scripts_fingerprint"), fp)
    print(f"[VERSION] Builds v{new_ver}, fingerprint: {fp[:16]}...")

def _update_pending_status(path, status, message="", progress=None):
    data = {"status": status, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "message": message}
    if progress:
        data["progress"] = progress
    _put_json(_rtdb_url(f"pending_updates/{path}"), data)

# ── Generation modes ────────────────────────────────
def generate_popular(driver, tank_db):
    """Generate popular tanks list via AI."""
    print("\n=== Generating Popular Tanks ===\n")
    prompt = ("List the 30 most popular World of Tanks tanks for tiers 8-11. "
              "Output only the tank names, one per line, using exact game client names. "
              "No numbers, no formatting, no explanations.")
    response = _submit_to_ai(driver, prompt, timeout=90)
    if not response:
        print("[POPULAR] No response")
        return False
    tags = _parse_popular_response(response, tank_db)
    if len(tags) < 5:
        print(f"[POPULAR] Only {len(tags)} valid tanks, ignoring")
        return False
    ok = _upload_popular(tags, tank_db)
    print(f"[POPULAR] Uploaded {len(tags)} tanks: {ok}")
    return ok

def generate_builds(driver, tank_db, prompts, single_tag=None, force=False, queue=None):
    """Generate builds for specified tanks."""
    print("\n=== Generating Builds ===\n")

    all_tags_sorted = sorted(tank_db.keys(), key=lambda t: (tank_db[t].get("tier",0), tank_db[t].get("name","")))
    if single_tag:
        if single_tag not in tank_db:
            print(f"[BUILD] Tag {single_tag} not found in DB")
            return False
        all_tags = [single_tag]
        total = 1
    elif queue is not None:
        all_tags = [t for t in queue if t in tank_db]
        total = len(all_tags)
        print(f"[BUILD] Queue: {total} tanks from detection")
    elif force:
        all_tags = all_tags_sorted
        total = len(all_tags)
        print(f"[BUILD] Force regenerate all {total} tanks")
    else:
        # Check cache — only missing/incomplete
        existing, _, _, _, _ = _load_ai_build_cache()
        all_tags = [t for t in all_tags_sorted if t not in existing or not _is_build_complete(existing.get(t, {}))]
        total = len(all_tags)

    if total == 0:
        print("[BUILD] All tanks already cached!")
        return True

    prog = load_progress() if not single_tag else {"pass":1,"index":0,"retry":[],"ok_count":0,"fail_count":0}
    ok_count = prog["ok_count"]
    fail_count = prog["fail_count"]
    start_idx = prog["index"]
    to_process = all_tags[start_idx:]

    for idx, tag in enumerate(to_process):
        actual_idx = start_idx + idx
        data = tank_db[tag]
        tank_name = data.get("name", tag)
        print(f"  [{actual_idx+1}/{total}] Tier {data.get('tier',0)} — {tank_name} [{tag}]", flush=True)

        # Get prompt
        prompt = prompts.get(tag)
        prompt_new = False
        if not prompt or len(prompt) < 50:
            prompt = generate_prompt(tag, tank_name)
            prompt_new = True
        if not prompt or len(prompt) < 50:
            print(f"    SKIP: no prompt")
            save_progress(prog["pass"], actual_idx+1, to_process[idx+1:], ok_count, fail_count)
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            continue

        # Submit to AI
        response = _submit_to_ai(driver, prompt, timeout=SELENIUM_TIMEOUT)
        if not response:
            print(f"    [FAIL] no response")
            fail_count += 1
            retry_tags = [tag] + to_process[idx+1:]
            save_progress(prog["pass"], actual_idx+1, retry_tags, ok_count, fail_count)
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            continue

        # Parse
        build_data = _parse_build_response(response)
        if not build_data or not _is_build_complete(build_data):
            print(f"    [FAIL] parse fail or incomplete")
            fail_count += 1
            retry_tags = [tag] + to_process[idx+1:]
            save_progress(prog["pass"], actual_idx+1, retry_tags, ok_count, fail_count)
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            continue

        # Upload
        if not single_tag:
            _update_pending_status("builds", "generating", progress={"done": actual_idx+1, "total": total, "current": tank_name})
        ok = _upload_build(tag, build_data)
        if ok:
            print(f"    [OK] uploaded")
            if prompt_new:
                _upload_prompt(tag, prompt)
            ok_count += 1
            save_progress(prog["pass"], actual_idx+1, to_process[idx+1:], ok_count, fail_count)
        else:
            print(f"    [FAIL] upload failed")
            fail_count += 1
            retry_tags = [tag] + to_process[idx+1:]
            save_progress(prog["pass"], actual_idx+1, retry_tags, ok_count, fail_count)

        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        print(f"    Wait {delay:.0f}s...", flush=True)
        time.sleep(delay)

    # Final
    if not single_tag:
        existing, _, _, _, _ = _load_ai_build_cache()
        total_cached = len(existing)
        _update_builds_version()
        print(f"\n=== Done: {total_cached} cached (ok={ok_count}, fail={fail_count}) ===\n")
    return True

# ─── Listen mode ────────────────────────────────────
def listen_mode(tank_db, wot_path=None):
    """Poll pending_updates and auto-generate. Periodically scan for game changes."""
    print(f"\n=== Listen Mode {'(WoT: ' + wot_path + ')' if wot_path else '(no WoT path)'} ===\n")
    _last_scan = -3600  # trigger initial scan immediately
    _last_wg = -21600  # trigger initial WG check immediately

    while True:
        now = time.time()

        # ── Periodic scripts.pkg scan (every 60 min) ─────
        if wot_path and now - _last_scan > 3600:
            _last_scan = now
            changed = detect_changed_tanks(wot_path)
            if changed:
                print(f"[LISTEN] {len(changed)} changed - writing pending_updates")
                _put_json(_rtdb_url("pending_updates/builds"), {
                    "status": "generating",
                    "queue": changed,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "message": f"{len(changed)} tanks changed in scripts.pkg"
                })

        # ── WG API check (every 6 hours) ─────────────────
        if now - _last_wg > 21600:
            _last_wg = now
            ts = check_wg_tanks_version()
            if ts:
                stored = _get_json(_rtdb_url("builds/tanks_updated_at")) or 0
                if ts > stored:
                    print(f"[LISTEN] WG tanks_updated_at: {stored} - {ts}")
                    _put_json(_rtdb_url("builds/tanks_updated_at"), ts)
                    if wot_path and now - _last_scan > 300:
                        _last_scan = now
                        changed = detect_changed_tanks(wot_path)
                        if changed:
                            _put_json(_rtdb_url("pending_updates/builds"), {
                                "status": "generating",
                                "queue": changed,
                                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "message": f"{len(changed)} tanks changed per WG API trigger"
                            })

        # ── Check pending_updates ────────────────────────
        pop = _get_json(_rtdb_url("pending_updates/popular_tanks"))
        builds = _get_json(_rtdb_url("pending_updates/builds"))

        if pop and pop.get("status") == "generating":
            print("[LISTEN] Popular tanks regeneration triggered!")
            driver = _create_driver()
            try:
                _update_pending_status("popular_tanks", "generating")
                ok = generate_popular(driver, tank_db)
                _update_pending_status("popular_tanks", "done" if ok else "error",
                    "Completed successfully" if ok else "Generation failed")
            except Exception as e:
                _update_pending_status("popular_tanks", "error", str(e))
                traceback.print_exc()
            finally:
                driver.quit()

        if builds and builds.get("status") == "generating":
            queue = builds.get("queue")
            if queue is not None and len(queue) == 0:
                # Empty queue from detection — skip
                _update_pending_status("builds", "done", "No changed tanks detected")
                continue
            print(f"[LISTEN] Builds regeneration triggered! queue={'all' if queue is None else str(len(queue))}")
            prompts = load_prompts()
            driver = _create_driver()
            try:
                _update_pending_status("builds", "generating", progress={"done":0,"total":0,"current":""})
                ok = generate_builds(driver, tank_db, prompts, force=(queue is None), queue=queue)
                _update_pending_status("builds", "done" if ok else "error",
                    "Completed successfully" if ok else "Generation failed")
            except Exception as e:
                _update_pending_status("builds", "error", str(e))
                traceback.print_exc()
            finally:
                driver.quit()

        time.sleep(10)

# ── Main ────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI Tank Build Generator")
    parser.add_argument("--popular", action="store_true", help="Regenerate popular tanks")
    parser.add_argument("--builds", nargs="?", const=True, default=False, help="Regenerate builds (optional: specific tag)")
    parser.add_argument("--listen", action="store_true", help="Watch pending_updates and auto-run")
    parser.add_argument("--wot-path", type=str, default=None, help="Path to WoT installation for change detection")
    args = parser.parse_args()

    print("="*60)
    print("SM WoT Assistant — AI Build Generator")
    print("="*60)

    tank_db = load_tank_db()
    print(f"[DB] {len(tank_db)} tanks")

    if args.listen:
        listen_mode(tank_db, wot_path=args.wot_path)
        return

    # Single run
    driver = _create_driver()
    try:
        if args.popular:
            generate_popular(driver, tank_db)
        elif args.builds:
            single_tag = args.builds if isinstance(args.builds, str) else None
            prompts = load_prompts()
            print(f"[PROMPTS] {len(prompts)} cached")
            generate_builds(driver, tank_db, prompts, single_tag=single_tag)
        else:
            parser.print_help()
    finally:
        driver.quit()
        print("\nDone.")

if __name__ == "__main__":
    main()
