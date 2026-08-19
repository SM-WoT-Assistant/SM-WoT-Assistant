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
        self._battle_active = False  # Чи була виявлена арена (бій) — hangar без бою не фіриться
        
        # Регулярний вираз для виявлення завантаження карти (бою)
        # Приклад: Loading space: spaces/01_karelia
        self.arena_re = re.compile(r"Loading space: spaces/(?P<map_id>\w+)")
        # Хангар та івент-простори клієнта (hangar, hangar_v4, h33_*, h42_Wot_Bday_2026 і т.д.)
        self.hangar_re = re.compile(r"Loading space: spaces/(?:hangar\w*|h\d+_\w+)")
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
            print(f"[LOGWATCHER] Started with log_path={self.log_path}, size={self._last_size}")
        else:
            print(f"[LOGWATCHER] Started with log_path={self.log_path} (NOT FOUND)")
            
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
                    self._battle_active = False
                
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
                            
                            # Перевіряємо повернення в ангар.
                            # battle_ended фіриться ТІЛЬКИ якщо був активний бій
                            # (_battle_active) — hangar без бою (старт гри, reset
                            # python.log, дублікат hangar-лінії) викликає тихе
                            # скидання стану без callback, інакше хибний
                            # battle_ended перемикає вікно з режиму в режим.
                            if self.hangar_re.search(line):
                                was_battle = self._battle_active
                                self._battle_active = False
                                self._last_arena_id = None
                                self._countdown_fired_for_arena = None
                                self._last_vehicle_cd = None
                                if was_battle and self.hangar_callback:
                                    self.hangar_callback()

                            # Основний тригер перемикання у бойовий режим
                            if self.battle_space_re.search(line):
                                if self._battle_active and self._last_arena_id is not None and self.countdown_callback:
                                    if self._countdown_fired_for_arena != self._last_arena_id:
                                        self._countdown_fired_for_arena = self._last_arena_id
                                        self.countdown_callback(self._last_arena_id, self.last_type)

                            # Fallback, якщо основний маркер з якоїсь причини не зловився
                            if self.battle_loaded_re.search(line):
                                if self._battle_active and self._last_arena_id is not None and self.countdown_callback:
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
                                # Пропускаємо ангар та івент-простори - це не бій
                                if not (map_id.startswith("hangar") or re.match(r"h\d+_\w+", map_id)):
                                    if self._last_arena_id != map_id:
                                        self._countdown_fired_for_arena = None
                                    self._battle_active = True
                                    self._last_arena_id = map_id  # Зберігаємо для мініматп
                                    type_to_mode = {
                                        1: "ctf",      # Standard
                                        2: "domination",  # Encounter
                                        3: "assault",  # Storm
                                        4: "comp7",    # Onslaught 10
                                        5: "comp7_light",    # Onslaught 8
                                    }
                                    mode = type_to_mode.get(self.last_type, "ctf")
                                    print(f"[LOGWATCHER] Arena detected: map={map_id}, mode={mode}, last_type={self.last_type}")
                                    if self.callback:
                                        self.callback(map_id, mode)
                            if "comp7_light" in clean_line and "loading" in clean_line.lower():
                                pass
                
                time.sleep(2)
            except Exception:
                time.sleep(5)

    def update_path(self, new_path):
        self.log_path = new_path
        if self.log_path and os.path.exists(self.log_path):
            self._last_size = os.path.getsize(self.log_path)
