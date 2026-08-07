# Architecture

## Pattern Overview

**Overall:** Monolithic tkinter application with manager delegation

**Key Characteristics:**
- Single `WotAssistantHQ` class in `main.py` serves as the central hub that owns all manager instances; `active_view=""` at startup (no view loaded initially)
- Each manager (`WindowManager`, `UIManager`, `DataManager`, `LocaleManager`, `MapManager`, `MapRenderer`, `HelpManager`, `MapPainter`, `DrawingPalette`, `StatsAI`) encapsulates a specific subsystem and receives the `app` (WotAssistantHQ) reference in its constructor
- Three distinct views (`maps`, `stats`, `ai_stats`) share the same root window via pack/unpack switching
- Game integration occurs through `python.log` tailing (`LogWatcher`) and WinAPI window manipulation (`WindowManager`)
- AI-powered tank builds are synced from Firebase RTDB (admin-side generation via `admin_build_generator.py` using Gemini); the client never launches a browser — `stats_ai.py` fetches builds from Firebase at startup
- Dual storage paths: `config.BASE_DIR` (read-only bundled assets, PyInstaller `_MEIPASS` when frozen) and `config.USER_DATA_DIR` (`%APPDATA%/SM WoT Assistant`, writable user data)
- Single-instance enforcement via `CreateMutexW("SM_WoT_Assistant_SingleInstance")` with `get_last_error() == 183` check — same pattern in `launcher.py`, `tray_watcher.py`, and `admin_app.py` (mutex `SM_WoT_Assistant_Admin_SingleInstance`)
- All UI text uses translation keys via `app.t('ui', key)` — translated for any game client language; class labels (LT/MT/HT/TD/SPG) always English

## Layers

**Presentation Layer:**
- Purpose: Render maps, UI controls, drawing overlays, AI build results
- Location: `main.py`, `ui_manager.py`, `painter.py`, `painting_palette.py`, `dialog_utils.py`, `map_renderer.py`, `help_system.py`, `tray_icon.py`, `stats_ai.py`
- Contains: tkinter widgets, Canvas drawing, floating tool palettes, dark-themed dialog utilities (`dialog_utils.make_custom_dialog` creates `overrideredirect(True)` Toplevel with dark header + close button; `dark_messagebox`, `dark_confirmbox`, `dark_promptbox` all use `make_custom_dialog` + `_DragHelper`), help overlay (Toplevel grid of Label widgets, not canvas text), system tray icon (pure ctypes WinAPI via `Shell_NotifyIconW`), Treeview-based AI build browser
- Depends on: Data Layer, tkinter, Pillow (PIL), custom TTF fonts (`xvmsymbol.ttf`, `fontawesome-webfont.ttf`)
- Used by: End user

**Application Logic Layer:**
- Purpose: Orchestrate views, handle hotkeys, coordinate battle detection, manage AI flows
- Location: `main.py` (class `WotAssistantHQ`), `window_manager.py`, `log_reader.py`, `tactics_manager.py`, `service_messages.py`, `tray_icon.py`
- Contains: WotAssistantHQ, WindowManager, LogWatcher, TrayIcon, tactic import/export (`import_unified` auto-detects single-map vs all-maps format), lock/unlock button (F8 duplicate on top_bar) that enables window drag/resize/opacity/contrast hotkeys without Ctrl, service messages flush on quit via `firebase_reporter.try_flush_service_messages()`, `root.attributes("-topmost", True)` at startup, `_restore_button` floating Toplevel shown after minimize-to-tray, `active_view=""` at startup, window position clamped to screen bounds on `initialize_window()`, `close_with_game` setting persisted to `settings.json` (tray_watcher terminates main app when WoT exits), `_run_verification()` 4-phase startup verification, `_cursor_over_app()` WindowFromPoint hit-test with GetParent chain (root + overlay, WS_CHILD-safe) so edit-mode drag only works when the cursor is over the app window, `sync_schemes_with_mode` setting filters tactical schemes by selected battle mode, `_toggle_select_all()` delegates to `painter.toggle_select_all()` on Ctrl+A
- Integrates `language_module.setup()` at startup for game language detection and `LocaleManager` for runtime translation
- Depends on: Presentation Layer managers, Data Layer, `keyboard` library, WinAPI via `ctypes`
- Used by: Presentation Layer

**AI Pipeline Layer:**
- Purpose: Fetch, validate, and cache AI tank builds from Firebase RTDB, normalize equipment/crew data; admin-side build generation
- Location: `stats_ai.py`, `ai_engine.py`, `stats_data.py`, `service_messages.py`, `generate_prompt_v2.py`, `admin_build_generator.py`, `_fill_all_builds.py`, `parse_tiers_devices.py`
- Contains: StatsAI class, Firebase sync methods (`_sync_popular_tanks()`, `_sync_builds()`), build validation (`_is_build_complete()`), cache management (version-tracked `ai_builds_cache.json` with version + scripts_fingerprint, shared `_is_cache_expired` for 30-day expiry), bulk-cache save via `_save_ai_build_cache_bulk()`, deduplicated fallback reporting via `firebase_reporter.report_fallback()`; equipment/consumable/skill mappings generated at runtime from `.mo` files by `stats_data.py:generate_mo_maps()`; admin daemon `admin_build_generator.py --listen` polls `pending_updates/builds` and regenerates all builds via Gemini, using `_fill_all_builds.py:parse_build` to parse responses and `generate_prompt_v2.py:generate_prompt` for prompt construction; `generate_builds` returns `(ok, done_tags)` — the change-tracking manifest (`update_manifest_for_tags`) advances only for tags actually uploaded to RTDB, and queue tags missing from the stale `tank_db.json` are built up from client data (`_tank_record_from_client` from list.xml + `_slots_and_crew_from_client` from the vehicle XML, persisted via `_persist_client_tank_data` into tank_db.json / tank_slots_full.json / crew_builds.json + generate_prompt_v2 module-level dicts) — new client tanks are never silently dropped (F141_Durendal fix, 07.08.2026)
- Depends on: Data Layer (tank_db.json, crew_builds.json, game_entities_english.json), Firebase RTDB (`builds/`, `popular_tanks/`, `pending_updates/` nodes), `requests`, selenium (admin side only)
- Used by: Presentation Layer (SETUP view)

**Data Layer:**
- Purpose: Load/save JSON, manage tank database, extract data from game client, provide translations
- Location: `data_manager.py`, `config.py`, `locale_manager.py`, `translations.py`, `map_manager.py`, `map_extractor.py`, `tank_extractor.py`, `wot_decoder.py`, `decode_xml.py`, `language_module.py`, `ui_translator.py`, `parse_game_entities.py`, `parse_tiers_devices.py`, `stats_data.py`, `name_localizer.py`, `tth_updater.py`, `build_crew_builds.py`, `extract_equipment_loadouts.py`, `map_updater.py`
- Contains: DataManager, MapExtractor, TankExtractor, WotXmlParser (bounds-checked decoder in `decode_xml.py`), LocaleManager, LanguageModule, UITranslator, GameEntitiesExtractor, configuration constants, version loader (`config.load_version()`), dual-path storage (`config.BASE_DIR`/`config.USER_DATA_DIR`)
- Depends on: Game client files (res/packages/*.pkg, version.xml, python.log, res/text/lc_messages/*.mo), filesystem, `deep_translator` (Google Translate)
- Used by: Application Logic Layer, AI Pipeline Layer

**External Integration Layer:**
- Purpose: Interact with the World of Tanks game client and its files, package the application for distribution, provide a standalone launcher for auto-update
- Location: `log_reader.py` (python.log tailing), `window_manager.py` (WinAPI window manipulation), `tray_icon.py` (system tray via `Shell_NotifyIconW`), `map_extractor.py` (client .pkg extraction), `tank_extractor.py` (client XML reading), `build_crew_builds.py`, `extract_equipment_loadouts.py`, `parse_game_entities.py`, `parse_tiers_devices.py`, `build.py`, `launcher.py`, `tray_watcher.py`, `build_admin.py`, `installer.nsi`, `wot_assistant.spec`
- Contains: LogWatcher, WinAPI wrappers (window manipulation + system tray icon), game client decoders, PyInstaller build pipeline (`build.py` — always creates GitHub release, `gh` CLI and NSIS required; dirty git working tree blocks build), `Launcher` class with splash UI that checks RTDB for updates and launches main app, `tray_watcher.py` (pure stdlib + ctypes background process monitor via `CreateToolhelp32Snapshot`, watches `WorldOfTanks.exe` at 5s intervals, launches launcher on game start, closes main app on game stop when `close_with_game` enabled; `PE_SIZE` 568 on 64-bit / 556 on 32-bit for `PROCESSENTRY32W`), standalone admin build via `build_admin.py` (onedir into `dist/SM WoT Assistant Admin/`, local build only)
- Depends on: World of Tanks game client, `ctypes`, `keyboard`, `mouse`, PyInstaller, GitHub CLI (`gh`) — required, NSIS (`makensis.exe`) — required
- Used by: Application Logic Layer (launcher runs before main)

**Firebase / Cloud Layer:**
- Purpose: Local identity (nickname + 4-digit PIN with RTDB-synced login), error reporting, usage pings, auto-update checks, drawing publication/sync via Firebase Realtime Database REST API, community scheme download in-app, group system for private scheme sharing
- Location: `firebase_identity.py`, `firebase_reporter.py`, `firebase_drawings.py`, `firebase_groups.py`, `public/` (Firebase Hosting static website), `firebase.json`, `.firebaserc`, `database.rules.json`
- Contains: Identity system (`register`, `login`, `connect`, `disconnect`, `check_nickname_available`, `change_nickname`, `change_pin`, `is_registered`, `is_connected`, `get_nickname`, `get_user_id` — nickname + PIN stored as SHA-256 hash in `identity.json` under `config.USER_DATA_DIR`, synced to RTDB `users/{user_id}`), RTDB REST API client (PUT/POST/GET with Firebase API key auth and `_rtdb_url()` path builder), error reporting (`report_error(type, stage, error_text, blocked=False, details=None)` with structured error types and `blocked=True` for fatal startup errors that show `_show_verification_error()` and exit; `report_fallback(source, context, error_text, level)` — lightweight wrapper for non-fatal data fallback events, deduplicated per caller+context via `_REPORTED_FALLBACKS` set), version ping/check via `versions/` node with `_pick_latest()` sorting by release_date then semver, drawing publish/load/delete via `schemes/` node, auto-update dialog in `main.py` and `launcher.py`, group system (`create_group`, `join_group`, `leave_group`, `get_user_groups`, `publish_to_group`, `update_group_scheme`, `get_group_schemes`, `get_group_schemes_meta`, `import_between_groups`, `delete_group_scheme` via PUT null, `invalidate_group_schemes_cache`) with RTDB `groups/{gid}/` and `user_groups/{uid}/` nodes
- Depends on: `requests`, Firebase RTDB (`europe-west1`), Firebase Hosting, `config.USER_DATA_DIR`
- Used by: Application Logic Layer (`main.py` startup, quit, auto-update, group sync polling), External Integration Layer (`launcher.py` pre-startup update check), Presentation Layer (`ui_manager.py` identity bar + registration dialog, `painting_palette.py` group management dialogs)

## Data Flow

**Startup Flow:**
1. **[Launcher path]** When distributed, `launcher.py` runs first as a standalone `--onefile` executable — shows its own splash, checks RTDB for updates synchronously, downloads and installs the latest version if found, then launches the main app with `--splash-geometry=` to preserve splash position. For Windows autostart, `tray_watcher.exe` runs as a background process (0 windows, pure stdlib + ctypes) monitoring `WorldOfTanks.exe` at 5s intervals via `CreateToolhelp32Snapshot` — launches launcher on game start, closes main app on game stop when `close_with_game` setting enabled
2. **[Direct path]** User double-clicks main EXE or runs `python main.py` — the app may receive `--splash-geometry=` from the launcher to position the splash window consistently; `--tray` CLI flag starts minimized (skips splash → `_start_startup_checks()` → minimize to tray)
3. Single-instance check via `CreateMutexW("SM_WoT_Assistant_SingleInstance")` — exits if `get_last_error() == 183`
4. Seed `config.DEFAULT_FILES` (6 files: settings.json, locales.json, map_drawings.json, service_messages.json, popular_tanks_cache.json, ai_builds_cache.json) to `config.USER_DATA_DIR` on first launch
5. **4-Phase Verification** (`main.py:_run_verification`):
   - Phase 0: Bundle Integrity — check `config.CRITICAL_BUNDLE_FILES` (6 JSONs + VERSION + 2 TTF fonts) + `extracted_maps/map_data.json` + `extracted_maps/map_dictionary.json` exist under `config.BASE_DIR`; on failure → `_show_verification_error()` + `report_error(blocked=True)` + `sys.exit(0)`
   - Phase 1: Seed popular tanks — copy `popular_tanks_seed.json` from bundle to `popular_tanks_cache.json` in `USER_DATA_DIR` if cache doesn't exist yet
   - Phase 2: Install Marker — when frozen, check `HKCU\Software\SM WoT Assistant` registry key for `installed=1` (set by NSIS installer); on failure → `_show_verification_error()` + `report_error(blocked=True)` + `sys.exit(0)`
   - Phase 3: Network Verify — on first run (`verified.marker` missing), fetch `verify.json` from Firebase Hosting, validate `status=ok`, save `popular_tanks` to local cache, write `verified.marker` file; on network failure → `_show_verification_error()` + `report_error(blocked=True)` + `sys.exit(0)`
   - Phase 4: Game Client (non-blocking) — check `version.xml` and `scripts.pkg` exist at configured WoT path; on missing → `report_error(blocked=False)` without exiting
6. Auto-detect WoT path and python.log — `main.py:_auto_detect_log_path`, `map_manager.py:auto_detect_wot_path`
7. Detect game language via `language_module.setup()` — reads `game_info.xml`, parses `.mo` files, rebuilds locale caches if language changed
8. Check game version, extract/update maps and tank data — `map_manager.py:check_game_version` → `map_extractor.py:MapExtractor`, `tank_extractor.py:TankExtractor`. On version change, runs `GameEntitiesExtractor` (`parse_game_entities.py`) to rebuild `game_entities.json`, runs `TankExtractor.update_compact_descr()`, and signals `pending_updates/builds` trigger in RTDB for admin-side rebuild
9. Write dev PID file (`dev_pid.txt`) for tray_watcher dev-mode awareness — `main.py:_write_dev_pid()` writes PID only when not frozen; `atexit.register(_dev_pid_cleanup)` cleans up on exit
10. Auto-restore login state — if `identity.json` has `connected: True`, call `firebase_identity.connect()` to restore the previous session without re-entering credentials
11. Start log watcher for battle detection — `log_reader.py:LogWatcher.start`
12. Load map list for current view — `map_manager.py:load_map_list`
13. Start Firebase sync for popular tanks and builds — `stats_ai.py:StatsAI._sync_popular_tanks()` + `_sync_builds()`
14. **Update check preemption:** During splash display (steps 4-6), a synchronous update check may preempt the normal startup flow — the splash displays update buttons instead of proceeding to the main UI (see Auto-Update Flow)
15. **Service flush on quit:** `quit_app()` calls `firebase_reporter.try_flush_service_messages()` — queued service events in `service_messages.json` are delivered to RTDB and marked `delivered=true`; internal failures are logged to the disk queue without user visibility

**Battle Detection Flow:**
1. `log_reader.py:LogWatcher._run` tails `python.log` with regex patterns; type-to-mode mapping: 1→ctf (Standard), 2→domination (Encounter), 3→assault (Storm), 4→comp7 (Onslaught), 5→comp7_light (OnslaughtLight)
2. On map detection → `main.py:on_battle_detected` → auto-sync map selector and battle mode filters
3. On countdown start → `main.py:on_battle_countdown_started` → optionally switch to battle mode (auto-battle)
4. On vehicle detection → `main.py:on_vehicle_detected` → auto-filter vehicle class
5. On battle end → `main.py:on_battle_ended` → optionally return to editor with last battle's map

**Map Rendering Flow:**
1. User selects map from dropdown → `ui_manager.py:show_view('maps')` → `map_manager.py:load_map_list` — unified map list from `extracted_maps/map_dictionary.json` for both TACTIC and MAPS modes; TACTIC mode filters via `_tactic_image_exists()` to only show maps with images in `maps/`; `_EVENT_MAP_IDS` (18 event/onboarding/removed maps) filtered out in both modes; when a non-Public group is active, the list is filtered to maps that have at least one scheme in that group
2. `map_renderer.py:MapRenderer.load_and_resize_map` loads image (`extracted_maps/*.png` for MAPS mode, `maps/<folder>/map.webp` via `_resolve_tactic_folder()` for TACTIC mode)
3. `map_renderer.py:MapRenderer.draw_grid` overlays 10×10 coordinate grid with A-J/0-9 labels; `draw_frame()` renders a 20px dark border; `draw_arena_bases` also checks `assault2` gameplay type as fallback for Storm mode
4. `map_renderer.py:MapRenderer.draw_arena_bases` renders spawn/base areas from `map_data.json` boundingBox
5. `painter.py:MapPainter.redraw` renders user drawings (markers, arrows, brush, text, tree icons) on a separate overlay canvas (`_po_canvas` in a dedicated `_po_win` Toplevel) with scale-aware rendering and edit-mode selection rectangle; class icons (`_draw_class_icons`) filtered against active checkbox state (`app.selected_classes`); battle mode labels resolved from game client `.mo` files via `language_module.get_lang_module()`, with Google Translate fallback via `app.t('ui', ...)`; `is_visible()` respects `sync_schemes_with_mode` setting; group-linked schemes from `painter._group_schemes` are overlaid as read-only alongside local drawings, filtered by `_source` field vs `active_group_id`
6. Overlay canvas uses `-transparentcolor=#010101` for independent opacity control; events bound to both main canvas and overlay via `painter.py:bind_events_to()`; overlay windowed via separate `_po_win` Toplevel with `.transient()`, `Unmap`/`Map` bindings for ghost-window prevention, and `_po_sync_timer` (500ms) for position-only sync; `_on_root_show()` guards against premature overlay show via `_startup_complete` flag; `_hidden_by_f10` guard blocks overlay show/restore/lift while minimized to tray
7. Property editing flows through `DrawingPalette` (`painting_palette.py`) — a floating non-modal palette with toolbar, arrow start/end checkboxes (brush objects only), publish/save/import rows, mode checkboxes with names from game client `.mo`, class checkboxes (LT/MT/HT/TD/SPG — always English), text entry, 12-color history picker, delete button, status bar; Ctrl+Z undo via creation + deletion history stacks; Ctrl+↑/↓ resize in edit mode (150ms debounce); Ctrl+A toggles select-all mode for bulk modification; uses `transient(self.app.root)` + `lift(aboveThis=...)` for stacking (no `-topmost`)

**AI Tank Build Flow (SETUP view):**
1. User searches/selects a tank → `stats_ai.py:StatsAI._on_tank_select`
2. Check `ai_builds_cache.json` — if cache has a complete build for the tag (validated via `_is_build_complete()`), render from cache
3. If stale (30-day expiry via `_is_cache_expired(updated, max_days=30)`) or missing → the build downloads from Firebase on next sync cycle (no fallback)
4. Firebase sync at startup: `_sync_builds()` fetches `builds/version` from RTDB, compares against local `_builds_cache_version`, bulk-syncs all changed builds via `_save_ai_build_cache_bulk()`
5. Admin-side generation: `admin_build_generator.py --listen` (ongoing daemon) generates builds via Gemini using `generate_prompt_v2.py:generate_prompt`, parses responses via `_fill_all_builds.py:parse_build`, publishes to RTDB `builds/tanks/{tag}`; `admin_app.py` is the desktop admin GUI front-end for the same pipeline
6. On game version change: `map_manager.py:check_game_version()` writes `pending_updates/builds` trigger to RTDB; `admin_build_generator.py --listen` picks up the trigger and regenerates all builds

**Auto-Update Flow:**
1. **[Launcher path]** `launcher.py` is the preferred update path — auto-detects the installed version via `_detect_installed_version()` (regex on EXE filenames, handles "Beta" suffix). On startup `_clean_old_versions()` removes stale EXEs. Then checks RTDB synchronously (`check_for_updates_sync()`) before launching the main app. If a newer version is found, it downloads the setup to `%TEMP%` with a progress bar on its splash, runs the NSIS installer silently (`/S /NCRC`), cleans up old versioned EXEs, then spawns `SM WoT Assistant Launcher.exe --skip-splash` (which relaunches the main EXE via `_find_main_exe()`) and exits. After install, `installer.nsi` auto-launches the new version via `Exec`
2. **[In-app path]** On startup → `firebase_reporter.ping_version_async()` sends current version to RTDB (`installations/` node)
3. **Splash-screen path:** During splash display, `_start_startup_checks()` calls `firebase_reporter.check_for_updates_sync()` synchronously; if a newer version is found, `_show_splash_update()` renders "UPDATE NOW" / "LATER" buttons on the splash canvas; "UPDATE NOW" triggers `_splash_download_thread()` (download → NSIS silent install → `_dev_pid_cleanup()` → `os._exit(0)`)
4. **Main-UI path:** If no update was found during splash, `_check_for_app_updates()` calls `firebase_reporter.check_for_updates()` asynchronously after the main UI is shown; a modal update dialog with download progress bar is presented
5. Latest version is determined via `_pick_latest()` which selects the version with the highest `release_date` from the RTDB `versions/` node, using semver as tiebreaker; the `versions/latest` pointer (with `release_date: "9999-12-31"`) always points to the canonical latest; `compare_versions()` compares semver tuples and strips " Beta" suffix before comparison; `display_version` field holds the human-facing label (e.g. `"1.0.40 Beta"`)
6. On build → `build.py:write_version_to_rtdb()` publishes version metadata (version, release_date, download_url, build_size) to RTDB `versions/{version}/` and updates the `versions/latest` pointer; RTDB publish only happens after a successful GitHub release and audit

**Drawing Publish/Download Flow:**
1. User clicks Publish (single map) or Publish All from `DrawingPalette` → `painting_palette._publish()` or `_publish_all()` → `firebase_drawings.publish_drawing()` serializes drawing elements, map info, author identity → PUT to RTDB `schemes/{drawing_id}`; description auto-translated to English via `deep_translator`; duplicate detection prevents publishing the same map+comment combination; when `active_group_id` is not `"public"`, publish goes to `groups/{gid}/schemes/{drawing_id}` via `firebase_groups.publish_to_group()`
2. `public/schemes.html` (Firebase Hosting) reads from RTDB `schemes/` node, renders community schemes table with map/author filters; publishing is app-only (upload modal removed); group schemes stay private
3. In-app download: `DrawingPalette._show_download_dialog()` → `firebase_groups.get_combined_schemes()` (aggregates public + group schemes) → multi-select download with map/author/Source filters → Replace/Add/Save-to-PC/Link (sync) choice; the "Link (sync)" option stores the scheme in `painter._group_schemes` for auto-sync via group sync polling; linked schemes list in palette shows hide/show checkboxes per scheme (`painter._hidden_download_schemes`, persisted to group cache)
4. Group sync polling (every 60s): `_sync_cycle()` compares `updated_at` against local `_synced_at` stamps — if remote is newer, shows a sync notification with Update/Later buttons; "Update" downloads changed schemes into `painter._group_schemes` and calls `painter.redraw()`

**Localization Flow:**
1. On startup → `language_module.setup()` detects game language from `game_info.xml` → rebuilds dictionaries only if language changed or cache missing
2. `LanguageModule.build_all_dictionaries()` parses all `.mo` files from `res/text/lc_messages/` into per-category JSON caches under `config.USER_DATA_DIR/localization/<lang>/` (accepts all game client languages, no hardcoded list); `setup()` stores a global `_lang_module` reference via `get_lang_module()` for lazy access by other modules
3. `LanguageModule.export_locale_json()` exports combined locale JSON to `public/locale/<lang>.json` for website consumption
4. `language_module.setup()` calls `stats_data.generate_mo_maps(src, lang)` where `src = _lang_module if _lang_module is not None else lm` — builds runtime `EQUIP_MAP`, `CONS_MAP`, `CREW_SKILL_MAP` from `.mo` dictionaries (replaces old hardcoded mapping dicts); result cached per language to `mo_maps_{lang}.json` in `config.USER_DATA_DIR`
5. `regenerate_map_dictionary(_lang_module)` (`language_module.py:383`) regenerates `extracted_maps/map_dictionary.json` from `arenas.mo` parsed data on EVERY startup (not only on language change — stale dictionaries from a previous client language would otherwise persist); the call uses the global `_lang_module` (populated from cache) since `lm.dictionaries` is empty in the no-change branch
6. `LocaleManager.t_ui()` provides dynamic UI translation:
   - English `translations.py` is the authoritative source
   - On-demand Google Translate via `ui_translator.py` with caching in `locales.json`
   - Re-translates when: cache missing, cached value is still English, or English source changed (compares against stored `en_snapshot`)
   - Rejects ASCII-only cached translations; protects placeholders (`{path}`) and symbols (`->`)
7. `LocaleManager.t_map` resolves map names through: `custom_names.json` → `extractor_names` (from `map_dictionary.json`) → `locales.json` → `config.TECH_MAPS_STAGING`
8. On game version change → `map_manager.py:check_game_version` calls `language_module.check_for_language_change()` to rebuild if game language shifted

**Memory to Persistence (Cross-Session):**
1. Tactical drawings → save on every edit → `data_manager.py:save_drawings` → `map_drawings.json` in `config.USER_DATA_DIR`; bulk export/import via `tactics_manager.py:export_all_tactics()` / `import_all_tactics()` with Replace/Merge choice; `import_unified()` auto-detects single-map vs all-maps format
2. AI build cache → saved during Firebase sync (`_save_ai_build_cache_bulk()`) → `ai_builds_cache.json`
3. Settings → save on window changes/close → `settings.json`
4. Identity → save on registration/PIN change → `identity.json` in `config.USER_DATA_DIR`; `register()` also syncs to RTDB `users/{user_id}`; `login()` verifies credentials against RTDB
5. Service events → `service_messages.json` queue for future server delivery (undelivered messages marked `delivered=true` after flush)

## Key Abstractions

**WotAssistantHQ:**
- Purpose: Central application hub owning all state and manager instances
- Location: `main.py` (class WotAssistantHQ)
- Constructor: `__init__(self, root, splash_geometry=None)` — accepts optional `splash_geometry` passed by the launcher; writes dev PID file for tray_watcher; auto-restores login state if `identity.json` has `connected: True`
- Pattern: God object with manager delegation — owns settings, tank database, map state, view routing, hotkey bindings, system tray icon, group state
- Group state fields: `active_group_id` (default `"public"`), `_cached_groups` (dict of `{group_id: {role, name}}` synced from RTDB), `_group_id_map` (label → group_id lookup), `_sync_running` (flag for group sync polling)
- Key methods: `export_all_tactics()` / `import_all_tactics()` delegate to `tactics_manager.py`; `toggle_visibility()` / `_minimize_to_tray()` / `_restore_from_tray()` implement F10 minimize-to-system-tray (creates/removes `TrayIcon`, shows floating `_restore_button`, uses `_hidden_by_f10` guard flag, pauses group sync while hidden); `toggle_formatting_mode()` (F8 / Lock button) controls `format_mode_enabled` — when enabled, arrow keys (opacity), Shift+Up/Down (contrast), and window drag work without Ctrl; drag is global in norm mode but in edit mode only when the cursor is over the window (`_cursor_over_app()` WindowFromPoint hit-test); hotkey `e` changed to `tab` for battle/editor toggle (guarded by `self.current_map_eng`); `_close_with_game_var` persisted to `settings.json`; `_set_windows_startup()` manages HKCU\Run entry using `tray_watcher.exe` for autostart
- Group sync methods: `_start_group_sync()` starts 60-second polling cycle; `_sync_cycle()` calls `firebase_groups.get_group_schemes_meta(gid)` and compares `updated_at` against local `_synced_at` — if remote is newer, triggers `_show_group_sync_notification()` with pending updates
- Group cache methods: `_load_group_schemes_from_cache()` reads `config.GROUP_CACHE_FILE` at startup; `_save_group_schemes_to_cache()` writes the same to disk on quit and after group scheme updates

**Manager Pattern:**
- Purpose: Encapsulate subsystem responsibilities behind a single class receiving `app` reference
- Location: `window_manager.py`, `ui_manager.py`, `data_manager.py`, `locale_manager.py`, `map_manager.py`, `map_renderer.py`, `help_system.py`, `dialog_utils.py`
- Pattern: Each Manager receives `app` (WotAssistantHQ) in constructor, accesses shared state through `self.app.*`, and exposes domain-specific methods. `dialog_utils.py` provides stateless dark-themed dialog utilities (`make_custom_dialog`, `dark_messagebox`, `dark_confirmbox`, `dark_promptbox`, `_set_dark_title_bar`, `_center_on_root`, `_DragHelper`). `firebase_groups.py` provides module-level function-based API (not class-based) with in-memory scheme cache via module-level `_group_schemes_cache` dict

**LogWatcher:**
- Purpose: Background thread that tails WoT's `python.log` and fires callbacks on battle events
- Location: `log_reader.py`
- Pattern: Regex-based log parsing in a daemon thread with callbacks for arena detection, countdown, vehicle, minimap, hangar return; silently catches exceptions and retries every 5 seconds

**MapPainter:**
- Purpose: Canvas-based drawing system for tactical markers, arrows, brush (freehand), text, and tree icons, plus read-only group-linked scheme overlay
- Location: `painter.py`
- Pattern: Stateful drawing list persisted via `DataManager`, creation history stack + deletion history stack for Ctrl+Z undo (undoes both create and delete), per-map/per-mode filtering. Supports three marker-like types: `marker` (circle+arrow with snapping), `arrow` (line with arrow only), `brush` (freehand polyline with min 10px point spacing, arrow start/end checkboxes). All painting renders on a dedicated overlay canvas (`_po_canvas`) inside a separate `_po_win` Toplevel for independent opacity control. Binds events to multiple canvases via `bind_events_to()`. Right-click context menu for edit/delete with `dialog_utils.dark_confirmbox` confirmation. Edit mode renders a yellow dashed selection rectangle. Resize via keyboard hooks (Ctrl+↑/↓, 150ms debounce). `_group_schemes` dict `{drawing_id: {map_id, elements, group_id, updated_at, _synced_at}}` holds linked group schemes; `_scheme_downloaded_at` tracks download timestamps for sync comparison; `_hidden_download_schemes` set tracks hidden linked schemes. `_render_elements` accepts `screen_scale` param for DPI-aware drawing scale; per-object `scale` property (0.3–3.0) written to drawing JSON. Select-all mode (Ctrl+A) enables bulk thickness/size/mode/class modification and bulk delete with undo

**DrawingPalette:**
- Purpose: Floating non-modal property editor for the selected drawing object
- Location: `painting_palette.py`
- Pattern: `tk.Toplevel` subclass with toolbar (marker, arrow, brush, XVMSymbol class icons, tree FontAwesome icon), arrow start/end checkboxes (brush objects only), mode/class checkboxes, text entry, 12-color picker, Publish/Publish All/Save/Save All/Import/Download buttons, delete button, status bar; live-syncs changes to the selected object; deselects on click-away; auto-deactivates tool after object creation; thickness slider + ALL select-all button + size slider (0.3–3.0) with `_update_sliders_state()` disabling sliders when neither select-all nor edit mode active

**StatsAI:**
- Purpose: Firebase-synced tank build browser with search, filtering, composite icon rendering
- Location: `stats_ai.py`
- Pattern: tkinter Treeview + Firebase RTDB sync via REST API, version-tracked disk cache with version + scripts_fingerprint, build validation (`_is_build_complete()`), bulk sync with `_save_ai_build_cache_bulk()`, equipment/crew/consumable TTH icon rendering; `_report_fallback()` helper deduplicated by `_REPORTED_FALLBACKS` set

**LanguageModule:**
- Purpose: WoT client `.mo` file parser, game language detection, per-category JSON cache builder, locale JSON exporter
- Location: `language_module.py`
- Pattern: Module-level global `_lang_module` set by `setup()` and accessed via `get_lang_module()` / `reset_lang_module()` for lazy lookups (battle mode names, map names, TTH labels) from other modules; `regenerate_map_dictionary(lm)` and `regenerate_game_entities(lm)` regenerate derived data from parsed `.mo` data

## Entry Points

**Application Entry (Main App):**
- Location: `main.py` (`if __name__ == "__main__":` at line 2449)
- Triggers: User double-clicks executable or runs `python main.py`
- Responsibilities: Call `multiprocessing.freeze_support()`, `os.chdir(config.BASE_DIR)` for consistent CWD, seed `config.DEFAULT_FILES` to AppData on first launch, detect `--splash-geometry=` CLI flag (passed by launcher), detect `--tray` CLI flag for minimized startup (skips splash, runs `_start_startup_checks()` directly, minimizes to system tray), remove stale versioned EXEs from install dir when frozen, initialize tkinter root with version title and taskbar icon (`iconbitmap(default=...)` + `SetCurrentProcessExplicitAppUserModelID`), create WotAssistantHQ with optional `splash_geometry` parameter, start mainloop

**Application Entry (Launcher):**
- Location: `launcher.py`
- Triggers: Installed shortcut or `python launcher.py`
- Responsibilities: Auto-detect installed version via `_detect_installed_version()`; if `--skip-splash` CLI flag is present, find and launch the main EXE via `_find_main_exe()` and exit immediately. Otherwise show a lightweight Splash window, check RTDB for updates synchronously, download and install if newer version found with progress bar, clean old versioned EXEs, launch `SM WoT Assistant Launcher.exe --skip-splash` to restart cleanly, then exit. `_launch_main()` reads `start_minimized` from `settings.json` and appends `--tray` CLI flag when true. Built as standalone `--onefile` PyInstaller binary with `--collect-all PIL` + `--collect-all unicodedata`

**Background Monitor (Tray Watcher):**
- Location: `tray_watcher.py`
- Triggers: HKCU\Run autostart entry or manual launch
- Responsibilities: Pure stdlib + ctypes background process (no tkinter/PIL/requests); watches `WorldOfTanks.exe` via `CreateToolhelp32Snapshot` at 5s intervals; launches `SM WoT Assistant Launcher.exe` on game start; closes `SM WoT Assistant v*.exe` on game stop when `close_with_game` setting enabled; `_find_dev_pid()` reads `dev_pid.txt` and validates the PID is python.exe/pythonw.exe; `PE_SIZE` 568/556 for `PROCESSENTRY32W` compatibility

**Build Entry:**
- Location: `build.py`
- Triggers: `python build.py [version] [--date=YYYY-MM-DD]`
- Responsibilities: Pre-flight validation (semver, Python 3.12+PyInstaller, NSIS, `gh` CLI, critical source files, git status — dirty working tree blocks build), clean dist/build, PyInstaller onedir via `wot_assistant.spec` + manual `copy_data_files()` (workaround for PyInstaller 6.x DATA TOC bug) + `generate_verify_json()` writes `public/verify.json` and `popular_tanks_seed.json`, `build_tray_watcher()` (onefile) + `_build_launcher()` (onefile), NSIS installer via `run_nsis()`, rename onedir to versioned directory + versioned EXE, build verification (`verify_launcher_bundle()` checks launcher for Tcl/Tk DLLs + `_imaging`), build manifest; then 4-phase release audit: `verify_release_artifacts()` → `create_github_release()` → `audit_github_release()` (deletes release on mismatch) → `write_version_to_rtdb()` → `audit_rtdb_entry()`. All builds are Beta/prerelease by default (`is_beta=True` unconditionally, `--prerelease` always set); every build is a GitHub release

**Admin Build Entry:**
- Location: `build_admin.py`
- Triggers: `python build_admin.py`
- Responsibilities: Build `admin_app.py` as `--onedir --windowed` EXE named `SM WoT Assistant Admin` into `dist/SM WoT Assistant Admin/` via PyInstaller with explicit `--add-data` for bundled JSONs, `admin_version.txt`, `admin_uk_seed.json`, `temp_scripts/decoded/tiers_devices_decoded.xml`, plus selenium 4 hidden imports and `--hidden-import deep_translator`; local build only — no GitHub upload, no RTDB publish; version read from `admin_version.txt`

**Admin Desktop App:**
- Location: `admin_app.py` (class `AdminApp`)
- Triggers: `python admin_app.py` or frozen EXE; `--tray` CLI for minimized start
- Responsibilities: tkinter GUI for build generation, scripts.pkg scanning, WG API game version monitoring, auto-detect changed tanks, generate builds via Gemini, tray icon with balloon notifications, settings persistence; single-instance mutex `SM_WoT_Assistant_Admin_SingleInstance` restores the existing window on second launch; `_read_admin_version()` reads `admin_version.txt` (shown in window title + Admin Version card); `_log()` appends to `admin.log` in `%APPDATA%\SM WoT Assistant` and reverses the UI log (capped at 1000 widget lines); i18n EN/UK with `_TR_EN` dict and cached UK translations in `admin_uk_cache.json` (seeded from `admin_uk_seed.json`); `_resolve_wot_path()` auto-detects WoT path (CLI `--wot-path` → `admin_settings.json` → main `settings.json` wot_path → common paths, validated via `version.xml`)

**Map List Loading:**
- Location: `map_manager.py:load_map_list`
- Triggers: View switch to MAPS/TACTIC, battle mode filter change
- Responsibilities: Load map list from `extracted_maps/map_dictionary.json` (both modes), filter by gameplay type and `_EVENT_MAP_IDS`, filter by active group's available schemes when a non-Public group is selected, populate dropdown; TACTIC mode with non-Standard battle mode clears the map list and shows a "no maps" message via `show_main_splash(message=...)`

**Game Version Check:**
- Location: `map_manager.py:check_game_version`
- Triggers: Application startup
- Responsibilities: Compare stored version with `version.xml`, trigger map/tank extraction if changed, update crew/equipment databases, run `GameEntitiesExtractor` (`parse_game_entities.py`) to rebuild `game_entities.json`, run `TankExtractor.update_compact_descr()`, call `language_module.check_for_language_change()` to rebuild localization if game language shifted; if game version changed, signals `pending_updates/builds` trigger in RTDB for admin-side rebuild

**Website (Firebase Hosting):**
- Location: `public/` directory — served by Firebase Hosting at `sm-wot-assistant.web.app`
- Pages: `index.html` (English-only landing page with logo, download button linking to the latest versioned GitHub release — button text uses RTDB `display_version` field, features grid, community schemes promo), `schemes.html` (community tactical schemes browser with map filter, invite-code groups, PIN-based auth), `drawings.html` (drawing gallery), `admin.html` (admin dashboard with stats, schemes management, version management; live Admin App (Desktop) section reads the `admin_app/` RTDB node — Admin Version, Status (Online if `last_seen` < 5 min), Activity, Last Generation, polled every 60s), `404.html`, `verify.json` (bundle verification manifest generated by `build.py`), `locale/` (exported locale JSON, e.g. `en.json`)
- Language: All pages use `lang="en"`; class labels (LT/MT/HT/TD/SPG) remain English
- Data source: All dynamic data (schemes, versions, releases) read from Firebase RTDB via REST API with API key auth

## Error Handling

**Strategy:** Defensive with graceful degradation — fallback chains in data loading, try/except around external calls, safety timeouts. Critical integrity checks use blocking error dialogs with `sys.exit(0)`. Non-critical fallback events are reported to Firebase via `report_fallback()` for remote monitoring without blocking the user.

- `data_manager.py:load_tank_db` implements a 3-level fallback: `tank_db.json` → `tank_tth.json` (with estimated tiers) → `extracted_data/*.xml` files; each fallback level calls `firebase_reporter.report_fallback()` to log the degradation
- `stats_ai.py` uses `_report_fallback()` helper (deduplicated by `_REPORTED_FALLBACKS` set) to report cache corruption or missing data files at init time (`ai_builds_cache.json`, `crew_builds.json`, `equipment_loadouts.json`, `popular_tanks_cache.json`)
- `map_manager.py`: `check_game_version` wraps the entire pipeline in try/except with threaded execution; `_detect_pending_tactic_maps` and `load_map_list` call `report_fallback()` on `map_dictionary.json` load failure; signals `report_fallback()` if `pending_updates/builds` Firebase write fails
- `map_renderer.py`: `_report_fallback_async()` fires a daemon-threaded `report_fallback()` when `boundingBox` is missing `bottomLeft`/`upperRight` in `map_data.json` for a map
- `generate_prompt_v2.py`: on `parse_tiers_devices.load_tiers_devices()` failure, logs `report_fallback()` and falls back to hardcoded equipment lists
- `log_reader.py:LogWatcher._run` silently catches exceptions and retries every 5 seconds
- `service_messages.py` logs internal failures to disk queue without user visibility
- `data_manager.py:load_json` returns empty defaults on any file error
- `main.py:_run_verification()` — 4-phase blocking verification at startup; phases 0 (bundle integrity), 2 (install marker), and 3 (network verify) show `_show_verification_error()` dialog and call `sys.exit(0)` on failure, with `report_error(blocked=True)` to RTDB; phase 4 (game client) is non-blocking — reports but does not exit

## Cross-Cutting Concerns

**Version System:**
- `VERSION` file at project root contains a plaintext semver string (e.g., `1.0.67`)
- `admin_version.txt` — independent plaintext semver for the Admin Desktop App (e.g., `1.0.6`); read by `admin_app.py:_read_admin_version()` and `build_admin.py:read_version()`, bundled into the admin EXE via `--add-data`; not tied to main `VERSION`; `firebase_reporter._report_version()` uses it for error-report `version` when the admin EXE is frozen (or when no `VERSION` is bundled)
- `config.load_version()` (`config.py`) reads VERSION and appends `" Beta"` unconditionally — all window titles display `"1.0.67 Beta"`; `build.py` controls the GitHub release title and RTDB `display_version` field with `is_beta=True` unconditionally but does not affect runtime `load_version()`

**Build & Packaging:**
- `build.py` — 8-phase pipeline: (1) Pre-flight validation (semver, Python 3.12+PyInstaller, NSIS, gh CLI, critical source files, git status — dirty working tree blocks build), (2) Clean dist/build, (3) PyInstaller onedir + manual `copy_data_files()` (workaround for PyInstaller 6.x DATA TOC bug) + `generate_verify_json()` writes `public/verify.json` and `popular_tanks_seed.json`, (4) `build_tray_watcher()` (onefile) + `_build_launcher()` (onefile), (5) NSIS installer via makensis, (6) Rename onedir to versioned directory + versioned EXE, (7) Build verification (`verify_launcher_bundle()` — launcher Tcl/Tk DLLs + `_imaging`), (8) Build manifest. After all phases a 4-phase release audit runs: `verify_release_artifacts()` → `create_github_release()` → `audit_github_release()` (deletes release on mismatch) → `write_version_to_rtdb()` → `audit_rtdb_entry()`
- Every build is a release — `--release` flag removed; `gh` CLI and NSIS are required (pre-flight fails if missing); RTDB version publish only happens after successful GitHub release and audit
- All builds are Beta/prerelease by default: `is_beta = True` unconditionally, `--prerelease` always set; " Beta" suffix added to GitHub release title and RTDB `display_version` field, but filenames remain clean; installer and portable ZIP get `_Beta` suffix
- `wot_assistant.spec` — PyInstaller spec with `_CRITICAL_JSON` list (6 core JSONs: `crew_builds.json`, `tank_db.json`, `tank_tth.json`, `game_entities_english.json`, `game_entities.json`, `tank_slots_full.json`), fonts, `.mo` localization files, `logo.png`, `maps/`, `extracted_maps/`, `extracted_icons/`, `extracted_data/common/post_progression/`; EXE name `SM WoT Assistant`; `console=False`, `upx=True`
- Output artifacts: `dist/SM WoT Assistant vX.Y.Z/` (versioned onedir), `dist/SM_WoT_Assistant_Setup_vX.Y.Z.exe` (NSIS installer), `dist/SM_WoT_Assistant_Portable_vX.Y.Z.zip`, `dist/build_manifest_vX.Y.Z.txt`
- `installer.nsi` — NSIS script: `InstallDir "$LOCALAPPDATA\SM WoT Assistant"`, `RequestExecutionLevel user` (no admin), kills running tray watcher via `ExecWait 'taskkill /f /im "SM WoT Assistant Tray Watcher.exe"'`, deletes old `SM WoT Assistant v*.exe`, cleans old `v*.lnk` shortcuts, writes `HKCU\Software\SM WoT Assistant installed=1`, auto-launches new version post-install via `Exec`; shortcuts are version-agnostic
- Single-instance enforcement: `CreateMutexW` + `get_last_error() == 183` at startup in `main.py`, `launcher.py`, `tray_watcher.py`, and `admin_app.py` (per-app mutex names)
- `config.DEFAULT_FILES` seeds 6 files to AppData on first launch: settings.json, locales.json, map_drawings.json, service_messages.json, popular_tanks_cache.json, ai_builds_cache.json

**Logging:** Print-based console output with bracketed tags (`[INIT]`, `[SYNC]`, `[AI Tank Build]`, `[SERVICE]`, `[BUILD]`). No structured logging framework. `admin_app.py` appends to `admin.log` in `%APPDATA%\SM WoT Assistant`.

**Caching:**
- `group_schemes_cache.json` — group scheme data disk cache in `config.USER_DATA_DIR`; saved on quit and after group scheme updates, loaded at startup; keeps `downloaded_at` timestamps per scheme for sync comparison
- `popular_tanks_cache.json` — popular tanks list (tiers 8-11), 30-day expiry via shared `_is_cache_expired(updated, max_days=30)`, fail_count tracking; seeded from `popular_tanks_seed.json` on first run, updated from `verify.json` on network verify, also updated by Firebase sync; `config.VERIFY_CACHE_DAYS=7` controls refresh
- `verified.marker` — empty marker file created after successful network verification
- `ai_builds_cache.json` — AI tank builds, version-tracked (version + scripts_fingerprint), 30-day expiry, fail_count tracking, bulk-synced from Firebase via `_save_ai_build_cache_bulk()`
- `locales.json` — dynamic UI translation cache per language (Google Translate results, rejects ASCII-only entries)
- `config.USER_DATA_DIR/localization/<lang>/ui_cache.json` — per-language UI translation cache from `ui_translator.py`
- `config.USER_DATA_DIR/localization/<lang>/` — per-language `.mo` parsed dictionaries from `language_module.py`
- `config.USER_DATA_DIR/mo_maps_{lang}.json` — runtime equipment/consumable/crew-skill ID maps per language, generated by `stats_data.generate_mo_maps()`
- `public/verify.json` — bundle verification manifest generated by `build.py:generate_verify_json()`
- `popular_tanks_seed.json` — seed data for first-run popular tanks cache, generated by `build.py`
- `config.USER_DATA_DIR/identity.json` — identity storage (nickname, PIN hash, user_id, connected flag)
- `config.INSTALL_REG_KEY` (`HKCU\Software\SM WoT Assistant`) — registry key with `installed=1` written by NSIS installer, checked by verification Phase 2
- In-memory caches: composite icons, loadout icons, TTH icons (in `stats_ai.py`), `_group_schemes_cache` in `firebase_groups.py`

**Storage:** Flat JSON files at project root (bundled, read-only) and under `config.USER_DATA_DIR` (writable). No database engine. Key files: `settings.json`, `tank_db.json`, `tank_tth.json`, `crew_builds.json`, `equipment_loadouts.json`, `map_drawings.json`, `game_entities_english.json`, `tank_slots_full.json`.

**Localization:** `translations.py` provides English-only authoritative source for all UI text. `LocaleManager` (`locale_manager.py`) resolves translations dynamically:
- `t_ui(key)` — on-demand Google Translate via `ui_translator.py` with caching in `locales.json`; rejects ASCII-only cached values; protects placeholders (`{path}`) and symbols (`->`)
- `t_map(eng)` — resolves map names through: `custom_names.json` → `extractor_names` (from `map_dictionary.json`) → `locales.json` → `config.TECH_MAPS_STAGING`
- `LanguageModule` (`language_module.py`) parses WoT client `.mo` files (gettext binary format) on startup or game version change, detects language via `game_info.xml` (accepts all client languages, no hardcoded list), builds per-category JSON caches in `config.USER_DATA_DIR/localization/<lang>/`, exports `public/locale/<lang>.json` for the website; maintains a module-level global `_lang_module` set by `setup()` and accessed via `get_lang_module()`
- `UITranslator` (`ui_translator.py`) translates app UI text at runtime via Google Translate (`deep_translator`), shielding keyboard shortcuts, symbols, and numbers from translation; caches per-language in `config.USER_DATA_DIR/localization/<lang>/ui_cache.json`
