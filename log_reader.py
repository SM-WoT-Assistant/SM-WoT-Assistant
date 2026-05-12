import os
import time
import threading
import re

class LogWatcher:
    def __init__(self, log_path, callback, hangar_callback=None, minimap_callback=None, countdown_callback=None, vehicle_callback=None):
        self.log_path = log_path
        self.callback = callback
        self.hangar_callback = hangar_callback  # Callback для повернення в ангар
        self.minimap_callback = minimap_callback  # Callback коли мініматери з'являється
        self.countdown_callback = countdown_callback  # Callback коли стартує передбойовий відлік
        self.vehicle_callback = vehicle_callback  # Callback коли виявлено техніку гравця
        self.running = False
        self.thread = None
        self._last_size = 0
        self._last_arena_id = None  # Відстежуємо, щоб не викликати мініматп двічі
        self._countdown_fired_for_arena = None
        self._last_vehicle_cd = None  # Останній виявлений compactDescr техніки
        
        # Регулярний вираз для виявлення завантаження карти (бою)
        # Приклад: Loading space: spaces/01_karelia
        self.arena_re = re.compile(r"Loading space: spaces/(?P<map_id>\w+)")
        self.hangar_re = re.compile(r"Loading space: spaces/hangar")
        self.arena_type_re = re.compile(r"arenaType = (?P<type>\d+)")
        # Регулярний вираз для мініматп - коли UI готова
        self.minimap_re = re.compile(r"Space is changed: WaitingSpace\(\) -> BattleLoadingSpace\(\)")
        # Тригер перемикання у бойовий режим:
        # 1) Основний — BattleLoadingSpace() -> BattleSpace()
        # 2) Fallback — log battle loading finished, arena period: 2
        self.battle_space_re = re.compile(r"Space is changed: BattleLoadingSpace\(\) -> BattleSpace\(\)")
        self.battle_loaded_re = re.compile(r"log battle loading finished, arena period: 2")
        # Техніка гравця: [helpers.tips] Tips context for battle: {'battlesCount': N, 'vehicleType': VehicleTypeInfoVO(compactDescr = NNNN), 'arenaType': N}
        self.vehicle_re = re.compile(r"\[helpers\.tips\] Tips context for battle:.*?compactDescr = (?P<cd>\d+)")
        self.last_type = 1  # default ctf

    def start(self):
        if self.running: return
        self.running = True
        # Починаємо з кінця файлу, щоб не перемикатися на старі бої при запуску
        if os.path.exists(self.log_path):
            self._last_size = os.path.getsize(self.log_path)
            
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        while self.running:
            try:
                if not self.log_path or not os.path.exists(self.log_path):
                    time.sleep(5)
                    continue
                
                current_size = os.path.getsize(self.log_path)
                if current_size < self._last_size:
                    # Файл був обнулений (гра перезапущена)
                    self._last_size = 0
                    self._last_arena_id = None
                    self._countdown_fired_for_arena = None
                
                if current_size > self._last_size:
                    with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(self._last_size)
                        lines = f.readlines()
                        self._last_size = current_size
                        
                        for line in lines:
                            clean_line = line.rstrip()

                            # Спочатку перевіряємо arenaType
                            match_type = self.arena_type_re.search(line)
                            if match_type:
                                self.last_type = int(match_type.group("type"))

                            # Виявлення техніки гравця
                            match_veh = self.vehicle_re.search(line)
                            if match_veh:
                                cd = int(match_veh.group("cd"))
                                if cd != self._last_vehicle_cd:
                                    self._last_vehicle_cd = cd
                                    if self.vehicle_callback:
                                        self.vehicle_callback(cd)
                            
                            # Перевіряємо повернення в ангар
                            if self.hangar_re.search(line):
                                self._last_arena_id = None
                                self._countdown_fired_for_arena = None
                                self._last_vehicle_cd = None
                                if self.hangar_callback:
                                    self.hangar_callback()

                            # Основний тригер перемикання у бойовий режим
                            if self.battle_space_re.search(line):
                                if self._last_arena_id is not None and self.countdown_callback:
                                    if self._countdown_fired_for_arena != self._last_arena_id:
                                        self._countdown_fired_for_arena = self._last_arena_id
                                        self.countdown_callback(self._last_arena_id, self.last_type)

                            # Fallback, якщо основний маркер з якоїсь причини не зловився
                            if self.battle_loaded_re.search(line):
                                if self._last_arena_id is not None and self.countdown_callback:
                                    if self._countdown_fired_for_arena != self._last_arena_id:
                                        self._countdown_fired_for_arena = self._last_arena_id
                                        self.countdown_callback(self._last_arena_id, self.last_type)
                            
                            # Перевіряємо появу мініматп (UI готова)
                            if self.minimap_re.search(line):
                                if self._last_arena_id is not None and self.minimap_callback:
                                    self.minimap_callback(self._last_arena_id, self.last_type)
                            
                            # Перевіряємо завантаження карти (для синхронізації фільтрів)
                            match = self.arena_re.search(line)
                            if match:
                                map_id = match.group("map_id")
                                # Пропускаємо ангар - це не бій
                                if not map_id.startswith("hangar"):
                                    if self._last_arena_id != map_id:
                                        self._countdown_fired_for_arena = None
                                    self._last_arena_id = map_id  # Зберігаємо для мініматп
                                    # Мапінг типу на режим
                                    type_to_mode = {
                                        1: "ctf",      # Standard
                                        2: "domination",  # Encounter
                                        3: "assault",  # Assault
                                        4: "comp7"     # Onslaught
                                    }
                                    mode = type_to_mode.get(self.last_type, "ctf")
                                    if self.callback:
                                        self.callback(map_id, mode)
                
                time.sleep(2)
            except Exception:
                time.sleep(5)

    def update_path(self, new_path):
        self.log_path = new_path
        if self.log_path and os.path.exists(self.log_path):
            self._last_size = os.path.getsize(self.log_path)
