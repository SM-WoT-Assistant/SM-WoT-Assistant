# -*- coding: utf-8 -*-
"""
Build script for SM WoT Tactics mod.
Compiles Python 2.7 .pyc and packages into .wotmod (ZIP format).

Usage: python build_mod.py
"""
import os
import sys
import py_compile
import zipfile
import shutil
import struct
import time

MOD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mod')
SRC_PY = os.path.join(MOD_DIR, 'res', 'scripts', 'client', 'gui', 'mods', 'mod_sm_tactics.py')
META_XML = os.path.join(MOD_DIR, 'meta.xml')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sm_tactics.wotmod')


def compile_pyc(src, dst):
    """Compile .py to .pyc for Python 2.7."""
    py_compile.compile(src, dst, doraise=True)
    print('  Compiled: %s -> %s' % (os.path.basename(src), os.path.basename(dst)))


def build_wotmod():
    """Package mod into .wotmod file."""
    if not os.path.isfile(SRC_PY):
        print('[BUILD] Source not found: %s' % SRC_PY)
        return False

    if not os.path.isfile(META_XML):
        print('[BUILD] meta.xml not found: %s' % META_XML)
        return False

    print('[BUILD] Building sm_tactics.wotmod...')

    tmp_dir = os.path.join(os.path.dirname(MOD_DIR), '_mod_build_tmp')
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

    # Create tmp structure
    pyc_dst_dir = os.path.join(tmp_dir, 'res', 'scripts', 'client', 'gui', 'mods')
    os.makedirs(pyc_dst_dir)

    # Copy meta.xml
    shutil.copy2(META_XML, os.path.join(tmp_dir, 'meta.xml'))

    # Compile .pyc
    pyc_dst = os.path.join(pyc_dst_dir, 'mod_sm_tactics.pyc')
    try:
        compile_pyc(SRC_PY, pyc_dst)
    except py_compile.PyCompileError as e:
        print('[BUILD] Compile error: %s' % e)
        shutil.rmtree(tmp_dir)
        return False

    # Also copy .py for reference
    shutil.copy2(SRC_PY, os.path.join(pyc_dst_dir, 'mod_sm_tactics.py'))

    # Package as ZIP (.wotmod)
    if os.path.isfile(OUTPUT):
        os.remove(OUTPUT)

    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(tmp_dir):
            for fn in files:
                fp = os.path.join(root, fn)
                arcname = os.path.relpath(fp, tmp_dir)
                zf.write(fp, arcname)
                print('  + %s' % arcname)

    shutil.rmtree(tmp_dir)

    size_kb = os.path.getsize(OUTPUT) / 1024.0
    print('[BUILD] Done: %s (%.1f KB)' % (OUTPUT, size_kb))
    return True


if __name__ == '__main__':
    ok = build_wotmod()
    sys.exit(0 if ok else 1)
