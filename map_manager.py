import os
import json
import re
import threading
import ctypes
import config

try:
    import map_extractor
except ImportError:
    map_extractor = None


def _is_wot_running():
    """Перевіряє чи запущений WorldOfTanks.exe (ctypes Toolhelp32Snapshot)."""
    try:
        kernel32 = ctypes.windll.kernel32
        TH32CS_SNAPPROCESS = 0x00000002
        PE_SIZE = 568 if ctypes.sizeof(ctypes.c_void_p) == 8 else 556
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == -1:
            return False
        try:
            pe = (ctypes.c_byte * PE_SIZE)()
            ctypes.memset(pe, 0, PE_SIZE)
            ctypes.memmove(pe, ctypes.byref(ctypes.c_ulong(PE_SIZE)), 4)
            if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
                return False
            while True:
                exe_buf = ctypes.create_unicode_buffer(260)
                ctypes.memmove(exe_buf, ctypes.byref(pe, 44), 260 * 2)
                if exe_buf.value and "WorldOfTanks.exe" in exe_buf.value:
                    return True
                if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                    break
            return False
        finally:
            kernel32.CloseHandle(snapshot)
    except Exception:
        return False

# Мапи-евенти/варіанти/старі мапи яких НЕМАЄ на сайті тактік
_EVENT_MAP_IDS = {
    "08_ruinberg_sm24", "101_dday_sm24", "105_germany_sm24", "108_normandy_nom",
    "140_fall_tanks", "141_dash_to_go", "142_road_to_dash",
    "14_siegfried_line_nom", "14_siegfried_line_wt", "34_redshire_wt", "35_steppes_wt",
    "208_bf_epic_normandy", "209_wg_epic_suburbia", "210_bf_epic_desert",
    "212_epic_random_valley_sm25",
    "250_br_battle_city2-1", "251_br_battle_city3", "252_br_battle_city4",
}
_UNAVAILABLE_FILE = os.path.join(config.USER_DATA_DIR, "unavailable_tactic_maps.json")
# Маніфест ETag тактичних мап сайту (детект змін через If-None-Match)
_SITE_MANIFEST_FILE = os.path.join(config.USER_DATA_DIR, "site_maps_manifest.json")

try:
    import tank_extractor
except ImportError:
    tank_extractor = None

class MapManager:
    def __init__(self, app):
        self.app = app
        self._update_lock = threading.Lock()
        self._update_in_progress = False
        self._last_changed_ids = []
        self._unavailable_maps = set(self._load_unavailable())
        self._tactic_sync_needed = False
        self._pending_tactic_path = os.path.join(config.USER_DATA_DIR, "pending_tactic_maps.json")
        self._mod_restart_warned = False
        self._sweep_running = False

    def _load_unavailable(self):
        try:
            if os.path.exists(_UNAVAILABLE_FILE):
                with open(_UNAVAILABLE_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                return d if isinstance(d, list) else []
        except Exception:
            pass
        return []

    def _save_unavailable(self):
        try:
            with open(_UNAVAILABLE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self._unavailable_maps), f)
        except Exception as e:
            print(f"[MAP_MGR] Failed to save unavailable maps: {e}")

    def _load_site_manifest(self):
        """Маніфест ETag тактичних мап сайту (детект змін). Атомарно через safe_io."""
        try:
            import safe_io
            data = safe_io.read_json(_SITE_MANIFEST_FILE, {})
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_site_manifest(self, manifest):
        try:
            import safe_io
            safe_io.write_json(_SITE_MANIFEST_FILE, manifest)
        except Exception as e:
            print(f"[MAP_MGR] Site manifest save error: {e}")

    @staticmethod
    def _site_entry_from_headers(headers):
        """ETag/Last-Modified/Content-Length з HEAD-відповіді як маніфест-запис."""
        return {
            "etag": (headers.get("ETag") or "").strip(),
            "last_modified": (headers.get("Last-Modified") or "").strip(),
            "size": (headers.get("Content-Length") or "").strip(),
        }

    def _on_site_map_event(self, kind, map_id, eng_name):
        """Подія сайту → service_events (сповіщення адмінки) + живий rerender.

        Викликається з фонового потоку sweep: log_event_now = файл + POST;
        rerender — ТІЛЬКИ через root.after (Tk-безпека, #2005)."""
        try:
            import service_messages
            verb = "added" if kind == "map_added" else "updated"
            service_messages.log_event_now(
                "site_maps", f"TACTIC map {verb}: {eng_name} ({map_id})")
        except Exception as e:
            print(f"[MAP_MGR] Site event report error: {e}")
        try:
            if getattr(self.app, "current_map_eng", None) == map_id:
                self.app.root.after(0, self._rerender_current_map)
        except Exception:
            pass

    def _rerender_current_map(self):
        """Показати щойно завантажену мапу замість порожнього вікна.

        show_main_splash() без аргументу: картинка вже існує → мапа;
        painter.redraw() перепокладає схеми на новий _map_img_rect.
        Без крадіжки фокусу/exit_edit_mode."""
        app = self.app
        try:
            app.map_renderer.show_main_splash()
            if hasattr(app, "painter"):
                app.painter.redraw()
        except Exception as e:
            print(f"[MAP_MGR] Rerender error: {e}")

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

    def fast_integrity_check(self):
        """Lightweight check: are local cached data files present and non-empty?
        Returns True if data looks OK for a fast skip, False if full pipeline needed."""
        import os as _os
        base = config.BASE_DIR
        ud = config.USER_DATA_DIR
        # 1. tank_db.json exists and has data
        try:
            path = _os.path.join(base, "tank_db.json")
            if not _os.path.exists(path):
                return False
            with open(path, "r", encoding="utf-8") as f:
                db = json.load(f)
            if not isinstance(db, dict) or len(db) < 100:
                return False
        except Exception:
            return False
        # 2. tank_tth.json exists and has data
        try:
            path = _os.path.join(base, "tank_tth.json")
            if not _os.path.exists(path):
                return False
            with open(path, "r", encoding="utf-8") as f:
                tth = json.load(f)
            if not isinstance(tth, dict) or len(tth) < 100:
                return False
        except Exception:
            return False
        # 3. loadout icon directories have PNG files
        loadout_base = _os.path.join(base, "extracted_icons", "loadout")
        for subdir in ("artefacts", "ammo", "crew_skills"):
            d = _os.path.join(loadout_base, subdir)
            if not _os.path.isdir(d):
                return False
            try:
                if not any(n.lower().endswith(".png") for n in _os.listdir(d)):
                    return False
            except Exception:
                return False
        # 4. game version saved in settings
        saved_v = self.app.settings.get("game_version", "")
        if not saved_v:
            return False
        return True

    def check_game_version(self, progress_cb=None, done_cb=None, allow_map_decode=True):
        def emit(percent, text_key, fg="yellow", **fmt):
            text = self.app.t('ui', text_key).format(**fmt) if fmt else self.app.t('ui', text_key)
            if progress_cb:
                self.app.safe_execute(lambda: progress_cb(percent, text))
            pass

        def finish():
            if done_cb:
                self.app.safe_execute(done_cb)

        if not map_extractor:
            emit(100, "update_module_missing", "orange", module="map_extractor.py")
            finish()
            return

        def checker():
            if not self._try_begin_update():
                emit(100, "update_already_running", "orange")
                finish()
                return
            try:
                emit(8, "checking_updates")
                ext = map_extractor.MapExtractor()
                emit(15, "reading_client_version")
                current_v = ext.get_version()
                saved_v = self.app.settings.get("game_version", "")
                if not current_v:
                    emit(100, "failed_read_version", "orange")
                    finish()
                    return

                real_version_changed = current_v != saved_v
                force_update_on_startup = bool(getattr(self.app, "settings", {}).get("force_update_on_startup", False))

                if not real_version_changed and not force_update_on_startup:
                    if self.fast_integrity_check():
                        print(f"[MAP_MGR] Fast path: version {current_v} unchanged, local data OK — skipping extraction")
                        emit(100, "version_unchanged", "lime", version=current_v)
                        self._detect_pending_tactic_maps()
                        self.apply_mod_mode()
                        return

                version_changed = real_version_changed
                if version_changed:
                    print(f"[MAP_MGR] Game version changed: {saved_v} → {current_v}")
                    # Раннє встановлення мода — до екстракції (секунди, не хвилини):
                    # після оновлення клієнта нова папка mods/<ver>/ отримує
                    # sm_tactics.wotmod одразу, а не після повного пайплайну.
                    self.apply_mod_mode()
                elif not version_changed:
                    try:
                        if ext.has_changed():
                            print("[MAP_MGR] scripts.pkg змінився — запускаю оновлення")
                            version_changed = True
                    except Exception as e:
                        print(f"[MAP_MGR] has_changed error: {e}")

                if version_changed:
                    try:
                        import firebase_reporter
                        ts = __import__('time').strftime("%Y-%m-%dT%H:%M:%S")
                        threading.Thread(target=firebase_reporter._put, args=(
                            "pending_updates/builds", {
                                "status": "idle",
                                "version": current_v or saved_v or "?",
                                "scripts_pkg_changed": True,
                                "triggered_at": ts,
                                "message": f"Game data changed (v{current_v})"
                            }
                        ), daemon=True).start()
                        print(f"[MAP_MGR] pending_updates/builds signaled")
                    except Exception:
                        try:
                            import firebase_reporter
                            firebase_reporter.report_fallback(
                                "map_manager.check_game_version", "pending_updates/builds",
                                "Failed to signal Firebase about game version change")
                        except Exception:
                            pass
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
                    emit(25, "version_changed_detected", version=current_v)

                elif should_force_refresh:
                    emit(25, "forced_update_mode", "orange", version=current_v)
                elif need_ui_icon_refresh:
                    emit(25, "restoring_icons", "yellow", count=sum(loadout_counts))
                else:
                    emit(25, "version_unchanged", version=current_v)

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
                        emit(pct, "parsing_xml" if "аналіз" in low else "decoding_xml" if "декодування" in low else "xml_decode_complete")

                    maps_ok = ext.extract(callback_status=map_status_cb)
                    self._last_changed_ids = ext.last_changed_ids
                    emit(58, "maps_stage2_done")
                elif version_changed and not allow_map_decode:
                    self._last_changed_ids = []
                    emit(55, "maps_autoupdate_disabled", "orange")
                else:
                    self._last_changed_ids = []
                    emit(45, "maps_up_to_date")

                tanks_ok = True
                tank_pipeline_ran = False
                tth_pipeline_ran = False
                if tank_extractor and should_refresh_data:
                    stability_mode = bool(getattr(self.app, "settings", {}).get("pause_tank_auto_rebuild", True))
                    if stability_mode:
                        emit(62, "stats_ai_stability_mode", "orange")
                        tex = tank_extractor.TankExtractor(ext.wot_path)
                        force_full = bool(need_tank_rebuild or should_force_refresh)
                        if tex.extract_metadata(force_full=force_full):
                            # stability_mode Bug 3 (28.08.2026 #1692 follow-up): after
                            # extract_metadata pulls new/changed XML, tank_db.json must be
                            # rebuilt from extracted_data/<nation>/list.xml so admin's
                            # generate_builds() sees the new tag (it filters by tank_db).
                            # Without this, new tank like F141_Durendal (#41ec299) is hidden
                            # forever — root cause of "1023 vs 1010" + "693 змінених" loops.
                            # Gate on force_full or any change: no every-start full rebuild.
                            if force_full or tex.changed_metadata_count > 0:
                                if tex.build_database():
                                    print(f"[MAP_MGR] tank_db.json rebuilt "
                                          f"(force_full={force_full}, "
                                          f"changed={tex.changed_metadata_count})")
                                else:
                                    print(f"[WARN] build_database failed in stability_mode")
                            emit(88, "stats_ai_updating_icons")
                            if not tex.extract_icons():
                                emit(90, "stats_ai_tth_done", "orange")
                            emit(94, "stats_ai_updating_tth")
                            allow_decode_retry = bool(getattr(self.app, "settings", {}).get("tth_decode_retry_enabled", False))
                            if tex.update_tth_database_safe(
                                allow_decode_retry=allow_decode_retry,
                            ):
                                tth_pipeline_ran = True
                                emit(98, "stats_ai_tth_done")
                                try:
                                    tex.update_compact_descr()
                                except Exception as e:
                                    print(f"[WARN] update_compact_descr: {e}")
                            else:
                                tanks_ok = False
                        else:
                            tanks_ok = False
                    else:
                        tank_pipeline_ran = True
                        emit(62, "stats_ai_analyzing")
                        tex = tank_extractor.TankExtractor(ext.wot_path)
                        db_exists = os.path.exists(os.path.join(config.BASE_DIR, "tank_db.json")) and os.path.exists(os.path.join(config.BASE_DIR, "tank_tth.json"))
                        force_full_extract = bool(need_tank_rebuild or should_force_refresh)
                        if tex.extract_metadata(force_full=force_full_extract) and tex.extract_icons():
                            emit(70, "stats_ai_xml_changed", count=tex.changed_metadata_count)
                            if tex.changed_metadata_count == 0 and db_exists and not need_tank_rebuild:
                                emit(85, "stats_ai_up_to_date")
                            else:
                                emit(88, "stats_ai_building_db")
                                db_ok = tex.build_database()
                                if not db_ok:
                                    emit(90, "stats_ai_db_unavailable", "orange")
                                emit(94, "stats_ai_building_tth")
                                tex.build_tth_database()
                                emit(98, "stats_ai_updated")
                        else:
                            tanks_ok = False
                elif tank_extractor:
                    emit(85, "stats_ai_up_to_date_full")

                # Auto-update crew and equipment ONLY when game client version changed
                if version_changed:
                    try:
                        import build_crew_builds
                        build_crew_builds.main()
                        emit(86, "crew_update_done")
                    except Exception as e:
                        print(f"[WARN] crew_builds update failed: {e}")

                    try:
                        wot_path = getattr(ext, 'wot_path', None) if ext else None
                        if wot_path:
                            pkg_path = os.path.join(wot_path, "res", "packages", "scripts.pkg")
                            import extract_equipment_loadouts
                            extract_equipment_loadouts.extract_loadouts(pkg_path, "equipment_loadouts.json")
                            emit(87, "equipment_update_done")
                    except Exception as e:
                        print(f"[WARN] equipment_loadouts update failed: {e}")

                    try:
                        from parse_game_entities import GameEntitiesExtractor
                        ex = GameEntitiesExtractor()
                        if ex.run_step1():
                            ex.save_to_json()
                            from language_module import regenerate_game_entities
                            regenerate_game_entities(None)
                            emit(88, "entity_update_done")
                    except Exception as e:
                        print(f"[WARN] parse_game_entities failed: {e}")

                if maps_ok and tanks_ok:
                    if version_changed:
                        self.app.settings["game_version"] = current_v
                    if tank_pipeline_ran or tth_pipeline_ran or current_tth_schema < required_tth_schema:
                        self.app.settings["tth_schema_version"] = required_tth_schema
                    self.app.safe_execute(self.app.save_settings)
                    if (tank_pipeline_ran or tth_pipeline_ran) and hasattr(self.app, "reload_tank_data"):
                        self.app.safe_execute(self.app.reload_tank_data)
                    if should_refresh_data:
                        emit(100, "update_complete_ai", "lime")
                    else:
                        emit(100, "update_complete_no_ai", "lime")
                    if version_changed and self.app.btn_mode_maps_2.cget("bg") == "#ff4500":
                        self.app.safe_execute(self.load_map_list)
                elif maps_ok and not tanks_ok:
                    emit(100, "update_complete_ai", "orange")
                else:
                    emit(100, "update_failed", "red")

                self._detect_pending_tactic_maps()
                self.apply_mod_mode()
            except Exception as e:
                import traceback
                print(f"[MAP_MGR] Background update error: {e}")
                traceback.print_exc()
            finally:
                self._end_update()
                finish()
        threading.Thread(target=checker, daemon=True).start()

    def _tactic_candidate_ids(self, maps_dict):
        """Арени, що реально можуть потрапити у TACTIC-список (Standard).

        Ті самі фільтри, що в load_map_list (map_manager.py:937-950):
        службові/евентні виключаються, має бути ctf-геймплей — інакше
        створились би фони для comp7-варіантів і hangar_v4_fortrush,
        які в TACTIC ніколи не показуються. map_data.json відсутній →
        арена лишається кандидатом (як і в load_map_list).
        """
        if not isinstance(maps_dict, dict):
            return []
        data_path = os.path.join(config.BASE_DIR, "extracted_maps", "map_data.json")
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        out = []
        for m in maps_dict:
            if m.startswith("type/") or m.startswith("h33_"):
                continue
            if m in ("invalid_map", "hangar_v4", "_default_"):
                continue
            if m in _EVENT_MAP_IDS:
                continue
            if m in data and "ctf" not in (data[m].get("gameplayTypes") or {}):
                continue
            out.append(m)
        return out

    def _detect_pending_tactic_maps(self):
        """HEAD-перевірка сайту: додавання + зміни тактичних мап.

        Додавання: мапи без локальної картинки → HEAD → 200: завантаження +
        подія map_added; 404 → unavailable (наявний негативний кеш); мережева
        помилка — НЕ unavailable (добовий sweep має шанс повторити).
        Зміни: умовний HEAD If-None-Match за маніфестом site_maps_manifest.json
        (ETag сервера); baseline першого запуску — лише запис ETag без події;
        різні ETag → перекачка + подія map_changed.
        Події → RTDB service_events (category=site_maps) → сповіщення адмінки;
        якщо мапа зараз показана — живий rerender без перезавантаження вікна.
        Гард _sweep_running: без накладань потоків (startup + добовий цикл)."""
        if getattr(self, "_sweep_running", False):
            return
        self._sweep_running = True
        try:
            dict_path = os.path.join(config.BASE_DIR, "extracted_maps", "map_dictionary.json")
            if not os.path.exists(dict_path):
                return
            try:
                with open(dict_path, "r", encoding="utf-8") as f:
                    maps_maps = json.load(f)
            except Exception:
                try:
                    import firebase_reporter
                    firebase_reporter.report_fallback(
                        "map_manager._detect_pending_tactic_maps", "map_dictionary.json",
                        "Failed to load map dictionary")
                except Exception:
                    pass
                return

            # ── Локальна верифікація фонів (офлайн, ДО мережі) ──────
            # Клієнт гри — джерело істини: фони, що не збігаються з
            # мінікартою (сайт віддав чужу мапу), ремонтується з
            # extracted_maps; відсутні — створюються. Після цього папка
            # з'являється в existing_folders і мапа рухається з хвоста
            # списку на алфавітне місце (Нібельбурґ, 26.10.2026).
            try:
                import map_updater
                rep = map_updater.ensure_local_backgrounds(
                    self._tactic_candidate_ids(maps_maps))
                if rep.get("repaired") or rep.get("created"):
                    print(f"[MAP_MGR] IMAGE GUARD: created={rep['created']} "
                          f"repaired={rep['repaired']} ok={rep['ok']} "
                          f"checked={rep['checked']}")
            except Exception as e:
                print(f"[MAP_MGR] IMAGE GUARD error: {e}")

            existing_folders = set()
            if os.path.isdir(config.MAPS_DIR):
                for fname in os.listdir(config.MAPS_DIR):
                    if os.path.exists(os.path.join(config.MAPS_DIR, fname, "map.webp")):
                        existing_folders.add(fname.lower().replace(' ', '_'))

            # Кандидати: new_maps — без локальної картинки; have_maps — з нею
            new_maps = []
            have_maps = []
            for map_id in maps_maps:
                if map_id.startswith("type/") or map_id in ("invalid_map", "hangar_v4", "_default_") or map_id.startswith("h33_"):
                    continue
                if map_id in _EVENT_MAP_IDS:
                    continue
                eng = config.MAP_NAMES_EN.get(map_id, map_id)
                folder = self._resolve_tactic_folder(eng)
                safe = folder.replace(' ', '_').lower()
                if safe in existing_folders:
                    have_maps.append(map_id)
                    continue
                if map_id in self._unavailable_maps or eng in self._unavailable_maps:
                    continue
                new_maps.append(map_id)

            if not new_maps and not have_maps:
                return

            import requests
            import map_updater  # selenium — лені-імпорт усередині sync_all

            manifest = self._load_site_manifest()

            # ── Додавання: локальної картинки немає ──
            for map_id in new_maps:
                eng = config.MAP_NAMES_EN.get(map_id, map_id)
                clean = eng.replace('?', '').replace(':', '').replace('|', '')
                safe = clean.replace(' - ', '_').replace(' ', '_').lower()
                url = f"https://images.wotmapsbyyaya.com/maps/{safe}.webp"
                try:
                    r = requests.head(url, timeout=5)
                    if r.status_code == 200:
                        if map_updater.download_single_map(eng, url):
                            # Маніфест ПЕРЕД подією: crash-вікно без дублікатів
                            manifest[map_id] = self._site_entry_from_headers(r.headers)
                            self._save_site_manifest(manifest)
                            self._on_site_map_event("map_added", map_id, eng)
                            print(f"[MAP_MGR] Downloaded TACTIC map: {eng} ({map_id})")
                        else:
                            print(f"[MAP_MGR] Download failed: {eng}")
                    else:
                        # 404: мапи на сайті ще немає — НЕ додаємо в unavailable.
                        # Постійний blacklist зламав би добовий sweep: перший sweep
                        # отруїв би мапу (сайт ще не додав), і «коли з'явиться»
                        # завантаження вже ніколи не відбулось би. Наявний
                        # unavailable (legacy) лишається skip-списком.
                        print(f"[MAP_MGR] Map not on site: {eng} ({r.status_code})")
                except Exception as e:
                    # Мережева помилка (таймаут/офлайн) — НЕ позначаємо
                    # unavailable: наступний sweep має шанс повторити.
                    print(f"[MAP_MGR] HEAD error for {eng}: {e}")

            # ── Зміни: локальна картинка є → умовний HEAD за ETag ──
            for map_id in have_maps:
                eng = config.MAP_NAMES_EN.get(map_id, map_id)
                clean = eng.replace('?', '').replace(':', '').replace('|', '')
                safe = clean.replace(' - ', '_').replace(' ', '_').lower()
                url = f"https://images.wotmapsbyyaya.com/maps/{safe}.webp"
                entry = manifest.get(map_id) or {}
                etag = entry.get("etag")
                try:
                    r = requests.head(url, headers={"If-None-Match": etag} if etag else {}, timeout=5)
                    if r.status_code == 304:
                        continue
                    if r.status_code != 200:
                        continue  # сайт недоступний — локальна копія лишається
                    new_etag = (r.headers.get("ETag") or "").strip()
                    if not etag:
                        # Baseline першого запуску: запис ETag без події/перекачки
                        manifest[map_id] = self._site_entry_from_headers(r.headers)
                        self._save_site_manifest(manifest)
                        continue
                    if not new_etag or new_etag == etag:
                        continue  # без ETag немає доказу зміни → не перекачуємо
                    if map_updater.download_single_map(eng, url):
                        manifest[map_id] = self._site_entry_from_headers(r.headers)
                        self._save_site_manifest(manifest)
                        self._on_site_map_event("map_changed", map_id, eng)
                        print(f"[MAP_MGR] TACTIC map updated: {eng} ({map_id})")
                    else:
                        # Відмова валідації (сайт віддав чужу мапу) або мережа.
                        # Локальна копія вже пройшла guard і валідна — фіксуємо
                        # ETag, щоб не качати ті самі байти щодня; якщо сайт
                        # виправиться, ETag зміниться і перекачка відбудеться.
                        local_ok, _ = map_updater.verify_map_background(map_id)
                        if local_ok:
                            manifest[map_id] = self._site_entry_from_headers(r.headers)
                            self._save_site_manifest(manifest)
                        print(f"[MAP_MGR] Download rejected/failed, local copy kept: {eng}")
                except Exception as e:
                    print(f"[MAP_MGR] HEAD error for {eng}: {e}")

            self._save_unavailable()
            self._last_changed_ids = []
        finally:
            self._sweep_running = False

    def _load_pending_tactic_maps(self):
        if not os.path.exists(self._pending_tactic_path):
            return []
        try:
            with open(self._pending_tactic_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_pending_tactic_maps(self, pending):
        try:
            with open(self._pending_tactic_path, "w", encoding="utf-8") as f:
                json.dump(pending, f)
        except Exception:
            pass

    def apply_mod_mode(self):
        """Install sm_tactics.wotmod if use_mod enabled; remove it from every mods/<ver>/ when disabled.

        Версія гри читається з version.xml на диску (fallback — settings.game_version),
        щоб папка mods/<ver>/ була актуальною навіть до оновлення settings після
        екстракції. Після встановлення наш застарілий wotmod прибирається з інших
        версійних папок. Якщо гра запущена і файл щойно (ре)встановлено — показується
        одноразове за сесію не-модальне вікно «перезапусти гру» (моди вантажаться
        тільки при старті гри; Aslain-модпак стирає mods/* при перевстановленні).
        """
        try:
            use_mod = bool(getattr(self.app, "_use_mod_var", None) and self.app._use_mod_var.get())
        except Exception:
            use_mod = False
        wot_path = self.app.settings.get("wot_path", "")
        # Stale folder created by the old raw-version bug (path from
        # version.xml with leading/trailing spaces, Win32-mangled name).
        # Exact name only - no wildcards (#1492). Checked on every call.
        if wot_path:
            _junk = os.path.join(wot_path, "mods", " v.2.4.0.1 #952")
            if os.path.isdir(_junk):
                try:
                    import shutil
                    shutil.rmtree(_junk)
                    print("[MAP_MGR] Removed stale version folder:", _junk)
                except Exception as _je:
                    print("[MAP_MGR] Stale folder cleanup failed:", _je)
        if not use_mod:
            self._uninstall_tactics_mod(wot_path)
            return
        wotmod_src = config.MOD_WOTMOD_FILE
        if not os.path.isfile(wotmod_src):
            print("[MAP_MGR] sm_tactics.wotmod not found, skipping install")
            return
        try:
            game_version = self._resolve_game_version()
            if not wot_path or not game_version:
                return
            # Нормалізуємо до 4-частинної версії та ПРЕФЕРУЄМО наявну папку
            # версії на диску (лагідний монтаж гри mods/<ver>/).
            m = re.search(r"\d+\.\d+\.\d+\.\d+", game_version)
            ver = m.group(0) if m else str(game_version).strip()
            mods_root = os.path.join(wot_path, "mods")
            mods_dir = None
            for cand in (ver, str(game_version).strip()):
                if cand and os.path.isdir(os.path.join(mods_root, cand)):
                    mods_dir = os.path.join(mods_root, cand)
                    break
            if mods_dir is None:
                mods_dir = os.path.join(mods_root, ver)
            os.makedirs(mods_dir, exist_ok=True)
            dst = os.path.join(mods_dir, "sm_tactics.wotmod")
            was_missing = not os.path.isfile(dst)
            import shutil
            shutil.copy2(wotmod_src, dst)
            print(f"[MAP_MGR] Installed sm_tactics.wotmod -> {mods_dir}")
            self._cleanup_other_version_wotmods(mods_root, os.path.basename(mods_dir))
            # Гра вже працює і файл щойно (ре)встановлено → моди вантажились
            # без нього; повідомити користувача (не-модально, 1 раз за сесію)
            if was_missing and _is_wot_running() and not self._mod_restart_warned:
                self._mod_restart_warned = True
                self.app.safe_execute(self._show_mod_restart_notice)
        except Exception as e:
            print(f"[MAP_MGR] Mod install error: {e}")

    def _resolve_game_version(self):
        """Актуальна версія гри: version.xml на диску (свіже читання),
        fallback — settings.game_version. Використовує app.settings wot_path
        (той самий, що й решта застосунку), без MapExtractor — щоб не
        змішувати джерела wot_path."""
        v = None
        wot_path = self.app.settings.get("wot_path", "")
        if wot_path:
            v_path = os.path.join(wot_path, "version.xml")
            if os.path.exists(v_path):
                try:
                    import xml.etree.ElementTree as ET
                    v = ET.parse(v_path).getroot().findtext("version")
                except Exception:
                    v = None
        if not v:
            v = str(self.app.settings.get("game_version", "") or "")
        return v

    def _cleanup_other_version_wotmods(self, mods_root, keep_dir_name):
        """Прибрати наш sm_tactics.wotmod з усіх версійних папок, крім поточної.

        Точне ім'я файлу (без wildcard — #1492). Не чіпаємо configs/ та інші моди.
        """
        try:
            for entry in os.listdir(mods_root):
                if entry == keep_dir_name:
                    continue
                p = os.path.join(mods_root, entry, "sm_tactics.wotmod")
                if os.path.isfile(p):
                    try:
                        os.remove(p)
                        print(f"[MAP_MGR] Removed stale wotmod from old version: {p}")
                    except Exception as e:
                        print(f"[MAP_MGR] Failed to remove stale wotmod {p}: {e}")
        except Exception as e:
            print(f"[MAP_MGR] Old-version wotmod cleanup error: {e}")

    def _show_mod_restart_notice(self):
        """Не-модальне вікно: гра запущена — перезапустіть гру для підвантаження мода.

        Без grab_set/wait_window — не блокує роботу застосунку (#1993: діалоги з
        Toplevel мають parent=self.app.root; тут Toplevel не потрібен, бо це нове
        верхнє вікно від root).
        """
        try:
            import tkinter as tk
            import dialog_utils
            title = self.app.t('ui', 'mod_restart_game_title')
            msg = self.app.t('ui', 'mod_restart_game_msg')
            dlg, hdr = dialog_utils.make_custom_dialog(self.app.root, title)
            dialog_utils._DragHelper(dlg, hdr)
            tk.Label(dlg, text=msg, bg="#222", fg="#ffaa00",
                     font=("Arial", 9), wraplength=400, justify="left").pack(padx=20, pady=(14, 12))
            tk.Button(dlg, text="OK", bg="#446644", fg="#cfc", bd=0,
                      font=("Arial", 9, "bold"), padx=20, pady=4,
                      command=dlg.destroy).pack(pady=(0, 12))
            dialog_utils._center_on_root(dlg, self.app.root)
        except Exception as e:
            print(f"[MAP_MGR] Restart notice error: {e}")

    def ensure_mod_installed(self):
        """Періодична самоперевірка (5 хв): use_mod увімкнено + файл відсутній/порожній → перевстановити."""
        try:
            use_mod = bool(getattr(self.app, "_use_mod_var", None) and self.app._use_mod_var.get())
        except Exception:
            return
        if not use_mod:
            return
        wot_path = self.app.settings.get("wot_path", "")
        if not wot_path:
            return
        game_version = self._resolve_game_version()
        if not game_version:
            return
        m = re.search(r"\d+\.\d+\.\d+\.\d+", game_version)
        ver = m.group(0) if m else str(game_version).strip()
        mods_root = os.path.join(wot_path, "mods")
        mods_dir = None
        for cand in (ver, str(game_version).strip()):
            if cand and os.path.isdir(os.path.join(mods_root, cand)):
                mods_dir = os.path.join(mods_root, cand)
                break
        if mods_dir is None:
            mods_dir = os.path.join(mods_root, ver)
        dst = os.path.join(mods_dir, "sm_tactics.wotmod")
        if os.path.isfile(dst) and os.path.getsize(dst) > 0:
            return
        print("[MAP_MGR] sm_tactics.wotmod missing — reinstalling (integrity check)")
        self.apply_mod_mode()

    def _uninstall_tactics_mod(self, wot_path):
        """Remove our sm_tactics.wotmod from every mods/<ver>/ folder (exact name only, other mods untouched)."""
        if not wot_path:
            return
        mods_root = os.path.join(wot_path, "mods")
        if not os.path.isdir(mods_root):
            return
        try:
            for entry in os.listdir(mods_root):
                dst = os.path.join(mods_root, entry, "sm_tactics.wotmod")
                if os.path.isfile(dst):
                    try:
                        os.remove(dst)
                        print(f"[MAP_MGR] Removed sm_tactics.wotmod -> {os.path.dirname(dst)}")
                    except Exception as e:
                        print(f"[MAP_MGR] Mod removal error ({dst}): {e}")
        except Exception as e:
            print(f"[MAP_MGR] Mod sweep error: {e}")

    def run_map_updater(self):
        if self.app.btn_mode_maps_1.cget("bg") == "#ff4500":
            try: import map_updater
            except ImportError:
                return
            def update_thread():
                def status_cb(text): pass
                success = False
                try: success = map_updater.sync_all(callback_status=status_cb)
                except Exception as e: print(f"[MAP_MGR] Updater error: {e}")
                def on_finish():
                    if success:
                        self.load_map_list()
                    else:
                        pass
                self.app.safe_execute(on_finish)
            threading.Thread(target=update_thread, daemon=True).start()
        else:
            if not map_extractor:
                return
            if not self._try_begin_update():
                return
            def update_thread():
                try:
                    ext = map_extractor.MapExtractor()
                    def status_cb(text): pass
                    success = ext.extract(callback_status=status_cb)
                    self._last_changed_ids = ext.last_changed_ids
                    def on_finish():
                        if success:
                            self.load_map_list()
                        else:
                            pass
                    self.app.safe_execute(on_finish)
                finally:
                    self._end_update()
            threading.Thread(target=update_thread, daemon=True).start()

    def load_map_list(self):
        ui_mode = self.app.selected_battle_mode.get()
        mode_mapping = {
            "Standard": "ctf",
            "Encounter": "domination",
            "Storm": "assault",
            "Onslaught": "comp7",
            "OnslaughtLight": "comp7",
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
                if m.startswith("type/"):
                    continue
                if m in ("invalid_map", "hangar_v4", "_default_") or m.startswith("h33_"):
                    continue
                if m in _EVENT_MAP_IDS:
                    continue
                if m in self.app.map_data:
                    gameplay_types = self.app.map_data[m].get("gameplayTypes", {})
                    has_mode = internal_mode in gameplay_types
                    if internal_mode == "assault" and "assault2" in gameplay_types:
                        has_mode = True
                    if not has_mode:
                        continue
                filtered_maps.append(m)
            self.app.map_list_eng = filtered_maps
            if is_tactic and ui_mode != "Standard":
                self.app.map_list_eng = []
                self.app.map_var.set("")
                self.app.current_map_eng = None
                self.app.map_renderer.show_main_splash(message=self.app.t('ui', 'tactic_no_maps'))
                return
        else:
            self.app.extractor_names = {}
            self.app.map_list_eng = []
            try:
                import firebase_reporter
                firebase_reporter.report_fallback(
                    "map_manager.load_map_list", "map_dictionary.json",
                    "Map dictionary empty or missing")
            except Exception:
                pass

        if is_tactic:
            # Розподіл замість виключення: мапи З тактичною картинкою перші,
            # без — в кінці списку (показуються з написом «no scheme yet»,
            # а не ховаються — спека користувача 23.10.2026). Дедуп нижче
            # віддає перевагу першому входженню → зображеному.
            _img = {m for m in self.app.map_list_eng if self._tactic_image_exists(m)}
            self.app.map_list_eng = (
                [m for m in self.app.map_list_eng if m in _img]
                + [m for m in self.app.map_list_eng if m not in _img])

        # Filter by active group schemes
        import firebase_groups
        active_id = getattr(self.app, "active_group_id", firebase_groups.PUBLIC_GROUP_ID)
        if active_id != firebase_groups.PUBLIC_GROUP_ID:
            try:
                group_schemes = firebase_groups.get_group_schemes(active_id)
                allowed_maps = set()
                for sid, sdata in group_schemes.items():
                    mid = sdata.get("map_id", "")
                    if mid:
                        allowed_maps.add(mid)
                if allowed_maps:
                    self.app.map_list_eng = [m for m in self.app.map_list_eng if m in allowed_maps]
            except Exception:
                pass

        unique_maps = []
        seen_names = set()
        for m in self.app.map_list_eng:
            name = self.app.translate_map_name(m)
            if name not in seen_names:
                unique_maps.append(m)
                seen_names.add(name)
        self.app.map_list_eng = unique_maps

        self._sort_map_list_eng_by_display()
        if is_tactic:
            # Сортування розриває розподіл «без картинки в кінці» — відновлюємо
            _img = {m for m in self.app.map_list_eng if self._tactic_image_exists(m)}
            _with = [m for m in self.app.map_list_eng if m in _img]
            _without = [m for m in self.app.map_list_eng if m not in _img]
            if _without:
                self.app.map_list_eng = _with + _without
        tmaps = [self.app.translate_map_name(m) for m in self.app.map_list_eng]
        self.app.map_selector.config(values=tmaps)
        
        if tmaps:
            if self.app.map_var.get() not in tmaps:
                self.app.map_selector.current(0)
            self.app.on_map_select()
        else:
            self.app.current_map_eng = None
            self.app.map_var.set("")
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
        eng_name = config.MAP_NAMES_EN.get(eng_key, eng_key)
        folder_name = self._resolve_tactic_folder(eng_name)
        safe_folder = folder_name.replace('?', '').replace(':', '').replace('|', '').replace("'", "").replace(' - ', '_').replace(' ', '_')
        webp_path = os.path.join(config.MAPS_DIR, safe_folder, "map.webp")
        if os.path.exists(webp_path):
            return True
        jpg_path = os.path.join(config.MAPS_DIR, f"{safe_folder}.jpg")
        png_path = os.path.join(config.MAPS_DIR, f"{safe_folder}.png")
        if os.path.exists(jpg_path) or os.path.exists(png_path):
            return True
        return False
