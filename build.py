#!/usr/bin/env python3
"""Build script for WoT Assistant -- PyInstaller onedir + NSIS installer + GitHub release.

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
ONEDIR_OUTPUT = os.path.join(DIST_DIR, "WoT Assistant")


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
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", SPEC_FILE],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        print("[BUILD] PyInstaller FAILED")
        sys.exit(1)
    print("[BUILD] PyInstaller OK")

    exe = os.path.join(ONEDIR_OUTPUT, "WoT Assistant.exe")
    if os.path.exists(exe):
        size_mb = os.path.getsize(exe) / (1024 * 1024)
        print(f"[BUILD] {ONEDIR_OUTPUT} -- exe {size_mb:.1f} MB")
    else:
        print(f"[BUILD] WARNING: {exe} not found")
    return exe


def run_nsis(version):
    makensis = find_nsis()
    if not makensis:
        print("[BUILD] WARNING: NSIS (makensis) not found. Skipping installer.")
        print("[BUILD] Install NSIS from https://nsis.sourceforge.io/Download")
        return None

    out_exe = os.path.join(DIST_DIR, f"WoT_Assistant_Setup_v{version}.exe")
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
    installer = os.path.join(DIST_DIR, f"WoT_Assistant_Setup_v{version}.exe")
    if os.path.exists(installer):
        release_file = installer
    else:
        zip_name = os.path.join(DIST_DIR, f"WoT_Assistant_v{version}.zip")
        if os.path.exists(ONEDIR_OUTPUT):
            print(f"[BUILD] Creating {zip_name}...")
            shutil.make_archive(zip_name.replace(".zip", ""), "zip", DIST_DIR, "WoT Assistant")
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
    print(f"[BUILD] Building WoT Assistant v{version}")

    update_nsi_version(version)
    run_pyinstaller()
    run_nsis(version)

    if do_release:
        create_github_release(version)

    print(f"[BUILD] Done: v{version}")


if __name__ == "__main__":
    main()
