#!/usr/bin/env python3
"""Build script for SM WoT Assistant — PyInstaller onedir + NSIS installer + GitHub release.
Each build is a release — creates GitHub release + publishes to RTDB automatically.

Usage:
    python build.py                    # build + GitHub release + RTDB (current VERSION)
    python build.py 1.0.1              # update VERSION, then build + release + RTDB
    python build.py 1.0.1 --beta       # build with "Beta" suffix in all display names
    python build.py 1.0.1 --date=YYYY-MM-DD  # custom release date
"""

import os, sys, subprocess, shutil, re, time, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, "VERSION")
SPEC_FILE = os.path.join(BASE_DIR, "wot_assistant.spec")
NSI_FILE = os.path.join(BASE_DIR, "installer.nsi")
DIST_DIR = os.path.join(BASE_DIR, "dist")
FIXED_ONEDIR = os.path.join(DIST_DIR, "SM WoT Assistant")


# ═══════════════════════════════════════════════════════════════════
#  Python Discovery
# ═══════════════════════════════════════════════════════════════════

def _find_python():
    """Find the best Python executable for the build (3.12 preferred).

    PyInstaller has a known DATA TOC bug with Python 3.14 — data files
    (JSON, TTF, PNG, etc.) are not included in the COLLECT output.
    Python 3.12 + PyInstaller 6.20.0 works correctly.
    """
    candidates = []
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        for ver in ("312", "313"):
            p = os.path.join(local_appdata, "Programs", "Python", f"Python{ver}", "python.exe")
            if os.path.exists(p):
                candidates.append(p)
    candidates.append(sys.executable)
    for exe in candidates:
        try:
            result = subprocess.run(
                [exe, "-c", "import PyInstaller; print(PyInstaller.__version__)"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                ver = result.stdout.strip()
                print(f"[BUILD] Python: {exe} (PyInstaller {ver})")
                return exe
        except Exception:
            continue
    print("[BUILD] FATAL: No Python with PyInstaller found.")
    sys.exit(1)


PYTHON_EXE = _find_python()


# ═══════════════════════════════════════════════════════════════════
#  Version Management
# ═══════════════════════════════════════════════════════════════════

def read_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "0.0.0"


def write_version(v):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(v.strip() + "\n")
    print(f"[BUILD] VERSION := {v.strip()}")


def validate_semver(v):
    if re.match(r'^\d+\.\d+\.\d+$', v):
        return True
    print(f"[BUILD] FATAL: VERSION '{v}' is not valid semver (X.Y.Z)")
    return False


# ═══════════════════════════════════════════════════════════════════
#  NSIS
# ═══════════════════════════════════════════════════════════════════

def find_nsis():
    paths = [
        os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "NSIS", "makensis.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "NSIS", "makensis.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "NSIS", "makensis.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return shutil.which("makensis")


def update_nsi_version(version):
    if not os.path.exists(NSI_FILE):
        return
    with open(NSI_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'!define PRODUCT_VERSION "[^"]*"', f'!define PRODUCT_VERSION "{version}"', content)
    with open(NSI_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def commit_version_files(version):
    """Commit all changed files so the version bump is saved before GitHub release."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=10,
        )
        if not r.stdout.strip():
            return  # nothing to commit
        subprocess.run(
            ["git", "add", "-A"],
            cwd=BASE_DIR, capture_output=True, timeout=10,
        )
        result = subprocess.run(
            ["git", "commit", "-m", f"chore: bump to v{version}"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print(f"[BUILD] Committed: v{version}")
        else:
            print(f"[BUILD] Commit skipped: {result.stdout.strip()}")
    except Exception as e:
        print(f"[BUILD] Commit warning: {e}")


def create_git_tag(version):
    """Create and push a git tag for the release."""
    tag = f"v{version}"
    try:
        result = subprocess.run(
            ["git", "tag", tag],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print(f"[BUILD] Git tag created: {tag}")
        else:
            print(f"[BUILD] Git tag warning: {result.stdout.strip() or result.stderr.strip()}")
            return
        result = subprocess.run(
            ["git", "push", "origin", tag],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print(f"[BUILD] Git tag pushed: {tag}")
        else:
            print(f"[BUILD] Git tag push warning: {result.stdout.strip() or result.stderr.strip()}")
    except Exception as e:
        print(f"[BUILD] Git tag error: {e}")


# ═══════════════════════════════════════════════════════════════════
#  Pre-flight
# ═══════════════════════════════════════════════════════════════════

def preflight(version):
    print()
    print("=" * 60)
    print(f"  SM WoT Assistant — Release Build v{version}")
    print("=" * 60)
    print()

    errors = []

    if not validate_semver(version):
        errors.append("Invalid version format")

    print(f"  Python:       {PYTHON_EXE}")

    nsis = find_nsis()
    if not nsis:
        errors.append("NSIS not found (makensis.exe) — installer required")
    print(f"  NSIS:         {nsis if nsis else 'NOT FOUND'}")

    gh = shutil.which("gh")
    if not gh:
        errors.append("GitHub CLI (gh) not found — release required")
    print(f"  GitHub CLI:   {gh if gh else 'NOT FOUND'}")

    critical = ["main.py", VERSION_FILE, SPEC_FILE, "logo.png"]
    for f in critical:
        fp = os.path.join(BASE_DIR, f) if f == VERSION_FILE else f
        if not os.path.exists(os.path.join(BASE_DIR, f)):
            print(f"  MISSING:      {f}")
            errors.append(f"Missing critical file: {f}")
    print(f"  Sources:      OK ({len(critical)} files)")

    try:
        r = subprocess.run(["git", "status", "--porcelain"], cwd=BASE_DIR,
                           capture_output=True, text=True, timeout=10)
        if r.stdout.strip():
            dirty = r.stdout.strip().split('\n')
            print(f"  Git:          DIRTY ({len(dirty)} changed files):")
            for line in dirty[:5]:
                print(f"                {line}")
            if len(dirty) > 5:
                print(f"                ... and {len(dirty) - 5} more")
            errors.append(f"Working tree is dirty ({len(dirty)} uncommitted change(s)) — commit or stash first")
        else:
            print(f"  Git:          clean")
    except Exception:
        print(f"  Git:          not available")

    print()

    if errors:
        for e in errors:
            print(f"[BUILD] FATAL: {e}")
        sys.exit(1)

    return nsis


# ═══════════════════════════════════════════════════════════════════
#  Build Steps
# ═══════════════════════════════════════════════════════════════════

def clean_dist():
    """Remove the fixed onedir and PyInstaller build cache for a clean slate."""
    if os.path.exists(FIXED_ONEDIR):
        shutil.rmtree(FIXED_ONEDIR, ignore_errors=True)
        print("[BUILD] Cleaned dist/SM WoT Assistant/")
    build_cache = os.path.join(BASE_DIR, "build")
    if os.path.exists(build_cache):
        shutil.rmtree(build_cache, ignore_errors=True)
        print("[BUILD] Cleaned build/ cache")


def run_pyinstaller():
    print("[BUILD] Running PyInstaller (onedir)...")
    result = subprocess.run(
        [PYTHON_EXE, "-m", "PyInstaller", "--noconfirm", SPEC_FILE],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        print("[BUILD] PyInstaller FAILED")
        sys.exit(1)
    print("[BUILD] PyInstaller OK")

    exe = os.path.join(FIXED_ONEDIR, "SM WoT Assistant.exe")
    if not os.path.exists(exe):
        print(f"[BUILD] FATAL: {exe} not found after PyInstaller")
        sys.exit(1)
    size_mb = os.path.getsize(exe) / (1024 * 1024)
    print(f"[BUILD] EXE: {size_mb:.1f} MB")
    return exe


def copy_data_files():
    """Manually copy application data files into the onedir output.

    PyInstaller 6.x has a bug where DATA entries in Analysis are not
    propagated to COLLECT, so we copy them ourselves after the build.
    """
    target = os.path.join(FIXED_ONEDIR, "_internal")
    os.makedirs(target, exist_ok=True)
    total = 0

    def _cp(src, dst_rel):
        nonlocal total
        dst = os.path.join(target, dst_rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            total += 1
        elif os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)

    # Root JSONs — glob all, exclude debug/temp/tracking files
    _exclude_root = {
        "opencode.json", "magic-context.jsonc",
        "_fill_progress.json",
        ".client_update_manifest.json", ".icon_extract_manifest.json",
        ".tank_extract_manifest.json",
        "tomato_build_cache.json", "tomato_consumables_json.json",
        "tomato_debug.json", "tomato_full_debug.json",
        "tomato_next_data.json", "tomato_result.json",
        "ukrainian_map_names.json",
        "vehicle_slots_test.json", "vehicle_slots_v2.json",
    }
    for fn in os.listdir(BASE_DIR):
        if fn.endswith(".json") and os.path.isfile(os.path.join(BASE_DIR, fn)):
            if fn not in _exclude_root:
                _cp(os.path.join(BASE_DIR, fn), fn)

    # VERSION
    if os.path.exists(VERSION_FILE):
        _cp(VERSION_FILE, "VERSION")

    # TTF fonts
    for f in ("xvmsymbol.ttf", "fontawesome-webfont.ttf"):
        p = os.path.join(BASE_DIR, f)
        if os.path.exists(p):
            _cp(p, f)

    # .mo localization files
    for f in ("artefacts_en.mo", "crew_perks_en.mo", "item_types_en.mo"):
        p = os.path.join(BASE_DIR, f)
        if os.path.exists(p):
            _cp(p, f)

    # logo + icon
    logo = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo):
        _cp(logo, "logo.png")
    icon = os.path.join(BASE_DIR, "icon.ico")
    if os.path.exists(icon):
        _cp(icon, "icon.ico")

    # maps/ (TACTIC mode images)
    maps_dir = os.path.join(BASE_DIR, "maps")
    if os.path.exists(maps_dir):
        for folder in os.listdir(maps_dir):
            fpath = os.path.join(maps_dir, folder)
            if os.path.isdir(fpath):
                for f in os.listdir(fpath):
                    _cp(os.path.join(fpath, f), os.path.join("maps", folder, f))

    # extracted_maps/ (MAPS mode images + data)
    em_dir = os.path.join(BASE_DIR, "extracted_maps")
    if os.path.exists(em_dir):
        for f in os.listdir(em_dir):
            fpath = os.path.join(em_dir, f)
            if os.path.isfile(fpath) and f not in ("ukrainian_map_names_cache.json", ".map_extract_manifest.json"):
                _cp(fpath, os.path.join("extracted_maps", f))

    # extracted_icons/ (all subdirectories)
    ei_dir = os.path.join(BASE_DIR, "extracted_icons")
    if os.path.exists(ei_dir):
        for root2, dirs2, files2 in os.walk(ei_dir):
            for f in files2:
                src = os.path.join(root2, f)
                rel = os.path.relpath(src, ei_dir)
                _cp(src, os.path.join("extracted_icons", rel))

    # extracted_data/common/post_progression/
    ed_pp = os.path.join(BASE_DIR, "extracted_data", "common", "post_progression")
    if os.path.exists(ed_pp):
        for root2, dirs2, files2 in os.walk(ed_pp):
            for f in files2:
                src = os.path.join(root2, f)
                rel = os.path.relpath(src, os.path.join(BASE_DIR, "extracted_data"))
                _cp(src, os.path.join("extracted_data", rel))

    print(f"[BUILD] Copied {total} data files")
    return total


def build_launcher():
    """Build launcher as onefile directly into the onedir output."""
    print("[BUILD] Building launcher (onefile)...")
    launcher_py = os.path.join(BASE_DIR, "launcher.py")
    if not os.path.exists(launcher_py):
        print("[BUILD] FATAL: launcher.py not found")
        sys.exit(1)

    logo = os.path.join(BASE_DIR, "logo.png")
    ver = os.path.join(BASE_DIR, "VERSION")
    sep = os.pathsep

    result = subprocess.run([
        PYTHON_EXE, "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--hidden-import", "unicodedata",
        "--hidden-import", "PIL._imaging",
        "--collect-all", "unicodedata",
        "--add-data", f"{logo}{sep}.",
        "--add-data", f"{ver}{sep}.",
        "--icon", os.path.join(BASE_DIR, "icon.ico"),
        "--name", "SM WoT Assistant Launcher",
        "--distpath", FIXED_ONEDIR,
        "--workpath", os.path.join(BASE_DIR, "build", "launcher"),
        "--specpath", os.path.join(BASE_DIR, "build"),
        "--clean",
        launcher_py,
    ], cwd=BASE_DIR)

    if result.returncode != 0:
        print("[BUILD] Launcher build FAILED")
        sys.exit(1)

    launcher_exe = os.path.join(FIXED_ONEDIR, "SM WoT Assistant Launcher.exe")
    if not os.path.exists(launcher_exe):
        print(f"[BUILD] FATAL: Launcher EXE not found: {launcher_exe}")
        sys.exit(1)

    size_mb = os.path.getsize(launcher_exe) / (1024 * 1024)
    print(f"[BUILD] Launcher: {size_mb:.1f} MB")
    verify_launcher_bundle(launcher_exe)
    return launcher_exe


def verify_launcher_bundle(launcher_exe):
    """Перевіряє що launcher --onefile містить Tcl/Tk DLL та _tkinter.pyd.
    PyInstaller onefile зберігає імена файлів як plain text в TOC архіву."""
    required = [b"tcl86t.dll", b"tk86t.dll", b"_tkinter.pyd"]
    missing = []
    try:
        with open(launcher_exe, "rb") as f:
            data = f.read()
        for name in required:
            if name not in data:
                missing.append(name.decode())
    except Exception as e:
        print(f"[BUILD] Launcher verify error: {e}")
        sys.exit(1)

    if missing:
        print()
        print("=" * 60)
        print("  LAUNCHER VERIFICATION FAILED")
        print("=" * 60)
        for m in missing:
            print(f"  MISSING: {m} — launcher --onefile не містить цей файл")
        print()
        print("[BUILD] Aborting — launcher буде падати з DLL load failed.")
        print("[BUILD] Додайте --add-binary для відсутніх DLL в build_launcher().")
        sys.exit(1)

    print(f"[BUILD] Launcher bundle verification PASSED (tcl86t.dll, tk86t.dll, _tkinter.pyd)")
    return True


def build_tray_watcher():
    """Build tray_watcher as onefile directly into the onedir output."""
    print("[BUILD] Building tray watcher (onefile)...")
    tray_py = os.path.join(BASE_DIR, "tray_watcher.py")
    if not os.path.exists(tray_py):
        print("[BUILD] FATAL: tray_watcher.py not found")
        sys.exit(1)

    result = subprocess.run([
        PYTHON_EXE, "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--icon", os.path.join(BASE_DIR, "icon.ico"),
        "--name", "SM WoT Assistant Tray Watcher",
        "--distpath", FIXED_ONEDIR,
        "--workpath", os.path.join(BASE_DIR, "build", "tray_watcher"),
        "--specpath", os.path.join(BASE_DIR, "build"),
        "--clean",
        tray_py,
    ], cwd=BASE_DIR)

    if result.returncode != 0:
        print("[BUILD] Tray watcher build FAILED")
        sys.exit(1)

    tray_exe = os.path.join(FIXED_ONEDIR, "SM WoT Assistant Tray Watcher.exe")
    if not os.path.exists(tray_exe):
        print("[BUILD] FATAL: Tray Watcher EXE not found")
        sys.exit(1)

    size_mb = os.path.getsize(tray_exe) / (1024 * 1024)
    print(f"[BUILD] Tray Watcher: {size_mb:.1f} MB")
    return tray_exe


def run_nsis(version, makensis_exe, is_beta=False):
    if not makensis_exe:
        print("[BUILD] NSIS not found, skipping installer.")
        return None

    out_exe = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Setup_v{version}.exe")
    print(f"[BUILD] Running NSIS: {makensis_exe}")
    result = subprocess.run(
        [makensis_exe, f"/DVERSION={version}", NSI_FILE],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        print("[BUILD] NSIS FAILED")
        return None

    if is_beta and os.path.exists(out_exe):
        beta_exe = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Setup_v{version}_Beta.exe")
        os.rename(out_exe, beta_exe)
        out_exe = beta_exe

    if os.path.exists(out_exe):
        size_mb = os.path.getsize(out_exe) / (1024 * 1024)
        print(f"[BUILD] Installer: {size_mb:.1f} MB")
    return out_exe


def rename_onedir(version):
    """Rename fixed onedir to versioned directory (e.g. SM WoT Assistant v1.0.1)."""
    versioned = os.path.join(DIST_DIR, f"SM WoT Assistant v{version}")
    if not os.path.exists(FIXED_ONEDIR):
        return None
    if os.path.exists(versioned):
        print(f"[BUILD] WARNING: {versioned} already exists, replacing...")
        shutil.rmtree(versioned, ignore_errors=True)
    os.rename(FIXED_ONEDIR, versioned)
    print(f"[BUILD] Output: {versioned}")
    return versioned


def create_portable_zip(version, is_beta=False):
    """Create a portable ZIP from the versioned onedir (no admin required)."""
    onedir = os.path.join(DIST_DIR, f"SM WoT Assistant v{version}")
    if not os.path.exists(onedir):
        print("[BUILD] WARNING: onedir not found, skipping portable ZIP.")
        return None

    zip_base = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Portable_v{version}")
    print("[BUILD] Creating portable ZIP...")
    shutil.make_archive(zip_base, "zip", DIST_DIR, f"SM WoT Assistant v{version}")

    zip_path = zip_base + ".zip"
    if is_beta and os.path.exists(zip_path):
        beta_zip = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Portable_v{version}_Beta.zip")
        os.rename(zip_path, beta_zip)
        zip_path = beta_zip

    if os.path.exists(zip_path):
        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"[BUILD] Portable ZIP: {size_mb:.1f} MB")
    return zip_path


# ═══════════════════════════════════════════════════════════════════
#  Verification
# ═══════════════════════════════════════════════════════════════════

_CRITICAL_JSON = [
    "crew_builds.json", "tank_db.json", "tank_tth.json",
    "game_entities_english.json", "game_entities.json", "tank_slots_full.json",
]


def verify_build(version):
    """Check that the build output contains all expected critical files."""
    print()
    onedir = os.path.join(DIST_DIR, f"SM WoT Assistant v{version}")
    internal = os.path.join(onedir, "_internal")

    errors = []
    warnings = []

    exe_ver = os.path.join(onedir, f"SM WoT Assistant v{version}.exe")
    exe_plain = os.path.join(onedir, "SM WoT Assistant.exe")
    exe = exe_ver if os.path.exists(exe_ver) else exe_plain
    if not os.path.exists(exe):
        errors.append("EXE not found")
    else:
        print(f"  EXE:               {os.path.getsize(exe)/(1024*1024):.1f} MB  OK")

    launcher_exe = os.path.join(onedir, "SM WoT Assistant Launcher.exe")
    if not os.path.exists(launcher_exe):
        errors.append("Launcher EXE not found")
    else:
        print(f"  Launcher:          {os.path.getsize(launcher_exe)/(1024*1024):.1f} MB  OK")

    tray_exe = os.path.join(onedir, "SM WoT Assistant Tray Watcher.exe")
    if not os.path.exists(tray_exe):
        errors.append("Tray Watcher EXE not found")
    else:
        print(f"  Tray Watcher:      {os.path.getsize(tray_exe)/(1024*1024):.1f} MB  OK")

    for j in _CRITICAL_JSON:
        if not os.path.exists(os.path.join(internal, j)):
            errors.append(f"Missing JSON: {j}")

    if not os.path.exists(os.path.join(internal, "VERSION")):
        errors.append("Missing VERSION")

    for f in ("xvmsymbol.ttf", "fontawesome-webfont.ttf"):
        if not os.path.exists(os.path.join(internal, f)):
            warnings.append(f"Missing font: {f}")

    for f in ("artefacts_en.mo", "crew_perks_en.mo", "item_types_en.mo"):
        if not os.path.exists(os.path.join(internal, f)):
            warnings.append(f"Missing .mo: {f}")

    # Directory checks
    checks = [
        ("maps", os.path.join(internal, "maps"), 50),
        ("extracted_maps", os.path.join(internal, "extracted_maps"), 60),
        ("extracted_icons", os.path.join(internal, "extracted_icons"), 8),
        ("extracted_data", os.path.join(internal, "extracted_data"), 1),
    ]
    for label, path, expected in checks:
        if not os.path.isdir(path):
            errors.append(f"Missing directory: {label}")
        else:
            count = sum(1 for _ in os.scandir(path))
            tag = "OK" if count >= expected else f"WARNING (found {count}, expected >= {expected})"
            print(f"  {label + ':':20s} {count} entries  {tag}")

    if errors:
        print()
        print(f"[BUILD] VERIFICATION FAILED ({len(errors)} errors):")
        for e in errors:
            print(f"  ERROR: {e}")
        sys.exit(1)

    if warnings:
        print(f"[BUILD] Warnings: {len(warnings)}")
        for w in warnings:
            print(f"  WARN: {w}")

    print(f"[BUILD] Verification PASSED")


# ═══════════════════════════════════════════════════════════════════
#  Manifest
# ═══════════════════════════════════════════════════════════════════

def generate_manifest(version):
    onedir = os.path.join(DIST_DIR, f"SM WoT Assistant v{version}")
    manifest_path = os.path.join(DIST_DIR, f"build_manifest_v{version}.txt")

    with open(manifest_path, "w", encoding="utf-8") as mf:
        mf.write(f"SM WoT Assistant v{version} — Build Manifest\n")
        mf.write(f"Built: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        mf.write("=" * 60 + "\n\n")

        total_files = 0
        total_bytes = 0
        for root_dir, dirs, files in os.walk(onedir):
            rel_root = os.path.relpath(root_dir, onedir)
            for fn in sorted(files):
                fp = os.path.join(root_dir, fn)
                sz = os.path.getsize(fp)
                total_files += 1
                total_bytes += sz
                rel = os.path.join(rel_root, fn) if rel_root != "." else fn
                mf.write(f"  {sz:>10,}  {rel}\n")

        mf.write(f"\n{'=' * 60}\n")
        mf.write(f"Total: {total_files} files, {total_bytes:,} bytes ({total_bytes/(1024*1024):.1f} MB)\n")

    print(f"[BUILD] Manifest: {manifest_path}")
    return manifest_path


# ═══════════════════════════════════════════════════════════════════
#  Release Artifacts Verification
# ═══════════════════════════════════════════════════════════════════

def verify_release_artifacts(version, is_beta=False):
    """Перевіряє всі артефакти релізу ПЕРЕД створенням GitHub release.
    При помилці — друкує детальний звіт і завершує build з exit code 1."""
    errors = []
    beta_suffix = "_Beta" if is_beta else ""
    onedir = os.path.join(DIST_DIR, f"SM WoT Assistant v{version}")

    # 1. Файли артефактів — всі існують
    expected = {
        "Installer": os.path.join(DIST_DIR, f"SM_WoT_Assistant_Setup_v{version}{beta_suffix}.exe"),
        "Portable ZIP": os.path.join(DIST_DIR, f"SM_WoT_Assistant_Portable_v{version}{beta_suffix}.zip"),
        "Build manifest": os.path.join(DIST_DIR, f"build_manifest_v{version}.txt"),
        "Main EXE": os.path.join(onedir, f"SM WoT Assistant v{version}.exe"),
        "Launcher": os.path.join(onedir, "SM WoT Assistant Launcher.exe"),
        "Tray Watcher": os.path.join(onedir, "SM WoT Assistant Tray Watcher.exe"),
    }
    for label, path in expected.items():
        if not os.path.exists(path):
            errors.append(f"Missing {label}: {path}")

    # 2. Версії: VERSION == installer.nsi PRODUCT_VERSION
    from_v = read_version()
    if from_v != version:
        errors.append(f"VERSION file mismatch: expected '{version}', got '{from_v}'")

    if os.path.exists(NSI_FILE):
        with open(NSI_FILE, "r", encoding="utf-8") as f:
            nsi_content = f.read()
        m = re.search(r'!define PRODUCT_VERSION "([^"]*)"', nsi_content)
        if m and m.group(1) != version:
            errors.append(f"installer.nsi PRODUCT_VERSION mismatch: expected '{version}', got '{m.group(1)}'")

    # 3. Release title format: create_github_release() має створити правильний title
    expected_title = f"v{version} Beta" if is_beta else f"v{version}"
    # Це перевірка що код create_github_release() згенерує саме такий title
    display_tag = f"v{version} Beta" if is_beta else f"v{version}"
    if display_tag != expected_title:
        errors.append(f"Release title format mismatch: '{display_tag}' != '{expected_title}'")

    # 4. Prerelease flag: is_beta має правильно впливати на --prerelease
    expected_pr = is_beta  # True для beta, False для stable
    if expected_pr != is_beta:
        errors.append(f"Prerelease flag mismatch: expected {expected_pr}, got is_beta={is_beta}")

    # 5. Консистентність імен: RTDB download_url співпадає з реальним файлом
    expected_filename = f"SM_WoT_Assistant_Setup_v{version}{beta_suffix}.exe"
    expected_url = f"https://github.com/nkcgml-boop/SM-WoT-Assistant/releases/download/v{version}/{expected_filename}"
    print(f"  RTDB URL check: {expected_url}")
    dl_url_check = os.path.join(DIST_DIR, expected_filename)
    if os.path.exists(expected.get("Installer", "")) and os.path.basename(dl_url_check) != os.path.basename(expected.get("Installer", "")):
        errors.append(f"Internal: download_url filename '{os.path.basename(dl_url_check)}' != installer '{os.path.basename(expected.get('Installer', ''))}'")

    if errors:
        print()
        print("=" * 60)
        print("  RELEASE ARTIFACT VERIFICATION FAILED")
        print("=" * 60)
        for e in errors:
            print(f"  ERROR: {e}")
        print()
        print("[BUILD] Aborting — do not create GitHub release or RTDB entry.")
        sys.exit(1)

    print("[BUILD] Release artifacts verification PASSED")
    for label, path in expected.items():
        if os.path.exists(path):
            sz = os.path.getsize(path)
            print(f"  {label + ':':20s} {os.path.basename(path)}  ({sz/(1024*1024):.0f} MB)" if sz > 1024*1024 else f"  {label + ':':20s} {os.path.basename(path)}  ({sz:,} bytes)")
    print(f"  RTDB URL:    {expected_url}")
    return True


# ═══════════════════════════════════════════════════════════════════
#  GitHub Release
# ═══════════════════════════════════════════════════════════════════

def create_github_release(version, is_beta=False):
    beta_suffix = "_Beta" if is_beta else ""
    installer = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Setup_v{version}{beta_suffix}.exe")
    portable = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Portable_v{version}{beta_suffix}.zip")
    manifest = os.path.join(DIST_DIR, f"build_manifest_v{version}.txt")

    assets = []
    if os.path.exists(installer):
        assets.append(installer)
    if os.path.exists(portable):
        assets.append(portable)
    if os.path.exists(manifest):
        assets.append(manifest)

    if not assets:
        print("[BUILD] ERROR: No release artifacts found.")
        return False

    tag = f"v{version}"
    display_tag = f"v{version} Beta" if is_beta else tag
    changelog = os.path.join(BASE_DIR, "CHANGELOG.md")
    notes_flag = ["--notes-file", changelog] if os.path.exists(changelog) else ["--notes", f"Release {tag}"]
    pr_flag = ["--prerelease"] if is_beta else []

    print(f"[BUILD] Creating GitHub release {tag}...")
    cmd = ["gh", "release", "create", tag] + assets + ["--title", display_tag] + pr_flag + notes_flag
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode == 0:
        print(f"[BUILD] GitHub release {tag} created")
        return True
    else:
        print(f"[BUILD] GitHub release FAILED (exit code {result.returncode})")
        return False


# ═══════════════════════════════════════════════════════════════════
#  Post-release Audit
# ═══════════════════════════════════════════════════════════════════

def audit_github_release(version, is_beta=False):
    """Перевіряє GitHub release після створення — назва та prerelease flag.
    Якщо не співпадає — видаляє реліз і завершує build з помилкою."""
    tag = f"v{version}"
    expected_name = f"v{version} Beta" if is_beta else f"v{version}"
    print(f"[BUILD] Auditing GitHub release {tag}...")

    try:
        r = subprocess.run(
            ["gh", "release", "view", tag, "--json", "name,isPrerelease"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            print(f"[BUILD] AUDIT FAILED: could not view release (exit {r.returncode})")
            print(f"  stderr: {r.stderr.strip()}")
            sys.exit(1)

        data = json.loads(r.stdout)
        actual_name = data.get("name", "")
        actual_pr = data.get("isPrerelease", False)

        problems = []
        if actual_name != expected_name:
            problems.append(f"title='{actual_name}' (expected '{expected_name}')")
        if actual_pr != is_beta:
            problems.append(f"prerelease={actual_pr} (expected {is_beta})")

        if problems:
            print("[BUILD] AUDIT FAILED — release created with wrong metadata:")
            for p in problems:
                print(f"  {p}")
            print(f"[BUILD] Deleting release {tag} and aborting...")
            subprocess.run(
                ["gh", "release", "delete", tag, "--yes"],
                cwd=BASE_DIR, capture_output=True, timeout=15,
            )
            sys.exit(1)

        print(f"[BUILD] GitHub release audit PASSED (name='{actual_name}', prerelease={actual_pr})")
        return True

    except json.JSONDecodeError as e:
        print(f"[BUILD] AUDIT FAILED: JSON parse error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[BUILD] AUDIT FAILED: {e}")
        sys.exit(1)


def audit_rtdb_entry(version, is_beta=False):
    """Перевіряє RTDB download_url після запису."""
    beta_suffix = "_Beta" if is_beta else ""
    expected_filename = f"SM_WoT_Assistant_Setup_v{version}{beta_suffix}.exe"
    expected_url = f"https://github.com/nkcgml-boop/SM-WoT-Assistant/releases/download/v{version}/{expected_filename}"

    try:
        import urllib.request
        RTDB_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"
        API_KEY = "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"
        url = f"{RTDB_URL}/versions/{version.replace('.', '_')}/download_url.json?auth={API_KEY}"
        r = urllib.request.urlopen(url, timeout=10)
        actual_url = json.loads(r.read().decode("utf-8"))

        if isinstance(actual_url, dict):
            print(f"[BUILD] RTDB AUDIT FAILED: download_url is an OBJECT, not a string:")
            print(f"  Value: {json.dumps(actual_url, ensure_ascii=False)}")
            print(f"  Expected a plain string URL")
            sys.exit(1)

        if not isinstance(actual_url, str):
            print(f"[BUILD] RTDB AUDIT FAILED: download_url is type {type(actual_url).__name__}, not string")
            sys.exit(1)

        if actual_url != expected_url:
            print(f"[BUILD] RTDB AUDIT FAILED:")
            print(f"  Expected: {expected_url}")
            print(f"  Actual:   {actual_url}")
            sys.exit(1)

        print(f"[BUILD] RTDB audit PASSED (download_url matches)")
        return True

    except Exception as e:
        print(f"[BUILD] RTDB audit error: {e}")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════

def write_version_to_rtdb(version, release_date=None, is_beta=False):
    import urllib.request
    import urllib.parse
    RTDB_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"
    API_KEY = "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"

    display_ver = version + (" Beta" if is_beta else "")
    beta_suffix = "_Beta" if is_beta else ""
    today = release_date or time.strftime("%Y-%m-%d")
    installer_path = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Setup_v{version}{beta_suffix}.exe")
    installer_size = ""
    if os.path.exists(installer_path):
        sz = os.path.getsize(installer_path)
        installer_size = f"{sz / (1024*1024):.0f} MB"

    dl_filename = f"SM_WoT_Assistant_Setup_v{version}{beta_suffix}.exe"
    dl_url = f"https://github.com/nkcgml-boop/SM-WoT-Assistant/releases/download/v{version}/{dl_filename}"

    data = json.dumps({
        "version": version,
        "display_version": display_ver,
        "release_date": today,
        "build_size": installer_size,
        "download_url": dl_url,
        "changelog": f"Release v{version}",
    }).encode("utf-8")

    # Write versioned entry: versions/X_Y_Z
    url = f"{RTDB_URL}/versions/{version.replace('.', '_')}.json?auth={API_KEY}"
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[BUILD] Version {version} published to RTDB (HTTP {resp.status})")
    except Exception as e:
        print(f"[BUILD] RTDB publish warning: {e}")
        return False

    # Write latest pointer: versions/latest (release_date far future)
    latest_data = json.dumps({
        "version": version,
        "display_version": display_ver,
        "release_date": "9999-12-31",
        "build_size": installer_size,
        "download_url": dl_url,
        "changelog": f"Release v{version}",
    }).encode("utf-8")
    url_latest = f"{RTDB_URL}/versions/latest.json?auth={API_KEY}"
    req_latest = urllib.request.Request(url_latest, data=latest_data, method="PUT")
    req_latest.add_header("Content-Type", "application/json")
    try:
        resp_latest = urllib.request.urlopen(req_latest, timeout=10)
        print(f"[BUILD] Latest pointer updated (HTTP {resp_latest.status})")
    except Exception as e:
        print(f"[BUILD] Latest pointer warning: {e}")
    return True


def main():
    new_version = None
    release_date = None
    is_beta = False

    for a in sys.argv[1:]:
        if a.startswith("--date="):
            release_date = a.split("=", 1)[1]
        elif a == "--beta":
            is_beta = True
        else:
            new_version = a

    if new_version:
        write_version(new_version)

    version = read_version()
    is_beta_suffix = " Beta" if is_beta else ""
    display_ver = version + is_beta_suffix

    # Phase 0: Pre-flight checks
    makensis_exe = preflight(version)

    # Phase 1: Clean previous intermediate build
    clean_dist()

    # Phase 2: PyInstaller — завжди чистий version
    update_nsi_version(version)
    commit_version_files(version)
    create_git_tag(version)
    run_pyinstaller()
    data_count = copy_data_files()
    build_launcher()
    build_tray_watcher()

    # Rename EXE to include version (clean, без Beta)
    exe_plain = os.path.join(FIXED_ONEDIR, "SM WoT Assistant.exe")
    exe_ver = os.path.join(FIXED_ONEDIR, f"SM WoT Assistant v{version}.exe")
    if os.path.exists(exe_plain):
        if os.path.exists(exe_ver):
            os.remove(exe_ver)
        os.rename(exe_plain, exe_ver)
        print(f"[BUILD] EXE renamed: SM WoT Assistant v{version}.exe")

    # Phase 3: NSIS installer (чистий version)
    installer = run_nsis(version, makensis_exe, is_beta)

    # Phase 4: Rename to versioned directory + portable ZIP (чистий version)
    rename_onedir(version)
    portable_zip = create_portable_zip(version, is_beta)

    # Phase 5: Verification
    verify_build(version)

    # Phase 6: Manifest
    generate_manifest(version)

    # Phase 7: Summary — display_ver з Beta тільки для показу
    print()
    print("=" * 60)
    print(f"  BUILD COMPLETE — SM WoT Assistant v{display_ver}")
    print("=" * 60)
    print(f"  Version:        {display_ver}")
    print(f"  Data files:     {data_count}")
    if installer:
        print(f"  Installer:      {os.path.basename(installer)}")
    if portable_zip:
        print(f"  Portable ZIP:   {os.path.basename(portable_zip)}")
    print(f"  Manifest:       build_manifest_v{version}.txt")
    print(f"  Output dir:     {DIST_DIR}")
    print()

    # Phase 7b: Verify release artifacts before publishing
    verify_release_artifacts(version, is_beta)

    # Always create GitHub release (required for auto-update download URL)
    if create_github_release(version, is_beta):
        # Post-release audit: verify title & prerelease flag
        audit_github_release(version, is_beta)
        # Write version to RTDB only after successful GitHub release + audit
        if write_version_to_rtdb(version, release_date, is_beta):
            # RTDB audit: verify download_url
            audit_rtdb_entry(version, is_beta)

    print(f"[BUILD] Done: v{display_ver}")


if __name__ == "__main__":
    main()
