#!/usr/bin/env python3
"""Build script for WoT Assistant — PyInstaller packaging + GitHub release.

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
DIST_DIR = os.path.join(BASE_DIR, "dist")


def read_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "0.0.0"


def write_version(v):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(v.strip() + "\n")
    print(f"[BUILD] VERSION = {v.strip()}")


def run_pyinstaller():
    print("[BUILD] Running PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", SPEC_FILE],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        print("[BUILD] PyInstaller FAILED")
        sys.exit(1)
    print("[BUILD] PyInstaller OK")

    exe_name = "WoT Assistant.exe"
    exe_path = os.path.join(DIST_DIR, exe_name)
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"[BUILD] {exe_name} — {size_mb:.1f} MB")
    else:
        print(f"[BUILD] WARNING: {exe_path} not found")
    return exe_path


def create_github_release(version):
    exe_path = os.path.join(DIST_DIR, "WoT Assistant.exe")
    if not os.path.exists(exe_path):
        print(f"[BUILD] ERROR: {exe_path} not found. Run build first.")
        sys.exit(1)

    # Check if gh CLI is available
    if shutil.which("gh") is None:
        print("[BUILD] WARNING: GitHub CLI (gh) not found. Skipping release.")
        print(f"[BUILD] Manual: gh release create v{version} dist/WoT_Assistant.exe")
        return

    tag = f"v{version}"
    changelog = os.path.join(BASE_DIR, "CHANGELOG.md")
    notes_flag = ["--notes-file", changelog] if os.path.exists(changelog) else ["--notes", f"Release {tag}"]

    print(f"[BUILD] Creating GitHub release {tag}...")
    result = subprocess.run(
        ["gh", "release", "create", tag, exe_path, "--title", tag] + notes_flag,
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

    run_pyinstaller()

    if do_release:
        create_github_release(version)

    print(f"[BUILD] Done: v{version}")


if __name__ == "__main__":
    main()
