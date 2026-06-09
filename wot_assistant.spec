# -*- mode: python ; coding: utf-8 -*-
import os, sys, glob

root = os.path.dirname(os.path.abspath(SPECPATH))

def _rp(rel):
    return os.path.join(root, rel)

runtime_jsons = [
    "crew_builds.json",
    "equipment_loadouts.json",
    "game_entities.json",
    "game_entities_english.json",
    "icon_mapping.json",
    "map_list.json",
    "map_links.json",
    "tank_db.json",
    "tank_slots_db.json",
    "tank_slots_full.json",
    "tank_tth.json",
    "tui.json",
    "VERSION",
]

datas = []

for f in runtime_jsons:
    path = _rp(f)
    if os.path.exists(path):
        datas.append((path, "."))

for f in ["xvmsymbol.ttf", "fontawesome-webfont.ttf"]:
    path = _rp(f)
    if os.path.exists(path):
        datas.append((path, "."))

for f in ["artefacts_en.mo", "crew_perks_en.mo", "item_types_en.mo"]:
    path = _rp(f)
    if os.path.exists(path):
        datas.append((path, "."))

logo = _rp("logo.png")
if os.path.exists(logo):
    datas.append((logo, "."))

maps_dir = _rp("maps")
if os.path.exists(maps_dir):
    for folder in os.listdir(maps_dir):
        fpath = os.path.join(maps_dir, folder)
        if os.path.isdir(fpath):
            for f in os.listdir(fpath):
                datas.append((os.path.join(fpath, f), os.path.join("maps", folder)))

em_dir = _rp("extracted_maps")
if os.path.exists(em_dir):
    for f in os.listdir(em_dir):
        fpath = os.path.join(em_dir, f)
        if os.path.isfile(fpath) and f not in ("ukrainian_map_names_cache.json", ".map_extract_manifest.json"):
            datas.append((fpath, "extracted_maps"))

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

ed_pp = _rp(os.path.join("extracted_data", "common", "post_progression"))
if os.path.exists(ed_pp):
    for root2, dirs2, files2 in os.walk(ed_pp):
        for f in files2:
            src = os.path.join(root2, f)
            rel = os.path.relpath(src, _rp("extracted_data"))
            datas.append((src, os.path.join("extracted_data", os.path.dirname(rel))))


hiddenimports = [
    "keyboard",
    "PIL._tkinter_finder",
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
    [],
    exclude_binaries=True,
    name="SM WoT Assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(root, "logo.png") if os.path.exists(os.path.join(root, "logo.png")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SM WoT Assistant",
)
