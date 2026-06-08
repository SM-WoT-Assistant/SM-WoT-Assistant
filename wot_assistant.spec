# -*- mode: python ; coding: utf-8 -*-
import os, sys, glob

root = os.path.dirname(os.path.abspath(SPECPATH))
BASE_DIR = root

def _rp(rel):
    return os.path.join(root, rel)

# ---------------------------------------------------------------------------
# Runtime JSON data files (root level, no tomato/cache/manifest junk)
# ---------------------------------------------------------------------------
runtime_jsons = [
    "crew_builds.json",
    "equipment_loadouts.json",
    "game_entities.json",
    "game_entities_english.json",
    "icon_mapping.json",
    "locales.json",
    "map_drawings.json",
    "map_links.json",
    "map_list.json",
    "service_messages.json",
    "settings.json",
    "tank_db.json",
    "tank_slots_db.json",
    "tank_slots_full.json",
    "tank_tth.json",
    "tui.json",
    "VERSION",
]

# ---------------------------------------------------------------------------
# Build the datas list
# ---------------------------------------------------------------------------
datas = []

# Root runtime JSON + VERSION + fonts + other root files
for f in runtime_jsons:
    path = _rp(f)
    if os.path.exists(path):
        datas.append((path, "."))

# Fonts
for f in ["xvmsymbol.ttf", "fontawesome-webfont.ttf"]:
    path = _rp(f)
    if os.path.exists(path):
        datas.append((path, "."))

# Localization (.mo files)
for f in ["artefacts_en.mo", "crew_perks_en.mo", "item_types_en.mo"]:
    path = _rp(f)
    if os.path.exists(path):
        datas.append((path, "."))

# Logo
logo = _rp("logo.png")
if os.path.exists(logo):
    datas.append((logo, "."))

# ---------------------------------------------------------------------------
# maps/ directory (TACTIC minimap images)
# ---------------------------------------------------------------------------
maps_dir = _rp("maps")
if os.path.exists(maps_dir):
    for folder in os.listdir(maps_dir):
        fpath = os.path.join(maps_dir, folder)
        if os.path.isdir(fpath):
            for f in os.listdir(fpath):
                datas.append((os.path.join(fpath, f), os.path.join("maps", folder)))

# ---------------------------------------------------------------------------
# extracted_maps/ (MAPS II minimaps + JSON data only, no temp_xml)
# ---------------------------------------------------------------------------
em_dir = _rp("extracted_maps")
if os.path.exists(em_dir):
    for f in os.listdir(em_dir):
        fpath = os.path.join(em_dir, f)
        if os.path.isfile(fpath) and f not in ("ukrainian_map_names_cache.json", ".map_extract_manifest.json"):
            datas.append((fpath, "extracted_maps"))

# ---------------------------------------------------------------------------
# extracted_icons/ (all 8 runtime subdirectories)
# ---------------------------------------------------------------------------
ei_dir = _rp("extracted_icons")
if os.path.exists(ei_dir):
    for sub in os.listdir(ei_dir):
        spath = os.path.join(ei_dir, sub)
        if os.path.isdir(spath):
            for root2, dirs2, files2 in os.walk(spath):
                for f in files2:
                    src = os.path.join(root2, f)
                    rel = os.path.relpath(src, ei_dir)
                    datas.append((src, os.path.join("extracted_icons", os.path.dirname(rel))))

# ---------------------------------------------------------------------------
# extracted_data/common/post_progression/ (field mod data only)
# ---------------------------------------------------------------------------
ed_pp = _rp(os.path.join("extracted_data", "common", "post_progression"))
if os.path.exists(ed_pp):
    for root2, dirs2, files2 in os.walk(ed_pp):
        for f in files2:
            src = os.path.join(root2, f)
            rel = os.path.relpath(src, _rp("extracted_data"))
            datas.append((src, os.path.join("extracted_data", os.path.dirname(rel))))

# ---------------------------------------------------------------------------
# tools/orion/ (XML decoder — all files except WebUpdate.ini)
# ---------------------------------------------------------------------------
orion_dir = _rp(os.path.join("tools", "orion"))
if os.path.exists(orion_dir):
    for root2, dirs2, files2 in os.walk(orion_dir):
        for f in files2:
            if f == "WebUpdate.ini":
                continue
            src = os.path.join(root2, f)
            rel = os.path.relpath(src, _rp("tools"))
            datas.append((src, os.path.join("tools", os.path.dirname(rel))))

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hiddenimports = [
    "keyboard",
    "PIL._tkinter_finder",
]

# ---------------------------------------------------------------------------
# Exclude garbage modules/dirs
# ---------------------------------------------------------------------------
excludes = [
    "selenium", "webdriver_manager", "urllib3",
    "PyQt6.QtWebEngineCore",  # pulled by ai_webview_gui import, but needed at runtime
]

# ===========================================================================
a = Analysis(
    ["main.py"],
    pathex=[root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WoT Assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(root, "logo.png") if os.path.exists(os.path.join(root, "logo.png")) else None,
)
