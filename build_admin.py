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


def build_admin_exe(version):
    """Build admin_app.py as --onefile EXE."""
    print(f"[BUILD] Building Admin v{version}...")
    admin_py = os.path.join(BASE_DIR, "admin_app.py")
    if not os.path.exists(admin_py):
        print("[BUILD] FATAL: admin_app.py not found")
        sys.exit(1)

    result = subprocess.run([
        PYTHON_EXE, "-m", "PyInstaller",
        "--onedir", "--windowed",
        "--icon", os.path.join(BASE_DIR, "admin_icon.ico"),
        "--name", "SM WoT Assistant Admin",
        "--distpath", DIST_DIR,
        "--workpath", os.path.join(BASE_DIR, "build", "admin_app"),
        "--specpath", os.path.join(BASE_DIR, "build"),
        "--clean",
        "--add-data", f"{os.path.join(BASE_DIR, 'admin_icon.ico')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'admin_version.txt')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, '_fill_all_builds.py')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'generate_prompt_v2.py')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'stats_data.py')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'tank_db.json')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'tank_tth.json')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'tank_slots_full.json')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'translations.py')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'game_entities_english.json')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'crew_builds.json')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'prompts_cache.json')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'game_entities.json')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'admin_uk_seed.json')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'temp_scripts', 'decoded', 'tiers_devices_decoded.xml')}{os.pathsep}temp_scripts/decoded/",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "requests",
        "--hidden-import", "deep_translator",
        "--hidden-import", "selenium.webdriver.chrome.webdriver",
        "--hidden-import", "selenium.webdriver.chrome.service",
        "--hidden-import", "selenium.webdriver.chrome.options",
        "--hidden-import", "selenium.webdriver.common.service",
        "--hidden-import", "selenium.webdriver.common.selenium_manager",
        "--hidden-import", "selenium.webdriver.common.driver_finder",
        admin_py,
    ], cwd=BASE_DIR)

    if result.returncode != 0:
        print("[BUILD] Admin EXE build FAILED")
        sys.exit(1)

    exe = os.path.join(ADMIN_DIR, "SM WoT Assistant Admin.exe")
    if not os.path.exists(exe):
        print("[BUILD] FATAL: Admin EXE not found")
        sys.exit(1)

    # A broken COLLECT leaves an empty _internal — bootloader then dies with
    # "Failed to load Python DLL" on the next launch (13.08.2026 incident).
    internal = os.path.join(ADMIN_DIR, "_internal")
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


def clean():
    """Clean build artifacts."""
    for p in [os.path.join(BASE_DIR, "build", "admin_app"),
              os.path.join(BASE_DIR, "SM WoT Assistant Admin.spec")]:
        if os.path.exists(p):
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
    if os.path.isdir(ADMIN_DIR):
        shutil.rmtree(ADMIN_DIR)
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
    build_admin_exe(version)

    print()
    print(f"[BUILD] Admin v{version} built!")
    print(f"[BUILD] EXE: {os.path.join(ADMIN_DIR, 'SM WoT Assistant Admin.exe')}")


if __name__ == "__main__":
    main()
