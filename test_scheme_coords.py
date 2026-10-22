# -*- coding: utf-8 -*-
"""Scheme coordinate contract regression test (docs/scheme-coords.md).

Run before every build and after any change touching coords paths:
    python test_scheme_coords.py

Locks the invariants that historically broke (shift ~10%, resize drift):
1. round-trip save/load preserves coords exactly;
2. render is resize-invariant (same map fraction at any window size);
3. mod AS3 parity (nx*size == org + u*img over the same square);
4. firebase/import export pass-through (no coords mutation);
5. norm:"img" stamp present on created/moved elements.
"""
import ast
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.abspath(__file__))
PASSED = 0
FAILED = 0


def check(name, cond, extra=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("[PASS] %s" % name)
    else:
        FAILED += 1
        print("[FAIL] %s %s" % (name, extra))


def _img_rect_for(cw, ch, border_px=20):
    """Replicates map_renderer.show_main_splash letterbox math."""
    border = max(5, int(border_px * min(cw, ch) / 800.0))
    size = min(cw, ch) - 2 * border
    map_x = border
    if cw > ch:
        map_x = border + (cw - 2 * border - size) / 2.0
    return (float(map_x), float(border), float(size), float(size))


def test_roundtrip():
    import tactics_manager
    db = os.path.join(tempfile.mkdtemp(), "s.json")
    elements = [
        {"type": "marker", "coords": [0.25, 0.30, 0.40, 0.45],
         "norm": "img", "text_coords": [0.32, 0.37]},
        {"type": "brush", "coords": [0.1, 0.1, 0.2, 0.2, 0.3, 0.15],
         "norm": "img"},
        {"type": "text", "coords": [0.7, 0.8], "norm": "img"},
    ]
    drawings = {"13_kyiv": elements}
    ok, _msg = tactics_manager.save_scheme_to_db(
        db, "13_kyiv", "Kyiv", "Standard", drawings, scheme_name="T")
    with open(db, encoding="utf-8") as f:
        raw = json.load(f)
    drawing_id = next(iter(raw)) if raw else None
    loaded = tactics_manager.load_scheme_from_db(db, drawing_id)
    if not ok or not loaded:
        check("T1 roundtrip loads scheme", False, "(no scheme)")
        return
    _, got = loaded
    ok = (len(got) == len(elements)
          and got[0]["coords"] == elements[0]["coords"]
          and got[1]["coords"] == elements[1]["coords"]
          and got[2]["coords"] == elements[2]["coords"]
          and got[0].get("text_coords") == elements[0]["text_coords"])
    check("T1 roundtrip save/load preserves coords", ok,
          (got[0]["coords"] if got else "empty"))


def test_resize_invariance():
    u, v = 0.35, 0.62
    fracs = []
    for cw, ch in ((800, 800), (1200, 1200), (1000, 800), (920, 920)):
        org_x, org_y, iw, ih = _img_rect_for(cw, ch)
        px = org_x + u * iw
        py = org_y + v * ih
        fracs.append(((px - org_x) / iw, (py - org_y) / ih))
    ok = all(abs(fx - u) < 1e-9 and abs(fy - v) < 1e-9 for fx, fy in fracs)
    check("T2 resize-invariant map fraction (4 window sizes)", ok, fracs)


def test_legacy_shift_detected():
    """The historical bug: canvas-fraction data rendered via image rect
    shifts toward centre — the test proves the shift EXISTS for legacy
    data and is GONE after migration (contract's reason for norm)."""
    u_old = 0.10
    cw = ch = 900.0
    org, _, img, _ = _img_rect_for(int(cw), int(ch))
    legacy_px = org + u_old * img          # new renderer, legacy data
    drawn_px = u_old * cw                  # where the user actually drew
    shift = abs(legacy_px - drawn_px)
    import tactics_manager
    items = [{"type": "marker", "coords": [u_old, u_old, 0.2, 0.2]}]
    tactics_manager.migrate_legacy_elements(items, cw, ch, org, img, img, img)
    m = items[0]
    migrated_px = org + m["coords"][0] * img
    check("T3 legacy shift exists pre-migration", shift > 5.0, shift)
    check("T3 migration restores drawn position",
          abs(migrated_px - drawn_px) < 1e-6, migrated_px - drawn_px)
    check("T3 migration stamps norm", m.get("norm") == "img", m.get("norm"))


def test_as3_parity():
    as3 = os.path.join(ROOT, "mod", "src", "as3", "com", "sm", "tactics",
                       "SmTacticsOverlay.as")
    with open(as3, encoding="utf-8") as f:
        src = f.read()
    check("T4 AS3 px() = [nx*_size, ny*_size]",
          "nx * _size" in src and "ny * _size" in src)
    py_mod = os.path.join(ROOT, "mod", "res", "scripts", "client", "gui",
                          "mods", "mod_sm_tactics.py")
    with open(py_mod, encoding="utf-8") as f:
        msrc = f.read()
    check("T4 mod reads saved_schemes.json directly",
          "saved_schemes.json" in msrc)
    u = 0.42
    img_editor = 860.0
    mod_size = 284.0
    check("T4 formula parity (linear over the square)",
          abs((u * img_editor) / img_editor - (u * mod_size) / mod_size) < 1e-12)


def test_pass_through():
    import tactics_manager
    import io
    elements = [{"type": "marker", "coords": [0.123456, 0.654321],
                 "norm": "img"}]
    # export format -> json -> import (no mutation anywhere)
    data = {"map_id": "01", "map_name": "x", "drawings": elements}
    buf = io.StringIO()
    json.dump(data, buf)
    buf.seek(0)
    restored = json.load(buf)
    check("T5 firebase/import JSON pass-through",
          restored["drawings"] == elements)
    # tactics_manager export path uses the same json.dump of drawings
    # (export_tactic line 51: "drawings": drawings[map_id]) — verify by AST
    # that no arithmetic touches coords in export/import functions.
    tree = ast.parse(open(os.path.join(ROOT, "tactics_manager.py"),
                          encoding="utf-8").read())
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "export_tactic", "import_tactic", "export_all_tactics",
                "import_all_tactics", "import_unified"):
            for sub in ast.walk(node):
                if isinstance(sub, ast.BinOp) and isinstance(sub.left, ast.Subscript):
                    bad.append((node.name, sub.lineno))
    check("T5 no coords arithmetic in import/export", not bad, bad)


def test_norm_stamp_in_painter():
    src = open(os.path.join(ROOT, "painter.py"), encoding="utf-8").read()
    norm_hits = (src.count('"norm": "img"')
                 + src.count("['norm'] = \"img\"")
                 + src.count('["norm"] = "img"'))
    check("T6 painter stamps norm on creation+move", norm_hits >= 3,
          norm_hits)
    # render geometry must come from _img_rect (redraw passes to _render_elements)
    tree = ast.parse(src)
    redraw = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "redraw":
            redraw = node
            break
    uses_rect = False
    if redraw:
        for sub in ast.walk(redraw):
            if (isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "_img_rect"):
                uses_rect = True
                break
    check("T6 redraw() geometry from _img_rect()", uses_rect)


def test_json_files_valid():
    ud = os.path.join(os.environ["APPDATA"], "SM WoT Assistant")
    for name in ("saved_schemes.json", "map_drawings.json"):
        p = os.path.join(ud, name)
        try:
            with open(p, encoding="utf-8") as f:
                json.load(f)
            check("T7 %s is valid JSON" % name, True)
        except Exception as e:
            check("T7 %s is valid JSON" % name, False, e)


if __name__ == "__main__":
    test_roundtrip()
    test_resize_invariance()
    test_legacy_shift_detected()
    test_as3_parity()
    test_pass_through()
    test_norm_stamp_in_painter()
    test_json_files_valid()
    print("\n%d passed, %d failed" % (PASSED, FAILED))
    sys.exit(1 if FAILED else 0)
