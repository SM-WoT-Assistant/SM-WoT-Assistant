import os
import time
import threading
import re

class LogWatcher:
    def __init__(self, log_path, callback, hangar_callback=None, minimap_callback=None, countdown_callback=None, vehicle_callback=None):
        self.log_path = log_path
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
                                    type_to_mode = {
                                        1: "ctf",
                                        2: "domination",
                                        3: "assault",
                                        4: "comp7",
                                        5: "comp7_light",
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
