#!/usr/bin/env python3
"""Build SM WoT Assistant Admin as a standalone onefile EXE.
Uploads to Firebase Hosting (admin-only download).
"""
import os, sys, json, subprocess, time, hashlib, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
PUBLIC_ADMIN_DIR = os.path.join(BASE_DIR, "public", "admin")
PYTHON_EXE = sys.executable

RTDB_URL = "https://sm-wot-assistant-default-rtdb.europe-west1.firebasedatabase.app"
API_KEY = "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"


def read_version():
    with open(os.path.join(BASE_DIR, "VERSION"), "r") as f:
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
        "--icon", os.path.join(BASE_DIR, "icon.ico"),
        "--name", "SM WoT Assistant Admin",
        "--distpath", DIST_DIR,
        "--workpath", os.path.join(BASE_DIR, "build", "admin_app"),
        "--specpath", os.path.join(BASE_DIR, "build"),
        "--clean",
        "--add-data", f"{os.path.join(BASE_DIR, 'icon.ico')}{os.pathsep}.",
        "--add-data", f"{os.path.join(BASE_DIR, 'VERSION')}{os.pathsep}.",
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


def deploy_to_firebase(version):
    """Upload admin EXE to GitHub Releases (Firebase Hosting blocks EXE files)."""
    print(f"[BUILD] Uploading to GitHub release v{version}...")
    src = os.path.join(DIST_DIR, "SM WoT Assistant Admin.exe")
    result = subprocess.run(
        ["gh", "release", "upload", f"v{version}", src, "--clobber"],
        cwd=BASE_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[BUILD] GitHub upload FAILED: {result.stderr}")
        return False
    print(f"[BUILD] GitHub upload OK")
    return True


def write_version_to_rtdb(version):
    """Write admin version metadata to RTDB."""
    import urllib.request

    size = os.path.getsize(os.path.join(DIST_DIR, "SM WoT Assistant Admin.exe"))
    size_str = f"{size / (1024 * 1024):.0f} MB"
    today = time.strftime("%Y-%m-%d")
    dl_url = f"https://github.com/nkcgml-boop/SM-WoT-Assistant/releases/download/v{version}/SM_WoT_Assistant_Admin.exe"

    data = json.dumps({
        "version": version,
        "display_version": f"{version} Beta",
        "release_date": today,
        "build_size": size_str,
        "download_url": dl_url,
    }).encode("utf-8")

    # Versioned entry
    for path in [f"versions/admin/{version.replace('.', '_')}", "versions/admin/latest"]:
        url = f"{RTDB_URL}/{path}.json?auth={API_KEY}"
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/json")
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            print(f"[BUILD] RTDB {path}: HTTP {resp.status}")
        except Exception as e:
            print(f"[BUILD] RTDB warning ({path}): {e}")

    print(f"[BUILD] Admin v{version} published")
    print(f"[BUILD] Download URL: {dl_url}")


def clean():
    """Clean build artifacts."""
    for p in [os.path.join(BASE_DIR, "build", "admin_app"),
              os.path.join(BASE_DIR, "SM WoT Assistant Admin.spec")]:
        if os.path.exists(p):
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
    # Clean old EXEs from dist (keep only latest)
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
    deploy_to_firebase(version)
    write_version_to_rtdb(version)

    print()
    print(f"[BUILD] Admin v{version} built and deployed!")
    print(f"[BUILD] Admin EXE: https://sm-wot-assistant.web.app/admin/SM_WoT_Assistant_Admin_v{version}.exe")
    print(f"[BUILD] Latest:     https://sm-wot-assistant.web.app/admin/SM_WoT_Assistant_Admin_latest.exe")


if __name__ == "__main__":
    main()
