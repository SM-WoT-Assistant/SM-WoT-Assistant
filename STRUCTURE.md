# Codebase Structure

## Directory Layout

```
[project-root]/
├── main.py                     # Application entry point, WotAssistantHQ hub class, single-instance mutex (CreateMutexW + get_last_error()==183), root.attributes("-topmost", True) at startup, active_view="", splash update check, CLI --splash-geometry= passthrough from launcher, CLI --tray for minimized startup; 4-phase _run_verification() (bundle integrity via config.CRITICAL_BUNDLE_FILES, seed popular tanks, install marker via HKCU\Software\SM WoT Assistant, network verify from verify.json, game client check); _cursor_over_app() drag guard; _set_windows_startup() manages HKCU\Run using tray_watcher.exe; _write_dev_pid()/_dev_pid_cleanup() manage dev_pid.txt; F10 minimize-to-system-tray with _restore_button; F8 Lock/Unlock (format_mode_enabled); auto-restore login state
├── launcher.py                 # Standalone pre-startup update checker (built as --onefile PyInstaller binary, imports unicodedata, --collect-all PIL); auto-detects installed version via _detect_installed_version(), _clean_old_versions() removes stale EXEs, supports --skip-splash for silent relaunch after update, checks RTDB for updates synchronously, downloads/installs, then launches main EXE; _launch_main() reads start_minimized from settings and passes --tray to main.exe
├── tray_watcher.py             # Minimal background process monitor (pure stdlib + ctypes, no tkinter/PIL/requests); built as --onefile. Watches WorldOfTanks.exe via CreateToolhelp32Snapshot at 5s intervals. Launches SM WoT Assistant Launcher.exe on game start; closes main app on game stop when close_with_game enabled. PE_SIZE 568/556 for PROCESSENTRY32W. _find_dev_pid() reads dev_pid.txt
├── tray_icon.py                # System tray icon (pure WinAPI ctypes: Shell_NotifyIconW, message-only window, polling 250ms); TrayIcon class with _click_flag polling; global WNDPROC; LoadImageW loads icon.ico
├── config.py                   # Paths (BASE_DIR, USER_DATA_DIR=%APPDATA%/SM WoT Assistant, ICON_FILE, LOGO_FILE), constants, load_version() (reads VERSION + " Beta"), TECH_MAPS_STAGING, MAP_NAMES_EN (37_caucasus → "Mountain Pass"), DEFAULT_FILES seeding list, GROUP_CACHE_FILE; verification constants (VERIFY_URL, VERIFY_CACHE_FILE, VERIFY_CACHE_DAYS, VERIFIED_MARKER, INSTALL_REG_KEY, CRITICAL_BUNDLE_FILES list of 9 critical files)
├── VERSION                     # Plaintext semver (1.0.68) — consumed by config.load_version() and build.py
├── admin_version.txt           # Plaintext semver for Admin Desktop App (1.0.14) — independent of main VERSION; read by admin_app.py and build_admin.py, bundled via --add-data
├── admin_uk_seed.json          # Seed EN→UK translations for admin app i18n (99 keys); bundled via build_admin.py --add-data; used when admin_uk_cache.json is missing (zero Google requests on fresh install)
├── build.py                    # PyInstaller build orchestrator + GitHub release (always creates release, gh CLI + NSIS required); dirty git working tree blocks build; generate_verify_json() writes public/verify.json + popular_tanks_seed.json; 4-phase release audit (verify → create → audit → write → audit); verify_launcher_bundle() checks launcher for Tcl/Tk DLLs + _imaging; write_version_to_rtdb() publishes versions via admin_auth ID token (fails without admin_creds.json); all builds Beta/prerelease by default
├── wot_assistant.spec          # PyInstaller spec: hidden imports, COLLECT step for onedir output; _CRITICAL_JSON list (6 core JSONs); EXE name "SM WoT Assistant"
├── build_admin.py              # Standalone build script for Admin Desktop App; --onedir --windowed into dist/SM WoT Assistant Admin/ (canonical launch location); clean() removes folder + root onefiles; reads admin_version.txt; selenium 4 hidden imports + deep_translator; local build only
├── admin_icon.ico              # Red border icon for admin app
├── installer.nsi               # NSIS installer script (lzma, InstallDir $LOCALAPPDATA, RequestExecutionLevel user — no admin); kills tray watcher via ExecWait 'taskkill /f /im "SM WoT Assistant Tray Watcher.exe"'; deletes old SM WoT Assistant v*.exe; writes installed=1 registry key; auto-launches new version via Exec; version-agnostic shortcuts
├── window_manager.py           # Window positioning, click-through, WinAPI, resizing; reads/writes edit_h from settings; format_mode_enabled (F8/Lock) allows drag in both norm and edit modes — global drag (cursor outside window) only in norm, in edit only when cursor over app window (_cursor_over_app(), WindowFromPoint hit-test + GetParent chain)
├── ui_manager.py               # UI layout, view switching, filter construction; top_bar with Lock/Unlock button, minimize-to-tray button, settings gear, Website link; battle mode labels from game client .mo (Assault→Storm, Onslaught " 10", OnslaughtLight " 8"); group selector Combobox + group token button; identity bar + registration dialog with debounced nickname availability check; settings menu (launch_on_game_start, close_with_game, auto_window_size, sync_schemes_with_mode)
├── data_manager.py             # JSON file I/O, tank DB loading with fallback chain (tank_db.json → tank_tth.json → extracted_data/ filenames), each level calls firebase_reporter.report_fallback(); load_json returns empty defaults on error
├── dialog_utils.py             # Dark-themed dialog utilities: make_custom_dialog() (overrideredirect Toplevel with dark header + close), dark_messagebox(), dark_confirmbox(), dark_promptbox() — all use make_custom_dialog + _DragHelper internally; _set_dark_title_bar(), _center_on_root(), _DragHelper class for window dragging
├── locale_manager.py           # Translation system, map name resolution (t_ui, t_map)
├── map_manager.py              # Map list loading (unified TACTIC↔MAPS from extracted_maps/map_dictionary.json), game version check, data updates, TACTIC image existence filter, _EVENT_MAP_IDS (18 event/onboarding/removed maps — Empire's Border + Mountain Pass live since 04.08.2026); group scheme map filtering; battle mode filtering; TACTIC no-maps message for non-Standard modes; on game version change runs GameEntitiesExtractor + update_compact_descr() + signals pending_updates/builds
├── map_renderer.py             # Map image rendering, 10×10 grid, draw_frame() border, _resolve_tactic_folder(), arena bases (assault2 gameplay type fallback for Storm); show_main_splash(message=None); _report_fallback_async() for missing boundingBox
├── painter.py                  # Canvas drawing: markers, arrows, brush (freehand), text, tree icons, undo (creation + deletion history stacks), edit mode, class icon filtering, overlay (_po_win Toplevel) with transient/Unmap/focus management, _po_sync_timer (500ms); _group_schemes dict for read-only linked group scheme overlay; _scheme_downloaded_at timestamps; _hidden_download_schemes set; select-all toggle (Ctrl+A); _render_elements(screen_scale) DPI-aware; scale property 0.3–3.0
├── painting_palette.py         # Floating DrawingPalette (tk.Toplevel): toolbar (marker + arrow + brush + XVMSymbol + tree FontAwesome icons), arrow start/end checkboxes for brush, live-sync editing, 12-color history, status bar, delete button, Publish/Publish All/Save/Save All/Import/Download; community schemes download dialog with search + multi-select; group management section (Create/Join/Manage) with overrideredirect(True) dialogs; group-aware publish; linked schemes list with hide/show; thickness slider + ALL select-all + size slider (0.3–3.0)
├── log_reader.py               # python.log tailing for battle event detection; type-to-mode mapping (1→ctf, 2→domination, 3→assault, 4→comp7, 5→comp7_light)
├── help_system.py              # F1 help overlay via Toplevel grid of Label widgets; auto-sized; all text via app.t(); FontAwesome icons
├── tactics_manager.py          # Import/export of tactical drawings as JSON; import_unified() auto-detects single-map vs all-maps format; dark-themed modals via dialog_utils
├── service_messages.py         # Internal event logging queue (undelivered messages to service_messages.json); log_event/get_pending/mark_delivered
├── translations.py             # Default UI/map translations (English-only authoritative source); class labels (LT/MT/HT/TD/SPG) kept English
├── stats_ai.py                 # AI tank build browser (Treeview + Firebase RTDB sync), popular tanks (tiers 8-11), version-tracked caches, _sync_popular_tanks() and _sync_builds(); _report_fallback() deduplicated via _REPORTED_FALLBACKS set; _is_build_complete(); _save_ai_build_cache_bulk(); imports generate_prompt_v2 for local prompt generation
├── stats_data.py               # Equipment, consumable, crew skill ID mappings; generates EQUIP_MAP/CONS_MAP/CREW_SKILL_MAP at runtime from .mo files via generate_mo_maps() (called from language_module.setup()), cached per language to mo_maps_{lang}.json; EQUIP_SLOT_TAGS, SLOT_TYPE_NAMES
├── ai_engine.py                # AI response normalization constants (EQUIP_ID_MAP, AI_CONS_MAP), AIEngine class, cache management with 30-day expiry; AI_CONS_MAP imported by generate_prompt_v2
├── generate_prompt_v2.py       # AI prompt generator for competitive tank builds (used by admin_build_generator.py and stats_ai.py); loads equipment data via parse_tiers_devices.load_tiers_devices() with hardcoded fallback + report_fallback(); _cons_rev_map() reverses ai_engine.AI_CONS_MAP for English ration names
├── admin_app.py                # Desktop admin tool (tkinter GUI): build generation, scripts.pkg scanning, WG API game version monitoring, auto-detect changed tanks, generate builds via Gemini, tray icon, settings persistence, --tray CLI; starts in the system tray by default (start_minimized: True); X button minimizes to tray; version from admin_version.txt; single-instance mutex SM_WoT_Assistant_Admin_SingleInstance; i18n EN/UK (_TR_EN dict, admin_uk_cache.json + admin_uk_seed.json); _log() appends to admin.log; _resolve_wot_path() auto-detect; daily build fill sweep (_run_build_fill_sweep, 24h self-heal for strictly incomplete builds via scan_incomplete_builds — direct generation, mutual exclusion with the --listen daemon); failure reasons from generate_builds render in the GUI log + pending_updates RTDB error message + tray balloon
├── admin_auth.py               # Admin RTDB write auth: get_id_token() — Firebase ID token via accounts:signInWithPassword from %APPDATA%/SM WoT Assistant/admin_creds.json (gitignored), cached + refresh-token auto-refresh; _rtdb_url_with_token() strips existing ?auth= param (RTDB uses the first auth param); used only by admin tooling (build.py, admin_build_generator.py, admin_app.py) — client app writes with API key only
├── admin_build_generator.py    # Admin daemon: --popular, --builds, --listen modes; polls pending_updates/builds every 10s, generates builds via Gemini using generate_prompt_v2 + _fill_all_builds.parse_build, publishes to RTDB builds/tanks/{tag} (via admin_auth ID token); manifest fingerprinting (detect_changed_tanks, snapshot_manifest, update_manifest_for_tags — advances only for done_tags and resets _failures); consecutive-failure registry (_failures node, update_manifest_failures/exclude_failed_tags, threshold 3 — a persistently failing tank is excluded from detection and the sweep until its scripts.pkg fingerprint changes, closing silent infinite FAILED loops); generate_builds returns (ok, done_tags, reasons) — per-tag failure categories flow to console + GUI + pending_updates + error_reports via report_fallback; _tank_record_from_client raises the list.xml parse error instead of a silent None; _fill_progress.json in AppData with stale-index guard; _MANIFEST_LOCK guards detect/snapshot/update; _put_json skips writes without admin credentials; daily fill sweep for strictly incomplete builds (strict_build_incomplete checks equipment_1/2 + consumables_1/2 + every client crew role with perks, _normalize_crew_role, scan_incomplete_builds, _run_daily_sweep — 24h, mutual exclusion with GUI, filtered by exclude_failed_tags); Chrome resilience: always-isolated profile copy in %TEMP%\sm_wot_admin_chrome_profile (_kill_chrome_matching, _DRIVER_RETRY_MARKERS, 3-attempt _create_driver, mid-run reconnect), window positioned fully off-screen (--window-position=-32000,-32000) so no Chrome window appears above other apps; save_prompt only after _upload_prompt success; _update_builds_version gated on ok_count>0
├── _fill_all_builds.py         # Batch AI build filler; parse_build() parses AI responses into build structure; imported by admin_build_generator
├── prompts_cache.json          # Pre-generated prompt cache (bundled, admin-side only)
├── firebase_identity.py        # Local identity system: register/login/connect/disconnect/check_nickname_available/change_nickname/change_pin; identity.json in AppData (nickname, PIN SHA-256 hash, user_id, connected flag); RTDB users/{user_id} node
├── firebase_reporter.py        # RTDB REST: report_error(type, stage, error_text, blocked=False, details=None), report_fallback(source, context, error_text, level), _report_version(), version pings, check_for_updates(_sync), _pick_latest(), compare_versions(); PUT null for deletions (requests.put(data=b"null"))
├── firebase_drawings.py        # RTDB REST: publish/download/delete tactical drawings (schemes/ node); get_all_schemes() synchronous fetch
├── firebase_groups.py          # Group system: create/join/leave/manage groups, group scheme publish/sync/import, invite codes, officer/member roles, get_combined_schemes(), delete_group_scheme() via PUT null, invalidate_group_schemes_cache(), update_group_scheme() upsert; in-memory _group_schemes_cache
├── name_localizer.py           # Tank name localization utilities (localize_tank_db via .mo files)
├── language_module.py          # .mo file parser, game language detection, locale JSON exporter; global _lang_module via get_lang_module()/reset_lang_module(); regenerate_map_dictionary() called on EVERY startup (with _lang_module); regenerate_game_entities(); setup() calls stats_data.generate_mo_maps()
├── ui_translator.py            # Runtime UI translation via Google Translate (deep_translator) with shortcut/symbol shielding; per-language cache in localization/<lang>/ui_cache.json
├── map_extractor.py            # Map extraction from game client (MAPS mode); manifest tracking
├── map_updater.py              # Map sync for TACTIC mode (website scraping via selenium)
├── tank_extractor.py           # Tank data extraction from game client; update_compact_descr() populates missing compact_descr fields; _sanitize_list_xml() escapes raw '&'/'<' markers + strips UTF-8 BOM for both list.xml parse sites; uses name_localizer + tth_updater
├── wot_decoder.py              # XML decoder for game client .pkg files (wraps decode_xml.WotXmlParser)
├── decode_xml.py               # Bounds-checked XML decoding (WotXmlParser) — guards against malformed data with offset/child_count/id bounds
├── parse_game_entities.py      # Game entities parser; GameEntitiesExtractor rebuilds game_entities.json; parses crew perk names from .mo at runtime; bounds-checked
├── parse_tiers_devices.py      # Equipment tier/device parser from tiers_devices.xml; reads scripts.pkg as ZIP (cached to AppData tiers_devices_raw.xml), writes decoded output to USER_DATA_DIR/tiers_devices_decoded.xml
├── build_crew_builds.py        # Crew composition from game client; commander role skill pool excludes fireFighting
├── extract_equipment_loadouts.py # Equipment loadouts from scripts.pkg
├── tth_updater.py              # TTH merge utilities (safe_merge_tth_from_extracted, safe_merge_tth_from_file_list)
├── map_drawings.json           # User tactical drawings (root copy seeds AppData on first launch)
├── settings.json               # Runtime user settings (root copy seeds AppData)
├── tank_db.json                # Tank database (bundled)
├── tank_tth.json               # Tank TTH data (bundled, fallback source)
├── tank_slots_db.json          # Tank slots database (bundled)
├── tank_slots_full.json        # Full tank slots data (bundled)
├── crew_builds.json            # Crew builds (bundled)
├── equipment_loadouts.json     # Equipment loadouts (bundled)
├── game_entities.json          # Game entity data (bundled, rebuilt by parse_game_entities on version change)
├── game_entities_english.json  # English game entity names (bundled)
├── popular_tanks_seed.json     # Seed data for first-run popular tanks cache, generated by build.py
├── popular_tanks_cache.json    # Popular tanks cache (root copy seeds AppData)
├── ai_builds_cache.json        # AI builds cache (root copy seeds AppData)
├── locales.json                # Editable translation overrides (root copy seeds AppData)
├── service_messages.json       # Service message queue (root copy seeds AppData)
├── icon_mapping.json           # Icon mapping data
├── ukrainian_map_names.json    # Map name translations (extractor output)
├── map_list.json               # TACTIC map list (legacy)
├── map_links.json              # Map links data
├── database.rules.json         # RTDB security rules: root deny; versions/builds/prompts/popular_tanks write only for admin uid; installations/service_events/admin_app auth-gated reads; error_reports append-only (create open, delete auth); drawings read-only; indexes (versions, schemes, error_reports, installations, service_events, groups, user_groups)
├── firebase.json               # Firebase Hosting + Database configuration
├── .firebaserc                 # Firebase project alias ("sm-wot-assistant")
├── artefacts_en.mo             # Equipment artefacts English .mo (bundled)
├── crew_perks_en.mo            # Crew perks English .mo (bundled)
├── item_types_en.mo            # Item types English .mo (bundled)
├── fontawesome-webfont.ttf     # FontAwesome icon font (bundled)
├── xvmsymbol.ttf               # XVMSymbol class icon font (bundled)
├── logo.png                    # App/website logo
├── icon.ico                    # App icon
├── public/                     # Firebase Hosting static website (sm-wot-assistant.web.app), English-only
├── maps/                       # Map images for TACTIC mode (webp/jpg/png, 52 map folders)
├── extracted_maps/             # Map images + data from game client (MAPS mode; map_data.json, map_dictionary.json, 65 PNGs)
├── extracted_icons/            # Tank/loadout icons extracted from client (8 category dirs)
├── extrated_icons/             # Additional tank icon set (1223 PNGs per tank)
├── extracted_data/             # Decoded XML tank data by nation + version-suffixed nation folders
├── localization/               # Translation JSON tables (item types, crew perks, artefacts, english_search)
├── Tactik_Shemi/               # Exported tactical drawing JSONs (per-map tactic files)
├── icon/                       # Custom icons (Broken_tree.svg + test PNGs)
├── temp_scripts/               # Extraction scripts + decoded XML (scripts/, decoded/; tiers_devices_decoded.xml used by admin build)
├── temp_scripts2/              # Extraction scripts v2 (scripts/ + component_defs, tutorial_docs, user_data_object_defs)
├── _decoded_search/            # Decoded XML map search results (per-map .xml files)
├── _archive/                   # Archived code variants: scripts/ (125 dead modules), docs/, temp_scripts/, temp_scripts2/, localization/, tools/, test_data/, etc.
├── docs/                       # Topical documentation (firebase.md, painter.md, maps.md, cache.md, release.md, admin.md, tray.md, game-data.md, decoder.md, changelog.md, bugs.md)
├── build/                      # PyInstaller intermediate build cache (Analysis, PYZ, EXE, COLLECT); admin_app subdir
├── dist/                       # Release output (versioned onedir, NSIS installer, portable ZIP, manifest; SM WoT Assistant Admin/ onedir)
├── .venv/                      # Python virtual environment(s)
├── .vscode/                    # VS Code workspace settings
└── .opencode/                  # OpenCode IDE configuration
```

## Directory Purposes

**Project Root:**
- Purpose: All application source code, data files, and configuration live at root level (no `src/` directory)
- Contains: 46 Python scripts, 27 JSON data files, TTF fonts, `.mo` localization files, markdown docs, SVG icons, `installer.nsi`
- Key files: `main.py`, `config.py`, `settings.json`

**public/:**
- Purpose: Firebase Hosting static website served at `sm-wot-assistant.web.app`
- Contains: English-only landing page (`index.html`, `lang="en"`) with logo, download button linking to the latest versioned GitHub release (button text from RTDB `display_version`), features grid, community schemes promo, borderless window warning; `schemes.html` community schemes browser (map filter, authors filter, invite-code groups, PIN-based auth; publishing is app-only — upload modal removed); `drawings.html` gallery; `admin.html` admin dashboard (stats, schemes management, version management, live Admin App (Desktop) section reading the `admin_app/` RTDB node via `loadAdminAppData()` polled every 60s); `verify.json` bundle verification manifest (version, popular_tanks, prompt_date_format) generated by `build.py` and fetched by `main.py:_run_verification` Phase 3; `404.html`; static assets (`logo.png`, `favicon.ico`, `example_map.png`); `locale/` subdirectory with exported locale JSON (e.g., `en.json`)
- Key files: `index.html`, `schemes.html`, `verify.json`

**maps/:**
- Purpose: Map images for TACTIC mode (sourced from website, not game client)
- Contains: 52 subdirectories named after maps (e.g., `Karelia/`, `Malinovka/`, `Empires_Border/`, `Mountain_Pass/`), each containing `map.webp`, `map.jpg`, or `map.png`
- Key files: Organized by human-readable folder names

**extracted_maps/:**
- Purpose: Map images and metadata extracted from the World of Tanks game client (MAPS mode)
- Contains: `map_data.json` (boundingBox, gameplay types, arena bases), `map_dictionary.json` (internal keys → display names in client language, regenerated from `arenas.mo` on every startup), 65 per-map PNG images, `.map_extract_manifest.json`
- Key files: `map_data.json`, `map_dictionary.json`

**extracted_icons/:**
- Purpose: Tank and loadout icons extracted from client `.pkg` files
- Contains: 8 category directories — `artefacts/`, `classes/`, `clean_nations/`, `levels/`, `loadout/` (with `ammo/`, `artefacts/`, `consumables/`, `crew_perks/`, `crew_roles/`, `crew_skills/`, `field_mods/` subdirs), `nations/`, `tth/`, `vehPostProgression/`
- Key files: `loadout/artefacts/*.png`, `loadout/ammo/*.png`, `loadout/crew_skills/*.png`

**extrated_icons/:**
- Purpose: Additional tank icon set extracted from game client, one `.png` per tank (1223 files; historically a variant of `extracted_icons/`)

**extracted_data/:**
- Purpose: Decoded XML tank data organized by nation (fallback data source for tank DB)
- Contains: Subdirectories per nation (`usa/`, `ussr/`, `germany/`, `france/`, `china/`, `uk/`, `czech/`, `japan/`, `italy/`, `poland/`, `sweden/`) plus version-suffixed nation folders (`usa_0/`, `usa_1/`, ... — `update_compact_descr()` reads from these), `common/` (includes `post_progression/` field mod data)

**Tactik_Shemi/:**
- Purpose: Exported tactical drawing JSON files, one per map, for backup/sharing

**localization/:**
- Purpose: Translation tables used by the locale system
- Contains: JSON translation files for item types, crew perks, artefacts, and general search terms

**icon/:**
- Purpose: Custom application icons not extracted from game
- Contains: `Broken_tree.svg` and test PNG files

**temp_scripts/, temp_scripts2/:**
- Purpose: Extraction/decode scripts for batch processing of game client data
- Contains: `scripts/` with `arena_defs/`, `common/`, `entity_defs/`, `item_defs/`, `space_defs/` (temp_scripts2 adds `component_defs/`, `tutorial_docs/`, `user_data_object_defs/`); `temp_scripts/decoded/` holds decoded XML output (`tiers_devices_decoded.xml` is bundled into the admin build via `build_admin.py --add-data`)
- Key files: `temp_scripts/decoded/tiers_devices_decoded.xml`

**_decoded_search/:**
- Purpose: Decoded XML files for map search results, organized per map

**_archive/:**
- Purpose: Archived/old code variants preserved for reference; dead modules moved here on 04.08.2026 (125 scripts in `scripts/` — AI scrapers, selenium helpers, one-off extractors, check/debug/test/patch scripts)
- Contains: `scripts/`, `docs/` (obsolete markdown files), `temp_scripts/`, `temp_scripts2/`, `localization/`, `extrated_icons/`, `tools/`, `test_data/`, `tmp/`, `tmp_check/`, `temp_pages/`, `browser_profile/`, `AI_ALTERNATIVES/`

**docs/:**
- Purpose: Topical documentation (11 files) — see the docs index table in `AGENTS.md`
- Contains: `firebase.md`, `painter.md`, `maps.md`, `cache.md`, `release.md`, `admin.md`, `tray.md`, `game-data.md`, `decoder.md`, `changelog.md`, `bugs.md`

**build/:**
- Purpose: PyInstaller intermediate build cache directory (temporary, cleaned between builds); `admin_app/` subdir used by `build_admin.py`
- Contains: Analysis, PYZ, EXE, COLLECT toc files, base_library.zip

**dist/ (git-ignored):**
- Purpose: Final release output directory generated by `build.py` and `build_admin.py`
- Contains: Versioned onedir (`SM WoT Assistant vX.Y.Z/`), NSIS installer (`SM_WoT_Assistant_Setup_vX.Y.Z.exe`), portable ZIP (`SM_WoT_Assistant_Portable_vX.Y.Z.zip`), build manifest (`build_manifest_vX.Y.Z.txt`), and the Admin onedir `SM WoT Assistant Admin/`

## Key File Locations

**Entry Points:** `main.py`: Application startup, single-instance mutex (`CreateMutexW` + `get_last_error()==183`), creates `WotAssistantHQ` with all managers, `--splash-geometry=` passthrough from launcher, `--tray` for minimized startup, `os.chdir(config.BASE_DIR)`, AppData seeding via `config.DEFAULT_FILES`, 4-phase `_run_verification()`, taskbar icon via `iconbitmap` + `SetCurrentProcessExplicitAppUserModelID`, dev PID file, auto-restore login state, F10 minimize-to-tray, F8 Lock/Unlock, `_set_windows_startup()` HKCU\Run management using `tray_watcher.exe`. `launcher.py`: Standalone pre-startup launcher (built as `--onefile`), checks RTDB for updates synchronously, downloads/installs, relaunches via `--skip-splash`. `tray_watcher.py`: Background process monitor (pure stdlib + ctypes) — launches launcher on game start, closes main app on game stop. `build.py`: `python build.py [version] [--date=YYYY-MM-DD]` — full build + GitHub release + RTDB publish. `build_admin.py`: `python build_admin.py` — local Admin EXE build only
**Configuration:** `config.py`: File paths (`BASE_DIR`, `USER_DATA_DIR` at `%APPDATA%/SM WoT Assistant`, `ICON_FILE`, `LOGO_FILE`), `load_version()`, `TECH_MAPS_STAGING`, `MAP_NAMES_EN` (English map name dictionary; `37_caucasus` → `"Mountain Pass"`), `DEFAULT_FILES` seeding list, `GROUP_CACHE_FILE`; verification constants (`VERIFY_URL`, `VERIFY_CACHE_FILE`, `VERIFY_CACHE_DAYS=7`, `VERIFIED_MARKER`, `INSTALL_REG_KEY`, `CRITICAL_BUNDLE_FILES` — 9 files). `VERSION`: Plaintext semver (currently `1.0.68`). `admin_version.txt`: independent admin app version (currently `1.0.14`). `wot_assistant.spec`: PyInstaller packaging spec. `installer.nsi`: NSIS installer script. `settings.json`: runtime user settings (root copy seeds AppData)
**Core Logic:** `main.py` (class `WotAssistantHQ`): central hub owning all managers; `map_manager.py`: map data and game version management; `stats_ai.py` (class `StatsAI`): AI build system + Firebase sync; `tray_icon.py` (class `TrayIcon`): system tray via pure WinAPI ctypes; `painter.py` (class `MapPainter`): tactical drawing; `painting_palette.py` (class `DrawingPalette`): drawing property editor
**Window Management:** `window_manager.py`: window positioning, resizing, transparency, click-through, game focus; drag with `format_mode_enabled` (F8/Lock) — global in norm mode, cursor-over-app only in edit mode (`_cursor_over_app()` WindowFromPoint hit-test); reads/writes `edit_h` from settings. `ui_manager.py`: UI layout construction, view switching, top_bar buttons, identity bar, settings menu
**Data Extraction:** `map_extractor.py` (class `MapExtractor`): map extraction from client; `tank_extractor.py` (class `TankExtractor`): tank data extraction; `wot_decoder.py` / `decode_xml.py`: bounds-checked XML decoding (`WotXmlParser`)
**Battle Integration:** `log_reader.py` (class `LogWatcher`): python.log tailing with regex-based event detection
**Drawing System:** `painter.py` (class `MapPainter`): markers/arrows/brush/text/tree with Ctrl+Z undo (creation + deletion history stacks), resize, right-click edit/delete, edit-mode selection rectangle, class icon filtering, overlay canvas (`_po_win` Toplevel) with 500ms `_po_sync_timer`, select-all mode, per-object scale property; `painting_palette.py` (class `DrawingPalette`): floating non-modal palette with toolbar, mode/class checkboxes, 12-color picker, publish/save/import/download, group management
**AI Pipeline:** `generate_prompt_v2.py`: build AI prompts from client data; `ai_engine.py`: AI response constants (`AI_CONS_MAP`) + `AIEngine` class; `stats_data.py`: runtime equipment/skill/consumable mappings from `.mo` files; `admin_build_generator.py`: admin-side generation daemon; `_fill_all_builds.py`: batch build filler with `parse_build()`
**Localization:** `translations.py`: English-only authoritative translations (class labels kept English); `locale_manager.py` (class `LocaleManager`): runtime translation resolution; `locales.json`: editable translation overrides; `language_module.py` (class `LanguageModule`): WoT client `.mo` parser, language detection, per-category JSON cache builder, locale exporter, `regenerate_map_dictionary()` on every startup; `ui_translator.py`: runtime UI translation via Google Translate with shortcut/symbol shielding
**Persistence Data:** `settings.json`, `tank_db.json`, `tank_tth.json`, `crew_builds.json`, `equipment_loadouts.json`, `tank_slots_full.json`, `map_drawings.json`, `game_entities_english.json`, `ai_builds_cache.json`, `popular_tanks_cache.json` — all seeded to AppData on first launch (runtime copies live in `%APPDATA%/SM WoT Assistant/`)
**Firebase/Cloud:** `firebase_identity.py`: local identity + PIN auth (identity.json in AppData); `firebase_reporter.py`: RTDB error/analytics/versions with `_pick_latest()`; `firebase_drawings.py`: RTDB drawing CRUD (`schemes/` node); `firebase_groups.py`: group system — create/join/leave/manage with invite codes, group scheme publish/sync, `get_combined_schemes()`; `admin_auth.py`: admin RTDB write auth via ID token from `admin_creds.json` (gitignored) — used by `build.py:write_version_to_rtdb()` and `admin_build_generator._put_json()`; `firebase.json` + `.firebaserc`: project config; `database.rules.json`: secured RTDB rules (root deny, admin-uid-gated writes, auth-gated reads, append-only error_reports, read-only drawings) with indexes; `public/`: static website deployed to Firebase Hosting
**Tests:** Scattered `test_*.py` files at root (no dedicated `tests/` directory); most archived to `_archive/scripts/`

## Naming Conventions

**Files:** Python scripts use `snake_case.py` for modules (e.g., `map_renderer.py`, `log_reader.py`, `stats_ai.py`). Admin/support scripts follow the same convention (`admin_app.py`, `admin_build_generator.py`, `build_admin.py`). Debug/check/test/patch scripts were prefixed `debug_`, `check_`, `test_`, `patch_` and are archived in `_archive/scripts/`.

**Directories:** Extracted data uses lowercase with underscores: `extracted_maps/`, `extracted_icons/`, `extracted_data/`. Map folders under `maps/` use capitalized human-readable names (`Empires_Border/`, `Mountain_Pass/`).

**Classes:** PascalCase: `WotAssistantHQ`, `WindowManager`, `MapRenderer`, `LogWatcher`, `StatsAI`, `MapExtractor`, `TankExtractor`, `MapPainter`, `DrawingPalette`, `LocaleManager`, `DataManager`, `HelpManager`, `UIManager`, `LanguageModule`, `AIEngine`

**Functions:** `snake_case` for module-level functions (e.g., `_load_ai_build_cache`, `_is_cache_expired`, `regenerate_map_dictionary`). Method names also `snake_case` (e.g., `load_map_list`, `show_main_splash`, `set_clickthrough`).

**JSON Keys:** Mixed casing following game client conventions: `camelCase` for tank data (`boundingBox`, `gameplayTypes`, `compact_descr`), `snake_case` for app settings (`wot_path`, `log_path`, `edit_alpha`).

**RTDB Nodes:** `lowercase` top-level nodes with `snake_case` paths: `builds/tanks/{tag}`, `builds/version`, `builds/scripts_fingerprint`, `popular_tanks/data`, `pending_updates/builds`, `schemes/{drawing_id}`, `groups/{gid}/schemes/{drawing_id}`, `users/{user_id}`, `versions/{version}`, `installations/`, `error_reports/`, `service_events/`.

## Where to Add New Code

**New manager:** Create `new_manager.py` at root, implement a class receiving `app` reference, instantiate in `main.py:WotAssistantHQ.__init__`
**New drawing tool:** Add toolbar button in `painting_palette.py:DrawingPalette._build_ui`, add the tool code/icon (XVMSymbol or FontAwesome), implement drawing logic in `painter.py:MapPainter.on_press`/`on_drag`/`on_release`, rendering in `painter.py:MapPainter.redraw`, and class icon filtering in `_draw_class_icons`
**New game event:** Add regex pattern in `log_reader.py:LogWatcher`, add callback parameter, wire in `main.py:WotAssistantHQ`
**New AI feature:** Add to `stats_ai.py:StatsAI` class or create a companion module imported from there; admin-side generation goes in `admin_build_generator.py` / `generate_prompt_v2.py`
**New data extraction:** Create `extract_*.py` at root, follow the pattern of `map_extractor.py` / `tank_extractor.py` (manifest tracking, callback_status)
**New translation:** Add keys to `translations.py`, they auto-merge into `locales.json` on next startup
**New localization category:** Add `.mo` filename to `LanguageModule.build_all_dictionaries()` categories dict in `language_module.py`, it auto-parses and caches on next language setup
**New settings:** Add property to `config.py`, read/write in `main.py:save_settings/__init__`, add UI control in `ui_manager.py:build_filters` or settings menu
**New view:** Add button in `ui_manager.py:setup_ui`, implement show_view logic in `ui_manager.py:show_view`, wire in `main.py`
**New deployment target:** Add to `build.py:copy_data_files()` exclusion logic or `build.py:_CRITICAL_JSON` list (for JSONs), or extend `build.py` with new packaging steps (e.g., new directories). EXE name is versioned automatically: `SM WoT Assistant vX.Y.Z.exe`
**New Firebase feature:** Add to `firebase_reporter.py` for analytics/reporting, `firebase_drawings.py` for cloud data sync, or create new `firebase_*.py` module following the REST API pattern (API key auth, `_rtdb_url()` path builder, `_put`/`_post` helpers; use `requests.put(data=b"null")` for deletions). Admin-side writes (builds, versions, prompts, popular_tanks) go through `admin_auth._rtdb_url_with_token()` with an ID token — client-side writes keep the API key only
**New website page:** Create `.html` file in `public/`, link from `public/index.html`, use Firebase RTDB REST API for dynamic data (same API key pattern as Python modules). All pages use English-only with `lang="en"`; no UA/EN toggle
**New version scheme:** Edit `VERSION`, update `config.load_version()` format handling if needed
**New admin capability:** Add to `admin_app.py` (class `AdminApp`), extend `admin_build_generator.py` for generation modes, add translations to `_TR_EN` dict; rebuild via `python build_admin.py` (onedir into `dist/SM WoT Assistant Admin/`)
**Dead code:** A new `.py` without importers (verify with grep) goes straight to `_archive/scripts/` — do not leave orphaned modules at root
