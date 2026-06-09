# Architecture

## Pattern Overview

**Overall:** Monolithic tkinter application with manager delegation

**Key Characteristics:**
- Single `WotAssistantHQ` class in `main.py` serves as the central hub that owns all manager instances
- Each manager (`WindowManager`, `UIManager`, `DataManager`, `LocaleManager`, `MapManager`, `MapRenderer`, `HelpManager`) encapsulates a specific subsystem
- Three distinct views (`maps`, `stats`, `ai_stats`) share the same root window via pack/unpack switching
- Game integration occurs through python.log tailing (`LogWatcher`) and WinAPI window manipulation (`WindowManager`)
- AI-powered tank build generation uses Google Gemini via a WebView browser (`ai_webview_gui.py`)

## Layers

**Presentation Layer:**
- Purpose: Render maps, UI controls, drawing overlays, AI build results
- Location: `main.py`, `ui_manager.py`, `painter.py`, `painting_palette.py`, `map_renderer.py`, `help_system.py`, `ai_webview_gui.py`
- Contains: tkinter widgets, Canvas drawing, floating tool palettes, help overlay (Toplevel grid of Label widgets, not canvas text)
- Depends on: Data Layer, tkinter, Pillow (PIL), custom TTF fonts (`xvmsymbol.ttf`, `fontawesome-webfont.ttf`)
- Used by: End user

**Application Logic Layer:**
- Purpose: Orchestrate views, handle hotkeys, coordinate battle detection, manage AI flows
- Location: `main.py` (class `WotAssistantHQ`), `window_manager.py`, `log_reader.py`, `tactics_manager.py`
- Contains: WotAssistantHQ, WindowManager, LogWatcher, tactic import/export
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
- Location: `data_manager.py`, `config.py`, `locale_manager.py`, `translations.py`, `map_manager.py`, `map_extractor.py`, `tank_extractor.py`, `wot_decoder.py`, `decode_xml.py`
- Contains: DataManager, MapExtractor, TankExtractor, WotXmlDecoder, LocaleManager, configuration constants, version loader (`config.load_version()`), `config.BASE_DIR` for portable path resolution
- Depends on: Game client files (res/packages/*.pkg, version.xml, python.log), filesystem
- Used by: Application Logic Layer, AI Pipeline Layer

**External Integration Layer:**
- Purpose: Interact with the World of Tanks game client and its files, package the application for distribution
- Location: `log_reader.py` (python.log tailing), `window_manager.py` (WinAPI window manipulation), `map_extractor.py` (client .pkg extraction), `tank_extractor.py` (client XML reading), `build_crew_builds.py`, `extract_equipment_loadouts.py`, `build.py` (PyInstaller packaging), `wot_assistant.spec` (PyInstaller spec)
- Contains: LogWatcher, WinAPI wrappers, game client decoders, PyInstaller build pipeline
- Depends on: World of Tanks game client, `ctypes`, `keyboard`, `mouse`, PyInstaller, GitHub CLI (`gh`)
- Used by: Application Logic Layer

## Data Flow

**Startup Flow:**
1. Load settings from `settings.json` — `data_manager.py`
2. Auto-detect WoT path and python.log — `main.py:_auto_detect_log_path`, `map_manager.py:auto_detect_wot_path`
3. Check game version, extract/update maps and tank data — `map_manager.py:check_game_version` → `map_extractor.py:MapExtractor`, `tank_extractor.py:TankExtractor`
4. Start log watcher for battle detection — `log_reader.py:LogWatcher.start`
5. Load map list for current view — `map_manager.py:load_map_list`
6. If needed, launch AI browser to refresh tank build data — `stats_ai.py:StatsAI.launch_ai_browser`

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
5. `painter.py:MapPainter.redraw` renders user drawings (markers, arrows, text, tree icons) on separate overlay canvas (`_po_canvas` in a dedicated `_po_win` Toplevel), with scale-aware rendering and edit-mode selection rectangle. Class icons (`_draw_class_icons`) are filtered against active checkbox state (`app.selected_classes`) — only checked classes render
6. Overlay canvas (`_po_canvas`) uses `-transparentcolor=#010101` for independent opacity control; events bound to both main canvas and overlay via `painter.py:bind_events_to()`. Overlay windowed via separate `_po_win` Toplevel with `.transient()`, `Unmap`/`Map` bindings for ghost-window prevention, and `_po_sync_timer` (500ms interval) for position sync. Topmost state managed on focus events
7. Property editing flows through `DrawingPalette` (`painting_palette.py`) — a floating non-modal palette with toolbar (marker + XVMSymbol icons + tree `chr(0xF18C)` FontAwesome), mode/class checkboxes, text entry, 5-color history color picker with `_custom_colors` stack, delete button, and status bar. Live-syncs changes to the selected object without modal dialogs. Deselects on click-away. Auto-deactivates tool after object creation. Ctrl+Z undo via creation history stack, Ctrl+↑/↓ resize in edit mode (150ms debounce)

**AI Tank Build Flow (SETUP view):**
1. User searches/selects a tank → `stats_ai.py:StatsAI._on_tank_select`
2. Check `ai_builds_cache.json` — if fresh (30-day expiry via `_is_cache_expired(updated, max_days=30)`), render from cache
3. If stale or missing → `generate_prompt_v2.py` builds Gemini prompt with tank data from `tank_slots_full.json`, `crew_builds.json`, `game_entities_english.json`
4. Prompt sent to Gemini via `ai_webview_gui.py` launched as subprocess (`python main.py --ai-webview`). Browser starts minimized (`showMinimized()`) with taskbar icon hidden. File-based capture to `wot_ai_response.txt` as primary mechanism, with stdout fallback; `RESPONSE_READY` sentinel marks completion
5. Response parsed and normalized by `ai_normalizer.py`
6. Result cached to `ai_builds_cache.json` and rendered as composite icons

**Memory to Persistence (Cross-Session):**
1. Tactical drawings → save on every edit → `data_manager.py:save_drawings` → `map_drawings.json`
2. AI build cache → save after each successful AI response → `ai_builds_cache.json`
3. Settings → save on window changes/close → `settings.json`
4. Service events → `service_messages.json` queue for future server delivery

## Key Abstractions

**WotAssistantHQ:**
- Purpose: Central application hub owning all state and manager instances
- Location: `main.py`
- Pattern: God object with manager delegation — owns settings, tank database, map state, view routing, hotkey bindings

**Manager Pattern:**
- Purpose: Encapsulate subsystem responsibilities behind a single class receiving `app` reference
- Location: `window_manager.py`, `ui_manager.py`, `data_manager.py`, `locale_manager.py`, `map_manager.py`, `map_renderer.py`, `help_system.py`
- Pattern: Each Manager receives `app` (WotAssistantHQ) in constructor, accesses shared state through `self.app.*`, and exposes domain-specific methods

**LogWatcher:**
- Purpose: Background thread that tails WoT's `python.log` and fires callbacks on battle events
- Location: `log_reader.py`
- Pattern: Regex-based log parsing in a daemon thread with callbacks for arena detection, countdown, vehicle, minimap, hangar return

**MapPainter:**
- Purpose: Canvas-based drawing system for tactical markers, arrows, text, and tree icons
- Location: `painter.py`
- Pattern: Stateful drawing list persisted via `DataManager`, creation history stack for Ctrl+Z undo, per-map/per-mode filtering. All painting renders on a dedicated overlay canvas (`_po_canvas`) inside a separate `_po_win` Toplevel for independent opacity control. Binds events to multiple canvases via `bind_events_to()`. Supports right-click context menu for edit/delete with confirmation dialog. Edit mode renders a yellow dashed selection rectangle around the edited element. Resize of selected elements via `resize_selected()` with keyboard hooks (Ctrl+↑/↓, 150ms debounce). Class icons rendered by `_draw_class_icons` are filtered against active checkboxes (`app.selected_classes`). Delegates property editing to `DrawingPalette` (`painting_palette.py`) — a floating non-modal palette with toolbar, mode/class checkboxes, text entry, color picker, delete button, and status bar showing editing type

**StatsAI:**
- Purpose: AI-powered tank build browser with search, filtering, composite icon rendering, and Gemini integration
- Location: `stats_ai.py`
- Pattern: tkinter Treeview + WebView browser, multi-level disk cache with expiry, equipment/crew/consumable TTH icon rendering

## Entry Points

**Application Entry:**
- Location: `main.py` (lines 1087-1098)
- Triggers: User double-clicks executable or runs `python main.py`
- Responsibilities: Call `multiprocessing.freeze_support()`, `os.chdir(config.BASE_DIR)` for consistent CWD, detect `--ai-webview` CLI flag to route to AI browser, initialize tkinter root with version title, create WotAssistantHQ, start mainloop

**CLI Entry (AI WebView):**
- Location: `main.py` (lines 1091-1094)
- Triggers: `python main.py --ai-webview` (spawned by `stats_ai.py` as subprocess)
- Responsibilities: Bypass tkinter entirely, run `ai_webview_gui.main()` directly, exit after completion

**Build Entry:**
- Location: `build.py`
- Triggers: `python build.py [version] [--release]`
- Responsibilities: Update `VERSION` file if version arg given, run PyInstaller via `wot_assistant.spec` for ~115 MB bundled `.exe`, optionally create GitHub release via `gh` CLI

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
- Responsibilities: Compare stored version with `version.xml`, trigger map/tank extraction if changed, update crew/equipment databases

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
- `VERSION` file at project root contains a plaintext semver string (e.g., `1.0.0`)
- `config.load_version()` reads it with `"0.0.0"` fallback
- `config.BASE_DIR` resolves to `sys.executable` directory when frozen (PyInstaller), or `__file__` directory in dev — all file paths are constructed relative to `BASE_DIR`
- `main.py` sets window title to `WoT Assistant v<version>` and calls `os.chdir(config.BASE_DIR)` at startup for consistent CWD
- `build.py` reads/writes `VERSION`, offers version bump + build + GitHub release commands

**Build & Packaging:**
- `build.py` — orchestrates version update, PyInstaller build (`--clean --noconfirm`), and optional GitHub release via `gh` CLI
- `wot_assistant.spec` — PyInstaller spec with explicit `datas` list: root JSONs, VERSION, fonts (`.ttf`), `.mo` localization files, `logo.png`, `maps/` subdirectories, `extracted_maps/` (excluding caches), `extracted_icons/` (all 8 subdirectories), `extracted_data/common/post_progression/` (field mod data), and `tools/orion/` decoder
- Hidden imports: `keyboard`, `PIL._tkinter_finder`
- `console=False`, `upx=True`, icon from `logo.png`
- Output: `dist/WoT Assistant.exe` (~115 MB)

**Logging:** Print-based console output with bracketed tags (`[INIT]`, `[SYNC]`, `[AI Tank Build]`, `[SERVICE]`, `[BUILD]`). No structured logging framework.

**Caching:**
- `ai_builds_cache.json` — AI tank builds, 30-day expiry, fail_count tracking (`stats_ai.py`)
- `popular_tanks_cache.json` — Popular tanks list (tiers 8-11), 30-day expiry via shared `_is_cache_expired(updated, max_days=30)`, fail_count tracking; saves top 30 tanks (`stats_ai.py`)
- `ukrainian_map_names_cache.json` — Map name translations (`map_extractor.py`)
- In-memory caches: composite icons, loadout icons, TTH icons, field mod pairs (`stats_ai.py:82-86`)

**Storage:** Flat JSON files at project root. No database engine. Key files: `settings.json`, `tank_db.json`, `tank_tth.json`, `crew_builds.json`, `equipment_loadouts.json`, `map_drawings.json`, `game_entities_english.json`

**Localization:** `translations.py` provides default UI/map translations. `locales.json` serves as a runtime-editable override that merges missing keys from `translations.py`. `LocaleManager.t_map` resolves map names through multiple sources: `custom_names.json` → `extractor_names` → `locales.json` → `config.TECH_MAPS_STAGING`.
