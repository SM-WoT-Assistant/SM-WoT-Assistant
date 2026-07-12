# Architecture

## Pattern Overview

**Overall:** Monolithic tkinter application with manager delegation

**Key Characteristics:**
- Single `WotAssistantHQ` class in `main.py` serves as the central hub that owns all manager instances; `active_view=""` at startup (no view loaded initially)
- Each manager (`WindowManager`, `UIManager`, `DataManager`, `LocaleManager`, `MapManager`, `MapRenderer`, `HelpManager`) encapsulates a specific subsystem
- Three distinct views (`maps`, `stats`, `ai_stats`) share the same root window via pack/unpack switching
- Game integration occurs through python.log tailing (`LogWatcher`) and WinAPI window manipulation (`WindowManager`)
- AI-powered tank build generation uses Google Gemini via a WebView browser (`ai_webview_gui.py`)

## Layers

**Presentation Layer:**
- Purpose: Render maps, UI controls, drawing overlays, AI build results
- Location: `main.py`, `ui_manager.py`, `painter.py`, `painting_palette.py`, `dialog_utils.py`, `map_renderer.py`, `help_system.py`, `ai_webview_gui.py`, `tray_icon.py`, `firebase_groups.py`, `firebase_identity.py`
- Contains: tkinter widgets, Canvas drawing, floating tool palettes, dark-themed dialog utilities (`dialog_utils.make_custom_dialog` creates `overrideredirect(True)` Toplevel with dark header + ✕ close button, `dialog_utils.dark_messagebox`, `dark_confirmbox`, `dark_promptbox` all use `make_custom_dialog` + `_DragHelper`), help overlay (Toplevel grid of Label widgets, not canvas text)
- All UI text uses translation keys via `app.t('ui', key)` — fully translated for any game client language (11 supported)
- Depends on: Data Layer, tkinter, Pillow (PIL), custom TTF fonts (`xvmsymbol.ttf`, `fontawesome-webfont.ttf`)
- Used by: End user

**Application Logic Layer:**
- Purpose: Orchestrate views, handle hotkeys, coordinate battle detection, manage AI flows
- Location: `main.py` (class `WotAssistantHQ`), `window_manager.py`, `log_reader.py`, `tactics_manager.py`, `service_messages.py`, `tray_icon.py`
- Contains: WotAssistantHQ, WindowManager, LogWatcher, TrayIcon (pure ctypes WinAPI system tray icon via `Shell_NotifyIconW`), tactic import/export (`import_unified` auto-detects single-map vs all-maps format), lock/unlock button (F8 duplicate on top_bar) that enables window drag/resize/opacity/contrast hotkeys without Ctrl, service messages periodic flush every 300s via `_periodic_flush_service_messages()`; `root.attributes("-topmost", True)` at startup ensures root stays on top; `_restore_button` floating Toplevel with logo + "EXPAND" shown after minimize-to-tray; `active_view=""` at startup defers all view loading; window position clamped to screen bounds on `initialize_window()`
- Integrates `language_module.setup()` at startup for game language detection and `LocaleManager` for runtime translation
- Depends on: Presentation Layer managers, Data Layer, `keyboard` library, WinAPI via `ctypes`
- Used by: Presentation Layer

**AI Pipeline Layer:**
- Purpose: Generate tank build prompts, parse AI responses, cache results, normalize equipment/crew data
- Location: `stats_ai.py`, `ai_engine.py`, `ai_normalizer.py`, `ai_assistant.py`, `generate_prompt_v2.py`, `stats_data.py`, `ai_webview_gui.py`, `ai_scraper.py`, `service_messages.py`
- Contains: StatsAI class, prompt generator (asks for tiers 8-11 popular tanks), AI response normalizer, cache management (30-day expiry for both popular_tanks_cache and ai_builds_cache via shared `_is_cache_expired`), equipment/consumable/skill mappings
- Depends on: Data Layer (tank_db.json, crew_builds.json, game_entities_english.json), Gemini API via visible PyQt6 QWebEngineView browser launched as subprocess (`python main.py --ai-webview`), file-based response capture (`wot_ai_response.txt`) with stdout fallback
- Used by: Presentation Layer (SETUP view)

**Data Layer:**
- Purpose: Load/save JSON, manage tank database, extract data from game client, provide translations
- Location: `data_manager.py`, `config.py`, `locale_manager.py`, `translations.py`, `map_manager.py`, `map_extractor.py`, `tank_extractor.py`, `wot_decoder.py`, `decode_xml.py`, `language_module.py`, `ui_translator.py`
- Contains: DataManager, MapExtractor, TankExtractor, WotXmlDecoder, LocaleManager, LanguageModule, UI Translator, configuration constants, version loader (`config.load_version()`), dual-path storage (`config.BUNDLE_DIR` for read-only bundled assets, `config.USER_DATA_DIR` for writable user data in `%APPDATA%/SM WoT Assistant`)
- Depends on: Game client files (res/packages/*.pkg, version.xml, python.log, res/text/lc_messages/*.mo), filesystem, `deep_translator` (Google Translate)
- Used by: Application Logic Layer, AI Pipeline Layer

**External Integration Layer:**
- Purpose: Interact with the World of Tanks game client and its files, package the application for distribution, provide a standalone launcher for auto-update
- Location: `log_reader.py` (python.log tailing), `window_manager.py` (WinAPI window manipulation), `tray_icon.py` (system tray icon via `Shell_NotifyIconW`), `map_extractor.py` (client .pkg extraction), `tank_extractor.py` (client XML reading), `build_crew_builds.py`, `extract_equipment_loadouts.py`, `build.py` (PyInstaller packaging, always creates GitHub release — no `--release` flag, `gh` CLI required), `launcher.py` (standalone update-checker built as `--onefile`, uses `import unicodedata` for PyInstaller compatibility), `wot_assistant.spec` (PyInstaller spec for main app)
- Contains: LogWatcher, WinAPI wrappers (window manipulation + system tray icon), TrayIcon class (message-only window + `after()` polling at 250ms), game client decoders, PyInstaller build pipeline, `Launcher` class with splash UI that checks RTDB for updates and launches main app
- Depends on: World of Tanks game client, `ctypes`, `keyboard`, `mouse`, PyInstaller, GitHub CLI (`gh`) — required, NSIS (`makensis.exe`) — required
- Used by: Application Logic Layer (launcher runs before main)

**Firebase / Cloud Layer:**
- Purpose: Local identity (nickname + 4-digit PIN with RTDB-synced login), error reporting, usage pings, auto-update checks, drawing publication/sync via Firebase Realtime Database REST API, community scheme download in-app, group system for private scheme sharing
- Location: `firebase_identity.py`, `firebase_reporter.py`, `firebase_drawings.py`, `firebase_groups.py`, `public/` (Firebase Hosting static website), `firebase.json`, `.firebaserc`, `database.rules.json`
- Contains: **Identity system** (`firebase_identity.py`) — nickname + 4-digit PIN stored as SHA-256 hash in `identity.json` under `config.USER_DATA_DIR`; `register(nickname, pin)` creates identity and syncs to RTDB `users/{user_id}` node; `login(nickname, pin)` verifies credentials against RTDB; `connect()` does local-only verification using saved credentials; `disconnect()` sets `connected=False`; `check_nickname_available(nickname)` queries RTDB for duplicate nicknames (debounced 400ms in UI); `change_nickname(new_nickname, pin)` and `change_pin(old_pin, new_pin)` for profile edits; `is_registered()`, `is_connected()`, `get_nickname()`, `get_user_id()` for status queries; **RTDB REST API client** (PUT/POST/GET with Firebase API key auth and `_rtdb_url()` path builder), error reporting with stack traces, version ping/check via `versions/` node with `_pick_latest()` sorting by release_date then semver, drawing publish/load/delete via `schemes/` node, `get_all_schemes()` synchronous fetch for in-app community scheme browser, auto-update dialog in `main.py` and `launcher.py`; **Group system** (`firebase_groups.py`) — `create_group()` creates a private group in RTDB `groups/{group_id}` with a 6-char invite code, `join_group()` finds a group by invite code and adds the user to `groups/{gid}/members/{uid}` as `member` role (creator becomes `officer`), `leave_group()` removes the user from group members and `user_groups/{uid}`, `get_user_groups()` returns all groups the user belongs to (always includes `PUBLIC_GROUP_ID="public"`), `get_group_info()` fetches group metadata, `publish_to_group()` writes a scheme to `groups/{gid}/schemes/{drawing_id}`, `get_group_schemes()` fetches all schemes for a group with in-memory cache (`_group_schemes_cache`), `get_group_schemes_meta()` returns lightweight `{drawing_id: {updated_at, element_count, map_id}}` for sync polling, `update_group_scheme()` updates an existing scheme in-place (upsert), `get_combined_schemes()` aggregates public schemes + all user's group schemes, `import_between_groups()` copies a scheme from one group to another, `get_user_role_in_group()` returns `officer`/`member`/`None`, `delete_group_scheme()` removes a scheme from a group via PUT null, `invalidate_group_schemes_cache()` clears in-memory cache for a specific group or all groups, `refresh_group_membership()` checks RTDB for stale memberships and updates local cache. RTDB structure: `groups/{group_id}/{name, description, invite_code, creator_user_id, creator_nickname, created_at, members/{uid}, schemes/{drawing_id}}`, `user_groups/{uid}/{gid}: {role, name}`. Database indexed on `groups/invite_code` and `groups/created_at` (`database.rules.json`). Group schemes cached to disk via `config.GROUP_CACHE_FILE` (`group_schemes_cache.json` in `USER_DATA_DIR`)
- Depends on: `requests`, Firebase RTDB (`europe-west1`), Firebase Hosting, `config.USER_DATA_DIR`
- Used by: Application Logic Layer (`main.py` startup, quit, auto-update, group sync polling), External Integration Layer (`launcher.py` pre-startup update check), Presentation Layer (`ui_manager.py` identity bar + registration dialog with nickname availability check and debounced validation, login/connect/disconnect/edit buttons, group selector + token button with invite code copy; `painting_palette.py` group management dialogs Create/Join/Manage with scheme delete and regenerate code, linked schemes list with hide/show per scheme, group-specific publish/download with Link (sync) option for group schemes, multi-select download with search and Source filters)

## Data Flow

**Startup Flow:**
1. **[Launcher path]** When distributed, `launcher.py` runs first as a standalone `--onefile` executable — shows its own splash, checks RTDB for updates synchronously, downloads and installs the latest version if found, then launches the main app with `--splash-geometry=` to preserve splash position
2. **[Direct path]** User double-clicks main EXE or runs `python main.py` — the app may receive `--splash-geometry=` from the launcher to position the splash window consistently
3. Single-instance check via `CreateMutexW("SM_WoT_Assistant_SingleInstance")` — exits if another instance is running
4. Load settings from `settings.json` — `data_manager.py`
5. Auto-detect WoT path and python.log — `main.py:_auto_detect_log_path`, `map_manager.py:auto_detect_wot_path`
6. Detect game language via `language_module.setup()` — reads `game_info.xml`, parses `.mo` files, rebuilds locale caches if language changed
7. Check game version, extract/update maps and tank data — `map_manager.py:check_game_version` → `map_extractor.py:MapExtractor`, `tank_extractor.py:TankExtractor`
8. Start log watcher for battle detection — `log_reader.py:LogWatcher.start`
9. Load map list for current view — `map_manager.py:load_map_list`
10. If needed, launch AI browser to refresh tank build data — `stats_ai.py:StatsAI.launch_ai_browser`
11. **Update check preemption:** During splash display (step 4-6), a synchronous update check may preempt the normal startup flow — the splash displays update buttons instead of proceeding to the main UI (see Auto-Update Flow)
12. **Startup service flush:** 2 seconds after startup completes, `_startup_flush_service()` calls `firebase_reporter.try_flush_service_messages()`, then starts `_periodic_flush_service_messages()` every 300 seconds (5 min) for periodic delivery of queued service events

**Battle Detection Flow:**
1. `log_reader.py:LogWatcher._run` tails `python.log` with regex patterns (`arena_re`, `battle_space_re`, `vehicle_re`, etc.)
2. On map detection → `main.py:on_battle_detected` → auto-sync map selector and battle mode filters
3. On countdown start → `main.py:on_battle_countdown_started` → optionally switch to battle mode (auto-battle)
4. On vehicle detection → `main.py:on_vehicle_detected` → auto-filter vehicle class
5. On battle end → `main.py:on_battle_ended` → optionally return to editor with last battle's map

**Map Rendering Flow:**
1. User selects map from dropdown → `ui_manager.py:show_view('maps')` → `map_manager.py:load_map_list` — unified map list from `extracted_maps/map_dictionary.json` for both TACTIC and MAPS modes; TACTIC mode additionally filters via `_tactic_image_exists()` to only show maps with images in `maps/`
2. `map_renderer.py:MapRenderer.load_and_resize_map` loads image (`extracted_maps/*.png` for MAPS mode, `maps/<folder>/map.webp` via `_resolve_tactic_folder()` for TACTIC mode)
3. `map_renderer.py:MapRenderer.draw_grid` overlays 10×10 coordinate grid with A-J/0-9 labels; `draw_frame()` renders a 20px dark border around the map
4. `map_renderer.py:MapRenderer.draw_arena_bases` renders spawn/base areas from `map_data.json` boundingBox
5. `painter.py:MapPainter.redraw` renders user drawings (markers, arrows, text, tree icons) on separate overlay canvas (`_po_canvas` in a dedicated `_po_win` Toplevel), with scale-aware rendering and edit-mode selection rectangle. Class icons (`_draw_class_icons`) are filtered against active checkbox state (`app.selected_classes`) — only checked classes render. Battle mode filter labels (Standard/Encounter/Assault/Onslaught) are resolved from game client `.mo` files via `language_module.get_lang_module()`, with Google Translate fallback via `app.t('ui', ...)` when `.mo` lookup fails. **Group scheme rendering:** `redraw()` also renders group-linked schemes from `painter._group_schemes` dict — schemes whose `group_id` matches `app.active_group_id` are overlaid alongside local drawings. Local drawings are filtered by `_source` field: if `active_group_id` is not `"public"`, only local objects with matching `_source` are shown; otherwise only objects with no `_source` or `_source == "public"` are shown. Group schemes are rendered as read-only overlay — they cannot be edited through the palette. `map_manager.py:load_map_list()` additionally filters the map list by active group's available schemes when a non-Public group is selected — only maps that have at least one scheme in the group appear in the dropdown
6. Overlay canvas (`_po_canvas`) uses `-transparentcolor=#010101` for independent opacity control; events bound to both main canvas and overlay via `painter.py:bind_events_to()`. Overlay windowed via separate `_po_win` Toplevel with `.transient()`, `Unmap`/`Map` bindings for ghost-window prevention, and `_po_sync_timer` (500ms interval) for position-only sync. `_on_root_show()` guards against premature overlay show via `_startup_complete` flag — only shows after startup finishes. `_hidden_by_f10` guard blocks overlay show/restore/lift while the app is minimized to system tray. `root.attributes("-topmost", True)` at startup keeps root on top; overlay Z-order maintained via specific lift calls (two safe locations in startup flow). ComboLBox dropdown visibility preserved via two-step `SetWindowPos` (HWND_TOPMOST → HWND_TOP) + withdraw approach in `postcommand`, with HWND caching and pre-find at startup (`main.py`). `lift()` only on explicit show/deiconify: `_on_root_show()`, `_handle_tab_switch()`, `_handle_root_focus_in()`
7. Property editing flows through `DrawingPalette` (`painting_palette.py`) — a floating non-modal palette with toolbar (marker + arrow + brush + XVMSymbol icons + tree `chr(0xF18C)` FontAwesome — arrow uses smaller FontAwesome `chr(0xF062)` at 11pt, brush uses FontAwesome `chr(0xF040)` at 13pt, marker at 16pt), arrow start/end checkboxes (shown only when editing a brush object), two publish rows (Publish/Publish All), two save/import rows (Save/Save All/Import/Download), mode checkboxes with names from game client `.mo` (Standard/Encounter/Assault/Onslaught, Google fallback via `app.t()`), class checkboxes (LT/MT/HT/TD/SPG — always English), text entry, 12-color history color picker with `_default_colors` array, delete button, and status bar. Live-syncs changes to the selected object without modal dialogs. Deselects on click-away. Auto-deactivates tool after object creation. Ctrl+Z undo via creation + deletion history stack (undoes element creation and deletion), Ctrl+↑/↓ resize in edit mode (150ms debounce). Uses `transient(self.app.root)` + `lift(aboveThis=...)` for stacking (no `-topmost`). Communicates with `dialog_utils` (`dark_messagebox`, `dark_confirmbox`, `dark_promptbox`) for all dialogs. Community scheme download via `_show_download_dialog()` with map/author/Source filters and preview (uses `overrideredirect(True)` + `_DragHelper` for draggable borderless preview). **Group Management UI** (`_group_mgmt_frame`) — a section below the status bar with Create/Join/Manage buttons, all opening `overrideredirect(True)` custom Toplevel dialogs with dark header (`_make_dark_header`) + `_DragHelper`. Create dialog calls `firebase_groups.create_group()` with name + description. Join dialog calls `firebase_groups.join_group()` with 6-char invite code. Manage dialog shows invite code (with Copy), member list with kick, Regenerate Code, Leave Group. **Group-aware publish:** when `active_group_id != "public"`, Publish calls `_publish_to_group()` / `_publish_all_to_group()` using `firebase_groups.publish_to_group()`. **Group-aware download:** `_download_populate()` aggregates public + group schemes via `firebase_groups.get_combined_schemes()`; download dialog adds Source filter column; group schemes offer "Link (sync)" option storing in `painter._group_schemes` for auto-sync

**AI Tank Build Flow (SETUP view):**
1. User searches/selects a tank → `stats_ai.py:StatsAI._on_tank_select`
2. Check `ai_builds_cache.json` — if fresh (30-day expiry via `_is_cache_expired(updated, max_days=30)`), render from cache
3. If stale or missing → `generate_prompt_v2.py` builds Gemini prompt with tank data from `tank_slots_full.json`, `crew_builds.json`, `game_entities_english.json`
4. Prompt sent to Gemini via `ai_webview_gui.py` launched as subprocess (`python main.py --ai-webview`). Browser starts minimized (`showMinimized()`) with taskbar icon hidden. File-based capture to `wot_ai_response.txt` as primary mechanism, with stdout fallback; `RESPONSE_READY` sentinel marks completion
5. Response parsed and normalized by `ai_normalizer.py`
6. Result cached to `ai_builds_cache.json` and rendered as composite icons

**Auto-Update Flow:**
1. **[Launcher path]** `launcher.py` is the preferred update path — it auto-detects the installed version via `_detect_installed_version()` (regex on EXE filenames in install dir), then checks RTDB synchronously before launching the main app. If a newer version is found, it downloads the setup to `%TEMP%` with a progress bar on its splash, runs the NSIS installer silently (`/S /NCRC`), cleans up old versioned EXEs from `$LOCALAPPDATA\\SM WoT Assistant` (installer.nsi deletes `SM WoT Assistant v*.exe` before copy), releases the single-instance mutex, spawns `SM WoT Assistant Launcher.exe --skip-splash` (which relaunches the main EXE via `_find_main_exe()`), and exits. The splash stays visible through the entire process with animated dots (`_start_dot_animation` / `_animate_dots`, 500ms interval). On success, it waits 3 seconds showing "Updated to vX.Y.Z" then launches the launcher with `--skip-splash`
2. **[In-app path]** On startup → `firebase_reporter.ping_version_async()` sends current version to RTDB (`installations/` node)
3. **Splash-screen path:** During splash display, `_start_startup_checks()` calls `firebase_reporter.check_for_updates_sync()` synchronously. If a newer version is found, `_show_splash_update()` renders "New version vX.Y.Z available!" with "UPDATE NOW" / "LATER" buttons directly on the splash canvas. Clicking "UPDATE NOW" triggers `_splash_download_thread()` which downloads the setup to `%TEMP%`, runs NSIS installer silently (`/S /NCRC`), releases the single-instance mutex (`_update_mutex`), spawns the new versioned EXE (`SM WoT Assistant vX.Y.Z.exe` from `$LOCALAPPDATA\\SM WoT Assistant`), and exits the old process — all while the splash remains visible with animated dots (`_splash_animate_dots`, 500ms interval). Clicking "LATER" dismisses splash and continues to main UI
4. **Main-UI path:** If no update was found during splash (or splash is disabled), `_check_for_app_updates()` calls `firebase_reporter.check_for_updates()` asynchronously after the main UI is shown. A modal update dialog with download progress bar is presented; the download-and-install flow is identical to the splash path
5. Latest version is determined via `_pick_latest()` which selects the version with the highest `release_date` from the RTDB `versions/` node, using semver as tiebreaker when dates match. The `versions/latest` pointer (with `release_date: "9999-12-31"`) always points to the canonical latest. `compare_versions()` compares semver tuples to decide if update is needed
6. On build → `build.py:write_version_to_rtdb()` publishes version metadata (version, release_date, download_url, build_size) to RTDB `versions/{version}/` node and updates the `versions/latest` pointer. The `--date=YYYY-MM-DD` flag allows overriding the release_date. Every build is a release — `--release` flag removed, `gh` CLI required, and RTDB publish only happens after a successful GitHub release

**Drawing Publish/Download Flow:**
1. User clicks Publish (single map) or Publish All (all maps with drawings) from `DrawingPalette` → `painting_palette._publish()` or `_publish_all()` → `firebase_drawings.publish_drawing()` serializes drawing elements, map info, author identity → PUT to RTDB `schemes/{drawing_id}`. Publish uses English map names via `config.MAP_NAMES_EN`. Description is auto-translated to English via `deep_translator` before upload. Duplicate detection prevents publishing the same map+comment combination. **Group publish:** when `active_group_id` is not `"public"`, publish goes to `groups/{gid}/schemes/{drawing_id}` via `firebase_groups.publish_to_group()` instead of public `schemes/`. The publish action label reads "Publish to group \"{group_name}\":" in the choice inline
2. `public/schemes.html` (Firebase Hosting) reads from RTDB `schemes/` node, renders community schemes table with map/author filters. Upload modal removed — publishing is now app-only. Help text updated to reflect in-app flow. Shows "All Maps" as a special entry. Group schemes are NOT visible on the website — they remain private to group members
3. `public/drawings.html` renders gallery with download links
4. Application can download published schemes in-app: `DrawingPalette._show_download_dialog()` → `firebase_groups.get_combined_schemes()` (aggregates public schemes from `firebase_drawings.get_all_schemes()` + group schemes from `firebase_groups.get_group_schemes()` for each group the user belongs to) → `_build_download_ui()` renders a 580×780 palette with map/author filters + search field (StringVar with trace, filters across map_name/author/comment/source_name) + multi-select checkboxes (click on tree column toggles ☐/☑) → `_handle_download_result()` with Replace/Add/Save-to-PC/Link (sync) choice → `_preview_scheme()` renders elements on a map preview Toplevel. The "Link (sync)" option is only shown for group schemes — it stores the scheme in `painter._group_schemes` for auto-sync via the group sync polling mechanism, bypassing local drawing storage. **Linked schemes list** (`_refresh_linked_schemes_list`) in palette's group management frame shows all linked group schemes with hide/show checkboxes per scheme (stored in `painter._hidden_download_schemes` set, persisted to group cache). Sync polling (every 60s) detects deleted schemes and removes them from cache

**Localization Flow:**
1. On startup → `language_module.setup()` detects game language from `game_info.xml` → rebuilds dictionaries only if language changed or cache missing. On rebuild, also regenerates `game_entities_english.json` and `extracted_maps/map_dictionary.json` from the parsed `.mo` data
2. `LanguageModule.build_all_dictionaries()` parses all `.mo` files from `res/text/lc_messages/` into per-category JSON caches under `config.USER_DATA_DIR/localization/<lang>/` (accepts all 11 game client languages, no hardcoded list). After building, `setup()` stores a global `_lang_module` reference via `get_lang_module()` for lazy access by other modules (battle mode names, map names, TTH labels)
3. `LanguageModule.export_locale_json()` exports combined locale JSON to `public/locale/<lang>.json` for website consumption and pushes to Firebase RTDB via `firebase_reporter.push_locale()`
4. `regenerate_map_dictionary(lm)` (`language_module.py:385`) regenerates `extracted_maps/map_dictionary.json` from `arenas.mo` parsed data — filters valid entries (excludes empty/placeholder), preserves existing keys not found in current `.mo`. Called only on language change during `setup()`
5. `LocaleManager.t_ui()` provides dynamic UI translation:
   - English `translations.py` is the authoritative source
   - On-demand Google Translate via `ui_translator.py` with caching in `locales.json`
   - Re-translates when: cache missing, cached value is still English (translation failed), or English source changed since last translation — compares current English against stored `en_snapshot`
   - Rejects ASCII-only cached translations (prevents bad translations like "BATLE MODE")
   - Protects placeholders (`{path}`) and symbols (`->`) from translation
6. `LocaleManager.t_map` resolves map names through: `custom_names.json` → `extractor_names` (from `map_dictionary.json`) → `locales.json` → `config.TECH_MAPS_STAGING`
7. `ui_translator.py` translates app-specific UI text at runtime using Google Translate with placeholder shielding for keyboard shortcuts (F1-F24, Ctrl, Alt, Shift, LMB/RMB, arrows, etc.), symbols, and numbers; caches translations per-language in `config.USER_DATA_DIR/localization/<lang>/ui_cache.json`
8. On game version change → `map_manager.py:check_game_version` calls `language_module.check_for_language_change()` to rebuild if game language shifted
9. Splash screen displays detected language (e.g., "Language: DE", "Language: UK", "Language: EN")

**Memory to Persistence (Cross-Session):**
1. Tactical drawings → save on every edit → `data_manager.py:save_drawings` → `map_drawings.json`; bulk export/import via `tactics_manager.py:export_all_tactics()` / `import_all_tactics()` with Replace/Merge choice dialog; unified import via `tactics_manager.import_unified()` auto-detects single-map vs all-maps format
2. AI build cache → save after each successful AI response → `ai_builds_cache.json`
3. Settings → save on window changes/close → `settings.json`
4. Identity → save on registration/PIN change → `identity.json` in `config.USER_DATA_DIR`; `register()` also syncs to RTDB `users/{user_id}`; `login()` verifies credentials against RTDB
5. Service events → `service_messages.json` queue for future server delivery

## Key Abstractions

**WotAssistantHQ:**
- Purpose: Central application hub owning all state and manager instances
- Location: `main.py` (class WotAssistantHQ)
- Constructor: `__init__(self, root, splash_geometry=None)` — accepts optional `splash_geometry` passed by the launcher to position the splash window consistently
- Pattern: God object with manager delegation — owns settings, tank database, map state, view routing, hotkey bindings, system tray icon, group state
- Group state fields: `active_group_id` (default `"public"`), `_cached_groups` (dict of `{group_id: {role, name}}` synced from RTDB), `_group_id_map` (label → group_id lookup), `_sync_running` (flag for group sync polling)
- Restore button: `_restore_button` (Toplevel) and `_restore_drag_start` dict — created by `_show_restore_button()` after `_minimize_to_tray()`, destroyed by `_hide_restore_button()`. Shows app logo (64×64 from `icon.ico`) + "EXPAND" label + FontAwesome down-arrow icon. Draggable; click with no significant drag triggers `_restore_from_tray()`
- Key methods: `export_all_tactics()`, `import_all_tactics()` delegate to `tactics_manager.py` for bulk import/export; `_splash_animate_dots()` renders animated loading dots on splash during updates (500ms interval); `toggle_visibility()` / `_minimize_to_tray()` / `_restore_from_tray()` implement F10 minimize-to-system-tray (creates `TrayIcon` on hide, calls `_show_restore_button()` to show floating restore button; removes `TrayIcon` on `_restore_from_tray()` which also calls `_hide_restore_button()`; uses `_hidden_by_f10` guard flag to block all overlay-show paths while hidden; `_minimize_to_tray` also calls `_stop_group_sync()` to pause polling while hidden; `_restore_from_tray` calls `_start_group_sync()` if view is maps and group is non-Public); `_show_restore_button()` creates an `overrideredirect(True)` Toplevel with logo + "EXPAND" + FontAwesome arrow icon, draggable, click-to-restore; `_hide_restore_button()` destroys the floating restore button; `toggle_formatting_mode()` (F8 / Lock button) controls `format_mode_enabled` — when enabled, arrow keys (opacity), Shift+Up/Down (contrast), and window drag work without Ctrl; hotkey `e` changed to `tab` for battle/editor toggle; no-Ctrl hotkeys (`up`, `down`, `left`, `right`, `shift+up`, `shift+down`) bound with `suppress=False` and guarded by `format_mode_enabled`
- Group sync methods: `_start_group_sync()` starts 60-second polling cycle for the active group; `_stop_group_sync()` stops polling; `_sync_schedule()` schedules `_sync_cycle()` via `root.after(60000)`; `_sync_cycle()` calls `firebase_groups.get_group_schemes_meta(gid)` and compares `updated_at` against local `_synced_at` stamps — if remote is newer, triggers `_show_group_sync_notification()` with pending updates; `_show_group_sync_notification()` renders an `overrideredirect(True)` Toplevel with custom dark header + `_DragHelper` + "Update" / "Later" buttons — "Update" downloads the changed schemes from RTDB into `painter._group_schemes`, updates `_synced_at`, calls `painter.redraw()`, and saves to group cache; "Later" dismisses without update
- Group cache methods: `_load_group_schemes_from_cache()` reads `config.GROUP_CACHE_FILE` at startup and populates `painter._group_schemes` and `painter._scheme_downloaded_at`; `_save_group_schemes_to_cache()` writes the same to disk on quit and after group scheme updates

**Manager Pattern:**
- Purpose: Encapsulate subsystem responsibilities behind a single class receiving `app` reference
- Location: `window_manager.py`, `ui_manager.py`, `data_manager.py`, `locale_manager.py`, `map_manager.py`, `map_renderer.py`, `help_system.py`, `dialog_utils.py`
- Pattern: Each Manager receives `app` (WotAssistantHQ) in constructor, accesses shared state through `self.app.*`, and exposes domain-specific methods. `dialog_utils.py` provides stateless dark-themed dialog utilities (`make_custom_dialog` creates `overrideredirect(True)` Toplevel with dark header + ✕ close button, `dark_messagebox`, `dark_confirmbox`, `dark_promptbox`, `_set_dark_title_bar`, `_center_on_root`, `_DragHelper`). `make_custom_dialog` + `_DragHelper` replaces manual Toplevel construction throughout the app (e.g., `main.py:ask_clear_confirm`, all dialog utils functions). `firebase_groups.py` provides module-level function-based API (not class-based) with in-memory scheme cache via module-level `_group_schemes_cache` dict

**LogWatcher:**
- Purpose: Background thread that tails WoT's `python.log` and fires callbacks on battle events
- Location: `log_reader.py`
- Pattern: Regex-based log parsing in a daemon thread with callbacks for arena detection, countdown, vehicle, minimap, hangar return

**MapPainter:**
- Purpose: Canvas-based drawing system for tactical markers, arrows, brush (freehand), text, and tree icons, plus read-only group-linked scheme overlay
- Location: `painter.py`
- Pattern: Stateful drawing list persisted via `DataManager`, creation history stack + deletion history stack for Ctrl+Z undo (undo both create and delete), per-map/per-mode filtering. `_hidden_download_schemes` set tracks linked group schemes hidden by user (toggled via checkboxes in palette's linked schemes list). `_scheme_downloaded_at` dict persists download timestamps per scheme for sync comparison Supports three marker-like types: `marker` (circle+arrow with snapping to existing markers), `arrow` (line with arrow only, no circle), and `brush` (freehand polyline with min 10px point spacing, arrow start/end checkboxes, arrow start/end/ both options). All painting renders on a dedicated overlay canvas (`_po_canvas`) inside a separate `_po_win` Toplevel for independent opacity control. Binds events to multiple canvases via `bind_events_to()`. Supports right-click context menu for edit/delete with confirmation dialog (`dialog_utils.dark_confirmbox`). Edit mode renders a yellow dashed selection rectangle around the edited element. Resize of selected elements via `resize_selected()` with keyboard hooks (Ctrl+↑/↓, 150ms debounce). Class icons rendered by `_draw_class_icons` are filtered against active checkboxes (`app.selected_classes`). Delegates property editing to `DrawingPalette` (`painting_palette.py`) — a floating non-modal palette with toolbar (marker, arrow, brush, XVMSymbol class icons, tree FontAwesome icon, 6 more tactical icons), mode/class checkboxes, text entry, 12-color picker, Publish/Publish All/Save/Save All/Import/Download buttons, delete button, arrow start/end checkboxes for brush editing, and status bar showing editing type. Community scheme browser with map/author/Source filters and preview dialog (uses `overrideredirect(True)` + `_DragHelper` instead of standard title bar). **Group scheme overlay:** `painter.py` maintains `_group_schemes` dict `{drawing_id: {map_id, elements, group_id, updated_at, _synced_at}}` and `_scheme_downloaded_at` dict `{drawing_id: timestamp}`. Redraw renders group-linked schemes alongside local drawings, filtered by `active_group_id`. Group schemes are read-only — they cannot be edited or deleted through the palette. Local drawings carry a `_source` field that controls visibility per group context

**StatsAI:**
- Purpose: AI-powered tank build browser with search, filtering, composite icon rendering, and Gemini integration
- Location: `stats_ai.py`
- Pattern: tkinter Treeview + WebView browser, multi-level disk cache with expiry, equipment/crew/consumable TTH icon rendering

## Entry Points

**Application Entry (Main App):**
- Location: `main.py` (lines 1568-1595)
- Triggers: User double-clicks executable or runs `python main.py`
- Responsibilities: Call `multiprocessing.freeze_support()`, `os.chdir(config.BASE_DIR)` for consistent CWD, seed DEFAULT_FILES to AppData on first launch, detect `--ai-webview` CLI flag to route to AI browser, detect `--splash-geometry=` CLI flag (passed by launcher to preserve splash position), initialize tkinter root with version title, create WotAssistantHQ with optional `splash_geometry` parameter, start mainloop. `active_view=""` at startup — no view is loaded until user explicitly switches

**Application Entry (Launcher):**
- Location: `launcher.py`
- Triggers: Installed shortcut or `python launcher.py`
- Responsibilities: Auto-detect installed version via `_detect_installed_version()` (regex on EXE filenames in install dir). If `--skip-splash` CLI flag is present, directly find and launch the main EXE via `_find_main_exe()` and exit immediately. Otherwise show a lightweight Splash window (450×350), check RTDB for updates synchronously (`check_for_updates_sync()`), download and install if newer version found with progress bar and animated dots (`_start_dot_animation`/`_animate_dots`, 500ms interval), clean old versioned EXEs from install dir, launch `SM WoT Assistant Launcher.exe --skip-splash` to preserve splash position and restart cleanly, then exit. Built as standalone `--onefile` PyInstaller binary distributed alongside the main app

**CLI Entry (AI WebView):**
- Location: `main.py` (lines 1583-1586)
- Triggers: `python main.py --ai-webview` (spawned by `stats_ai.py` as subprocess)
- Responsibilities: Bypass tkinter entirely, run `ai_webview_gui.main()` directly, exit after completion

**Build Entry:**
- Location: `build.py`
- Triggers: `python build.py [version]`
- Responsibilities: Update `VERSION` file if version arg given, run PyInstaller via `wot_assistant.spec` producing a onedir output (~5795 files, ~750 MB total), manually copy data files via `build.py:copy_data_files()` (workaround for PyInstaller 6.x DATA TOC bug), run NSIS to produce installer (~320 MB), create portable ZIP (~390 MB), optionally create GitHub release via `gh` CLI

**Map List Loading:**
- Location: `map_manager.py:load_map_list`
- Triggers: View switch to MAPS/TACTIC, battle mode filter change
- Responsibilities: Load map list from `extracted_maps/map_dictionary.json` (MAPS) or `map_list.json` (TACTIC), filter by gameplay type, populate dropdown

**AI Browser Launch:**
- Location: `stats_ai.py:StatsAI.launch_ai_browser`
- Triggers: Startup if cache expired, manual refresh
- Responsibilities: Spawn `ai_webview_gui.py` as subprocess (`python main.py --ai-webview`), which starts a minimized PyQt6 QWebEngineView browser, navigates to Google AI Mode chat, sends prompt, and captures response to `wot_ai_response.txt`

**Game Version Check:**
- Location: `map_manager.py:check_game_version`
- Triggers: Application startup
- Responsibilities: Compare stored version with `version.xml`, trigger map/tank extraction if changed, update crew/equipment databases, call `language_module.check_for_language_change()` to rebuild localization if game language shifted

**Website (Firebase Hosting):**
- Location: `public/` directory — served by Firebase Hosting at `sm-wot-assistant.web.app`
- Pages: `index.html` (English-only landing page with logo (2x), download button linking to the latest versioned GitHub release at `github.com/nkcgml-boop/SM-WoT-Assistant/releases`, features grid, community schemes promo, releases table from RTDB sorted by release_date → version), `schemes.html` (community tactical schemes browser with map filter, invite-code groups, PIN-based auth), `drawings.html` (drawing gallery), `admin.html` (admin dashboard with stats, schemes management, version management), `404.html`
- Language: All pages use `lang="en"` with no UA/EN toggle — browser language auto-detection only; class labels (LT/MT/HT/TD/SPG) remain English; `public/locale/uk.json` exists for locale export
- Data source: All dynamic data (schemes, versions, releases) read from Firebase RTDB via REST API with API key auth. Releases sorted server-side by `release_date` descending, with semver as tiebreaker
- Triggers: User visits website URL; `build.py` publishes version info on release

## Error Handling

**Strategy:** Defensive with graceful degradation — fallback chains in data loading, try/except around external calls, safety timeouts for AI operations

- `data_manager.py:load_tank_db` implements a 3-level fallback: `tank_db.json` → `tank_tth.json` (with estimated tiers) → `extracted_data/*.xml` files
- `map_manager.py:check_game_version` wraps the entire pipeline in try/except with threaded execution
- `main.py:_ai_safety_timeout` forces splash close after 60 seconds if AI browser hangs
- `log_reader.py:LogWatcher._run` silently catches exceptions and retries every 5 seconds
- `service_messages.py` logs internal failures to disk queue without user visibility
- `data_manager.py:load_json` returns empty defaults on any file error

## Cross-Cutting Concerns

**Version System:**
- `VERSION` file at project root contains a plaintext semver string (e.g., `1.0.2`)
- `config.load_version()` reads it with `"0.0.0"` fallback — all window titles use this function
- Version displayed in: main window (`main.py:1107`), splash (`main.py:1045`), editor watermark (`map_renderer.py:249`), help dialog (`help_system.py:49`), AI WebView (`ai_webview_gui.py:28`)
- `config.BASE_DIR` resolves to `sys.executable` directory when frozen (PyInstaller), or `__file__` directory in dev — all file paths are constructed relative to `BASE_DIR`
- `build.py` reads/writes `VERSION`, offers version bump + build + GitHub release commands
- `installer.nsi` version auto-synced via `build.py:update_nsi_version()` using regex on `!define PRODUCT_VERSION`

**Build &amp; Packaging:**
- `build.py` — 7-phase pipeline: (1) Pre-flight validation (semver, Python 3.12+PyInstaller, NSIS, gh CLI, critical source files, git status), (2) Clean dist/build, (3) PyInstaller onedir + manual `copy_data_files()` (workaround for PyInstaller 6.x DATA TOC bug — data files from Analysis not propagated to COLLECT), (4) NSIS installer via makensis, (5) Rename onedir to versioned directory (`dist/SM WoT Assistant vX.Y.Z/`) + rename generic EXE to versioned `SM WoT Assistant vX.Y.Z.exe`, (6) Build verification (versioned EXE, 6 critical JSONs, VERSION, fonts, directory counts), (7) Build manifest (`dist/build_manifest_vX.Y.Z.txt`)
- Every build is a release — `--release` flag removed. `gh` CLI and NSIS are required (pre-flight fails if missing). RTDB version publish only happens after successful GitHub release. `create_github_release()` returns `bool`
- `wot_assistant.spec` — PyInstaller spec with `_CRITICAL_JSON` list (6 core JSONs: `crew_builds.json`, `tank_db.json`, `tank_tth.json`, `game_entities_english.json`, `game_entities.json`, `tank_slots_full.json` — runtime caches excluded), fonts (`.ttf`), `.mo` localization files, `logo.png`, `maps/` subdirectories, `extracted_maps/` (excluding caches), `extracted_icons/` (all 8 subdirectories), `extracted_data/common/post_progression/` (field mod data). EXE name: `SM WoT Assistant`. Includes `COLLECT` step for onedir output
- `build.py:copy_data_files()` — manual file copy workaround for PyInstaller 6.x DATA TOC bug (data from Analysis not propagated to COLLECT). Uses exclusion-based glob: all root `*.json` except debug/temp/tomato/manifest files (`opencode.json`, `magic-context.jsonc`, `tomato_*.json`, `vehicle_slots_*.json`, etc.); also copies fonts, `.mo` files, `logo.png`, `maps/`, `extracted_maps/`, `extracted_icons/`, `extracted_data/common/post_progression/`. New JSON files automatically included without list updates
- Hidden imports: `keyboard`, `PIL._tkinter_finder`, `deep_translator`
- `console=False`, `upx=True`, icon from `logo.png`
- Output artifacts: `dist/SM WoT Assistant vX.Y.Z/` (versioned onedir containing `SM WoT Assistant vX.Y.Z.exe`, ~5795 files, ~750 MB), `dist/SM_WoT_Assistant_Setup_vX.Y.Z.exe` (NSIS installer, ~320 MB, lzma 42.4%), `dist/SM_WoT_Assistant_Portable_vX.Y.Z.zip` (portable ZIP, ~390 MB), `dist/build_manifest_vX.Y.Z.txt` (full file manifest)
- `launcher.py` is built as a separate `--onefile` PyInstaller binary (`launcher.exe` in installer.nsi) with `--collect-all unicodedata` (ensures unicodedata is bundled). It is not part of the main spec — built separately via `build.py:_build_launcher()` if the file exists. The launcher uses `tkinter` + `PIL` for splash rendering and `requests` for RTDB version checking, all DLLs extracted to `%TEMP%`
- Python 3.12 (C:\\Users\\PRO\\AppData\\Local\\Programs\\Python\\Python312) with PyInstaller 6.20.0 preferred — Python 3.14 has known DATA TOC bug
- NSIS: `C:\\Program Files (x86)\\NSIS\\makensis.exe` (auto-detected by `build.py:find_nsis()`). Installer uses `InstallDir "$LOCALAPPDATA\\SM WoT Assistant"` and `RequestExecutionLevel user` (no admin privileges required). Before copying files, installer deletes all `SM WoT Assistant v*.exe` from the install dir to clean up previous versions. Shortcuts are versioned (`SM WoT Assistant vX.Y.Z.lnk`) and cleaned via wildcard before re-creation
- Single-instance enforcement: `CreateMutexW("SM_WoT_Assistant_SingleInstance")` at startup (line 49 of `main.py`); if error 183 (already exists), the process exits immediately. The mutex is released before launching a new version after update
- `config.DEFAULT_FILES` seeds 6 files to AppData on first launch: settings.json, locales.json, map_drawings.json, service_messages.json, popular_tanks_cache.json, ai_builds_cache.json
- `build.py:write_version_to_rtdb()` — publishes version metadata (version, release_date, download_url, build_size) to Firebase RTDB `versions/{version}/` via REST API PUT after successful build; also writes `versions/latest` pointer with `release_date: "9999-12-31"` as sentinel; consumed by `main.py` auto-update check and `public/index.html` releases list
- Firebase Hosting: `public/` directory deployed via `firebase deploy --only hosting` (manual); serves English-only (`lang="en"`) static website with RTDB-backed dynamic content. Website shows "Download" button linking to GitHub releases; latest version label read from RTDB `versions/` node. Website releases table removed — no in-page releases listing

**Logging:** Print-based console output with bracketed tags (`[INIT]`, `[SYNC]`, `[AI Tank Build]`, `[SERVICE]`, `[BUILD]`). No structured logging framework.

**Caching:**
- `group_schemes_cache.json` — Group scheme data disk cache in `config.USER_DATA_DIR`; saved on quit and after group scheme updates, loaded at startup (`main.py:_load_group_schemes_from_cache` / `_save_group_schemes_to_cache`); also keeps `downloaded_at` timestamps per scheme for sync comparison
- `ai_builds_cache.json` — AI tank builds, 30-day expiry, fail_count tracking (`stats_ai.py`)
- `popular_tanks_cache.json` — Popular tanks list (tiers 8-11), 30-day expiry via shared `_is_cache_expired(updated, max_days=30)`, fail_count tracking; saves top 30 tanks (`stats_ai.py`)
- `ukrainian_map_names_cache.json` — Map name translations (`map_extractor.py`); map dictionary also regenerated from `arenas.mo` on language change via `language_module.regenerate_map_dictionary()`
- `locales.json` — Dynamic UI translation cache per language (Google Translate results, rejects ASCII-only entries)
- `config.USER_DATA_DIR/localization/<lang>/ui_cache.json` — Per-language UI translation cache from `ui_translator.py`
- `config.USER_DATA_DIR/localization/<lang>/` — Per-language `.mo` parsed dictionaries from `language_module.py`
- In-memory caches: composite icons, loadout icons, TTH icons, field mod pairs (`stats_ai.py:82-86`)

**Storage:** Flat JSON files at project root. No database engine. Key files: `settings.json`, `tank_db.json`, `tank_tth.json`, `crew_builds.json`, `equipment_loadouts.json`, `map_drawings.json`, `game_entities_english.json`. Identity stored in `config.USER_DATA_DIR/identity.json` (nickname, PIN hash, user_id, connected flag)

**Localization:** `translations.py` provides English-only authoritative source for all UI text (100+ keys). `LocaleManager` (`locale_manager.py`) resolves translations dynamically:
- `t_ui(key)` — on-demand Google Translate via `ui_translator.py` with caching in `locales.json`; rejects ASCII-only cached values; protects placeholders (`{path}`) and symbols (`->`)
- `t_map(eng)` — resolves map names through: `custom_names.json` → `extractor_names` (from `map_dictionary.json`) → `locales.json` → `config.TECH_MAPS_STAGING`
- `LanguageModule` (`language_module.py`) parses WoT client `.mo` files (gettext binary format) on startup or game version change, detects language via `game_info.xml` (accepts all 11 client languages, no hardcoded list), builds per-category JSON caches in `config.USER_DATA_DIR/localization/<lang>/`, exports `public/locale/<lang>.json` for the website, and pushes locale to Firebase RTDB. Maintains a module-level global `_lang_module` set by `setup()` and accessed via `get_lang_module()` for lazy lookups (battle mode names, map names, TTH labels) from other modules
- `UITranslator` (`ui_translator.py`) translates app UI text at runtime via Google Translate (`deep_translator`), shielding keyboard shortcuts (F1-F24, Ctrl, Alt, Shift, LMB/RMB, arrows, etc.), symbols, and numbers from translation; caches per-language in `config.USER_DATA_DIR/localization/<lang>/ui_cache.json`
