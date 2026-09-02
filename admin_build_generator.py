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
import os, sys, json, time, re, random, threading, traceback, hashlib, zipfile, shutil, tempfile, subprocess

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_prompt_v2 import generate_prompt
import generate_prompt_v2 as _gp
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

PROGRESS_FILE = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "_fill_progress.json")
PROMPTS_FILE = "prompts_cache.json"

# Маркери тегів, виключених з tank_db (івент-клони: CFE/7x7/FL/SH/fallout/StoryMode…).
# ОДНА точка правди для load_tank_db() і фільтрів генерації (#1604: розбіжність
# 995 танків vs 996 промптів — промпти для відфільтрованих клонів рахувались, танки ні).
_BAD_TAG_MARKERS = [
    "_7x7", "_fallout", "_fl", "_sh", "_bootcamp", "_igr", "_test", "_training",
    "tutorial", "observer", "r05_kv", "r70_t_50_2", "sherman_crab", "g00_",
    "_cfe", "auto_s", "auto_test", "_shxxi", "_bomber", "pillbox", "env_artillery",
    "a08_t23", "a26_t18", "a15_t57", "_newonboarding", "_storymode",
]

def _is_bad_tag(tag):
    return any(b in tag.lower() for b in _BAD_TAG_MARKERS)

# ── Helpers ─────────────────────────────────────────
def _rtdb_url(path):
    return f"{FIREBASE_URL}/{path}.json?auth={API_KEY}"

def _put_json(url, data, timeout=15):
    import requests
    import admin_auth
    auth_url = admin_auth._rtdb_url_with_token(url)
    if auth_url is None:
        print("[ADMIN] RTDB write skipped: no admin credentials "
              "(admin_creds.json у %APPDATA%/SM WoT Assistant/)")
        return False
    if data is None:
        # PUT null — видалення вузла (json=None не шле тіло, RTDB повертає 400)
        r = requests.put(auth_url, data=b"null",
                         headers={"Content-Type": "application/json"}, timeout=timeout)
    else:
        r = requests.put(auth_url, json=data, timeout=timeout)
    return r.status_code in (200, 204)

def _get_json(url, timeout=10):
    import requests
    r = requests.get(url, timeout=timeout)
    return r.json() if r.status_code == 200 else None

def load_tank_db():
    with open("tank_db.json", "r", encoding="utf-8") as f:
        db = json.load(f)
    clean = {}
    for k, v in db.items():
        if _is_bad_tag(k) or any(b in v.get("name", "").lower() for b in _BAD_TAG_MARKERS):
            continue
        tier = v.get("tier", 0)
        if tier < 1 or tier > 11:
            continue
        clean[k] = v
    return clean

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pass":1,"index":0,"retry":[],"ok_count":0,"fail_count":0}

def save_progress(pass_num, idx, retry, ok_c, fail_c):
    try:
        os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump({"pass":pass_num,"index":idx,"retry":retry,
                        "ok_count":ok_c,"fail_count":fail_c}, f)
    except Exception:
        pass

def load_prompts():
    if os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    return {}


def load_prompts_merged(timeout=10):
    """Local + RTDB merge: local prompts_cache.json + GET prompts/tanks from RTDB.

    Bug 6 (02.09.2026 #1692): load_prompts() read only local file. After admin
    rebuild + backfill (v1.0.8 #1537), the local file lags behind RTDB —
    _check_tank_prompt_match reported '1023 vs 1010' (admin.log:15:18:39
    [ПОМИЛКА] 'Невідповідність резервуарів/підказок: 1023 tanks vs 1010 prompts')
    even though RTDB has 1023+ prompts. Card stayed red, log printed
    [ПОМИЛКА] on every restart.

    RTDB has 'auth != null' WRITE only; READ is open (database.rules.json
    per #1529) — no admin token needed for GET, the API key from FIREBASE_URL
    is sufficient. Source of truth: RTDB (overrides local, same rule as
    save_prompt gating on _upload_prompt success in v1.0.9 #1537).

    Silent fallback: any network/parse error returns local dict unchanged.
    No exception propagates to the GUI thread.
    """
    local = load_prompts()
    try:
        import requests as _req
        url = _rtdb_url("prompts/tanks")
        r = _req.get(url, timeout=timeout)
        if r.status_code == 200:
            rtdb = r.json() if r.content else None
            if isinstance(rtdb, dict) and rtdb:
                merged = dict(local)
                merged.update(rtdb)
                return merged
    except Exception as e:
        print(f"[WARN] load_prompts_merged: RTDB fetch failed, using local: {e}")
    return local

def save_prompt(tag, prompt):
    """Зберігає згенерований промпт у prompts_cache.json (самолікування кешу).

    prompt_cache.json — статичний файл, згенерований разово; без цього запису
    нові танки (напр. F141_Durendal) давали б вічну розбіжність tank_db/prompts.
    Валідація на load і write (#1346): пошкоджений кеш скидається.
    """
    try:
        if not prompt or not isinstance(prompt, str) or len(prompt) < 50:
            return
        prompts = {}
        if os.path.exists(PROMPTS_FILE):
            try:
                with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    prompts = loaded
            except Exception:
                prompts = {}
        prompts[tag] = prompt
        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(prompts, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"    [WARN] prompt cache save failed: {e}")

def check_prompt_tank_mismatch(tank_db=None, prompts=None):
    """Диф ключів prompts_cache vs (відфільтрованого) tank_db.

    Повертає (prompts_only, tanks_only) — теги з промптом без танка і танки
    без промпта. Обидва списки мають бути порожніми: будь-яка розбіжність
    означає, що лічильники «Танків/Промптів» не співпадають (#1604).
    """
    if tank_db is None:
        tank_db = load_tank_db()
    if prompts is None:
        prompts = load_prompts()
    tk, pk = set(tank_db), set(prompts)
    return sorted(pk - tk), sorted(tk - pk)

# ── Change detection ──────────────────────────────
def _entry_fingerprint(info):
    return {"size": int(getattr(info, "file_size", 0)), "crc": int(getattr(info, "CRC", 0))}

def _fingerprint_equal(a, b):
    if not a or not b:
        return False
    return a.get("size") == b.get("size") and a.get("crc") == b.get("crc")

def detect_changed_tanks(wot_path, manifest_path=".tank_extract_manifest.json"):
    """Return list of tank tags whose vehicle XML changed in scripts.pkg.

    Tags with _FAIL_THRESHOLD consecutive generation failures (see
    update_manifest_failures) are excluded — a persistent failure must not
    spin an hourly re-detection loop. A fingerprint change of the tank's XML
    (new game version) resets the counter and re-enables detection.

    Bug 7 (02.09.2026 #1692 follow-up): Tags in manifest `_pending` are SKIPPED
    on every subsequent detect until `update_manifest_for_tags` removes them
    (after a successful generation). Without this guard, when generate_builds
    fails (Chrome 183 race, network SSL EOF, AI parse fail), the manifest is
    NOT advanced for the failed tags — next detect re-detects the same tags
    forever. The admin.log 16:19:55 '693 zminenyx tankiv' was the result: a
    detect -> generate failure -> next detect re-detected the same 693.
    """
    pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.exists(pkg_path):
        print(f"[DETECT] scripts.pkg not found at {pkg_path}")
        try:
            from firebase_reporter import report_fallback
            report_fallback("admin_detect", "scripts.pkg", f"scripts.pkg not found at {pkg_path}")
        except Exception:
            pass
        return []
    old = {}
    pending_tags = set()
    if os.path.exists(manifest_path):
        with _MANIFEST_LOCK:
            with open(manifest_path, "r", encoding="utf-8") as f:
                old = json.load(f)
        # _pending is a top-level dict {tag: {fp, ts}} — tags already detected
        # but still waiting for successful generation. Skip them on re-detect.
        if isinstance(old, dict):
            _pending_obj = old.get("_pending")
            if isinstance(_pending_obj, dict):
                pending_tags = {str(t) for t in _pending_obj.keys()}
    changed = []
    changed_names = {}
    fps = {}
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
                if _is_bad_tag(tag):
                    continue
                # Bug 7: skip tags already in _pending (waiting for generation)
                if tag in pending_tags:
                    continue
                changed.append(tag)
                changed_names[tag] = name
                fps[name] = fp
    # Exclude tanks stuck in the consecutive-failure registry (same fingerprint).
    if changed:
        fails = _manifest_failures(manifest_path)
        if fails:
            excluded = []
            for tag in list(changed):
                name = changed_names.get(tag)
                f = fails.get(tag)
                if (f and int(f.get("count", 0)) >= _FAIL_THRESHOLD
                        and name and f.get("fp") == fps.get(name)):
                    excluded.append(tag)
                    changed.remove(tag)
            if excluded:
                print(f"[DETECT] {len(excluded)} tanks excluded after {_FAIL_THRESHOLD} failed generations: "
                      f"{', '.join(excluded[:10])}{'...' if len(excluded) > 10 else ''}")
    # Bug 7: stash the detected tags in manifest._pending so next detect skips
    # them. update_manifest_for_tags removes them on success. Without this,
    # every detect returns the same tags (admin.log 15:18:41 / 19:51:55 cycle).
    if changed:
        names = ", ".join(changed[:10])
        print(f"[DETECT] {len(changed)} changed: {names}{'...' if len(changed) > 10 else ''}")
        _mark_pending(manifest_path, changed_names, fps)
    else:
        if pending_tags:
            print(f"[DETECT] No new changes; {len(pending_tags)} tags still in _pending (awaiting generation)")
        else:
            print(f"[DETECT] No changed tanks ({len(old)} entries checked)")
    return changed


def _mark_pending(manifest_path, changed_names, fps):
    """Persist detected tags in manifest._pending (Bug 7).

    Side-effect: writes a {tag: {fp, ts}} entry per detected tag so the next
    detect_changed_tanks() invocation skips them. update_manifest_for_tags()
    clears the entry on successful generation.
    """
    if not changed_names or not manifest_path:
        return
    try:
        with _MANIFEST_LOCK:
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
            if not isinstance(data, dict):
                data = {}
            pending = data.get("_pending")
            if not isinstance(pending, dict):
                pending = {}
            ts = int(time.time())
            for tag, name in changed_names.items():
                fp = fps.get(name) if name else None
                if fp is None:
                    fp = {"size": 0, "crc": 0}
                pending[tag] = {"fp": fp, "ts": ts, "arcname": name}
            data["_pending"] = pending
            tmp = manifest_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, manifest_path)
    except Exception as e:
        print(f"[WARN] _mark_pending failed: {e}")


_MANIFEST_LOCK = threading.Lock()

def snapshot_manifest(wot_path, manifest_path):
    """Write current scripts.pkg vehicle XML fingerprints as baseline manifest."""
    pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.exists(pkg_path):
        return False
    new = {}
    with zipfile.ZipFile(pkg_path, 'r') as z:
        for name in z.namelist():
            if not name.startswith("scripts/item_defs/vehicles/") or not name.endswith(".xml"):
                continue
            if "common/" in name or "components/" in name or "list.xml" in name:
                continue
            new[name] = _entry_fingerprint(z.getinfo(name))
    with _MANIFEST_LOCK:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(new, f)
            return True
        except Exception:
            return False


def update_manifest_for_tags(wot_path, manifest_path, tags):
    """Advance manifest entries for generated tags to current pkg fingerprints."""
    if not tags or not os.path.exists(manifest_path):
        return False
    pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.exists(pkg_path):
        return False
    tags_set = set(tags)
    updates = {}
    with zipfile.ZipFile(pkg_path, 'r') as z:
        for name in z.namelist():
            if not name.startswith("scripts/item_defs/vehicles/") or not name.endswith(".xml"):
                continue
            if "common/" in name or "components/" in name or "list.xml" in name:
                continue
            tag = os.path.splitext(os.path.basename(name))[0]
            if tag in tags_set:
                updates[name] = _entry_fingerprint(z.getinfo(name))
    if not updates:
        return False
    with _MANIFEST_LOCK:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data.update(updates)
            # Success resets the consecutive-failure counter for these tags.
            fails = data.get("_failures")
            if isinstance(fails, dict) and fails:
                for tag in tags_set:
                    fails.pop(tag, None)
                data["_failures"] = fails
            # Bug 7 (02.09.2026): cleanup _pending for successfully generated
            # tags. Without this, the next detect re-detects the same tags
            # because they stay marked as 'waiting for generation' forever.
            pending = data.get("_pending")
            if isinstance(pending, dict) and pending:
                for tag in tags_set:
                    pending.pop(tag, None)
                data["_pending"] = pending
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return True
        except Exception:
            return False


_FAIL_THRESHOLD = 3  # consecutive failed generations before a tank is excluded from scans

def _manifest_failures(manifest_path):
    """Read the {tag: {count, fp}} consecutive-failure registry from the manifest."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        fails = d.get("_failures") if isinstance(d, dict) else None
        return fails if isinstance(fails, dict) else {}
    except Exception:
        return {}

def update_manifest_failures(wot_path, manifest_path, failed_tags):
    """Increment consecutive-failure counters for tags that failed to generate.

    Counters are keyed by the current scripts.pkg fingerprint — a fingerprint
    change (new game version/hotfix) resets the counter, so a failed tank gets
    a fresh attempt when its XML actually changes again.
    """
    if not failed_tags or not os.path.exists(manifest_path):
        return False
    pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.exists(pkg_path):
        return False
    failed_set = set(failed_tags)
    failures = _manifest_failures(manifest_path)
    with zipfile.ZipFile(pkg_path, 'r') as z:
        for name in z.namelist():
            if not name.startswith("scripts/item_defs/vehicles/") or not name.endswith(".xml"):
                continue
            if "common/" in name or "components/" in name or "list.xml" in name:
                continue
            tag = os.path.splitext(os.path.basename(name))[0]
            if tag not in failed_set:
                continue
            fp = _entry_fingerprint(z.getinfo(name))
            prev = failures.get(tag)
            if prev and prev.get("fp") == fp:
                failures[tag] = {"count": int(prev.get("count", 0)) + 1, "fp": fp}
            else:
                failures[tag] = {"count": 1, "fp": fp}
    with _MANIFEST_LOCK:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data["_failures"] = failures
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return True
        except Exception:
            return False

def exclude_failed_tags(tags, manifest_path, wot_path=""):
    """Filter out tags stuck in the consecutive-failure registry.

    A tag stays excluded only while its current fingerprint matches the one
    recorded at the failure — a new game version (fingerprint change) lifts
    the exclusion and grants a fresh attempt.
    """
    if not tags:
        return []
    fails = _manifest_failures(manifest_path)
    if not fails:
        return list(tags)
    pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg") if wot_path else ""
    fps = {}
    if pkg_path and os.path.exists(pkg_path):
        with zipfile.ZipFile(pkg_path, 'r') as z:
            for name in z.namelist():
                if not name.startswith("scripts/item_defs/vehicles/") or not name.endswith(".xml"):
                    continue
                if "common/" in name or "components/" in name or "list.xml" in name:
                    continue
                tag = os.path.splitext(os.path.basename(name))[0]
                if tag in tags:
                    fps[tag] = _entry_fingerprint(z.getinfo(name))
    out = []
    for t in tags:
        f = fails.get(t)
        if f is None:
            out.append(t)
            continue
        if int(f.get("count", 0)) < _FAIL_THRESHOLD:
            out.append(t)
            continue
        if fps and f.get("fp") != fps.get(t):
            out.append(t)  # fingerprint changed — new game version, fresh attempt
    return out


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

# ── Chrome profile handling ─────────────────────────
CHROME_COPY_DIR = os.path.join(tempfile.gettempdir(), "sm_wot_admin_chrome_profile")

_PROFILE_SKIP = shutil.ignore_patterns(
    "Cache", "Code Cache", "GPUCache", "DawnCache", "GraphiteDawnCache",
    "ShaderCache", "GrShaderCache", "component_crx_cache",
    "SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile",
    "Last Session", "Current Session", "Last Tabs", "Current Tabs",
    "Sessions", "Profile *", "Guest Profile",
)

# Failure classes worth retrying in _create_driver(). Chrome auto-updates
# often: a fresh major/binary can briefly lack a matching chromedriver
# (Selenium Manager then fails to resolve/download it) or stall session
# creation. All of these resolve themselves once Chrome's driver is
# published/network returns — a retry with a fresh profile copy is enough.
_DRIVER_RETRY_MARKERS = (
    "session not created",
    "This version of ChromeDriver only supports",
    "Could not obtain version",
    "Could not successfully connect to the driver manager",
    "Error communicating with the remote browser",
    "Local file not found",
    "se-manager",
)


def _kill_chrome_matching(pattern):
    """Force-kill chrome.exe processes whose command line contains ``pattern``.

    A failed Selenium session creation (DevToolsActivePort timeout / hand-off
    exit) can leave the spawned chrome.exe running and holding its profile
    directory. That leftover poisons every later run: the next session either
    times out the same way or dies with the fast 'Chrome instance exited'
    hand-off — one failure cascades until the zombie dies. Chrome processes
    started by the admin pipeline always carry the profile path in their
    command line; the user's own Chrome (started normally) does not.

    Bug 5 (02.09.2026 #1692): Stop-Process -Force is async on Windows — it
    sends WM_CLOSE / TerminateProcess and returns immediately, but the OS
    may take 50-500ms to actually release handles on profile files
    (Preferences, Local State, Login Data). The next shutil.copytree hits
    ERROR_SHARING_VIOLATION -> ignore_errors silently swallows it ->
    incomplete profile copy -> RuntimeError("missing Local State"). The same
    race window caused the 122/693 hang at admin.log:16:19:26.

    Fix: after Stop-Process, poll chrome.exe state via PowerShell every 200ms
    until either the process is gone OR the hard timeout (10s) elapses. Any
    subsequent shutil.rmtree/copytree then sees a fully released profile dir.
    """
    pat = pattern.replace("'", "''")
    q = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
         "Where-Object {{ $_.CommandLine -like '*{0}*' }} | "
         "ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}").format(pat)
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", q],
                       capture_output=True, timeout=20,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass
    # Poll for actual process exit (Stop-Process -Force is async).
    # Without this, a subsequent rmtree/copytree race with the dying
    # process hits WinError 183 silently via shutil.rmtree(ignore_errors=True).
    _wait_chrome_dead(pat, timeout=10, interval=0.2)


def _wait_chrome_dead(pattern, timeout=10, interval=0.2):
    """Poll for chrome.exe processes matching ``pattern`` to actually exit.

    Uses PowerShell Get-CimInstance Win32_Process (same source as the kill,
    so we get the same visibility) on a tight loop. Returns once the process
    is gone OR the timeout elapses. Always returns — callers should not
    block forever on a stuck AV or zombie.
    """
    pat = pattern.replace("'", "''")
    q = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
         "Where-Object {{ $_.CommandLine -like '*{0}*' }} | "
         "Select-Object -ExpandProperty ProcessId").format(pat)
    end_at = time.time() + timeout
    while time.time() < end_at:
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", q],
                               capture_output=True, timeout=5,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            output = (r.stdout or b"").decode("utf-8", errors="ignore").strip()
            if not output:
                return  # No matching process — we're done
        except Exception:
            return
        time.sleep(interval)
    # Timeout reached: process may still be exiting. Caller continues with
    # rmtree/copytree which has its own ignore_errors — graceful degradation.


def _copy_chrome_profile(src, dst):
    """Best-effort copy of the real Chrome profile for an isolated instance.

    Chrome running + real --user-data-dir → new chrome.exe hands off the URL to
    the running instance and exits → "session not created: Chrome instance
    exited" before any AI prompt. A fresh copy has no SingletonLock, so the
    driver keeps its own instance. Caches, lock files and session files are
    excluded (session files of the running Chrome would otherwise trigger the
    "restore pages?" crash-recovery bubble and a tab storm in the isolated
    instance); locked files are skipped (state only, non-critical).
    """
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    skipped = []
    try:
        shutil.copytree(src, dst, ignore=_PROFILE_SKIP)
    except shutil.Error as e:
        skipped = list(e.args[0]) if e.args else []
    for needed in ("Default", "Local State"):
        if not os.path.exists(os.path.join(dst, needed)):
            raise RuntimeError(f"Chrome profile copy incomplete: missing {needed} in {dst}")
    if skipped:
        print(f"[CHROME] {len(skipped)} locked files skipped during profile copy")
    return dst


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
    # ALWAYS drive an isolated copy of the profile, never the real one.
    # Chrome blocks remote debugging (--remote-debugging-port) on the default
    # user-data-dir: the browser starts but never writes DevToolsActivePort and
    # the session times out after 60s ("session not created: DevToolsActivePort
    # file doesn't exist"). A copy in %TEMP% is a non-default dir, so the
    # driver works with it whether Chrome is open or closed; the copy also
    # keeps the CAPTCHA-free login state of the user's Default profile.
    print("[CHROME] preparing isolated profile copy (never drives the real profile)")
    try:
        _kill_chrome_matching(CHROME_COPY_DIR)
        profile_dir = _copy_chrome_profile(CHROME_PROFILE, CHROME_COPY_DIR)
    except Exception as e:
        raise RuntimeError(
            f"Profile copy failed ({e}). Close Chrome and retry.") from e
    opts.add_argument(f"--user-data-dir={profile_dir}")
    opts.add_argument(f"--profile-directory={CHROME_PROFILE_DIR}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    # Off-screen window: the AI Mode session runs fully hidden (no visible
    # Chrome window above other apps). Position far outside the screen bounds.
    opts.add_argument("--window-position=-32000,-32000")
    opts.add_argument("--window-size=1400,900")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    last_err = None
    for attempt in (1, 2, 3):
        try:
            driver = webdriver.Chrome(options=opts)
            break
        except Exception as e:
            last_err = e
            msg = str(e)
            if not any(m in msg for m in _DRIVER_RETRY_MARKERS):
                raise
            delay = 3 if attempt < 3 else 15
            print(f"[CHROME] session creation attempt {attempt} failed ({msg[:100]});"
                  f" retrying in {delay}s with a fresh profile copy")
            # A failed session can leave the spawned chrome.exe alive and holding
            # the profile dir — the next attempt would repeat the same failure.
            # Kill leftovers, then rebuild a clean profile copy for the retry.
            _kill_chrome_matching(CHROME_COPY_DIR)
            try:
                if os.path.isdir(CHROME_COPY_DIR):
                    shutil.rmtree(CHROME_COPY_DIR, ignore_errors=True)
                profile_dir = _copy_chrome_profile(CHROME_PROFILE, CHROME_COPY_DIR)
            except Exception as e2:
                print(f"[CHROME] fresh profile copy for retry failed: {e2}")
            time.sleep(delay)
    else:
        raise RuntimeError(
            "Could not start the Chrome driver session after 3 attempts. "
            "Chrome was probably updated recently and the matching chromedriver "
            "is not published yet (or the network is down) — wait a few hours "
            "and retry. Last error: "
            f"{str(last_err)[:120]}") from last_err
    # Version log: instant diagnosis after any future Chrome update incident.
    try:
        bv = driver.capabilities.get("browserVersion", "?")
        cv = (driver.capabilities.get("chrome") or {}).get("chromedriverVersion", "?")
        print(f"[CHROME] session OK: chrome={bv} chromedriver={cv}")
    except Exception:
        pass
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

    # Navigate to Google AI Mode. The first navigation can race Chrome startup
    # on a freshly copied profile (document stuck at readyState=loading with an
    # empty page) — retry with a clean blank-page reset in between.
    selectors = [
        "textarea[jsname]",
        "textarea[aria-label]",
        "div[role='dialog'] textarea",
        "div.AgWCw textarea",
        "div.Txyg0d textarea",
        "textarea",
    ]
    textarea = None
    for attempt in range(1, 4):
        try:
            driver.get("about:blank")
        except Exception:
            pass
        driver.get("https://www.google.com/search?q=&udm=50")
        deadline = time.time() + 30
        while time.time() < deadline and textarea is None:
            # Page half-initialized state: textarea exists+enabled but the click
            # throws "element not interactable" (overlay/boot race on the fresh
            # profile copy). Only accept the input once the document is fully
            # loaded — the readyState gate replaces the old accept-and-click.
            try:
                if driver.execute_script("return document.readyState") != "complete":
                    time.sleep(1)
                    continue
            except Exception:
                time.sleep(1)
                continue
            for sel in selectors:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                    if el.is_enabled() and el.is_displayed():
                        textarea = el
                        break
                except:
                    continue
            if textarea is None:
                time.sleep(1)
        if textarea:
            break
        try:
            print(f"[AI] page load attempt {attempt} failed (readyState={driver.execute_script('return document.readyState')}), retrying...")
        except Exception:
            print(f"[AI] page load attempt {attempt} failed, retrying...")

    if not textarea:
        print("[AI] textarea not found!")
        return None

    # The page can still be settling (boot overlay / re-render) right after
    # readyState=complete, and the input node gets replaced during hydration —
    # a stale reference never becomes clickable. Re-query a displayed+enabled
    # input every attempt and click until it sticks (20s budget).
    clicked = False
    for _ in range(20):
        for sel in selectors:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_enabled() and el.is_displayed():
                    try:
                        el.click()
                        textarea = el
                        clicked = True
                        break
                    except Exception:
                        continue
            except:
                continue
        if clicked:
            break
        time.sleep(1)
    if not clicked:
        print("[AI] textarea never became interactive")
        return None
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

# ── Daily fill sweep for incomplete builds ──────────
def _normalize_crew_role(role):
    """Normalize a crew role name to the canonical base role(s) used by client data.

    Combined/secondary roles map to their primary slot: loader_radio -> loader + radioman,
    loader_2/gunner_2 -> loader/gunner, radioman_2 -> radioman.
    """
    r = str(role or "").lower()
    if "loader_radio" in r:
        return ("loader", "radioman")
    if "radio" in r:
        return ("radioman",)
    if "loader" in r:
        return ("loader",)
    if "gunner" in r:
        return ("gunner",)
    if "driver" in r:
        return ("driver",)
    if "commander" in r:
        return ("commander",)
    return (r,)

def strict_build_incomplete(tag, build_data):
    """Strict completeness check: every equipment/consumable loadout non-empty and every
    client crew role present with non-empty perks. Returns list of missing sections
    (e.g. ['equipment_2', 'crew:loader']) or [] when the build is fully filled."""
    missing = []
    for k in ("equipment_1", "equipment_2", "consumables_1", "consumables_2"):
        if not build_data.get(k):
            missing.append(k)
    build_roles = {}
    for member in (build_data.get("crew") or []):
        if not isinstance(member, (list, tuple)) or not member:
            continue
        role = member[0]
        perks = member[1] if len(member) > 1 else []
        for r in _normalize_crew_role(role):
            build_roles.setdefault(r, []).extend(perks or [])
    slots = getattr(_gp, "tank_slots", {}) or {}
    slots = slots.get(tag, {}) if isinstance(slots, dict) else {}
    expected = set()
    for role in (slots.get("crew_roles") or []):
        expected.update(_normalize_crew_role(role))
    for r in sorted(expected):
        if not build_roles.get(r):
            missing.append("crew:" + r)
    return missing

def scan_incomplete_builds():
    """Fetch all RTDB builds and return {tag: [missing sections]} for strictly incomplete ones.

    Івент-клони (_is_bad_tag) пропускаються — їх білди невидимі в застосунку,
    регенерація тільки відтворювала б розбіжність лічильників (#1604)."""
    all_builds = _get_json(_rtdb_url("builds/tanks")) or {}
    incomplete = {}
    for tag, entry in all_builds.items():
        if not isinstance(entry, dict):
            continue
        if _is_bad_tag(tag):
            continue
        missing = strict_build_incomplete(tag, entry.get("data", entry))
        if missing:
            incomplete[tag] = missing
    return incomplete

def _run_daily_sweep(wot_path=""):
    """Queue all strictly incomplete builds for regeneration via pending_updates/builds.
    Returns the list of queued tags (empty when nothing to fill)."""
    incomplete = scan_incomplete_builds()
    if not incomplete:
        print("[SWEEP] Daily fill sweep: no incomplete builds")
        return []
    queue = sorted(incomplete.keys())
    queue = exclude_failed_tags(queue, ".tank_extract_manifest.json", wot_path)
    if not queue:
        print("[SWEEP] Daily fill sweep: all incomplete builds are in the failure registry")
        return []
    _put_json(_rtdb_url("pending_updates/builds"), {
        "status": "generating",
        "queue": queue,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "message": f"Daily fill sweep: {len(queue)} incomplete builds",
    })
    print(f"[SWEEP] Daily fill sweep: {len(queue)} incomplete builds queued")
    for tag in queue:
        print(f"[SWEEP]   {tag}: {', '.join(incomplete[tag])}")
    return queue

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

def _tank_record_from_client(tag, wot_path):
    """Build a tank_db record for a tag missing from tank_db, from client scripts.pkg.

    Parses the nation's list.xml (BigWorld binary XML) via WotXmlParser and
    extracts level/tags/id/price — the same fields TankExtractor.build_database uses.
    Returns a record dict or None. Returns None without error when wot_path is unknown.
    """
    import xml.etree.ElementTree as ET
    from decode_xml import WotXmlParser

    if not wot_path:
        return None
    pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.exists(pkg_path):
        return None

    NATION_IDS = {
        "ussr": 0, "germany": 1, "usa": 2, "china": 3,
        "france": 4, "uk": 5, "japan": 6, "czech": 7,
        "sweden": 8, "poland": 9, "italy": 10,
    }
    tmp = os.path.join(tempfile.gettempdir(), f"admin_list_{tag}.xml")
    decoder = WotXmlParser()

    def _clean_xml(text):
        text = re.sub(r'<xmlns:xmlref>.*?</xmlns:xmlref>', '', text, flags=re.DOTALL)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+);)', '&amp;', text)
        text = re.sub(r'<(?![\w/!?-])', '&lt;', text)
        return text

    try:
        with zipfile.ZipFile(pkg_path, 'r') as z:
            list_names = [n for n in z.namelist()
                          if n.startswith("scripts/item_defs/vehicles/")
                          and n.endswith("/list.xml")]
            last_parse_err = None
            for entry in sorted(list_names):
                try:
                    raw = z.read(entry)
                except Exception:
                    continue
                with open(tmp, "wb") as f:
                    f.write(raw)
                try:
                    if not decoder.decode_file(tmp, tmp):
                        last_parse_err = f"{entry}: decode failed"
                        continue
                    with open(tmp, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                except Exception as e:
                    last_parse_err = f"{entry}: {e}"
                    continue
                try:
                    root = ET.fromstring(_clean_xml(text))
                except Exception as e:
                    last_parse_err = f"{entry}: {e}"
                    continue
                tank = None
                for child in root:
                    if child.tag == tag:
                        tank = child
                        break
                if tank is None:
                    continue
                level_text = tank.findtext("level", "")
                tags_text = tank.findtext("tags", "") or ""
                id_text = (tank.findtext("id", "") or "").strip()
                price_node = tank.find("price")
                is_premium_hint = (price_node is not None
                                   and "gold" in ET.tostring(price_node, encoding="unicode").lower())
                nation_base = entry.split("/")[3]
                nation_mapping = {"usa": "USA", "ussr": "USSR", "uk": "UK"}
                display_nation = nation_mapping.get(nation_base, nation_base.capitalize())
                nation_id = NATION_IDS.get(nation_base, -1)

                clean_name = re.sub(r'^[A-Z][a-z]?\d{1,3}_', '', tag)
                clean_name = clean_name.replace("_", " ")
                clean_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean_name)
                clean_name = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', clean_name)
                clean_name = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', clean_name)

                tags_text_l = tags_text.lower()
                v_class = "Unknown"
                if "lighttank" in tags_text_l: v_class = "LT"
                elif "mediumtank" in tags_text_l: v_class = "MT"
                elif "heavytank" in tags_text_l: v_class = "HT"
                elif "at-spg" in tags_text_l: v_class = "TD"
                elif "spg" in tags_text_l: v_class = "SPG"

                is_premium = bool(is_premium_hint)
                if "premium" in tags_text_l or "special" in tags_text_l:
                    is_premium = True

                compact_descr = None
                if nation_id >= 0 and id_text.isdigit():
                    compact_descr = (int(id_text) << 8) | (nation_id << 4) | 1

                try:
                    tier_val = int(level_text) if str(level_text).strip() else 0
                except Exception:
                    tier_val = 0

                return {
                    "name": clean_name,
                    "tier": tier_val,
                    "class": v_class,
                    "nation": display_nation,
                    "icon": f"{tag}.png".lower(),
                    "is_premium": is_premium,
                    "compact_descr": compact_descr,
                }
        # Tag not found in any nation list — if any list failed to parse, that is
        # the reason (a WG format change must surface loudly, not as a silent None).
        if last_parse_err:
            raise RuntimeError(f"list.xml parse failed: {last_parse_err}")
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
    return None


def _slots_and_crew_from_client(tag, wot_path):
    """Build tank_slots_full.json + crew_builds.json records for a tag missing from local data.

    Parses the vehicle's own XML in scripts.pkg (decoded via WotXmlParser):
    crew roles, supplySlots (equipment count + slot types), consumable slots,
    postProgressionTree, customRoleSlotOptions, optDevsOverrides.
    Returns (slots_rec, crew_rec) or (None, None).
    """
    from decode_xml import WotXmlParser

    if not wot_path:
        return (None, None)
    pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
    if not os.path.exists(pkg_path):
        return (None, None)

    tmp = os.path.join(tempfile.gettempdir(), f"admin_veh_{tag}.xml")
    decoder = WotXmlParser()
    try:
        with zipfile.ZipFile(pkg_path, 'r') as z:
            entry = None
            for n in z.namelist():
                if n.startswith("scripts/item_defs/vehicles/") and n.endswith(f"/{tag}.xml"):
                    entry = n
                    break
            if entry is None:
                return (None, None)
            raw = z.read(entry)
        with open(tmp, "wb") as f:
            f.write(raw)
        if not decoder.decode_file(tmp, tmp):
            return (None, None)
        with open(tmp, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return (None, None)
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass

    slots = {
        "crew_roles": [],
        "equipment_slots": 0,
        "consumable_slots": [],
        "available_equipment": [],
        "has_post_progression": False,
        "field_mods": [],
        "nation": "unknown",
    }
    nation = None
    if entry:
        parts = entry.split("/")
        if len(parts) >= 4:
            nation = parts[3]
    if nation:
        slots["nation"] = nation

    crew_block = re.search(r"<crew>(.*?)</crew>", content, re.DOTALL)
    roles = []
    if crew_block:
        roles = re.findall(r"<(\w+)\s*>.*?</\w+>", crew_block.group(1), re.DOTALL)
        roles = [r for r in roles if r in ("commander", "gunner", "driver", "loader", "radioman")]
    slots["crew_roles"] = roles

    supply_match = re.search(r"<supplySlots>([^<]+)", content)
    if supply_match:
        slot_list = supply_match.group(1).strip().split()
        equip_types = []
        consumables = []
        for s in slot_list:
            if s in ("6", "7", "8"):
                consumables.append(s)
            else:
                equip_types.append(s)
        slots["equipment_slots"] = len(equip_types)
        slots["consumable_slots"] = consumables
        if equip_types:
            slots["equipment_slot_types"] = [int(x) for x in equip_types]

    pp_match = re.search(r"<postProgressionTree>([^<]+)", content)
    if pp_match:
        slots["has_post_progression"] = True
        slots["post_progression_tree"] = pp_match.group(1).strip()

    opt_match = re.search(r"<optDevsOverrides>(.*?)</optDevsOverrides>", content, re.DOTALL)
    if opt_match:
        items = [m.group(1) for m in re.finditer(r"<([a-zA-Z_]+)>(.*?)</\1>", opt_match.group(1), re.DOTALL)
                 if "<" in m.group(2)]
        slots["available_equipment"] = sorted(set(items))

    crew_rec = {
        "crew_members": [],
        "crew": [],
        "custom_role_slot_options": None,
    }
    if crew_block:
        seen_roles = []
        for role in roles:
            member_text = re.search(rf"<{role}\s*>(.*?)</{role}>", crew_block.group(1), re.DOTALL)
            also = []
            if member_text:
                inner = member_text.group(1)
                for token in re.split(r"[\s,;/|]+", inner.strip()):
                    if token in ("commander", "gunner", "driver", "loader", "radioman") and token != role:
                        also.append(token)
            seen_roles.append(role)
            crew_rec["crew_members"].append({"role": role, "also": also})
            crew_rec["crew"].append(role)
    slot_match = re.search(r"<customRoleSlotOptions>\s*([^<]+?)\s*</customRoleSlotOptions>", content, re.DOTALL)
    if slot_match:
        crew_rec["custom_role_slot_options"] = re.sub(r"\s+", " ", slot_match.group(1)).strip()

    if not crew_rec["crew_members"]:
        crew_rec = None
    return (slots, crew_rec)


def _persist_client_tank_data(tag, db_rec, slots_rec, crew_rec):
    """Persist a client-derived tank record into the local data files (best-effort).

    Updates tank_db.json, tank_slots_full.json and crew_builds.json with the
    new tag so subsequent runs and admin rebuilds include the tank. Safe to call
    from frozen onedir builds (_BUNDLE_DIR files are writable but the update
    simply persists there; failures are ignored).
    """
    try:
        with open("tank_db.json", "r", encoding="utf-8") as f:
            tank_db = json.load(f)
        if isinstance(tank_db, dict):
            tank_db[tag] = db_rec
            with open("tank_db.json", "w", encoding="utf-8") as f:
                json.dump(tank_db, f, ensure_ascii=False, indent=4)
            print(f"[BUILD] {tag}: tank_db.json updated")
    except Exception as e:
        print(f"[WARN] tank_db.json persist failed: {e}")

    try:
        with open("tank_slots_full.json", "r", encoding="utf-8") as f:
            slots_all = json.load(f)
        if isinstance(slots_all, dict):
            slots_all[tag] = slots_rec
            with open("tank_slots_full.json", "w", encoding="utf-8") as f:
                json.dump(slots_all, f, ensure_ascii=False, indent=2)
            print(f"[BUILD] {tag}: tank_slots_full.json updated")
    except Exception as e:
        print(f"[WARN] tank_slots_full.json persist failed: {e}")

    if crew_rec:
        try:
            with open("crew_builds.json", "r", encoding="utf-8") as f:
                crew_all = json.load(f)
            if isinstance(crew_all, dict) and isinstance(crew_all.get("tanks"), dict):
                crew_all["tanks"][tag] = crew_rec
                with open("crew_builds.json", "w", encoding="utf-8") as f:
                    json.dump(crew_all, f, ensure_ascii=False, indent=4)
                print(f"[BUILD] {tag}: crew_builds.json updated")
        except Exception as e:
            print(f"[WARN] crew_builds.json persist failed: {e}")


def generate_builds(driver, tank_db, prompts, single_tag=None, force=False, queue=None, wot_path=None):
    """Generate builds for specified tanks.

    Returns (ok, done_tags, reasons): ok=True when at least one build was
    uploaded, done_tags is the list of tags actually uploaded to RTDB,
    reasons is {tag: "category: detail"} for every failed tag plus a
    "summary" entry — the failure reason must always reach the caller, it is
    never allowed to disappear into a bare False.
    """
    print("\n=== Generating Builds ===\n")

    all_tags_sorted = sorted(tank_db.keys(), key=lambda t: (tank_db[t].get("tier",0), tank_db[t].get("name","")))
    unknown = []
    reasons = {}
    if single_tag:
        if single_tag not in tank_db:
            try:
                rec = _tank_record_from_client(single_tag, wot_path)
                slots_rec, crew_rec = _slots_and_crew_from_client(single_tag, wot_path)
            except Exception as e:
                reasons[single_tag] = f"client_parse_fail: {e}"
                print(f"[BUILD] {single_tag}: {reasons[single_tag]}")
                return (False, [], reasons)
            if rec and slots_rec:
                tank_db[single_tag] = rec
                _gp.tank_db[single_tag] = rec
                _gp.tank_slots[single_tag] = slots_rec
                if crew_rec:
                    _gp.crew_builds['tanks'][single_tag] = crew_rec
                _persist_client_tank_data(single_tag, rec, slots_rec, crew_rec)
                print(f"[BUILD] {single_tag}: added from client scripts.pkg (tier {rec.get('tier')}, {rec.get('class')})")
            else:
                reasons[single_tag] = "unknown_tank: not found in DB or client scripts.pkg"
                print(f"[BUILD] {single_tag}: {reasons[single_tag]}")
                return (False, [], reasons)
        all_tags = [single_tag]
        total = 1
    elif queue is not None:
        all_tags = []
        for t in queue:
            if t in tank_db:
                all_tags.append(t)
            else:
                try:
                    rec = _tank_record_from_client(t, wot_path)
                    slots_rec, crew_rec = _slots_and_crew_from_client(t, wot_path)
                except Exception as e:
                    reasons[t] = f"client_parse_fail: {e}"
                    unknown.append(t)
                    continue
                if rec and slots_rec:
                    tank_db[t] = rec
                    _gp.tank_db[t] = rec
                    _gp.tank_slots[t] = slots_rec
                    if crew_rec:
                        _gp.crew_builds['tanks'][t] = crew_rec
                    _persist_client_tank_data(t, rec, slots_rec, crew_rec)
                    all_tags.append(t)
                    print(f"[BUILD] {t}: added from client scripts.pkg (tier {rec.get('tier')}, {rec.get('class')})")
                else:
                    reasons[t] = "unknown_tank: not found in DB or client scripts.pkg"
                    unknown.append(t)
        total = len(all_tags)
        print(f"[BUILD] Queue: {total} tanks from detection"
              + (f" (+{len(unknown)} unknown skipped: {', '.join(unknown)})" if unknown else ""))
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
        if unknown:
            reasons["summary"] = f"no tanks to generate — unknown in DB/client: {', '.join(unknown)}"
            print(f"[BUILD] {reasons['summary']}")
        else:
            print("[BUILD] All tanks already cached!")
        return (False, [], reasons)

    prog = ({"pass":1,"index":0,"retry":[],"ok_count":0,"fail_count":0}
            if single_tag or queue is not None
            else load_progress())
    ok_count = prog["ok_count"]
    fail_count = prog["fail_count"]
    start_idx = prog["index"]
    # Stale/out-of-range progress (e.g. from an older queue) must never silently
    # empty the run — fall back to the beginning.
    if start_idx >= len(all_tags):
        start_idx = 0
    to_process = all_tags[start_idx:]
    done_tags = []

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
            reasons[tag] = "no_prompt: generate_prompt returned nothing usable"
            print(f"    [FAIL] {reasons[tag]}")
            fail_count += 1
            retry_tags = [tag] + to_process[idx+1:]
            save_progress(prog["pass"], actual_idx+1, retry_tags, ok_count, fail_count)
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            continue

        # Submit to AI
        submit_err = None
        try:
            response = _submit_to_ai(driver, prompt, timeout=SELENIUM_TIMEOUT)
        except Exception as e:
            # Session died mid-run (e.g. Chrome updated/restarted externally,
            # OS killed the browser). Reconnect ONCE and retry the same tank so
            # the rest of the queue is not lost; a second failure just fails
            # this tank (it returns to the queue via save_progress).
            submit_err = str(e)
            print(f"    [RECONNECT] session died ({submit_err[:100]}); recreating driver...")
            try:
                driver.quit()
            except Exception:
                pass
            _kill_chrome_matching(CHROME_COPY_DIR)
            try:
                if os.path.isdir(CHROME_COPY_DIR):
                    shutil.rmtree(CHROME_COPY_DIR, ignore_errors=True)
            except Exception:
                pass
            driver = _create_driver()
            try:
                response = _submit_to_ai(driver, prompt, timeout=SELENIUM_TIMEOUT)
            except Exception as e2:
                submit_err = str(e2)
                print(f"    [RECONNECT] second attempt failed ({submit_err[:100]});"
                      f" failing tank {tag}")
                response = None
        if not response:
            reasons[tag] = "ai_no_response" + (f": {submit_err[:150]}" if submit_err else "")
            print(f"    [FAIL] {reasons[tag]}")
            fail_count += 1
            retry_tags = [tag] + to_process[idx+1:]
            save_progress(prog["pass"], actual_idx+1, retry_tags, ok_count, fail_count)
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            continue

        # Parse
        build_data = _parse_build_response(response)
        if not build_data or not _is_build_complete(build_data):
            reasons[tag] = "ai_parse_fail: no build or incomplete parse from AI response"
            print(f"    [FAIL] {reasons[tag]}")
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
                if _upload_prompt(tag, prompt):
                    save_prompt(tag, prompt)
            ok_count += 1
            done_tags.append(tag)
            save_progress(prog["pass"], actual_idx+1, to_process[idx+1:], ok_count, fail_count)
        else:
            reasons[tag] = "upload_fail: RTDB write rejected"
            print(f"    [FAIL] {reasons[tag]}")
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
        # Version/fingerprint advance only on actual uploads — failed runs must
        # not force every client into a full re-sync of unchanged data.
        if ok_count > 0:
            _update_builds_version()
        print(f"\n=== Done: {total_cached} cached (ok={ok_count}, fail={fail_count}) ===\n")

    # Every failure must reach the caller with its reason — reported to RTDB
    # error_reports (admin.html Errors) and embedded in the summary.
    if reasons:
        try:
            from firebase_reporter import report_fallback
            for tag, reason in list(reasons.items())[:5]:
                if tag == "summary":
                    continue
                report_fallback("admin_generation", tag, reason)
        except Exception:
            pass
        summary = "; ".join(f"{t}={r}" for t, r in list(reasons.items())[:5])
        if len(reasons) > 5:
            summary += f" (+{len(reasons)-5} more)"
        reasons["summary"] = summary
        print(f"[FAILED] {summary}")
    return (len(done_tags) > 0, done_tags, reasons)

# ─── Listen mode ────────────────────────────────────
def listen_mode(tank_db, wot_path=None):
    """Poll pending_updates and auto-generate. Periodically scan for game changes."""
    print(f"\n=== Listen Mode {'(WoT: ' + wot_path + ')' if wot_path else '(no WoT path)'} ===\n")
    _last_scan = -3600  # trigger initial scan immediately
    _last_wg = -21600  # trigger initial WG check immediately
    _last_sweep = -86400  # trigger initial fill sweep immediately

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

        # ── Daily incomplete-build fill sweep (every 24h) ──
        if now - _last_sweep > 86400:
            _last_sweep = now
            st = _get_json(_rtdb_url("pending_updates/builds"))
            admin_st = _get_json(_rtdb_url("admin_app/status"))
            admin_seen = _get_json(_rtdb_url("admin_app/last_seen")) or 0
            if st and st.get("status") == "generating":
                print("[SWEEP] skipped - builds generation in progress (pending)")
            elif admin_st == "generating" and int(now) - int(admin_seen) < 180:
                print("[SWEEP] skipped - admin app is generating builds")
            else:
                _run_daily_sweep(wot_path or "")

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
                ok, done_tags, reasons = generate_builds(driver, tank_db, prompts, force=(queue is None), queue=queue,
                                                         wot_path=wot_path)
                failed = [t for t in (queue or []) if t not in done_tags]
                try:
                    if failed:
                        update_manifest_failures(wot_path or "", ".tank_extract_manifest.json", failed)
                    if ok and done_tags:
                        update_manifest_for_tags(wot_path, ".tank_extract_manifest.json", done_tags)
                except Exception:
                    pass
                err_msg = reasons.get("summary") or "Generation failed" if reasons else "Generation failed"
                _update_pending_status("builds", "done" if ok else "error",
                    "Completed successfully" if ok else err_msg)
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
            generate_builds(driver, tank_db, prompts, single_tag=single_tag, wot_path=args.wot_path)
        else:
            parser.print_help()
    finally:
        driver.quit()
        print("\nDone.")

if __name__ == "__main__":
    main()
