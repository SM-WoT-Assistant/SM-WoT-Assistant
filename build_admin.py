#!/usr/bin/env python3
"""Build SM WoT Assistant Admin as a standalone onefile EXE.
Local build only — no GitHub or RTDB publish.
"""
import os, sys, subprocess, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
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
        "--onefile", "--windowed",
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
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "requests",
        admin_py,
    ], cwd=BASE_DIR)

    if result.returncode != 0:
        print("[BUILD] Admin EXE build FAILED")
        sys.exit(1)

    exe = os.path.join(DIST_DIR, "SM WoT Assistant Admin.exe")
    if not os.path.exists(exe):
        print("[BUILD] FATAL: Admin EXE not found")
        sys.exit(1)

    size_mb = os.path.getsize(exe) / (1024 * 1024)
    print(f"[BUILD] Admin EXE: {size_mb:.1f} MB")
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
    print(f"[BUILD] EXE: {os.path.join(DIST_DIR, 'SM WoT Assistant Admin.exe')}")


if __name__ == "__main__":
    main()
