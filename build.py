#!/usr/bin/env python3
"""Build script for SM WoT Assistant -- PyInstaller onedir + NSIS installer + GitHub release.

Usage:
    python build.py                    # build with current VERSION
    python build.py 1.0.1              # update VERSION, then build
    python build.py 1.0.1 --release    # build + create GitHub release
    python build.py --release          # create GitHub release from existing build
"""

import os, sys, subprocess, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, "VERSION")
SPEC_FILE = os.path.join(BASE_DIR, "wot_assistant.spec")
NSI_FILE = os.path.join(BASE_DIR, "installer.nsi")
DIST_DIR = os.path.join(BASE_DIR, "dist")
ONEDIR_OUTPUT = os.path.join(DIST_DIR, "SM WoT Assistant")


def _find_python():
    """Find the best Python executable for the build (3.12 preferred over 3.14).

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
    print("[BUILD] WARNING: No Python with PyInstaller found, using sys.executable")
    return sys.executable


PYTHON_EXE = _find_python()


def read_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "0.0.0"


def write_version(v):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(v.strip() + "\n")
    print(f"[BUILD] VERSION = {v.strip()}")


def update_nsi_version(version):
    if not os.path.exists(NSI_FILE):
        print("[BUILD] WARNING: installer.nsi not found, skipping NSIS version update")
        return
    with open(NSI_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    import re
    content = re.sub(r'!define PRODUCT_VERSION "[\d.]+"', f'!define PRODUCT_VERSION "{version}"', content)
    with open(NSI_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[BUILD] installer.nsi version = {version}")


def find_nsis():
    """Locate makensis.exe"""
    paths = [
        os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "NSIS", "makensis.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "NSIS", "makensis.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "NSIS", "makensis.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    result = shutil.which("makensis")
    return result


def run_pyinstaller():
    print("[BUILD] Running PyInstaller (onedir)...")
    result = subprocess.run(
        [PYTHON_EXE, "-m", "PyInstaller", "--clean", "--noconfirm", SPEC_FILE],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        print("[BUILD] PyInstaller FAILED")
        sys.exit(1)
    print("[BUILD] PyInstaller OK")

    exe = os.path.join(ONEDIR_OUTPUT, "SM WoT Assistant.exe")
    if os.path.exists(exe):
        size_mb = os.path.getsize(exe) / (1024 * 1024)
        print(f"[BUILD] {ONEDIR_OUTPUT} -- exe {size_mb:.1f} MB")
    else:
        print(f"[BUILD] WARNING: {exe} not found")
    return exe


def copy_data_files():
    """Manually copy application data files into the onedir output.

    PyInstaller 6.x has a bug where DATA entries in Analysis are not
    propagated to COLLECT, so we copy them ourselves after the build.
    """
    target = os.path.join(ONEDIR_OUTPUT, "_internal")
    os.makedirs(target, exist_ok=True)
    total = 0

    def _cp(src, dst_rel):
        nonlocal total
        dst = os.path.join(target, dst_rel)
        os.makedirs(os.path.dirname(dst) if os.path.splitext(dst)[1] else dst, exist_ok=True)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            total += 1

    # Root JSONs + VERSION
    root_jsons = [
        "crew_builds.json", "equipment_loadouts.json", "game_entities.json",
        "game_entities_english.json", "icon_mapping.json", "map_list.json",
        "map_links.json", "tank_db.json", "tank_slots_db.json",
        "tank_slots_full.json", "tank_tth.json", "VERSION",
    ]
    for f in root_jsons:
        p = os.path.join(BASE_DIR, f)
        if os.path.exists(p):
            _cp(p, f)

    # TTF fonts
    for f in ["xvmsymbol.ttf", "fontawesome-webfont.ttf"]:
        p = os.path.join(BASE_DIR, f)
        if os.path.exists(p):
            _cp(p, f)

    # .mo localization files
    for f in ["artefacts_en.mo", "crew_perks_en.mo", "item_types_en.mo"]:
        p = os.path.join(BASE_DIR, f)
        if os.path.exists(p):
            _cp(p, f)

    # logo
    logo = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo):
        _cp(logo, "logo.png")

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

    # extracted_icons/ (all 8 subdirectories)
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

    print(f"[BUILD] Copied {total} data files to {target}")


def run_nsis(version):
    makensis = find_nsis()
    if not makensis:
        print("[BUILD] WARNING: NSIS (makensis) not found. Skipping installer.")
        print("[BUILD] Install NSIS from https://nsis.sourceforge.io/Download")
        return None

    out_exe = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Setup_v{version}.exe")
    print(f"[BUILD] Running NSIS: {makensis}")
    result = subprocess.run(
        [makensis, f"/DVERSION={version}", NSI_FILE],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        print("[BUILD] NSIS FAILED")
        return None
    if os.path.exists(out_exe):
        size_mb = os.path.getsize(out_exe) / (1024 * 1024)
        print(f"[BUILD] Installer: {out_exe} -- {size_mb:.1f} MB")
    return out_exe


def create_github_release(version):
    installer = os.path.join(DIST_DIR, f"SM_WoT_Assistant_Setup_v{version}.exe")
    if os.path.exists(installer):
        release_file = installer
    else:
        zip_name = os.path.join(DIST_DIR, f"SM_WoT_Assistant_v{version}.zip")
        if os.path.exists(ONEDIR_OUTPUT):
            print(f"[BUILD] Creating {zip_name}...")
            shutil.make_archive(zip_name.replace(".zip", ""), "zip", DIST_DIR, "SM WoT Assistant")
        release_file = zip_name

    if not os.path.exists(release_file):
        print("[BUILD] ERROR: No release file found.")
        return

    if shutil.which("gh") is None:
        print("[BUILD] WARNING: GitHub CLI (gh) not found. Skipping release.")
        print(f"[BUILD] Manual: gh release create v{version} {release_file}")
        return

    tag = f"v{version}"
    changelog = os.path.join(BASE_DIR, "CHANGELOG.md")
    notes_flag = ["--notes-file", changelog] if os.path.exists(changelog) else ["--notes", f"Release {tag}"]

    print(f"[BUILD] Creating GitHub release {tag}...")
    result = subprocess.run(
        ["gh", "release", "create", tag, release_file, "--title", tag] + notes_flag,
        cwd=BASE_DIR,
    )
    if result.returncode == 0:
        print(f"[BUILD] GitHub release {tag} created")
    else:
        print(f"[BUILD] GitHub release FAILED (exit {result.returncode})")


def main():
    new_version = None
    do_release = False

    args = sys.argv[1:]
    for a in args:
        if a == "--release":
            do_release = True
        else:
            new_version = a

    if new_version:
        write_version(new_version)

    version = read_version()
    print(f"[BUILD] Building SM WoT Assistant v{version}")

    update_nsi_version(version)
    run_pyinstaller()
    copy_data_files()
    run_nsis(version)

    if do_release:
        create_github_release(version)

    print(f"[BUILD] Done: v{version}")


if __name__ == "__main__":
    main()
