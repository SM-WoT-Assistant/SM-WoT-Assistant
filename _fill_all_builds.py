#!/usr/bin/env python3
"""Fill AI build cache for ALL tanks (~931) with 25-35s random delay.
Retries failed tanks in subsequent passes until all are cached.
Progress saved to _fill_progress.json for crash recovery.
"""
import os, sys, json, time, subprocess, re, random

def _safe(s):
    return s.encode('ascii', errors='replace').decode('ascii')

# Wrap print to handle encoding issues
_orig_print = print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    safe_args = [_safe(str(a)) if isinstance(a, str) else a for a in args]
    _orig_print(*safe_args, **kwargs)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_prompt_v2 import generate_prompt
from stats_ai import _save_ai_build_cache, _load_ai_build_cache

_PROGRESS = "_fill_progress.json"

# --- helpers ---
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
    if os.path.exists(_PROGRESS):
        with open(_PROGRESS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"pass": 1, "index": 0, "retry": [], "ok_count": 0, "fail_count": 0}

def save_progress(pass_num, idx, retry, ok_c, fail_c):
    with open(_PROGRESS, "w", encoding="utf-8") as f:
        json.dump({"pass": pass_num, "index": idx, "retry": retry,
                    "ok_count": ok_c, "fail_count": fail_c}, f)

def launch_ai(tag, prompt):
    """Launch ai_webview_gui.py with prompt, return (success, lines)."""
    script = os.path.join(os.path.dirname(__file__), "ai_webview_gui.py")
    cmd = [sys.executable, script, "--prompt", prompt]
    try:
        proc = subprocess.Popen(cmd, cwd=os.path.dirname(__file__),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding='utf-8', errors='replace')
        response_lines = []
        ok = False
        for line in proc.stdout:
            line = line.strip()
            if 'RESPONSE_READY' in line:
                ok = True
                break
            if line and not line.startswith('[AI Browser]'):
                response_lines.append(line)
        if proc.poll() is None:
            try: proc.terminate(); proc.wait(timeout=5)
            except: pass
        return ok, response_lines
    except Exception as e:
        try: proc.terminate(); proc.wait(timeout=3)
        except: pass
        return False, [str(e)]

def parse_build(text):
    """Mirrors stats_ai._parse_ai_tank_build"""
    idx = text.rfind('Build Generated:')
    if idx >= 0:
        text = text[idx:]
    loadout1_eq, loadout2_eq = [], []
    loadout1_cons, loadout2_cons = [], []
    ammo1, ammo2 = [], []
    crew, field_mods = [], []
    section = None
    from stats_data import EQUIP_MAP, CONS_MAP, CREW_SKILL_MAP

    def ci(name):
        n = name.strip().strip('*').strip()
        nl = n.lower()
        for ek, ev in EQUIP_MAP.items():
            if nl == ek.lower(): return ev
        for ck, cv in CONS_MAP.items():
            if nl == ck.lower(): return cv
        best_val, best_len = None, 0
        for ek, ev in EQUIP_MAP.items():
            ekl = ek.lower()
            if ekl in nl or nl in ekl:
                if len(ek) > best_len: best_val, best_len = ev, len(ek)
        if best_val: return best_val
        for ck, cv in CONS_MAP.items():
            ckl = ck.lower()
            if ckl in nl or nl in ckl:
                if len(ck) > best_len: best_val, best_len = cv, len(ck)
        if best_val: return best_val
        return n.lower().replace(' ','').replace('-','')

    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        ll = line.lower()
        if 'slot' not in ll:
            if ('equipment' in ll and ('loadout' in ll or ':' in ll)):
                section = 'eq'; continue
            elif 'ammo' in ll and ('loadout' in ll or ':' in ll):
                section = 'ammo'; continue
            elif 'consumables' in ll and ('loadout' in ll or ':' in ll):
                section = 'cons'; continue
            elif ('crew' in ll and 'perks' in ll) or ('perks' in ll and ('commander' in ll or ':' in ll)):
                section = 'crew'; continue
            elif ('field' in ll and ('mod' in ll or 'modification' in ll)) or 'level' in ll:
                section = 'fm'

        if section == 'eq':
            if 'loadout 1' in ll or 'main' in ll:
                s = re.findall(r'Slot\s+\d+:\s*([^|]+)', line)
                if s: loadout1_eq = [ci(x) for x in s[:3]]
            elif 'loadout 2' in ll or 'advanced' in ll:
                s = re.findall(r'Slot\s+\d+:\s*([^|]+)', line)
                if s: loadout2_eq = [ci(x) for x in s[:3]]
        elif section == 'ammo':
            if 'loadout 1' in ll or 'main' in ll:
                t = re.findall(r'([A-Z_]+)\s*:', line)
                if t: ammo1 = t[:3]
            elif 'loadout 2' in ll or 'advanced' in ll:
                t = re.findall(r'([A-Z_]+)\s*:', line)
                if t: ammo2 = t[:3]
        elif section == 'cons':
            if 'loadout 1' in ll or 'main' in ll:
                s = re.findall(r'Slot\s+\d+:\s*([^|]+)', line)
                if s: loadout1_cons = [ci(x) for x in s[:3]]
            elif 'loadout 2' in ll or 'advanced' in ll:
                s = re.findall(r'Slot\s+\d+:\s*([^|]+)', line)
                if s: loadout2_cons = [ci(x) for x in s[:3]]
        elif section == 'crew':
            m = re.match(r'\s*(?:\*|[─└├│\->]+\s*)?\s*([\w\-]+(?:\s*-\s*\w+)?)(?:\s*\([^)]*\))?\s*:\s*(.+)', line)
            if m:
                role = m.group(1).strip().lower().replace(' ','_').replace('-','_')
                if role == 'loader_radioman': role = 'loader_radio'
                st = re.sub(r'^\s*\((?:primary|secondary)[^)]*\)\s*:\s*', '', m.group(2))
                st = re.sub(r'\s*\(choose\s+\d+\)\s*$', '', st).strip('[]')
                skills = [s.strip() for s in st.split(',') if s.strip()]
                mapped = []
                for s in skills:
                    sl = s.lower()
                    found = False
                    for sk, sv in CREW_SKILL_MAP.items():
                        if sl == sk.lower(): mapped.append(sv); found = True; break
                    if found: continue
                    best_val, best_len = None, 0
                    for sk, sv in CREW_SKILL_MAP.items():
                        skl = sk.lower()
                        if skl in sl or sl in skl:
                            if len(sk) > best_len: best_val, best_len = sv, len(sk)
                    mapped.append(best_val if best_val else sl.replace(' ','').replace('-',''))
                crew.append((role, mapped[:6]))
        elif section == 'fm':
            if 'level' in ll:
                for p in line.split('|'):
                    if ':' in p:
                        field_mods.append(p.split(':')[1].strip().lower().replace(' ',''))

    return {
        'equipment_1': loadout1_eq, 'equipment_2': loadout2_eq,
        'consumables_1': loadout1_cons, 'consumables_2': loadout2_cons,
        'ammo': ammo1 or ammo2, 'crew': crew if crew else None,
        'field_mods': field_mods,
    }

# --- main ---
def main():
    print("="*60, flush=True)
    print("FILL ALL AI BUILDS", flush=True)
    print("="*60, flush=True)
    print(flush=True)

    db = load_tank_db()
    all_tags = sorted(db.keys(), key=lambda t: (db[t].get("tier",0), db[t].get("name","")))
    total = len(all_tags)
    print(f"[DB] {total} tanks", flush=True)

    existing, _, _ = _load_ai_build_cache()
    cached_before = len(existing)
    print(f"[CACHE] {cached_before} already cached", flush=True)
    print(flush=True)

    prog = load_progress()
    pass_num = prog["pass"]
    retry_tags = prog["retry"]
    ok_count = prog["ok_count"]
    fail_count = prog["fail_count"]
    start_idx = prog["index"]

    # Build current pass queue
    existing_now, _, _ = _load_ai_build_cache()
    if pass_num == 1:
        to_process = [t for t in all_tags if t not in existing_now]
    else:
        to_process = retry_tags if retry_tags else [t for t in all_tags if t not in existing_now]

    # Sort processing list: tier asc, name asc
    to_process.sort(key=lambda t: (db[t].get("tier",0), db[t].get("name","")))

    # If resuming, fast-forward to start_idx
    if start_idx > 0:
        if start_idx < len(to_process):
            print(f"[RESUME] pass {pass_num}, index {start_idx}/{len(to_process)}", flush=True)
        else:
            # Already past this pass, start fresh
            pass_num += 1
            to_process = [t for t in all_tags if t not in existing_now]
            start_idx = 0
            ok_count = 0
            fail_count = 0
            print(f"[SKIP] pass {pass_num}, {len(to_process)} remaining", flush=True)
    else:
        print(f"[PASS {pass_num}] {len(to_process)} tanks", flush=True)

    print(flush=True)

    MAX_PASSES = 5
    STALL_SEC = 1200  # 20 minutes
    last_ok_time = time.time()

    while pass_num <= MAX_PASSES:
        if not to_process:
            existing_now, _, _ = _load_ai_build_cache()
            uncached = [t for t in all_tags if t not in existing_now]
            if not uncached:
                break
            pass_num += 1
            if pass_num > MAX_PASSES:
                break
            to_process = uncached
            start_idx = 0
            ok_count = 0
            fail_count = 0
            print(f"\n=== PASS {pass_num}: {len(to_process)} remaining ===\n", flush=True)

        for idx, tag in enumerate(to_process):
            if idx < start_idx:
                continue

            # Skip if already cached (another pass might have done it)
            existing_now, _, _ = _load_ai_build_cache()
            if tag in existing_now:
                save_progress(pass_num, idx+1, to_process[idx+1:], ok_count, fail_count)
                continue

            data = db[tag]
            tier = data.get("tier", 0)
            tank_name = data.get("name", tag)
            print(f"  [{pass_num}.{idx+1}/{len(to_process)}] Tier {tier} — {tank_name} [{tag}]", flush=True)

            prompt = generate_prompt(tag, tank_name)
            if not prompt:
                print(f"    SKIP: no prompt", flush=True)
                save_progress(pass_num, idx+1, to_process[idx+1:], ok_count, fail_count)
                delay = random.uniform(25, 35)
                print(f"    Wait {delay:.0f}s...", flush=True)
                time.sleep(delay)
                continue
            if 'not found' in prompt or len(prompt) < 50:
                print(f"    SKIP: tank data missing ({len(prompt)} chars)", flush=True)
                save_progress(pass_num, idx+1, to_process[idx+1:], ok_count, fail_count)
                delay = random.uniform(25, 35)
                print(f"    Wait {delay:.0f}s...", flush=True)
                time.sleep(delay)
                continue

            start = time.time()
            success, lines = launch_ai(tag, prompt)
            elapsed = time.time() - start

            combined = '\n'.join(lines) if lines else ''
            build_data = parse_build(combined) if success and len(lines) >= 3 and 'Build Generated:' in combined else None

            if build_data and build_data.get('equipment_1'):
                _save_ai_build_cache(tag, build_data, fail_count=0)
                print(f"    [OK] ({elapsed:.0f}s)", flush=True)
                ok_count += 1
                last_ok_time = time.time()
                save_progress(pass_num, idx+1, to_process[idx+1:], ok_count, fail_count)
            else:
                reason = "parse fail" if success else f"no response ({len(lines)} lines)"
                print(f"    [FAIL] {reason} ({elapsed:.0f}s)", flush=True)
                fail_count += 1
                # Push this tag to retry list for next pass
                retry_tags = [tag] + to_process[idx+1:]
                save_progress(pass_num, idx+1, retry_tags, ok_count, fail_count)

            # Check stall (no successful build in 20 min)
            if time.time() - last_ok_time > STALL_SEC:
                existing_now, _, _ = _load_ai_build_cache()
                uncached = [t for t in all_tags if t not in existing_now]
                print(f"\n[STALL] No success for 20 min. {len(uncached)} uncached.", flush=True)
                break

            # Random delay 25-35s (even on failure, to avoid Google detection)
            delay = random.uniform(25, 35)
            print(f"    Wait {delay:.0f}s...", flush=True)
            time.sleep(delay)

        # End of pass
        existing_now, _, _ = _load_ai_build_cache()
        total_cached = len(existing_now)
        print(f"\n=== PASS {pass_num}: {total_cached}/{total} cached (ok={ok_count}, fail={fail_count}) ===\n", flush=True)

        if total_cached >= total:
            break

        pass_num += 1
        if pass_num > MAX_PASSES:
            print(f"[STOP] Reached max {MAX_PASSES} passes", flush=True)
            break

        uncached = [t for t in all_tags if t not in existing_now]
        to_process = uncached
        start_idx = 0
        ok_count = 0
        fail_count = 0
        save_progress(pass_num, 0, uncached, 0, 0)
        print(f"[NEXT PASS {pass_num}] {len(uncached)} uncached tanks\n", flush=True)

    # --- final ---
    existing_now, _, _ = _load_ai_build_cache()
    total_cached = len(existing_now)
    print(f"\n{'='*60}", flush=True)
    if total_cached >= total:
        print(f"ALL DONE: {total_cached}/{total} tanks cached!", flush=True)
    else:
        uncached = [t for t in all_tags if t not in existing_now]
        print(f"PARTIAL: {total_cached}/{total} cached, {len(uncached)} remaining", flush=True)
        print(f"Uncached ({len(uncached)}): {', '.join(uncached[:30])}", flush=True)
        if len(uncached) > 30:
            print(f"... and {len(uncached)-30} more", flush=True)
    print(f"{'='*60}", flush=True)

if __name__ == "__main__":
    main()
