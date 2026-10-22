#!/usr/bin/env python3
"""SM WoT Assistant Tray Watcher — minimal process monitor (no tkinter/no PIL/no requests).

Built as --onefile (PyInstaller). Watches for WorldOfTanks.exe via
CreateToolhelp32Snapshot at 5s intervals. When game starts: launches
SM WoT Assistant Launcher.exe (gated by launch_on_game_start). When game
stops + close_with_game setting: closes SM WoT Assistant v*.exe.
Also keeps sm_tactics.wotmod in mods/<current version>/ after game updates
(mod-sync on start + every ~60s — план А, 16.10.2026). Then returns to
monitoring.
"""

import os, sys, json, time, ctypes, subprocess, re, shutil, threading
from ctypes import wintypes

DEBUG = False

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001
# sizeof(PROCESSENTRY32W): 32-bit=556, 64-bit=568
PE_SIZE = 568 if ctypes.sizeof(ctypes.c_void_p) == 8 else 556
if DEBUG: print(f"[DEBUG] tray_watcher PE_SIZE={PE_SIZE}")

def _read_settings():
    appdata = os.environ.get("APPDATA", "")
    path = os.path.join(appdata, "SM WoT Assistant", "settings.json")
    if not os.path.exists(path):
        if DEBUG: print(f"[DEBUG] _read_settings: {path} NOT FOUND")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if DEBUG: print(f"[DEBUG] _read_settings: loaded {len(data)} keys")
            return data
    except Exception as e:
        if DEBUG: print(f"[DEBUG] _read_settings error: {e}")
        return {}

def _install_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "SM WoT Assistant")

def _find_launcher_exe():
    install_dir = _install_dir()
    launcher = os.path.join(install_dir, "SM WoT Assistant Launcher.exe")
    if DEBUG: print(f"[DEBUG] _find_launcher_exe: install_dir={install_dir}")
    if os.path.exists(launcher):
        if DEBUG: print(f"[DEBUG] _find_launcher_exe: found at {launcher}")
        return launcher
    exe_dir = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, 'frozen', False) else __file__))
    launcher2 = os.path.join(exe_dir, "SM WoT Assistant Launcher.exe")
    if DEBUG: print(f"[DEBUG] _find_launcher_exe: exe_dir={exe_dir}")
    if os.path.exists(launcher2):
        if DEBUG: print(f"[DEBUG] _find_launcher_exe: found at {launcher2}")
        return launcher2
    src_dir = os.path.dirname(os.path.abspath(__file__))
    launcher3 = os.path.join(src_dir, "SM WoT Assistant Launcher.exe")
    if DEBUG: print(f"[DEBUG] _find_launcher_exe: src_dir={src_dir}")
    if os.path.exists(launcher3):
        if DEBUG: print(f"[DEBUG] _find_launcher_exe: found at {launcher3}")
        return launcher3
    if DEBUG: print(f"[DEBUG] _find_launcher_exe: NOT FOUND in any location")
    return None

def _is_wot_running():
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        if DEBUG: print(f"[DEBUG] _is_wot_running: CreateToolhelp32Snapshot returned INVALID_HANDLE_VALUE")
        return False
    try:
        pe = (ctypes.c_byte * PE_SIZE)()
        ctypes.memset(pe, 0, PE_SIZE)
        ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            err = kernel32.GetLastError()
            if DEBUG: print(f"[DEBUG] _is_wot_running: Process32FirstW failed, GetLastError={err}")
            return False
        wot_count = 0
        while True:
            exe_buf = ctypes.create_unicode_buffer(260)
            ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
            if exe_buf.value and "WorldOfTanks.exe" in exe_buf.value:
                wot_count += 1
                return True  # found at least one
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        if DEBUG: print(f"[DEBUG] _is_wot_running: not found (scanned all processes)")
        return False
    finally:
        kernel32.CloseHandle(snapshot)

def _find_dev_pid():
    """Прочитати dev_pid.txt, валідувати що PID живий і це python.exe/pythonw.exe."""
    appdata = os.environ.get("APPDATA", "")
    path = os.path.join(appdata, "SM WoT Assistant", "dev_pid.txt")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            target = int(f.read().strip())
    except (ValueError, OSError):
        return None
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return None
    try:
        pe = (ctypes.c_byte * PE_SIZE)()
        ctypes.memset(pe, 0, PE_SIZE)
        ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            err = kernel32.GetLastError()
            if DEBUG: print(f"[DEBUG] _find_dev_pid: Process32FirstW failed, GetLastError={err}")
            return None
        while True:
            pid_bytes = (ctypes.c_byte * 4)()
            ctypes.memmove(pid_bytes, ctypes.byref(pe, 8), 4)
            pid = int.from_bytes(bytes(pid_bytes), 'little')
            exe_buf = ctypes.create_unicode_buffer(260)
            ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
            if pid == target and exe_buf.value:
                name = exe_buf.value.lower()
                if name in ("python.exe", "pythonw.exe"):
                    if DEBUG: print(f"[DEBUG] _find_dev_pid: found valid dev PID {target}")
                    return target
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        if DEBUG: print(f"[DEBUG] _find_dev_pid: PID {target} not found or not python")
        return None
    finally:
        kernel32.CloseHandle(snapshot)

def _find_main_pids():
    pids = []
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return pids
    try:
        pe = (ctypes.c_byte * PE_SIZE)()
        ctypes.memset(pe, 0, PE_SIZE)
        ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            err = kernel32.GetLastError()
            if DEBUG: print(f"[DEBUG] _find_main_pids: Process32FirstW failed, GetLastError={err}")
            return pids
        while True:
            exe_buf = ctypes.create_unicode_buffer(260)
            ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
            name = exe_buf.value
            if name and re.match(r"SM WoT Assistant v\d+\.\d+\.\d+.*\.exe", name):
                pid_bytes = (ctypes.c_byte * 4)()
                ctypes.memmove(pid_bytes, ctypes.byref(pe, 8), 4)
                pid = int.from_bytes(bytes(pid_bytes), 'little')
                if DEBUG: print(f"[DEBUG] _find_main_pids: found main PID {pid} ({name})")
                pids.append(pid)
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
        if DEBUG and not pids: print(f"[DEBUG] _find_main_pids: no main processes found")
        return pids
    finally:
        kernel32.CloseHandle(snapshot)

def _get_main_pids():
    """Об'єднати frozen EXE + dev PID."""
    pids = _find_main_pids()
    dev_pid = _find_dev_pid()
    if dev_pid is not None and dev_pid not in pids:
        pids.append(dev_pid)
    return pids

def _close_main_app():
    pids = _get_main_pids()
    if not pids:
        if DEBUG: print(f"[DEBUG] _close_main_app: no main pids to close")
        return
    if DEBUG: print(f"[DEBUG] _close_main_app: closing PIDs {pids}")
    for pid in pids:
        h = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if h:
            if DEBUG: print(f"[DEBUG] _close_main_app: TerminateProcess PID {pid}")
            kernel32.TerminateProcess(h, 0)
            kernel32.CloseHandle(h)
        else:
            if DEBUG: print(f"[DEBUG] _close_main_app: OpenProcess failed for PID {pid}, err={kernel32.GetLastError()}")

def _launch_app():
    main_pids = _get_main_pids()
    if DEBUG: print(f"[DEBUG] _launch_app: _get_main_pids()={main_pids}")
    if main_pids:
        if DEBUG: print(f"[DEBUG] _launch_app: main already running, skipping")
        return
    launcher = _find_launcher_exe()
    if launcher:
        if DEBUG: print(f"[DEBUG] _launch_app: launching {launcher}")
        subprocess.Popen([launcher], creationflags=0x08000000)
        return
    install_dir = _install_dir()
    if DEBUG: print(f"[DEBUG] _launch_app: launcher not found, checking install_dir={install_dir}")
    if os.path.isdir(install_dir):
        for f in os.listdir(install_dir):
            if f.startswith("SM WoT Assistant v") and f.endswith(".exe"):
                exe = os.path.join(install_dir, f)
                settings = _read_settings()
                args = [exe]
                if settings.get("start_minimized", False):
                    args.append("--tray")
                if DEBUG: print(f"[DEBUG] _launch_app: fallback launching {exe} args={args}")
                subprocess.Popen(args, creationflags=0x08000000)
                return
    if DEBUG: print(f"[DEBUG] _launch_app: NOTHING to launch — all paths failed")

def _launch_if_enabled(settings):
    """Запустити основну програму ТІЛЬКИ за launch_on_game_start (план А, 16.10.2026).

    Реєстрація tray_watcher в автозапуску від цього налаштування більше не
    залежить — mod-sync + close_with_game працюють завжди.
    """
    if settings.get("launch_on_game_start", False):
        _launch_app()

def _find_wotmod_source():
    """Джерело sm_tactics.wotmod для синхронізації мода.

    frozen (onedir): _internal/ біля цього exe — там саме лежить бандл основної
    програми (config.BASE_DIR). dev: поруч з tray_watcher.py (project root).
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        cands = [
            os.path.join(exe_dir, "_internal", "sm_tactics.wotmod"),
            os.path.join(exe_dir, "sm_tactics.wotmod"),
        ]
    else:
        cands = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "sm_tactics.wotmod")]
    for c in cands:
        if os.path.isfile(c) and os.path.getsize(c) > 0:
            return c
    return None

def _resolve_game_version(settings):
    """Актуальна версія гри: version.xml на диску, fallback — settings.game_version.

    Той самий підхід, що map_manager._resolve_game_version (формат
    « v.2.4.1.0 #974 » з пробілами — нормалізується регекстом у _sync_mod).
    """
    v = None
    wot_path = settings.get("wot_path", "")
    if wot_path:
        v_path = os.path.join(wot_path, "version.xml")
        if os.path.isfile(v_path):
            try:
                import xml.etree.ElementTree as ET
                v = ET.parse(v_path).getroot().findtext("version")
            except Exception:
                v = None
    if not v:
        v = str(settings.get("game_version", "") or "")
    return v

def _cleanup_stale_wotmods(mods_root, keep_dir_name):
    """Прибрати НАШ sm_tactics.wotmod з усіх версійних папок, крім поточної.

    Точне ім'я файлу (без wildcard — #1492); res_mods/ та сторонні моди не
    чіпаємо (#2041). Повертає True, якщо щось видалено.
    """
    changed = False
    try:
        for entry in os.listdir(mods_root):
            if entry == keep_dir_name:
                continue
            p = os.path.join(mods_root, entry, "sm_tactics.wotmod")
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    changed = True
                    if DEBUG: print(f"[DEBUG] _cleanup_stale_wotmods: removed {p}")
                except Exception as e:
                    if DEBUG: print(f"[DEBUG] _cleanup_stale_wotmods: failed {p}: {e}")
    except Exception as e:
        if DEBUG: print(f"[DEBUG] _cleanup_stale_wotmods error: {e}")
    return changed

def _sync_mod(settings):
    """Тримати sm_tactics.wotmod у mods/<поточна версія>/ (план А, 16.10.2026).

    Патч гри стирає mods/<стара версія>/ і створює порожню нову; основна
    програма може не бути запущена (launch_on_game_start=false) — тому
    синхронізація робиться тут: на старті та раз на ~60s. Логіка повторює
    map_manager.apply_mod_mode (use_mod gate, нормалізація версії регекстом,
    prefer-наявна-папка на диску). Джерело відсутнє → нічого не робимо
    (без half-sync). Повертає True, якщо щось змінено.
    """
    wot_path = settings.get("wot_path", "")
    if not wot_path:
        return False
    mods_root = os.path.join(wot_path, "mods")
    if not os.path.isdir(mods_root):
        return False
    if not settings.get("use_mod", False):
        # мод вимкнено користувачем — прибрати наш файл з усіх версійних папок
        removed = False
        try:
            for entry in os.listdir(mods_root):
                p = os.path.join(mods_root, entry, "sm_tactics.wotmod")
                if os.path.isfile(p):
                    try:
                        os.remove(p)
                        removed = True
                        if DEBUG: print(f"[DEBUG] _sync_mod: use_mod=off removed {p}")
                    except Exception as e:
                        if DEBUG: print(f"[DEBUG] _sync_mod: remove failed {p}: {e}")
        except Exception as e:
            if DEBUG: print(f"[DEBUG] _sync_mod sweep error: {e}")
        return removed
    game_version = _resolve_game_version(settings)
    if not game_version:
        return False
    m = re.search(r"\d+\.\d+\.\d+\.\d+", str(game_version))
    ver = m.group(0) if m else str(game_version).strip()
    # ПРЕФЕРУЄМО наявну папку версії на диску (лагідний монтаж, як у map_manager)
    mods_dir = None
    for cand in (ver, str(game_version).strip()):
        if cand and os.path.isdir(os.path.join(mods_root, cand)):
            mods_dir = os.path.join(mods_root, cand)
            break
    if mods_dir is None:
        mods_dir = os.path.join(mods_root, ver)
    src = _find_wotmod_source()
    if not src:
        if DEBUG: print("[DEBUG] _sync_mod: sm_tactics.wotmod source not found, skipping")
        return False
    changed = False
    try:
        dst = os.path.join(mods_dir, "sm_tactics.wotmod")
        if not os.path.isfile(dst):
            need = True
        else:
            try:
                dmt = os.path.getmtime(dst)
                smt = os.path.getmtime(src)
            except OSError:
                dmt = smt = 0
            if dmt > smt:
                # Guard 17.10 (#clobber 16-17.10): НІКОЛИ не затирати новіший
                # встановлений мод старішим джерелом — src із _internal (13.10)
                # затер зфіксований 16.10 білд лише за різницею розмірів.
                need = False
            else:
                need = (os.path.getsize(dst) != os.path.getsize(src) or smt > dmt)
        if need:
            os.makedirs(mods_dir, exist_ok=True)
            shutil.copy2(src, dst)
            changed = True
            if DEBUG: print(f"[DEBUG] _sync_mod: installed -> {mods_dir}")
    except Exception as e:
        if DEBUG: print(f"[DEBUG] _sync_mod: copy error: {e}")
        return changed
    if _cleanup_stale_wotmods(mods_root, os.path.basename(mods_dir)):
        changed = True
    return changed


# ── Сповіщення про помилки мода (16.10.2026; фікси 17.10) ─────────────────
# Сигнатури дзеркалять log_reader._match_mod_error_text (watcher — standalone
# onefile без імпортів з проєкту, тому логіка продубльована свідомо).
# 17.10.2026 (false positive 02:00): «Mod package ... loaded» — УСПІШНИЙ рядок —
# package-сигнатура вимагає error-ключове слово; .pyc-рядки ASL лоадера НЕ
# озброюють вікно пари (тільки traceback File "...mod_sm_tactics.py"); ASL
# one-line «failed to load mod_sm_tactics.pyc: ... ImportError» ловиться окремо.
_MOD_MENTION_FILE_RE = re.compile(r"mod_sm_tactics\.py(?!c)")
_MOD_ONE_LINE_RE = re.compile(
    r"(?:failed|Error|Exception|Traceback|not found)[^\r\n]*mod_sm_tactics"
    r"|mod_sm_tactics[^\r\n]*(?:failed|Error|Exception|Traceback|not found)",
    re.I)
_MOD_TAG_ERR_RE = re.compile(r"\[SM Tactics\].*(failed|not found|Error|Exception|Traceback)", re.I)
_MOD_KEYWORD_RE = re.compile(r"Error|Exception|Traceback|failed|not found", re.I)
_MOD_PACKAGE_RE = re.compile(
    r"(?:Mod package[^\r\n]*sm_tactics|sm_tactics[^\r\n]*Mod package)"
    r"[^\r\n]*(?:error|failed|not loaded|not supported)",
    re.I)
_MOD_WINDOW = 4
_MOD_SCAN_WINDOW = 2 * 1024 * 1024  # backward-вікно, як у log_reader._try_switch_to_game_log
_DELIVERY_MISS_BEATS = 3  # ~3×60s до balloon про нестачу файлу мода
_TS_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def _match_mod_error(text):
    """Повертає snippet першої помилки sm_tactics у тексті логу або None.

    Сигнатури (з реального game.log 15-16.10.2026):
    - `Mod package ... sm_tactics ... error` (#2025 клас; «loaded» НЕ ловиться);
    - one-line: `failed to load mod_sm_tactics.pyc: ... ImportError` (ASL лоадер);
    - import-pair: `File "...mod_sm_tactics.py"` (не .pyc) → протягом 4 наступних
      рядків keyword (Error/Exception/Traceback/failed/not found);
    - `[SM Tactics] ... failed|not found|Error...` — власні LOG.error мода.
    Навмисно НЕ ловить: логування успіху мода ([SM Tactics] ready, Mod package
    loaded, ASL executed script), «NO SCHEME»-попередження, помилки сторонніх
    модів (#2041).
    """
    window = 0
    mention = ""
    for line in text.splitlines():
        if _MOD_PACKAGE_RE.search(line):
            return line.strip()
        if _MOD_ONE_LINE_RE.search(line):
            return line.strip()
        if _MOD_MENTION_FILE_RE.search(line):
            window = _MOD_WINDOW
            mention = line
            continue
        if window > 0:
            if _MOD_KEYWORD_RE.search(line):
                return (mention + " || " + line).strip()
            window -= 1
        if _MOD_TAG_ERR_RE.search(line):
            return line.strip()
    return None


def _game_log_path(settings):
    lp = str(settings.get("log_path", "") or "")
    if lp and os.path.isfile(lp):
        return lp
    wot = str(settings.get("wot_path", "") or "")
    if wot:
        p = os.path.join(wot, "logs", "game.log")
        if os.path.isfile(p):
            return p
    return None


def _scan_game_log(settings, offset, tail_lines):
    """Інкрементальний скан game.log на помилки мода.

    Повертає (new_offset, snippet|None, tail_lines, scanned_text). tail_lines
    (останні 3 рядки попереднього чанку) тримають вікно пари File→Error
    цілісним на межі чанків. scanned_text = prefix+data потрібен caller'у для
    staleness-гейту (_error_is_fresh). offset=None або offset>size → baseline
    max(0, size−2MB).
    """
    path = _game_log_path(settings)
    if not path:
        return offset, None, tail_lines, ""
    try:
        size = os.path.getsize(path)
    except OSError:
        return offset, None, tail_lines, ""
    if offset is None or offset > size:
        offset = max(0, size - _MOD_SCAN_WINDOW)
        tail_lines = []  # нова сесія логу (truncation) — старий хвіст не сіє вікно
    if size <= offset:
        return offset, None, tail_lines, ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return offset, None, tail_lines, ""
    prefix = ""
    if tail_lines:
        prefix = "\n".join(tail_lines) + "\n"
    scanned = prefix + data
    snippet = _match_mod_error(scanned)
    lines = data.splitlines()
    if snippet:
        tail_lines = []  # спрацьована пара File→Error не сіє наступне вікно
    else:
        tail_lines = (tail_lines + lines)[-3:]
    return size, snippet, tail_lines, scanned


def _installed_mod_mtime(settings):
    """mtime встановленого mods/<ver>/sm_tactics.wotmod або None.

    Потрібен для staleness-гейту: game.log append-only без ротації сесій
    (#append-only), у backward-вікні 2MB лежать помилки минулих сесій і
    минулих білдів, уже виправлених (інцидент 16-17.10: помилка 15.10
    спрацювала як false positive на старті програми).
    """
    wot_path = str(settings.get("wot_path", "") or "")
    if not wot_path:
        return None
    mods_root = os.path.join(wot_path, "mods")
    if not os.path.isdir(mods_root):
        return None
    gv = _resolve_game_version(settings)
    if not gv:
        return None
    m = re.search(r"\d+\.\d+\.\d+\.\d+", str(gv))
    ver = m.group(0) if m else str(gv).strip()
    for cand in (ver, str(gv).strip()):
        if cand:
            p = os.path.join(mods_root, cand, "sm_tactics.wotmod")
            if os.path.isfile(p):
                try:
                    return os.path.getmtime(p)
                except OSError:
                    return None
    return None


def _error_is_fresh(full_text, snippet, mod_mtime):
    """Помилка свіжа, якщо її таймстамп НОВІШИЙ за mtime встановленого мода.

    mod_mtime None → не свіжа (мод не встановлено — помилка історична;
    відсутність файлу окремо сповіщає _check_mod_delivery B2). Без
    таймстампа у контексті snippet → свіжа (не гасимо формати без [ts]).
    """
    if mod_mtime is None or not snippet:
        return False
    pos = full_text.find(snippet)
    search = full_text if pos < 0 else full_text[:pos + len(snippet)]
    stamps = _TS_RE.findall(search)
    if not stamps:
        return True
    try:
        ts = time.mktime(time.strptime(stamps[-1], "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return True
    return ts > mod_mtime


def _mod_error_flag_path():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "SM WoT Assistant", "mod_error_pending.json")


def _write_mod_error_flag(snippet, game_version):
    """Прапорець для основної програми: Firebase-репорт при наступному старті
    (config.MOD_ERROR_FLAG_FILE — той самий шлях)."""
    path = _mod_error_flag_path()
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "found_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "game_version": game_version,
                "snippet": snippet[:500],
            }, f, ensure_ascii=False)
    except Exception as e:
        if DEBUG: print(f"[DEBUG] _write_mod_error_flag error: {e}")


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hWnd", wintypes.HWND),
        ("uID", ctypes.c_uint),
        ("uFlags", ctypes.c_uint),
        ("uCallbackMessage", ctypes.c_uint),
        ("hIcon", wintypes.HICON),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", ctypes.c_uint),
        ("dwStateMask", ctypes.c_uint),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeoutOrVersion", ctypes.c_uint),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.c_uint),
        ("guidItem", ctypes.c_wchar * 39),
        ("hBalloonIcon", wintypes.HICON),
    ]


_BALLOON_WP_REF = None  # живий референс WNDPROC для balloon-вікна проти GC


def _show_balloon(title, text, linger=20):
    """Одноразовий balloon (чистий ctypes, без постійної іконки в треї).

    Шаблон admin_main._Win32Tray: приховане вікно + NIM_ADD (іконка системна
    IDI_INFORMATION — без бандлу іконки) + NIM_MODIFY(NIF_INFO) → NIM_DELETE
    у daemon-потоці через linger секунд. Помилки ковтаються (best-effort).
    """
    try:
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = wintypes.LPARAM
        hinst = kernel32.GetModuleHandleW(None)

        WNDCLASSEXW = type("WNDCLASSEXW", (ctypes.Structure,), {"_fields_": [
            ("cbSize", ctypes.c_uint), ("style", ctypes.c_uint),
            ("lpfnWndProc", ctypes.c_void_p), ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON), ("hCursor", ctypes.c_void_p),
            ("hbrBackground", ctypes.c_void_p), ("lpszMenuName", ctypes.c_wchar_p),
            ("lpszClassName", ctypes.c_wchar_p), ("hIconSm", wintypes.HICON),
        ]})

        def _wp(hwnd, msg, wparam, lparam):
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wndproc = ctypes.WINFUNCTYPE(
            wintypes.LPARAM, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM)(_wp)
        global _BALLOON_WP_REF
        _BALLOON_WP_REF = wndproc  # референс проти GC

        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(cls)
        cls.lpfnWndProc = ctypes.cast(wndproc, ctypes.c_void_p)
        cls.hInstance = hinst
        cls.lpszClassName = "SMWoTBalloonClass"
        user32.RegisterClassExW(ctypes.byref(cls))  # 1410 (already exists) — ок

        hwnd = user32.CreateWindowExW(
            0, "SMWoTBalloonClass", "", 0, 0, 0, 0, 0, 0, 0, hinst, None)
        if not hwnd:
            return
        hicon = user32.LoadIconW(0, 32512)  # IDI_INFORMATION
        nid = _NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = 0x00000001 | 0x00000004  # NIF_ICON | NIF_TIP
        nid.hIcon = hicon
        nid.szTip = title[:128]
        shell32.Shell_NotifyIconW(0, ctypes.byref(nid))  # NIM_ADD
        nid2 = _NOTIFYICONDATAW()
        nid2.cbSize = ctypes.sizeof(nid2)
        nid2.hWnd = hwnd
        nid2.uID = 1
        nid2.uFlags = 0x00000010  # NIF_INFO
        nid2.szInfoTitle = title[:64]
        nid2.szInfo = text[:256]
        nid2.dwInfoFlags = 0x1  # NIIF_INFO
        shell32.Shell_NotifyIconW(1, ctypes.byref(nid2))  # NIM_MODIFY

        def _cleanup():
            time.sleep(linger)
            try:
                nid3 = _NOTIFYICONDATAW()
                nid3.cbSize = ctypes.sizeof(nid3)
                nid3.hWnd = hwnd
                nid3.uID = 1
                shell32.Shell_NotifyIconW(2, ctypes.byref(nid3))  # NIM_DELETE
                user32.DestroyWindow(hwnd)
            except Exception:
                pass

        threading.Thread(target=_cleanup, daemon=True).start()
        if DEBUG: print(f"[DEBUG] _show_balloon: {title!r} {text[:60]!r}")
    except Exception as e:
        if DEBUG: print(f"[DEBUG] _show_balloon error: {e}")


def _notify_mod_error(snippet, settings, main_running=None):
    """Координація сповіщень про помилку мода.

    Програма запущена → LogWatcher ловить ту саму помилку наживо і репортить
    сам (messagebox + Firebase) — watcher мовчить, щоб не дублювати.
    Програма НЕ запущена → balloon + flag-файл (програма відрапортує у
    Firebase при наступному старті). Повертає "program"|"balloon".
    """
    if main_running is None:
        main_running = bool(_get_main_pids())
    gv = _resolve_game_version(settings)
    mver = re.search(r"\d+\.\d+\.\d+\.\d+", str(gv or ""))
    ver = mver.group(0) if mver else ""
    if main_running:
        return "program"
    if ver:
        text = ("Помилка мода після оновлення гри (%s). "
                "Схеми на мінімапі можуть не працювати. Деталі: game.log") % ver
    else:
        text = "Помилка мода. Схеми на мінімапі можуть не працювати. Деталі: game.log"
    _show_balloon("SM WoT Assistant", text)
    _write_mod_error_flag(snippet, ver)
    return "balloon"


def _check_mod_delivery(settings, state):
    """B2: мод має лежати в mods/<поточна версія>/ поки гра запущена.

    Ловить клас симптому 16.10.2026, коли file-відсутність не лишає ЖОДНИХ
    слідів у game.log (меню модів просто зникає). state = {"counter", "notified"}
    оновлюється in-place; помилка лишається непоміченою _DELIVERY_MISS_BEATS
    ~60s-циклів поспіль (щоб не сповіщати про race на старті синку).
    Повертає "source"|"notinstalled"|None.
    """
    try:
        if not settings.get("use_mod", False):
            state["counter"] = 0
            return None
        wot_path = settings.get("wot_path", "")
        mods_root = os.path.join(wot_path, "mods") if wot_path else ""
        if not mods_root or not os.path.isdir(mods_root):
            state["counter"] = 0
            return None
        gv = _resolve_game_version(settings)
        if not gv:
            state["counter"] = 0
            return None
        m = re.search(r"\d+\.\d+\.\d+\.\d+", str(gv))
        ver = m.group(0) if m else str(gv).strip()
        mods_dir = None
        for cand in (ver, str(gv).strip()):
            if cand and os.path.isdir(os.path.join(mods_root, cand)):
                mods_dir = os.path.join(mods_root, cand)
                break
        if mods_dir is None:
            # папки версії ще немає на диску — не рахуємо як miss
            state["counter"] = 0
            return None
        dst = os.path.join(mods_dir, "sm_tactics.wotmod")
        if os.path.isfile(dst):
            state["counter"] = 0
            return None
        state["counter"] += 1
        if state["counter"] >= _DELIVERY_MISS_BEATS and not state["notified"]:
            state["notified"] = True
            return "source" if _find_wotmod_source() is None else "notinstalled"
        return None
    except Exception as e:
        if DEBUG: print(f"[DEBUG] _check_mod_delivery error: {e}")
        return None

def main():
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    _k32.CreateMutexW.restype = ctypes.c_void_p
    mutex = _k32.CreateMutexW(None, False, "SM_WoT_Assistant_TrayWatcher")
    if ctypes.get_last_error() == 183:
        if DEBUG: print(f"[DEBUG] main: another tray watcher already running, exiting")
        sys.exit(0)
    if DEBUG: print(f"[DEBUG] main: tray watcher started, PID={os.getpid()}")
    game_was = _is_wot_running()
    if DEBUG: print(f"[DEBUG] main: initial game_was={game_was}")
    launched = False  # сесію гри помічено (дедуп старту + умова close_with_game)
    cycle = 0
    scan_offset = None    # байтовий offset у game.log для скана помилок мода
    scan_tail = []        # останні 3 рядки попереднього чанку (вікно пари File→Error)
    mod_err_fired = False  # dedup: один balloon за ігрову сесію
    delivery_state = {"counter": 0, "notified": False}
    while True:
        cycle += 1
        settings = _read_settings()
        close_game = settings.get("close_with_game", False)
        # План А (16.10.2026): мод у mods/<поточна версія>/ — на старті та раз
        # на ~60s (патч гри може статись, поки основна програма не запущена).
        if cycle == 1 or cycle % 12 == 0:
            _sync_mod(settings)
        game_is = _is_wot_running()
        if game_is and not game_was and not launched:
            if DEBUG: print(f"[DEBUG] main cycle {cycle}: game DETECTED (game_was={game_was}, game_is={game_is}), launch_on_game_start={settings.get('launch_on_game_start', False)}")
            _launch_if_enabled(settings)
            launched = True
            # нова ігрова сесія — reset стану сповіщень про мод
            mod_err_fired = False
            delivery_state = {"counter": 0, "notified": False}
            scan_offset = None
            scan_tail = []
        elif not game_is and game_was and launched:
            if DEBUG: print(f"[DEBUG] main cycle {cycle}: game STOPPED, close_game={close_game}")
            if close_game:
                _close_main_app()
            launched = False
        game_was = game_is
        # Скан game.log на помилки мода (~60s, тільки поки гра запущена).
        # Baseline при першому скані сесії = max(0, size−2MB); помилки імпорту
        # зазвичай пишуться за хвилини ПОЧАТКУ сесії, тому вікна вистачає.
        if game_is and (cycle == 1 or cycle % 12 == 0) and not mod_err_fired:
            scan_offset, snippet, scan_tail, scanned = _scan_game_log(settings, scan_offset, scan_tail)
            if snippet:
                # staleness-гейт (17.10): game.log append-only — помилка старого
                # білда у вікні НЕ має сповіщати (false positive 02:00 на «loaded»
                # + три старі ImportError). Свіжі помилки поточної сесії проходять.
                if _error_is_fresh(scanned, snippet, _installed_mod_mtime(settings)):
                    mod_err_fired = True
                    outcome = _notify_mod_error(snippet, settings)
                    if DEBUG: print(f"[DEBUG] main cycle {cycle}: mod error detected -> {outcome}")
                else:
                    if DEBUG: print(f"[DEBUG] main cycle {cycle}: mod error suppressed (stale): {snippet[:120]}")
        # B2 (~60s): мод має бути у mods/<поточна версія>/ поки гра запущена
        # (відсутність файлу не лишає слідів у game.log — клас 16.10.2026).
        if game_is and cycle % 12 == 0:
            miss = _check_mod_delivery(settings, delivery_state)
            if miss:
                gv = _resolve_game_version(settings) or ""
                mver = re.search(r"\d+\.\d+\.\d+\.\d+", str(gv))
                vtag = " (%s)" % mver.group(0) if mver else ""
                if miss == "source":
                    text = "sm_tactics.wotmod відсутній в інсталяції програми" + vtag
                else:
                    text = "Мод не встановлено у mods" + vtag + " — схеми не працюватимуть"
                _show_balloon("SM WoT Assistant", text)
                _write_mod_error_flag("mod delivery: " + miss, str(gv or ""))
                if DEBUG: print(f"[DEBUG] main cycle {cycle}: delivery miss -> {miss}")
        if cycle % 12 == 0:  # every ~60s
            if DEBUG: print(f"[DEBUG] main cycle {cycle}: game_is={game_is}, launched={launched}, pids={_get_main_pids()}")
        time.sleep(5)

if __name__ == "__main__":
    main()
