# -*- coding: utf-8 -*-
"""
Build script for SM WoT Tactics mod.
Packages mod files into .wotmod (ZIP).

CRITICAL constraints (verified against this game client, 30.09.2026):
- Compression MUST be ZIP_STORED (compress=0). The client's package reader
  rejects DEFLATE with "Mod package ... load error: compression not supported"
  (game.log PY_DEBUG) - proven on both our DEFLATE packages vs all working
  community mods (pruszko, FastReconnect, ...) being STORE.
- Ship .pyc compiled by Python 2.7 ONLY (magic 62211). The game runs
  Python 2.7; a .pyc from this project's Python 3.12 (magic 3531) cannot be
  imported. Live evidence (30.09.2026): the .py-only package executed
  NOTHING - zero loader lines in game.log - while all 40 working mods are
  mod_*.pyc. Both loaders (the client's built-in scripts/client/gui/mods
  loader and Aslain's replacement of it) import .pyc from the standard
  VFS path; shipping .pyc keeps the mod autonomous of any modpack.
- meta.xml root tag must be <root> (all working mods), no XML declaration.
- Ship res/gui/flash/SmTacticsOverlay.swf alongside the pyc: a Scaleform
  View (community pattern wotstat/wotstat-positions) whose AS3 layer
  attaches INSIDE minimap.entriesContainer - no root anchoring, no z-stack.
  Compiling it needs the WG SWC externals in mod/src/as3/libs (fetched
  from the wotstat-positions repo on first build, gitignored).

Toolchain: portable Python 2.7.18 at tools/python27 (auto-provisioned from
python.org MSI via administrative extract - no system install, no admin);
optional Apache Flex SDK for SWF rebuild (falls back to the committed SWF).

Usage: python build_mod.py
"""
import os
import sys
import zipfile
import shutil
import subprocess
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOD_DIR = os.path.join(BASE_DIR, 'mod')
SRC_PY = os.path.join(MOD_DIR, 'res', 'scripts', 'client', 'gui', 'mods', 'mod_sm_tactics.py')
META_XML = os.path.join(MOD_DIR, 'meta.xml')
SWF_SRC = os.path.join(MOD_DIR, 'res', 'gui', 'flash', 'SmTacticsOverlay.swf')
AS3_DIR = os.path.join(MOD_DIR, 'src', 'as3')
AS3_FILE = os.path.join(AS3_DIR, 'com', 'sm', 'tactics', 'SmTacticsOverlay.as')
AS3_LIBS = os.path.join(AS3_DIR, 'libs')
# WG externals (compile-time only) fetched from the wotstat-positions repo
WG_SWCS = ['base_app-1.0-SNAPSHOT.swc', 'battle.swc',
           'common-1.0-SNAPSHOT.swc', 'common_i18n_library-1.0-SNAPSHOT.swc',
           'flash.swc', 'gui_base-1.0-SNAPSHOT.swc',
           'gui_battle-1.0-SNAPSHOT.swc', 'gui_lobby-1.0-SNAPSHOT.swc',
           'lobby.swc']
WG_SWCS_URL = ('https://raw.githubusercontent.com/wotstat/'
               'wotstat-positions/3e770f3a/as3/libs/')
FONTS = [os.path.join(BASE_DIR, 'xvmsymbol.ttf'),
         os.path.join(BASE_DIR, 'fontawesome-webfont.ttf')]
OUTPUT = os.path.join(BASE_DIR, 'sm_tactics.wotmod')

PY27_DIR = os.path.join(BASE_DIR, 'tools', 'python27')
PY27_EXE = os.path.join(PY27_DIR, 'python.exe')
PY27_MSI_URL = 'https://www.python.org/ftp/python/2.7.18/python-2.7.18.amd64.msi'


def ensure_python27():
    """Locate (or auto-provision) the portable Python 2.7 compiler.

    pyc must carry the client's magic 62211 - only a real Python 2.7
    interpreter can produce it; Python 3.12 cannot.
    """
    if os.path.isfile(PY27_EXE):
        return PY27_EXE

    print('[BUILD] Portable Python 2.7 not found at %s' % PY27_DIR)
    print('[BUILD] Downloading python-2.7.18.amd64.msi ...')
    msi_path = os.path.join(tempfile.gettempdir(), 'python-2.7.18.amd64.msi')
    try:
        from urllib.request import urlretrieve
        urlretrieve(PY27_MSI_URL, msi_path)
    except Exception as exc:
        raise RuntimeError('[BUILD] Python 2.7 download failed: %s' % exc)

    # Administrative extract = plain file copy into the target dir,
    # no system install and no elevation required.
    print('[BUILD] Extracting (msiexec /a) ...')
    os.makedirs(PY27_DIR, exist_ok=True)
    proc = subprocess.Popen(
        ['msiexec', '/a', msi_path, '/qn', 'TARGETDIR=' + PY27_DIR])
    code = proc.wait()
    if code not in (0, 3010) or not os.path.isfile(PY27_EXE):
        raise RuntimeError('[BUILD] Python 2.7 extract failed (exit=%s)' % code)

    print('[BUILD] Python 2.7 ready: %s' % PY27_EXE)
    return PY27_EXE


def compile_py27(py27, src, dst):
    """Compile src -> dst with the py2.7 interpreter; verify pyc magic."""
    code = ('import py_compile,sys; '
            'py_compile.compile(sys.argv[1], sys.argv[2], doraise=True)')
    subprocess.check_call([py27, '-c', code, src, dst])
    # imp.get_magic() through text-mode stdout would be mangled by Windows
    # newline translation (\n -> \r\n) - write the magic to a binary file.
    magic_file = dst + '.magic'
    subprocess.check_call(
        [py27, '-c',
         'import imp,sys; f=open(sys.argv[1],"wb"); '
         'f.write(imp.get_magic()); f.close()', magic_file])
    with open(magic_file, 'rb') as fh:
        expected = fh.read()
    os.remove(magic_file)
    with open(dst, 'rb') as fh:
        header = fh.read(4)
    if header != expected:
        raise RuntimeError(
            '[BUILD] pyc magic mismatch: got %r want %r' % (header, expected))
    print('  compiled %s (magic %r OK)'
          % (os.path.basename(dst), expected[:2]))


FLEX_CANDIDATES = [
    os.path.join(os.environ.get('LOCALAPPDATA') or '', 'Temp', 'opencode',
                 'apache-flex-sdk-4.16.1-bin'),
    os.path.join(BASE_DIR, 'tools', 'flexsdk'),
]


def find_flex_sdk():
    for cand in FLEX_CANDIDATES:
        if not cand:
            continue
        jar = os.path.join(cand, 'lib', 'mxmlc.jar')
        cfg = os.path.join(cand, 'frameworks', 'flex-config.xml')
        if os.path.isfile(jar) and os.path.isfile(cfg):
            return cand
    return None


def ensure_wg_swcs():
    """Fetch the WG compile-time externals if missing (gitignored, ~6 MB)."""
    os.makedirs(AS3_LIBS, exist_ok=True)
    for name in WG_SWCS:
        dst = os.path.join(AS3_LIBS, name)
        if os.path.isfile(dst) and os.path.getsize(dst) > 1000:
            continue
        print('[BUILD] Fetching WG external: %s' % name)
        from urllib.request import urlopen
        try:
            resp = urlopen(WG_SWCS_URL + name, timeout=60)
            data = resp.read()
            resp.close()
            if not data.startswith(b'PK'):
                print('[BUILD] FATAL: %s is not a zip (got %r)'
                      % (name, data[:16]))
                return False
            with open(dst, 'wb') as fh:
                fh.write(data)
        except Exception as exc:
            print('[BUILD] FATAL: cannot fetch %s: %s' % (name, exc))
            return False
    return True


def rebuild_swf():
    """Rebuild the SWF from mod/src/as3 when a Flex SDK is available.

    Recipe (working, 30.09.2026): options must be SPACE-form
    (-swf-version 36, NOT -swf-version=36 - "=" forms fail with
    "default arguments may not be interspersed"), cwd must be
    <sdk>/frameworks (the default config loads as ./flex-config.xml).
    WG classes (AbstractView, Minimap, ...) are compile-time externals
    from mod/src/as3/libs via repeated -external-library-path+=.
    Without an SDK the committed SWF is shipped.
    """
    sdk = find_flex_sdk()
    if sdk is None:
        if os.path.isfile(SWF_SRC):
            print('[BUILD] No Flex SDK found - using committed SWF: %s' % SWF_SRC)
            return True
        print('[BUILD] FATAL: no Flex SDK and no committed SWF at %s' % SWF_SRC)
        return False
    if not ensure_wg_swcs():
        return False
    # Embed sources resolve beside the .as file - keep the fonts there
    pkg_dir = os.path.dirname(AS3_FILE)
    for font in FONTS:
        if not os.path.isfile(font):
            print('[BUILD] FATAL: font missing: %s' % font)
            return False
        shutil.copy2(font, os.path.join(pkg_dir, os.path.basename(font)))
    print('[BUILD] Rebuilding SWF with %s ...' % sdk)
    os.makedirs(os.path.dirname(SWF_SRC), exist_ok=True)
    cmd = ['java', '-jar', os.path.join(sdk, 'lib', 'mxmlc.jar'),
           '-source-path', AS3_DIR]
    for name in WG_SWCS:
        cmd.append('-external-library-path+=%s' % os.path.join(AS3_LIBS, name))
    cmd += ['-swf-version', '36',
            '-target-player', '32.0',
            '-output', SWF_SRC,
            AS3_FILE]
    subprocess.check_call(cmd, cwd=os.path.join(sdk, 'frameworks'))
    with open(SWF_SRC, 'rb') as fh:
        hdr = fh.read(4)
    if hdr[:3] not in (b'FWS', b'CWS') or hdr[3] != 36:
        print('[BUILD] FATAL: unexpected SWF header %r' % (hdr,))
        return False
    print('  SWF OK: %d bytes, version %d' % (os.path.getsize(SWF_SRC), hdr[3]))
    return True


def build_wotmod():
    """Package mod into .wotmod file."""
    if not os.path.isfile(SRC_PY):
        print('[BUILD] Source not found: %s' % SRC_PY)
        return False

    if not os.path.isfile(META_XML):
        print('[BUILD] meta.xml not found: %s' % META_XML)
        return False

    py27 = ensure_python27()

    if not rebuild_swf():
        return False

    print('[BUILD] Building sm_tactics.wotmod (ZIP_STORED, py2.7 pyc)...')

    tmp_dir = os.path.join(BASE_DIR, '_mod_build_tmp')
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

    # tmp structure: meta.xml + mod_sm_tactics.pyc (no .py in the package -
    # all working mods ship .pyc only; dual postfix risks double registration)
    # + res/gui/flash/SmTacticsOverlay.swf (the View loaded by the pyc)
    py_dst_dir = os.path.join(tmp_dir, 'res', 'scripts', 'client', 'gui', 'mods')
    os.makedirs(py_dst_dir)
    swf_dst_dir = os.path.join(tmp_dir, 'res', 'gui', 'flash')
    os.makedirs(swf_dst_dir)
    shutil.copy2(META_XML, os.path.join(tmp_dir, 'meta.xml'))
    shutil.copy2(SWF_SRC, os.path.join(swf_dst_dir, 'SmTacticsOverlay.swf'))
    compile_py27(py27, SRC_PY,
                 os.path.join(py_dst_dir, 'mod_sm_tactics.pyc'))

    # Package as ZIP (.wotmod)
    if os.path.isfile(OUTPUT):
        os.remove(OUTPUT)

    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_STORED) as zf:
        for root, dirs, files in os.walk(tmp_dir):
            for fn in files:
                fp = os.path.join(root, fn)
                arcname = os.path.relpath(fp, tmp_dir)
                zf.write(fp, arcname)
                print('  + %s' % arcname)

    shutil.rmtree(tmp_dir)

    # Read-back verification of the two hard constraints
    with zipfile.ZipFile(OUTPUT) as zf:
        bad = [i.filename for i in zf.infolist() if i.compress_type != 0]
        names = zf.namelist()
    if bad:
        print('[BUILD] FATAL: non-STORE entries: %s' % bad)
        return False
    if 'meta.xml' not in names:
        print('[BUILD] FATAL: meta.xml missing from package')
        return False
    if 'res/gui/flash/SmTacticsOverlay.swf' not in names:
        print('[BUILD] FATAL: SmTacticsOverlay.swf missing from package')
        return False
    if 'res/scripts/client/gui/mods/mod_sm_tactics.pyc' not in names:
        print('[BUILD] FATAL: mod_sm_tactics.pyc missing from package')
        return False

    size_kb = os.path.getsize(OUTPUT) / 1024.0
    print('[BUILD] Done: %s (%.1f KB, %d entries, all STORED)'
          % (OUTPUT, size_kb, len(names)))
    return True


if __name__ == '__main__':
    ok = build_wotmod()
    sys.exit(0 if ok else 1)
