import os
import json
import threading
import config

try:
    import map_extractor
except ImportError:
    map_extractor = None

try:
    import tank_extractor
except ImportError:
    tank_extractor = None

class MapManager:
    def __init__(self, app):
        self.app = app
        self._update_lock = threading.Lock()
        self._update_in_progress = False

    def _try_begin_update(self):
        with self._update_lock:
            if self._update_in_progress:
                return False
            self._update_in_progress = True
            return True

    def _end_update(self):
        with self._update_lock:
            self._update_in_progress = False
        
    def get_eng_map_name(self, loc):
        for m in self.app.map_list_eng:
            if self.app.translate_map_name(m) == loc: return m
        for tid, eng in config.TECH_MAPS_STAGING.items():
            if self.app.translate_map_name(eng) == loc: return eng
        return None

    def _sort_map_list_eng_by_display(self):
        """Спільне сортування МАПИ I / II за людською назвою."""
        if not self.app.map_list_eng:
            return
        self.app.map_list_eng.sort(key=lambda m: self.app.translate_map_name(m).casefold())

    def auto_detect_wot_path(self):
        if not self.app.settings.get("wot_path"):
            log_path = self.app.settings.get("log_path", "")
            if log_path and os.path.exists(log_path):
                self.app.settings["wot_path"] = os.path.dirname(log_path)
                self.app.save_settings()
            else:
                common_paths = [
                    "C:/Games/World_of_Tanks_EU", "D:/Games/World_of_Tanks_EU",
                    "E:/Games/World_of_Tanks_EU", "C:/Games/World_of_Tanks",
                    "D:/Games/World_of_Tanks", "E:/Games/World_of_Tanks"
                ]
                for p in common_paths:
                    if os.path.exists(os.path.join(p, "WorldOfTanks.exe")):
                        self.app.settings["wot_path"] = p
                        self.app.save_settings()
                        break

    def check_game_version(self, progress_cb=None, done_cb=None, allow_map_decode=True):
        def emit(percent, text, fg="yellow"):
            if progress_cb:
                self.app.safe_execute(lambda: progress_cb(percent, text))
            if hasattr(self.app, "status_label"):
                self.app.safe_execute(lambda: self.app.status_label.config(text=f"[ОНОВЛЕННЯ] {text}", fg=fg))

        def finish():
            if done_cb:
                self.app.safe_execute(done_cb)

        if not map_extractor:
            emit(100, "Модуль map_extractor.py не знайдено", "orange")
            finish()
            return

        def checker():
            if not self._try_begin_update():
                emit(100, "Оновлення вже виконується", "orange")
                finish()
                return
            try:
                emit(8, "Триває перевірка оновлень...")
                ext = map_extractor.MapExtractor()
                emit(15, "Читання версії клієнта...")
                current_v = ext.get_version()
                saved_v = self.app.settings.get("game_version", "")
                if not current_v:
                    emit(100, "Не вдалося прочитати version.xml", "orange")
                    return

                real_version_changed = current_v != saved_v
                force_update_on_startup = bool(getattr(self.app, "settings", {}).get("force_update_on_startup", False))
                version_changed = real_version_changed
                required_tth_schema = 2
                current_tth_schema = int(self.app.settings.get("tth_schema_version", 0) or 0)
                tth_has_data = False
                tth_count = 0
                tth_json = {}
                if os.path.exists(os.path.join(config.BASE_DIR, "tank_tth.json")):
                    try:
                        with open(os.path.join(config.BASE_DIR, "tank_tth.json"), "r", encoding="utf-8") as f:
                            tth_json = json.load(f)
                        tth_has_data = isinstance(tth_json, dict) and bool(tth_json)
                        if isinstance(tth_json, dict):
                            tth_count = len(tth_json)
                    except Exception:
                        tth_has_data = False

                tank_db_count = 0
                if os.path.exists(os.path.join(config.BASE_DIR, "tank_db.json")):
                    try:
                        with open(os.path.join(config.BASE_DIR, "tank_db.json"), "r", encoding="utf-8") as f:
                            tank_db_json = json.load(f)
                        if isinstance(tank_db_json, dict):
                            tank_db_count = len(tank_db_json)
                    except Exception:
                        tank_db_count = 0

                tank_db_has_data = tank_db_count > 0

                # Перевіряємо, чи присутні критичні папки іконок для СТАТ AI (збірки).
                loadout_base = os.path.join(config.BASE_DIR, "extracted_icons", "loadout")
                loadout_dirs = [
                    os.path.join(loadout_base, "artefacts"),
                    os.path.join(loadout_base, "ammo"),
                    os.path.join(loadout_base, "crew_skills"),
                ]
                loadout_counts = []
                for d in loadout_dirs:
                    if os.path.isdir(d):
                        try:
                            loadout_counts.append(len([n for n in os.listdir(d) if n.lower().endswith('.png')]))
                        except Exception:
                            loadout_counts.append(0)
                    else:
                        loadout_counts.append(0)
                need_ui_icon_refresh = any(c <= 0 for c in loadout_counts)

                # Якщо ТТХ значно менше, ніж танків у базі, вважаємо файл неповним і перебудовуємо.
                tth_coverage_bad = tank_db_count > 0 and tth_count < max(200, int(tank_db_count * 0.6))
                popular_missing_tth = False
                popular_missing_core_tth = False
                if isinstance(tth_json, dict) and hasattr(self.app, "popular_tanks"):
                    tth_norm = {str(k).lower().replace('-', '_') for k in tth_json.keys()}
                    for p_tag in self.app.popular_tanks:
                        p_norm = str(p_tag).lower().replace('-', '_')
                        if p_tag in self.app.tank_db and p_norm not in tth_norm:
                            popular_missing_tth = True
                            break

                    # Якісна перевірка: якщо у популярних танків немає ключових ТТХ, потрібен rebuild.
                    for p_tag in self.app.popular_tanks:
                        p_norm = str(p_tag).lower().replace('-', '_')
                        if p_tag not in self.app.tank_db:
                            continue
                        rec = tth_json.get(p_tag)
                        if rec is None:
                            for k, v in tth_json.items():
                                if str(k).lower().replace('-', '_') == p_norm:
                                    rec = v
                                    break
                        if isinstance(rec, dict):
                            has_core = ('reload' in rec) or ('turret_armor' in rec) or ('view_range' in rec)
                            if not has_core:
                                popular_missing_core_tth = True
                                break

                need_tank_rebuild = tank_extractor and (
                    not os.path.exists(os.path.join(config.BASE_DIR, "tank_db.json"))
                    or not os.path.exists(os.path.join(config.BASE_DIR, "tank_tth.json"))
                    or not tank_db_has_data
                    or not tth_has_data
                    or tth_coverage_bad
                    or popular_missing_tth
                    or popular_missing_core_tth
                    or current_tth_schema < required_tth_schema
                )
                should_force_refresh = force_update_on_startup
                should_refresh_data = version_changed or need_tank_rebuild or should_force_refresh or need_ui_icon_refresh

                if version_changed:
                    emit(25, f"Виявлено нову версію {current_v}: триває оновлення")

                elif should_force_refresh:
                    emit(25, f"Тестовий режим: примусове оновлення даних для {current_v}", "orange")
                elif need_ui_icon_refresh:
                    emit(25, f"Відновлюю іконки збірок ({sum(loadout_counts)} файлів)", "yellow")
                else:
                    emit(25, f"Версія {current_v} без змін")

                maps_ok = True
                if version_changed and allow_map_decode:
                    def map_status_cb(text):
                        low = text.lower()
                        pct = 30
                        if "аналіз" in low:
                            pct = 30
                        elif "декодування" in low:
                            pct = 45
                        elif "оновлено" in low or "актуаль" in low:
                            pct = 55
                        emit(pct, text)

                    maps_ok = ext.extract(callback_status=map_status_cb)
                    emit(58, "МАПИ II: етап завершено")
                elif version_changed and not allow_map_decode:
                    emit(55, "МАПИ II: автооновлення на старті вимкнено (оновіть вручну)", "orange")
                else:
                    emit(45, "Оновлення не потрібне: МАПИ II актуальні")

                tanks_ok = True
                tank_pipeline_ran = False
                tth_pipeline_ran = False
                if tank_extractor and should_refresh_data:
                    stability_mode = bool(getattr(self.app, "settings", {}).get("pause_tank_auto_rebuild", True))
                    if stability_mode:
                        emit(62, "СТАТ AI: режим стабільності (оновлюю тільки TTH)...", "orange")
                        tex = tank_extractor.TankExtractor(ext.wot_path)
                        force_full = bool(need_tank_rebuild or should_force_refresh)
                        if tex.extract_metadata(force_full=force_full):
                            emit(88, "СТАТ AI: оновлюю UI-іконки (збірки/снаряди/навички)...")
                            if not tex.extract_icons():
                                emit(90, "СТАТ AI: іконки оновлено частково", "orange")
                            emit(94, "СТАТ AI: безпечне оновлення TTH...")
                            allow_decode_retry = bool(getattr(self.app, "settings", {}).get("tth_decode_retry_enabled", False))
                            if tex.update_tth_database_safe(
                                allow_decode_retry=allow_decode_retry,
                            ):
                                tth_pipeline_ran = True
                                emit(98, "СТАТ AI: TTH оновлено (tank_db без змін)")
                            else:
                                tanks_ok = False
                        else:
                            tanks_ok = False
                    else:
                        tank_pipeline_ran = True
                        emit(62, "СТАТ AI: аналіз техніки...")
                        tex = tank_extractor.TankExtractor(ext.wot_path)
                        db_exists = os.path.exists(os.path.join(config.BASE_DIR, "tank_db.json")) and os.path.exists(os.path.join(config.BASE_DIR, "tank_tth.json"))
                        force_full_extract = bool(need_tank_rebuild or should_force_refresh)
                        if tex.extract_metadata(force_full=force_full_extract) and tex.extract_icons():
                            emit(70, f"СТАТ AI: змінено XML: {tex.changed_metadata_count}")
                            if tex.changed_metadata_count == 0 and db_exists and not need_tank_rebuild:
                                emit(85, "СТАТ AI актуальний, декодування пропущено")
                            else:
                                emit(88, "СТАТ AI: формую базу техніки...")
                                db_ok = tex.build_database()
                                if not db_ok:
                                    # На старті не запускаємо Orion автоматично: він може відкрити REPL-вікно і заблокувати splash.
                                    emit(90, "СТАТ AI: база недоступна, використовую fallback (декодування вручну)", "orange")
                                emit(94, "СТАТ AI: формую TTH...")
                                tex.build_tth_database()
                                emit(98, "СТАТ AI оновлено")
                        else:
                            tanks_ok = False
                elif tank_extractor:
                    emit(85, "Оновлення не потрібне: СТАТ AI актуальний")

                # Auto-update crew and equipment ONLY when game client version changed
                if version_changed:
                    try:
                        import build_crew_builds
                        build_crew_builds.main()
                        emit(86, "Оновлення екіпажу з клієнта завершено")
                    except Exception as e:
                        print(f"[WARN] crew_builds update failed: {e}")

                    try:
                        wot_path = getattr(ext, 'wot_path', None) if ext else None
                        if wot_path:
                            pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
                            import extract_equipment_loadouts
                            extract_equipment_loadouts.extract_loadouts(pkg_path, "equipment_loadouts.json")
                            emit(87, "Оновлення обладнання з клієнта завершено")
                    except Exception as e:
                        print(f"[WARN] equipment_loadouts update failed: {e}")

                if maps_ok and tanks_ok:
                    if version_changed:
                        self.app.settings["game_version"] = current_v
                    if tank_pipeline_ran or tth_pipeline_ran or current_tth_schema < required_tth_schema:
                        self.app.settings["tth_schema_version"] = required_tth_schema
                    self.app.safe_execute(self.app.save_settings)
                    if (tank_pipeline_ran or tth_pipeline_ran) and hasattr(self.app, "reload_tank_data"):
                        self.app.safe_execute(self.app.reload_tank_data)
                    if should_refresh_data:
                        emit(100, "Перевірка завершена: оновлення виконано", "lime")
                    else:
                        emit(100, "Перевірка завершена: оновлення не потрібне", "lime")
                    if version_changed and self.app.btn_mode_maps_2.cget("bg") == "#ff4500":
                        self.app.safe_execute(self.load_map_list)
                elif maps_ok and not tanks_ok:
                    emit(100, "МАПИ II оновлено, але СТАТ AI з помилками", "orange")
                else:
                    emit(100, "Оновлення завершено з помилками", "red")
            except Exception as e:
                import traceback
                print(f"[ШТАБ] Помилка фонового оновлення: {e}")
                traceback.print_exc()
            finally:
                self._end_update()
                finish()
        threading.Thread(target=checker, daemon=True).start()

    def run_map_updater(self):
        if self.app.btn_mode_maps_1.cget("bg") == "#ff4500":
            try: import map_updater
            except ImportError:
                self.app.status_label.config(text="[ПОМИЛКА] Файл map_updater.py не знайдено!", fg="red")
                return
            self.app.status_label.config(text="[ОНОВЛЕННЯ МАП I...] Запуск браузера...", fg="yellow")
            def update_thread():
                def status_cb(text): self.app.safe_execute(lambda: self.app.status_label.config(text=f"[ОНОВЛЕННЯ] {text}", fg="yellow"))
                success = False
                try: success = map_updater.sync_all(callback_status=status_cb)
                except Exception as e: print(f"[ШТАБ] Помилка апдейтера: {e}")
                def on_finish():
                    if success:
                        self.app.status_label.config(text="[ОНОВЛЕННЯ МАП I] Успішно завершено!", fg="lime")
                        self.load_map_list()
                    else:
                        self.app.status_label.config(text="[ОНОВЛЕННЯ МАП I] Завершено з помилками", fg="red")
                self.app.safe_execute(on_finish)
            threading.Thread(target=update_thread, daemon=True).start()
        else:
            if not map_extractor:
                self.app.status_label.config(text="[ПОМИЛКА] Файл map_extractor.py не знайдено!", fg="red")
                return
            if not self._try_begin_update():
                self.app.status_label.config(text="[ОНОВЛЕННЯ] Вже виконується фонове оновлення", fg="yellow")
                return
            self.app.status_label.config(text="[ОНОВЛЕННЯ МАП II...] Витягуємо з клієнта...", fg="yellow")
            def update_thread():
                try:
                    ext = map_extractor.MapExtractor()
                    def status_cb(text): self.app.safe_execute(lambda: self.app.status_label.config(text=f"[ОНОВЛЕННЯ] {text}", fg="yellow"))
                    success = ext.extract(callback_status=status_cb)
                    def on_finish():
                        if success:
                            self.app.status_label.config(text="[ОНОВЛЕННЯ МАП II] Успішно завершено!", fg="lime")
                            self.load_map_list()
                        else:
                            self.app.status_label.config(text="[ОНОВЛЕННЯ МАП II] Помилка екстрактора (перевір шлях до гри)", fg="red")
                    self.app.safe_execute(on_finish)
                finally:
                    self._end_update()
            threading.Thread(target=update_thread, daemon=True).start()

    def load_map_list(self):
        ui_mode = self.app.selected_battle_mode.get()
        mode_mapping = {
            "Standard": "ctf",
            "Encounter": "domination",
            "Assault": "assault",
            "Onslaught": "comp7"
        }
        internal_mode = mode_mapping.get(ui_mode, "ctf")
        is_tactic = self.app.btn_mode_maps_1.cget("bg") == "#ff4500"

        dict_path = os.path.join(config.BASE_DIR, "extracted_maps", "map_dictionary.json")
        data_path = os.path.join(config.BASE_DIR, "extracted_maps", "map_data.json")

        loaded_dict = self.app.data_mgr.load_json(dict_path)
        self.app.map_data = self.app.data_mgr.load_json(data_path)

        if isinstance(loaded_dict, dict) and loaded_dict:
            self.app.extractor_names = loaded_dict
            all_maps = list(loaded_dict.keys())
            filtered_maps = []
            for m in all_maps:
                if m in self.app.map_data:
                    gameplay_types = self.app.map_data[m].get("gameplayTypes", {})
                    has_mode = internal_mode in gameplay_types
                    if internal_mode == "assault" and "assault2" in gameplay_types:
                        has_mode = True
                    if has_mode:
                        filtered_maps.append(m)
                else:
                    filtered_maps.append(m)
            self.app.map_list_eng = filtered_maps
        else:
            self.app.extractor_names = {}
            self.app.map_list_eng = []

        if is_tactic:
            self.app.map_list_eng = [m for m in self.app.map_list_eng if self._tactic_image_exists(m)]

        unique_maps = []
        seen_names = set()
        for m in self.app.map_list_eng:
            name = self.app.translate_map_name(m)
            if name not in seen_names:
                unique_maps.append(m)
                seen_names.add(name)
        self.app.map_list_eng = unique_maps

        self._sort_map_list_eng_by_display()
        tmaps = [self.app.translate_map_name(m) for m in self.app.map_list_eng]
        self.app.map_selector.config(values=tmaps)
        
        if tmaps:
            if self.app.map_var.get() not in tmaps:
                self.app.map_selector.current(0)
            self.app.on_map_select()
        else:
            self.app.current_map_eng = None
            self.app.map_var.set("")
            if is_tactic:
                self.app.status_label.config(text=self.app.t('ui', 'tactic_no_maps'), fg="red")
            self.app.map_renderer.show_main_splash()


    def _resolve_tactic_folder(self, eng_key):
        folder = config.TECH_MAPS_STAGING.get(eng_key)
        if folder:
            return folder
        for suffix in ['_v', '_big', '_sm24', '_sm25', '_nom', '_scc', '_ctf']:
            if eng_key.endswith(suffix):
                base = eng_key[:-len(suffix)]
                folder = config.TECH_MAPS_STAGING.get(base)
                if folder:
                    return folder
        return eng_key

    def _tactic_image_exists(self, eng_key):
        folder_name = self._resolve_tactic_folder(eng_key)
        safe_folder = folder_name.replace('?', '').replace(':', '').replace('|', '').replace("'", "").replace(' - ', '_').replace(' ', '_')
        webp_path = os.path.join(config.MAPS_DIR, safe_folder, "map.webp")
        if os.path.exists(webp_path):
            return True
        jpg_path = os.path.join(config.MAPS_DIR, f"{safe_folder}.jpg")
        png_path = os.path.join(config.MAPS_DIR, f"{safe_folder}.png")
        return os.path.exists(jpg_path) or os.path.exists(png_path)
