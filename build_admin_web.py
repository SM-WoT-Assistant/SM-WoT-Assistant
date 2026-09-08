#!/usr/bin/env python3
"""Build SM WoT Assistant Admin (Flask + webbrowser) as standalone onedir EXE.

Output: dist/SM WoT Assistant Admin/SM WoT Assistant Admin.exe
        + _internal/ (admin_backend, admin_web, flask, selenium, ...)
"""
from __future__ import annotations
import os, shutil, subprocess, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
ADMIN_DIR = os.path.join(DIST_DIR, "SM WoT Assistant Admin")
PYTHON_EXE = sys.executable  # Use the Python that's running this script
ADMIN_WEB_DIR = os.path.join(BASE_DIR, "admin_web")
ADMIN_BACKEND_DIR = os.path.join(BASE_DIR, "admin_backend")
ADMIN_ICON_ICO = os.path.join(BASE_DIR, "admin_icon.ico")
ADMIN_VERSION_TXT = os.path.join(BASE_DIR, "admin_version.txt")
ADMIN_ICON_PNG = os.path.join(BASE_DIR, "logo.png")
SEP = ";"  # os.pathsep on Windows


def read_version(f=ADMIN_VERSION_TXT):
    with open(f) as fp:
        return fp.read().strip()


def _rmtree_tolerant(path):
    """Remove tree even if locked (invisible handle incident #1546)."""
    for root, _dirs, files in os.walk(path, topdown=False):
        for f in files:
            p = os.path.join(root, f)
            try: os.remove(p)
            except Exception: pass
    try:
        os.rmdir(path)
    except Exception:
        pass


def build_admin_web(dist_dir=None):
    """Build admin_main.py as --onedir EXE with webbrowser + Flask API."""
    if dist_dir is None:
        dist_dir = DIST_DIR
    admin_exe_dir = os.path.join(dist_dir, "SM WoT Assistant Admin")
    print("[BUILD] Building Admin (web) v" + read_version() + "...")
    for p in (ADMIN_WEB_DIR, ADMIN_BACKEND_DIR):
        if not os.path.exists(p):
            print("[BUILD] FATAL: " + p + " not found")
            sys.exit(1)
    datas = [ADMIN_WEB_DIR, ADMIN_BACKEND_DIR]
    add_data_args = []
    for d in datas:
        add_data_args.extend(["--add-data", os.path.join(d) + SEP + "."])
    hidden = ["PIL", "flask", "flask_cors", "werkzeug", "selenium", "selenium.webdriver.chrome.webdriver"]
    for h in hidden:
        add_data_args.extend(["--hidden-import", h])
    cmd = [PYTHON_EXE, "-m", "PyInstaller",
           "--onedir", "--windowed",
           "--name", "SM WoT Assistant Admin",
           "--icon", ADMIN_ICON_ICO,
           "--distpath", dist_dir,
           "--workpath", os.path.join(BASE_DIR, "build"),
           "--specpath", os.path.join(BASE_DIR, "build"),
           "--clean", "--noconfirm",
           "--add-data", ADMIN_ICON_ICO + SEP + ".",
           "--add-data", ADMIN_VERSION_TXT + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "_fill_all_builds.py") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "generate_prompt_v2.py") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "stats_data.py") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "tank_db.json") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "tank_tth.json") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "tank_slots_full.json") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "translations.py") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "game_entities_english.json") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "crew_builds.json") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "prompts_cache.json") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "game_entities.json") + SEP + ".",
           "--add-data", os.path.join(BASE_DIR, "admin_uk_seed.json") + SEP + "."]
    cmd.extend(add_data_args)
    cmd.append(os.path.join(BASE_DIR, "admin_main.py"))
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print("[BUILD] PyInstaller FAILED")
        sys.exit(1)
    exe = os.path.join(admin_exe_dir, "SM WoT Assistant Admin.exe")
    if not os.path.exists(exe):
        print("[BUILD] FATAL: EXE not found at " + exe)
        sys.exit(1)
    internal = os.path.join(admin_exe_dir, "_internal")
    if not os.path.isdir(internal):
        print("[BUILD] FATAL: _internal missing")
        sys.exit(1)
    if not os.path.exists(os.path.join(internal, "python312.dll")):
        print("[BUILD] FATAL: _internal missing python312.dll")
        sys.exit(1)
    count = sum(1 for _ in os.scandir(internal))
    size_mb = os.path.getsize(exe) / 1048576.0
    print("[BUILD] Admin (web) EXE: " + format(size_mb, ".1f") + " MB, _internal: " + str(count) + " entries")
    return admin_exe_dir


def clean():
    """SM WoT Assistant Admin.spec"""
    for p in (os.path.join(DIST_DIR, "SM WoT Assistant Admin"), os.path.join(DIST_DIR, "SM WoT Assistant Admin.exe")):
        if os.path.exists(p):
            if os.path.isdir(p):
                _rmtree_tolerant(p)
            else:
                os.remove(p)


def main():
    print("=" * 60)
    print("  SM WoT Assistant Admin (Web) - Build v" + read_version())
    print("=" * 60)
    version = read_version()
    clean()
    tmp_build = os.path.join(DIST_DIR, "Admin_TMP_BUILD_WEB")
    if os.path.exists(tmp_build):
        _rmtree_tolerant(tmp_build)
    if os.path.exists(ADMIN_DIR):
        print("[BUILD] canonical dir locked - building into Admin_TMP_BUILD_WEB, then deploying")
        build_admin_web(dist_dir=tmp_build)
        print("[BUILD] Deploying " + tmp_build + " -> " + ADMIN_DIR)
        shutil.copytree(os.path.join(tmp_build, "SM WoT Assistant Admin"), ADMIN_DIR, dirs_exist_ok=True)
        shutil.rmtree(tmp_build, ignore_errors=True)
    else:
        build_admin_web()
    print("[BUILD] Admin v" + version + " built!")
    print("[BUILD] EXE: " + os.path.join(ADMIN_DIR, "SM WoT Assistant Admin.exe"))


if __name__ == "__main__":
    main()
    sys.exit(0)
