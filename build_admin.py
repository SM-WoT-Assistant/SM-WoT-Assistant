#!/usr/bin/env python3
"""Build SM WoT Assistant Admin as a standalone onedir EXE (dist/SM WoT Assistant Admin/).
Local build only — no GitHub or RTDB publish.
"""
import os, sys, subprocess, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
ADMIN_DIR = os.path.join(DIST_DIR, "SM WoT Assistant Admin")
PYTHON_EXE = r"C:\Users\PRO\AppData\Local\Programs\Python\Python312\python.exe"


def read_version():
    with open(os.path.join(BASE_DIR, "admin_version.txt"), "r") as f:
        return f.read().strip()


def build_admin_exe(version, dist_dir=None):
    """Build admin_ui/main_window.py as --onedir EXE.
    dist_dir: override output dir (used when the canonical ADMIN_DIR is
    locked by the invisible handle incident #1546 — WinError 32 on the
    folder itself while writing inside still works)."""
    if dist_dir is None:
        dist_dir = DIST_DIR
    admin_exe_dir = os.path.join(dist_dir, "SM WoT Assistant Admin")
    print(f"[BUILD] Building Admin v{version}...")
    entry_py = os.path.join(BASE_DIR, "admin_ui", "main_window.py")
    if not os.path.exists(entry_py):
        print("[BUILD] FATAL: admin_ui/main_window.py not found")
        sys.exit(1)

    def _add(rel_path):
        src = os.path.join(BASE_DIR, rel_path)
        if os.path.exists(src):
            return ["--add-data", f"{src}{os.pathsep}."]
        print(f"[BUILD] WARN: {rel_path} not found, skipping")
        return []

    result = subprocess.run([
        PYTHON_EXE, "-m", "PyInstaller",
        "--onedir", "--windowed",
        "--icon", os.path.join(BASE_DIR, "admin_icon.ico"),
        "--name", "SM WoT Assistant Admin",
        "--distpath", dist_dir,
        "--workpath", os.path.join(BASE_DIR, "build", "admin_app"),
        "--specpath", os.path.join(BASE_DIR, "build"),
        "--clean",
        "--noconfirm",
        # Admin UI package
        "--collect-submodules", "admin_ui",
        "--collect-submodules", "admin_backend",
        # Pipeline dependencies
        "--hidden-import", "admin_build_generator",
        "--hidden-import", "admin_auth",
        "--hidden-import", "tank_extractor",
        "--hidden-import", "build_crew_builds",
        "--hidden-import", "extract_equipment_loadouts",
        "--hidden-import", "parse_game_entities",
        "--hidden-import", "name_localizer",
        "--hidden-import", "decode_xml",
        "--hidden-import", "wot_decoder",
        "--hidden-import", "language_module",
        "--hidden-import", "tth_updater",
        "--hidden-import", "config",
        "--hidden-import", "firebase_reporter",
        "--hidden-import", "firebase_identity",
        "--hidden-import", "firebase_groups",
        "--hidden-import", "firebase_drawings",
        "--hidden-import", "stats_data",
        "--hidden-import", "stats_ai",
        "--hidden-import", "generate_prompt_v2",
        "--hidden-import", "_fill_all_builds",
        # UI framework
        "--hidden-import", "customtkinter",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "requests",
        "--hidden-import", "deep_translator",
        # Selenium (for build generation)
        "--hidden-import", "selenium.webdriver.chrome.webdriver",
        "--hidden-import", "selenium.webdriver.chrome.service",
        "--hidden-import", "selenium.webdriver.chrome.options",
        "--hidden-import", "selenium.webdriver.common.service",
        "--hidden-import", "selenium.webdriver.common.selenium_manager",
        "--hidden-import", "selenium.webdriver.common.driver_finder",
        # Data files
        *_add("admin_icon.ico"),
        *_add("admin_version.txt"),
        *_add("_fill_all_builds.py"),
        *_add("generate_prompt_v2.py"),
        *_add("stats_data.py"),
        *_add("tank_db.json"),
        *_add("tank_tth.json"),
        *_add("tank_slots_full.json"),
        *_add("translations.py"),
        *_add("game_entities_english.json"),
        *_add("crew_builds.json"),
        *_add("prompts_cache.json"),
        *_add("game_entities.json"),
        *_add("admin_uk_seed.json"),
        *_add("equipment_loadouts.json"),
        *_add("temp_scripts/decoded/tiers_devices_decoded.xml"),
        entry_py,
    ], cwd=BASE_DIR)

    if result.returncode != 0:
        print("[BUILD] Admin EXE build FAILED")
        sys.exit(1)

    exe = os.path.join(admin_exe_dir, "SM WoT Assistant Admin.exe")
    if not os.path.exists(exe):
        print("[BUILD] FATAL: Admin EXE not found")
        sys.exit(1)

    # A broken COLLECT leaves an empty _internal — bootloader then dies with
    # "Failed to load Python DLL" on the next launch (13.08.2026 incident).
    internal = os.path.join(admin_exe_dir, "_internal")
    if not os.path.isdir(internal) or not os.path.exists(os.path.join(internal, "python312.dll")):
        print("[BUILD] FATAL: bundle incomplete — _internal missing python312.dll")
        sys.exit(1)
    count = sum(1 for _ in os.scandir(internal))
    if count == 0:
        print("[BUILD] FATAL: bundle incomplete — _internal is empty")
        sys.exit(1)

    size_mb = os.path.getsize(exe) / (1024 * 1024)
    print(f"[BUILD] Admin EXE: {size_mb:.1f} MB, _internal: {count} entries")
    return exe


def _rmtree_tolerant(path):
    """Remove a tree; a locked directory (invisible handle incident #1546 —
    WinError 32 on the folder itself while writing inside still works) is left
    EMPTY instead of failing the build — PyInstaller COLLECT overwrites it."""
    if not os.path.isdir(path):
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            p = os.path.join(root, f)
            try:
                os.remove(p)
            except Exception:
                pass
        for d in dirs:
            p = os.path.join(root, d)
            try:
                os.rmdir(p)
            except Exception:
                pass
    try:
        os.rmdir(path)
    except Exception:
        pass


def clean():
    """Clean build artifacts."""
    for p in [os.path.join(BASE_DIR, "build", "admin_app"),
              os.path.join(BASE_DIR, "SM WoT Assistant Admin.spec")]:
        if os.path.exists(p):
            if os.path.isdir(p):
                _rmtree_tolerant(p)
            else:
                os.remove(p)
    if os.path.isdir(ADMIN_DIR):
        _rmtree_tolerant(ADMIN_DIR)
    if os.path.exists(DIST_DIR):
        for f in os.listdir(DIST_DIR):
            if f.startswith("SM WoT Assistant Admin") and f.endswith(".exe"):
                os.remove(os.path.join(DIST_DIR, f))


def main():
    version = read_version()
    print("=" * 60)
    print(f"  SM WoT Assistant Admin — Build v{version}")
    print("=" * 60)

    clean()
    if os.path.isdir(ADMIN_DIR) and os.listdir(ADMIN_DIR):
        # Invisible handle incident #1546: the canonical folder can't be
        # removed — build into a temp dir and overwrite (writing inside the
        # locked folder still works).
        tmp_build = os.path.join(DIST_DIR, "Admin_TMP_BUILD")
        if os.path.isdir(tmp_build):
            shutil.rmtree(tmp_build, ignore_errors=True)
        print("[BUILD] canonical dir locked — building into Admin_TMP_BUILD, then deploying")
        build_admin_exe(version, dist_dir=tmp_build)
        shutil.copytree(os.path.join(tmp_build, "SM WoT Assistant Admin"),
                        ADMIN_DIR, dirs_exist_ok=True)
        shutil.rmtree(tmp_build, ignore_errors=True)
    else:
        build_admin_exe(version)

    print()
    print(f"[BUILD] Admin v{version} built!")
    print(f"[BUILD] EXE: {os.path.join(ADMIN_DIR, 'SM WoT Assistant Admin.exe')}")


if __name__ == "__main__":
    main()
