import os
import time
import threading
import re

# ── Сигнатури помилок sm_tactics у логу (16.10.2026; фікси 17.10) ─────────
# Дзеркаляться у tray_watcher._match_mod_error (standalone onefile watcher
# без імпортів з проєкту — логіка продубльована свідомо; міняти разом).
# 17.10.2026: package-сигнатура вимагає error-ключове слово («Mod package ...
# loaded» — успіх, був false positive); .pyc ASL лоадера НЕ озброює вікно пари;
# ASL one-line «failed to load mod_sm_tactics.pyc: ... ImportError» окремо.
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
_TS_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def _installed_mod_mtime(wot_path):
    """mtime встановленого mods/<ver>/sm_tactics.wotmod або None (staleness-гейт)."""
    if not wot_path:
        return None
    mods_root = os.path.join(wot_path, "mods")
    if not os.path.isdir(mods_root):
        return None
    vp = os.path.join(wot_path, "version.xml")
    try:
        with open(vp, "r", encoding="utf-8", errors="ignore") as f:
            ver_text = f.read()
    except OSError:
        return None
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)", ver_text)
    if not m:
        return None
    p = os.path.join(mods_root, m.group(1), "sm_tactics.wotmod")
    try:
        return os.path.getmtime(p) if os.path.isfile(p) else None
    except OSError:
        return None


def _mod_error_stale(text, snippet, mod_mtime):
    """True = сповіщати НЕ треба (помилка зі старого білда/сесії).

    game.log append-only без ротації (#2053): backward-вікно містить помилки
    минулих днів. Свіжі (зараз у бою) — ts > mtime мода — проходять.
    mod_mtime None (мод не встановлено) → гасимо: відсутність файлу окремо
    сповіщає B2-перевірка tray_watcher.
    """
    if mod_mtime is None or not snippet:
        return True
    pos = text.find(snippet)
    search = text if pos < 0 else text[:pos + len(snippet)]
    stamps = _TS_RE.findall(search)
    if not stamps:
        return False
    try:
        ts = time.mktime(time.strptime(stamps[-1], "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return False
    return ts <= mod_mtime


def _match_mod_error_text(text):
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


class LogWatcher:
    def __init__(self, log_path, callback, hangar_callback=None, minimap_callback=None, countdown_callback=None, vehicle_callback=None, wot_path=""):
        self.log_path = log_path
        self.wot_path = wot_path
        self.callback = callback
        self.hangar_callback = hangar_callback
        self.minimap_callback = minimap_callback
        self.countdown_callback = countdown_callback
        self.vehicle_callback = vehicle_callback
        self.running = False
        self.thread = None
        self._last_size = 0
        self._last_arena_id = None
        self._countdown_fired_for_arena = None
        self._last_vehicle_cd = None
        self._battle_active = False
        self._stale_ticks = 0
        self._STALE_THRESHOLD = 15
        self._not_found_ticks = 0
        self._NOT_FOUND_THRESHOLD = 6
        self._log_error_fired = False
        self.on_log_error = None
        self.on_mod_error = None
        self._mod_fired_keys = set()   # dedup: ідентичний snippet — раз за сесію
        self._mod_window = 0           # вікно пари File→Error у live-циклі
        self._mod_mention = ""

        self.arena_re = re.compile(r"Loading space: spaces/(?P<map_id>\w+)")
        self.hangar_re = re.compile(r"Loading space: spaces/(?:hangar\w*|h\d+_\w+)")
        self.arena_type_re = re.compile(r"arenaType = (?P<type>\d+)")
        self.minimap_re = re.compile(r"Space is changed: WaitingSpace\(\) -> BattleLoadingSpace\(\)")
        self.battle_space_re = re.compile(r"Space is changed: BattleLoadingSpace\(\) -> BattleSpace\(\)")
        self.battle_loaded_re = re.compile(r"log battle loading finished, arena period: 2")
        self.vehicle_re = re.compile(r"\[helpers\.tips\] Tips context for battle:.*?compactDescr = (?P<cd>\d+)")
        self.last_type = 1

    def start(self):
        if self.running: return
        self.running = True
        if os.path.exists(self.log_path):
            self._last_size = os.path.getsize(self.log_path)
            print(f"[LOGWATCHER] Started with log_path={self.log_path}, size={self._last_size}")
        else:
            print(f"[LOGWATCHER] Started with log_path={self.log_path} (NOT FOUND)")
        # Backward one-shot для помилок мода (#1890-патерн): лог-помилка могла
        # бути записана ДО старту watcher. Виконується синхронно ДО потоку —
        # on_mod_error має бути призначений викликачем ПЕРЕД start().
        # Бойові події з цього вікна НЕ реплеяться (_last_size у кінці файлу).
        self._scan_mod_errors_backward()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _fire_log_error(self, msg):
        if self._log_error_fired:
            return
        self._log_error_fired = True
        print(f"[LOGWATCHER] ERROR: {msg}")
        if self.on_log_error:
            try:
                self.on_log_error(msg)
            except Exception as e:
                print(f"[LOGWATCHER] on_log_error callback failed: {e}")

    def _fire_mod_error(self, snippet):
        text = str(snippet or "")[:500]
        key = text[:200]
        if key in self._mod_fired_keys:
            return  # ідентична помилка вже сповіщалась (dedup)
        self._mod_fired_keys.add(key)
        print(f"[LOGWATCHER] MOD ERROR: {text}")
        if self.on_mod_error:
            try:
                self.on_mod_error(text)
            except Exception as e:
                print(f"[LOGWATCHER] on_mod_error callback failed: {e}")

    def _process_mod_error_line(self, line):
        """Інкрементальна детекція sm_tactics-помилок у live-циклі.

        Стан вікна пари File→Error зберігається між рядками
        (self._mod_window/self._mod_mention); сигнатури — _MOD_*_RE.
        Dedup (ідентичний snippet → раз) — у _fire_mod_error.
        """
        if _MOD_PACKAGE_RE.search(line):
            self._fire_mod_error(line)
            return
        if _MOD_ONE_LINE_RE.search(line):
            self._fire_mod_error(line)
            return
        if _MOD_MENTION_FILE_RE.search(line):
            self._mod_window = _MOD_WINDOW
            self._mod_mention = line
            return
        if self._mod_window > 0:
            if _MOD_KEYWORD_RE.search(line):
                self._fire_mod_error(self._mod_mention + " || " + line)
                return
            self._mod_window -= 1
        if _MOD_TAG_ERR_RE.search(line):
            self._fire_mod_error(line)

    def _scan_mod_errors_backward(self):
        """One-shot скан останніх 2MB логу на помилки мода при старті.

        Стейтлесний (_match_mod_error_text); не чіпає battle-події.
        """
        try:
            if not self.log_path or not os.path.exists(self.log_path):
                return
            size = os.path.getsize(self.log_path)
            if size <= 0:
                return
            start = max(0, size - 2 * 1024 * 1024)
            with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(start)
                text = f.read()
            snippet = _match_mod_error_text(text)
            if snippet:
                if _mod_error_stale(text, snippet, _installed_mod_mtime(self.wot_path)):
                    print("[LOGWATCHER] mod error suppressed (stale, older than installed mod): %s" % snippet[:120])
                    return
                self._fire_mod_error(snippet)
        except Exception as e:
            print(f"[LOGWATCHER] _scan_mod_errors_backward error: {e}")

    def _run(self):
        while self.running:
            try:
                if not self.log_path or not os.path.exists(self.log_path):
                    self._not_found_ticks += 1
                    if self._not_found_ticks >= self._NOT_FOUND_THRESHOLD:
                        self._fire_log_error(
                            f"Log file not found: {self.log_path}. "
                            "Auto-detect battle functions may not work."
                        )
                    time.sleep(5)
                    continue

                self._not_found_ticks = 0
                current_size = os.path.getsize(self.log_path)
                if current_size < self._last_size:
                    self._last_size = 0
                    self._last_arena_id = None
                    self._countdown_fired_for_arena = None
                    self._battle_active = False

                if current_size > self._last_size:
                    self._stale_ticks = 0
                    with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(self._last_size)
                        lines = f.readlines()
                        self._last_size = current_size

                        for line in lines:
                            clean_line = line.rstrip()
                            self._process_mod_error_line(clean_line)

                            match_type = self.arena_type_re.search(line)
                            if match_type:
                                self.last_type = int(match_type.group("type"))

                            match_veh = self.vehicle_re.search(line)
                            if match_veh:
                                cd = int(match_veh.group("cd"))
                                if cd != self._last_vehicle_cd:
                                    self._last_vehicle_cd = cd
                                    if self.vehicle_callback:
                                        self.vehicle_callback(cd)

                            if self.hangar_re.search(line):
                                was_battle = self._battle_active
                                self._battle_active = False
                                self._last_arena_id = None
                                self._countdown_fired_for_arena = None
                                self._last_vehicle_cd = None
                                if was_battle and self.hangar_callback:
                                    self.hangar_callback()

                            if self.battle_space_re.search(line):
                                ready = self._battle_active and self._last_arena_id is not None and self.countdown_callback
                                dedup = self._countdown_fired_for_arena != self._last_arena_id if ready else False
                                if ready and dedup:
                                    self._countdown_fired_for_arena = self._last_arena_id
                                    self.countdown_callback(self._last_arena_id, self.last_type)

                            if self.battle_loaded_re.search(line):
                                ready = self._battle_active and self._last_arena_id is not None and self.countdown_callback
                                dedup = self._countdown_fired_for_arena != self._last_arena_id if ready else False
                                if ready and dedup:
                                    self._countdown_fired_for_arena = self._last_arena_id
                                    self.countdown_callback(self._last_arena_id, self.last_type)

                            if self.minimap_re.search(line):
                                if self._last_arena_id is not None and self.minimap_callback:
                                    self.minimap_callback(self._last_arena_id, self.last_type)

                            match = self.arena_re.search(line)
                            if match:
                                map_id = match.group("map_id")
                                if not (map_id.startswith("hangar") or re.match(r"h\d+_\w+", map_id)):
                                    if self._last_arena_id != map_id:
                                        self._countdown_fired_for_arena = None
                                    self._battle_active = True
                                    self._last_arena_id = map_id
                                    # loading/battleTypes from client menu.json:
                                    # 30=Onslaught, 33=Onslaught, 34=Onslaught Training, 35=Onslaught Light
                                    type_to_mode = {
                                        1: "ctf",
                                        2: "domination",
                                        3: "assault",
                                        4: "comp7",
                                        5: "comp7_light",
                                        30: "comp7",
                                        33: "comp7",
                                        34: "comp7",
                                        35: "comp7_light",
                                    }
                                    mode = type_to_mode.get(self.last_type, "ctf")
                                    if self.callback:
                                        self.callback(map_id, mode)

                if current_size == self._last_size:
                    self._stale_ticks += 1
                    if self._stale_ticks >= self._STALE_THRESHOLD:
                        self._stale_ticks = 0
                        self._try_switch_to_game_log()

                time.sleep(2)
            except Exception:
                time.sleep(5)

    def update_path(self, new_path):
        self.log_path = new_path
        if self.log_path and os.path.exists(self.log_path):
            self._last_size = os.path.getsize(self.log_path)

    def _try_switch_to_game_log(self):
        if not self.log_path:
            return
        if "game.log" in self.log_path.lower():
            return
        log_dir = os.path.dirname(self.log_path)
        base_name = os.path.basename(self.log_path).lower()
        if base_name != "python.log":
            return
        game_log = os.path.join(log_dir, "game.log")
        if not os.path.exists(game_log):
            self._fire_log_error(
                f"python.log is stale and game.log not found in {log_dir}. "
                "Auto-detect battle functions may not work."
            )
            return
        gl_size = os.path.getsize(game_log)
        if gl_size <= 0:
            return
        scan_start = max(0, gl_size - 2 * 1024 * 1024)
        self.log_path = game_log
        self._last_size = scan_start
        self._stale_ticks = 0
        self._last_arena_id = None
        self._countdown_fired_for_arena = None
        self._battle_active = False
        print(f"[LOGWATCHER] Switched from python.log to game.log (scan from {scan_start}): {game_log}")
