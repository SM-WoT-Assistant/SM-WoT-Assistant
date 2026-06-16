# Codebase Structure

## Directory Layout

```
[project-root]/
├── main.py                     # Application entry point, WotAssistantHQ hub class, CLI --ai-webview routing
├── config.py                   # Paths (BASE_DIR), constants, load_version(), TECH_MAPS_STAGING mapping
├── VERSION                     # Plaintext semver (e.g., 1.0.0) — consumed by config.load_version() and build.py
├── build.py                    # PyInstaller build orchestrator + GitHub release via gh CLI
├── wot_assistant.spec          # PyInstaller spec: fixed runtime_jsons list, hidden imports, COLLECT step for onedir output
├── installer.nsi                # NSIS installer script (lzma-compressed, no MUI2 dependency)
├── window_manager.py           # Window positioning, click-through, WinAPI, resizing
├── ui_manager.py               # UI layout, view switching, filter construction; battle mode labels from game client .mo via language_module.get_lang_module() with Google fallback
├── data_manager.py             # JSON file I/O, tank DB loading with fallback chain
├── locale_manager.py           # Translation system, map name resolution
├── map_manager.py              # Map list loading (unified TACTIC↔MAPS from extracted_maps/map_dictionary.json), game version check, data updates, TACTIC image existence filter, filters out type/*, invalid_map, hangar_v4, h33_* maps
├── map_renderer.py             # Map image rendering, 10×10 grid, draw_frame() border, _resolve_tactic_folder(), arena bases
├── painter.py                  # Canvas drawing: markers, arrows, text, tree icons, undo, edit mode, class icon filtering, overlay (_po_win) with transient/Unmap/focus management, _po_sync_timer (500ms)
├── painting_palette.py         # Floating DrawingPalette: toolbar, live-sync editing, 5-color history (_custom_colors), status bar, delete button, deselection; battle mode checkboxes with .mo names via language_module.get_lang_module() (Google fallback), class checkboxes always English (LT/MT/HT/TD/SPG)
├── log_reader.py               # python.log tailing for battle event detection
├── help_system.py              # F1 help overlay via Toplevel grid of Label widgets (table layout)
├── tactics_manager.py          # Import/export of tactical drawings as JSON
├── service_messages.py         # Internal event logging queue (undelivered messages)
├── translations.py             # Default UI/map translations (English-only authoritative source); class labels (LT/MT/HT/TD/SPG) kept in English for all languages
├── stats_ai.py                 # AI tank build browser (Treeview + subprocess Gemini WebView), popular tanks (tiers 8-11), 30-day caches
├── stats_data.py               # Equipment, consumable, crew skill ID mappings
├── ai_engine.py                # AI response normalization, equipment resolution, caching
├── ai_normalizer.py            # Validates AI-generated builds against known items
├── ai_assistant.py             # AI assistant orchestration
├── ai_webview_gui.py           # PyQt6 QWebEngineView browser launched as subprocess (--ai-webview); starts minimized, taskbar icon hidden, file-based + stdout dual capture
├── ai_scraper.py               # HTML scraping of AI responses
├── ai_scraper_strict.py        # Strict variant of AI scraper
├── ai_scraper_triple.py        # Triple-pass variant of AI scraper
├── ai_triple_scrape.py         # Triple-scrape AI response strategy
├── generate_prompt_v2.py       # AI prompt generator for competitive tank builds
├── generate_prompt.py          # Original prompt generator
├── generate_prompt_is7.py      # IS-7 specific prompt generator
├── map_extractor.py            # Map extraction from game client (MAPS mode)
├── map_updater.py              # Map sync for TACTIC mode (website scraping)
├── tank_extractor.py           # Tank data extraction from game client
├── wot_decoder.py              # XML decoder for game client .pkg files
├── decode_xml.py               # XML decoding utilities
├── decode_vehicle_xml.py       # Vehicle-specific XML decoding
├── __decode_defs.py            # Decoder definitions/constants
├── __decode_and_search_grid.py # Search grid decoding
├── bw_xml.py                   # Black/white XML operations
├── extract_all_client_data.py  # Bulk extraction from game client
├── extract_equipment_loadouts.py # Equipment loadouts from scripts.pkg
├── extract_vehicle_from_zip.py # Vehicle extraction from .pkg archives
├── extract_vehicle_slots.py    # Vehicle equipment slot extraction
├── extract_vehicle_slots_v2.py # Vehicle slot extraction v2
├── extract_slots_from_decoded.py # Slot extraction from decoded XML
├── extract_icons_and_map.py    # Icon and map extraction
├── extract_full_tank_data.py   # Full tank data extraction pipeline
├── build_crew_builds.py        # Crew composition from game client
├── build_field_mod_pairs_by_tank.py # Field modernization pair builder
├── create_tank_slots_db.py     # Tank slots database builder
├── create_english_names.py     # English tank name generator
├── add_english_tank_names.py   # English name augmentation
├── add_field_mods.py           # Field modernization data adder
├── parse_game_entities.py      # Game entities parser
├── parse_decoded.py            # Decoded XML parser
├── parse_mo_localization.py    # .mo localization file parser
├── parse_slots.py              # Slot data parser
├── parse_slots2.py             # Slot data parser v2
├── click_consumables.py        # Selenium: click consumables tab
├── click_consumables_js.py     # JavaScript-based consumable clicking
├── click_consumables_section.py # Selenium: click consumable section
├── click_loadout_tab.py        # Selenium: click loadout tab
├── click_loadout_analytics.py  # Selenium: loadout analytics clicker
├── selenium_consumables.py     # Selenium consumable automation
├── selenium_find_consumables.py # Selenium: find consumables
├── selenium_loadout_tab.py     # Selenium: loadout tab interaction
├── selenium_parse_consumables.py # Selenium: parse consumable data
├── selenium_selected.py        # Selenium: handle selected state
├── name_localizer.py           # Tank name localization utilities
├── language_module.py          # .mo file parser, game language detection, locale JSON exporter for website; global _lang_module via get_lang_module()/reset_lang_module(); regenerate_map_dictionary() and regenerate_game_entities() on language change
├── ui_translator.py            # Runtime UI translation via Google Translate with shortcut/symbol shielding
├── firebase_identity.py        # Local identity system (nickname + 4-digit PIN, SHA-256 hash, stored in AppData/identity.json)
├── firebase_reporter.py        # RTDB REST: error reports, version pings, update checks, service events
├── firebase_drawings.py        # RTDB REST: publish/download/delete tactical drawings (schemes/ node)
├── firebase.json               # Firebase Hosting + Database configuration
├── .firebaserc                 # Firebase project alias ("sm-wot-assistant")
├── database.rules.json         # RTDB security rules + indexes (versions, schemes, error_reports, installations, service_events)
├── network_requests.py         # HTTP request utilities
├── finder.py                   # File/pattern finder utility
├── find_refs3.py               # Reference finder
├── find_english.py             # English text finder
├── find_block.py               # Content block finder
├── find_tanks.py               # Tank search utility
├── find_consumables_data.py    # Consumable data finder
├── find_consumables_ui.py      # Consumable UI element finder
├── find_consumables_final.py   # Final consumable finder
├── arc_archive.py              # ARC archive manager
├── arc_sync.py                 # ARC sync utility
├── debug_*.py                  # Debugging scripts (9 files)
├── check_*.py                  # Validation/check scripts (9 files)
├── test_*.py                   # Test scripts
├── patch_*.py                  # Patch/hotfix scripts
├── tomato_*.py                 # tomato.gg scraper tools (deprecated)
├── analyse_*.py                # Data analysis scripts
├── explore_*.py                # Exploration/Discovery scripts
├── deep_*.py                   # Deep search utilities
├── repair_tth.py               # TTH repair utility
├── tth_updater.py              # TTH update batch processor
├── tth_orion_batch.py          # Orion-based TTH batch processing
├── _fill_all_builds.py         # Batch AI build filler
├── patch_stats_ai_*.py         # Stats AI patches
├── public/                     # Firebase Hosting static website (sm-wot-assistant.web.app)
│   ├── index.html              # English-only landing page (logo 2x, download link to GitHub releases at github.com/nkcgml-boop/SM-WoT-Assistant/releases, features grid, community schemes, releases table from RTDB)
│   ├── schemes.html            # Community tactical schemes browser (map filter, invite-code groups, PIN auth)
│   ├── drawings.html           # Drawing gallery with download
│   ├── admin.html              # Admin dashboard (stats, schemes management, version management)
│   ├── 404.html                # Custom 404 page
│   ├── logo.png                # Website logo
│   ├── example_map.png         # Example map image
│   └── locale/                 # Exported locale JSON files (e.g., uk.json) for website i18n
├── maps/                       # Map images for TACTIC mode (webp/jpg/png)
│   ├── Karelia/                # One subfolder per map
│   ├── Malinovka/
│   └── ...
├── extracted_maps/             # Map images + data from game client (MAPS mode)
│   ├── map_data.json           # Map coordinates, boundingBox, gameplay types
│   ├── map_dictionary.json     # Internal key → Ukrainian display name
│   └── *.png                   # Map images
├── extracted_icons/            # Tank icons extracted from client
│   ├── loadout/
│   │   ├── artefacts/          # Equipment icons (.png)
│   │   ├── ammo/               # Ammo/consumable icons (.png)
│   │   └── crew_skills/        # Crew skill icons (.png)
│   └── ...
├── extracted_data/             # Decoded XML tank data by nation
│   ├── usa/
│   ├── ussr/
│   └── ...
├── extracted_gui/              # Extracted GUI assets
├── extrated_icons/             # Additional tank icons extracted from client (.png per tank)
├── Tactik_Shemi/               # Exported tactical drawing JSONs (per-map tactic files)
├── icon/                       # Custom icons
│   └── Broken_tree.svg         # Broken tree marker icon
├── localization/               # Translation JSON files
│   ├── all_translations.json
│   ├── item_types_translations.json
│   ├── crew_perks_translations.json
│   └── artefacts_translations.json
├── tools/
│   └── orion/                  # Orion XML decoder tool
│       └── DLLs/
├── build/                      # PyInstaller intermediate build cache (Analysis, PYZ, EXE, COLLECT); final output in dist/
├── dist/                       # Release output (versioned onedir, NSIS installer, portable ZIP, manifest)
├── _archive/                   # Archived/old code variants
├── _decoded_search/            # Decoded XML map search results (per-map .xml files)
├── temp_scripts/               # Temporary extraction scripts (scripts/, arena_defs/, common/, entity_defs/, space_defs/)
├── temp_scripts2/              # Temporary extraction scripts v2 (scripts/, arena_defs/, common/, component_defs/, entity_defs/)
├── .firebase/                  # Firebase CLI cache (auto-generated)
├── .kilo/                      # Kilo worktree system data
├── .venv/                      # Python virtual environment(s)
├── .vscode/                    # VS Code workspace settings
└── .opencode/                  # OpenCode IDE configuration
```

## Directory Purposes

**Project Root:**
- Purpose: All application source code, data files, and configuration live at root level (no `src/` directory)
- Contains: 180+ Python scripts, JSON data files, TTF fonts, markdown docs, SVG icons, `installer.nsi`
- Key files: `main.py`, `config.py`, `settings.json`

**public/:**
- Purpose: Firebase Hosting static website served at `sm-wot-assistant.web.app`
- Contains: English-only landing page (`index.html`) with logo (2x), download button linking to GitHub releases (`github.com/nkcgml-boop/SM-WoT-Assistant/releases`), features grid, tactical schemes promo, releases table from RTDB; `schemes.html` community schemes browser with map filter, invite-code groups, and PIN-based auth; `drawings.html` gallery; `admin.html` admin dashboard; `404.html` custom error page; static assets (`logo.png`, `example_map.png`); `locale/` subdirectory with exported locale JSON files (e.g., `uk.json`) for website internationalization
- Key files: `index.html`, `schemes.html`

**maps/:**
- Purpose: Map images for TACTIC mode (sourced from website, not game client)
- Contains: Subdirectories named after maps (e.g., `Karelia/`, `Malinovka/`), each containing `map.webp`, `map.jpg`, or `map.png`
- Key files: Organized by human-readable folder names

**extracted_maps/:**
- Purpose: Map images and metadata extracted from the World of Tanks game client (MAPS mode)
- Contains: `map_data.json` (boundingBox, gameplay types, arena bases), `map_dictionary.json` (internal keys to Ukrainian names), per-map PNG images
- Key files: `map_data.json`, `map_dictionary.json`

**extracted_icons/:**
- Purpose: Tank and loadout icons extracted from client `.pkg` files
- Contains: `loadout/` subdirectories for equipment (artefacts), ammo/consumables, and crew skills as `.png` files
- Key files: `loadout/artefacts/*.png`, `loadout/ammo/*.png`, `loadout/crew_skills/*.png`

**extracted_data/:**
- Purpose: Decoded XML tank data organized by nation (fallback data source)
- Contains: Subdirectories per nation (`usa/`, `ussr/`, `germany/`, etc.) with per-tank `.xml` files

**extracted_gui/:**
- Purpose: Extracted GUI assets from game client

**extrated_icons/:**
- Purpose: Additional tank icon set extracted from game client, one `.png` per tank (historically variant of `extracted_icons/`)

**Tactik_Shemi/:**
- Purpose: Exported tactical drawing JSON files, one per map, for backup/sharing

**icon/:**
- Purpose: Custom application icons not extracted from game
- Contains: `Broken_tree.svg` and various test PNG files

**localization/:**
- Purpose: Translation tables used by the locale system
- Contains: JSON translation files for item types, crew perks, artefacts, and general search terms

**tools/orion/:**
- Purpose: Embedded Orion decoder tool for XML decoding (not bundled in release builds)
- Contains: Orion executable and its DLLs

**build/:**
- Purpose: PyInstaller intermediate build cache directory (temporary, cleaned between builds)
- Contains: Analysis, PYZ, EXE, COLLECT toc files, base_library.zip

**dist/ (not in repo):**
- Purpose: Final release output directory generated by `build.py` (git-ignored)
- Contains: Versioned onedir (`SM WoT Assistant vX.Y.Z/`), NSIS installer (`SM_WoT_Assistant_Setup_vX.Y.Z.exe`), portable ZIP (`SM_WoT_Assistant_Portable_vX.Y.Z.zip`), build manifest

**_archive/:**
- Purpose: Archived/old code variants preserved for reference

**_decoded_search/:**
- Purpose: Decoded XML files for map search results, organized per map

**temp_scripts/**, **temp_scripts2/:**
- Purpose: Temporary extraction/decode scripts for batch processing of game client data
- Contains: Subdirectories for scripts, arena_defs, common, entity_defs, space_defs, component_defs

**.kilo/:**
- Purpose: Kilo worktree system internal data (git worktrees, node_modules, plans)

**.venv/:**
- Purpose: Python virtual environment (dependencies installed locally)

## Key File Locations

**Entry Points:** `main.py`: Application startup, creates `WotAssistantHQ` with all managers, `--ai-webview` CLI routing, `os.chdir(config.BASE_DIR)`, AppData seeding via `config.DEFAULT_FILES`, Firebase global excepthook + ping + auto-update check; `build.py`: 7-phase PyInstaller onedir build + NSIS installer + portable ZIP + GitHub release + RTDB version publish
**Configuration:** `config.py`: File paths (`BUNDLE_DIR` for bundled assets, `USER_DATA_DIR` for writable AppData), `load_version()`, `TECH_MAPS_STAGING` map name mappings, `DEFAULT_FILES` seeding list; `VERSION`: Plaintext semver consumed by config and build; `wot_assistant.spec`: PyInstaller packaging spec (fixed `runtime_jsons`, COLLECT step); `installer.nsi`: NSIS installer script (lzma, standard pages); `settings.json`: Runtime user settings
**Core Logic:** `main.py` (class WotAssistantHQ): Central hub; `map_manager.py`: Map data and game version management, unified TACTIC↔MAPS list; `stats_ai.py` (class StatsAI): AI build system, subprocess webview launch
**Window Management:** `window_manager.py`: Window positioning, resizing, transparency, click-through, game focus; `ui_manager.py`: UI layout construction, view switching, battle mode filter labels from game client .mo (Google fallback)
**Data Extraction:** `map_extractor.py` (class MapExtractor): Map extraction from client; `tank_extractor.py` (class TankExtractor): Tank data extraction; `wot_decoder.py`: Low-level XML decoding
**Battle Integration:** `log_reader.py` (class LogWatcher): python.log tailing with regex-based event detection
**Drawing System:** `painter.py` (class MapPainter): Tactical markers/arrows/text with Ctrl+Z undo, resize, right-click edit/delete, edit-mode selection rectangle, _draw_class_icons filtered against active checkboxes, overlay canvas (_po_win Toplevel) with transient/Unmap/Map bindings, _po_sync_timer 500ms; `painting_palette.py` (class DrawingPalette): Floating non-modal palette with toolbar (marker, XVMSymbol class icons, tree FontAwesome icon, 8 tactical icons), mode checkboxes with names from game client .mo (Google fallback), class checkboxes (LT/MT/HT/TD/SPG — always English), text entry, 5-color history color picker, delete button, status bar, deselection on click-away
**AI Pipeline:** `generate_prompt_v2.py`: Build AI prompts from client data (popular tanks prompt asks for tiers 8-11); `ai_webview_gui.py`: PyQt6 QWebEngineView browser launched as subprocess via `--ai-webview`, starts minimized with taskbar icon hidden, file-based capture (wot_ai_response.txt) with stdout fallback and RESPONSE_READY sentinel; `ai_normalizer.py`: Response validation; `stats_data.py`: Equipment/skill/consumable mappings
**Localization:** `translations.py`: English-only authoritative translations (class labels kept English); `locale_manager.py` (class LocaleManager): Runtime translation resolution; `locales.json`: Editable translation overrides; `language_module.py` (class LanguageModule): WoT client .mo file parser, game language detection, per-category JSON cache builder, locale JSON exporter to `public/locale/` and Firebase RTDB; `regenerate_map_dictionary()` and `regenerate_game_entities()` on language change; global `_lang_module` via `get_lang_module()`/`reset_lang_module()` for lazy access by other modules (battle mode names, map names, TTH labels); `ui_translator.py`: Runtime UI translation via Google Translate (`deep_translator`) with shortcut/symbol shielding, per-language cache in `config.USER_DATA_DIR/localization/<lang>/ui_cache.json`
**Persistence Data:** `settings.json`, `tank_db.json`, `tank_tth.json`, `crew_builds.json`, `equipment_loadouts.json`, `tank_slots_full.json`, `map_drawings.json`, `game_entities_english.json`, `ai_builds_cache.json`, `popular_tanks_cache.json`, `identity.json` (AppData — nickname, PIN hash, user_id)
**Firebase/Cloud:** `firebase_identity.py`: Local identity + PIN auth; `firebase_reporter.py`: RTDB error/analytics/versions; `firebase_drawings.py`: RTDB drawing CRUD; `firebase.json` + `.firebaserc`: Firebase project config; `database.rules.json`: RTDB security rules; `public/`: English-only static website deployed to Firebase Hosting (download links point to `github.com/nkcgml-boop/SM-WoT-Assistant/releases`)
**Tests:** Scattered `test_*.py` files at root (no dedicated `tests/` directory)

## Naming Conventions

**Files:** Python scripts use `snake_case.py` for modules (e.g., `map_renderer.py`, `log_reader.py`, `stats_ai.py`). Debug/check scripts prefixed with `debug_` or `check_`. Selenium scripts prefixed with `selenium_`. Patch scripts prefixed with `patch_`. Test scripts prefixed with `test_`.

**Directories:** Extracted data uses lowercase with underscores: `extracted_maps/`, `extracted_icons/`. Map folders under `maps/` use capitalized human-readable names.

**Classes:** PascalCase: `WotAssistantHQ`, `WindowManager`, `MapRenderer`, `LogWatcher`, `StatsAI`, `MapExtractor`, `TankExtractor`, `MapPainter`, `DrawingPalette`, `LocaleManager`, `DataManager`, `HelpManager`, `UIManager`

**Functions:** `snake_case` for module-level functions (e.g., `_load_ai_build_cache`, `_is_cache_expired`). Method names also `snake_case` (e.g., `load_map_list`, `show_main_splash`, `set_clickthrough`).

**JSON Keys:** Mixed casing following game client conventions: `camelCase` for tank data (`boundingBox`, `gameplayTypes`, `compact_descr`), `snake_case` for app settings (`wot_path`, `log_path`, `edit_alpha`)

## Where to Add New Code

**New manager:** Create `new_manager.py` at root, implement a class receiving `app` reference, instantiate in `main.py:WotAssistantHQ.__init__`
**New drawing tool:** Add toolbar button in `painting_palette.py:DrawingPalette._build_ui` (all_tools list), add the tool code/icon (XVMSymbol or FontAwesome), implement drawing logic in `painter.py:MapPainter.on_press`/`on_drag`/`on_release`, rendering in `painter.py:MapPainter.redraw`, and class icon filtering in `_draw_class_icons`
**New game event:** Add regex pattern in `log_reader.py:LogWatcher`, add callback parameter, wire in `main.py:WotAssistantHQ`
**New AI feature:** Add to `stats_ai.py:StatsAI` class or create a companion module imported from there
**New data extraction:** Create `extract_*.py` at root, follow the pattern of `map_extractor.py` / `tank_extractor.py` (manifest tracking, callback_status)
**New translation:** Add keys to `translations.py`, they auto-merge into `locales.json` on next startup
**New localization category:** Add .mo filename to `LanguageModule.build_all_dictionaries()` categories dict in `language_module.py`, it auto-parses and caches on next language setup
**New settings:** Add property to `config.py`, read/write in `main.py:save_settings/__init__`, add UI control in `ui_manager.py:build_filters` or settings menu
**New view:** Add button in `ui_manager.py:setup_ui`, implement show_view logic in `ui_manager.py:show_view`, wire in `main.py`
**New deployment target:** Add to `build.py:copy_data_files()` exclusion logic or `wot_assistant.spec` `runtime_jsons` list (for JSONs), or extend `build.py` with new packaging steps (e.g., new directories)
**New Firebase feature:** Add to `firebase_reporter.py` for analytics/reporting, `firebase_drawings.py` for cloud data sync, or create new `firebase_*.py` module following the REST API pattern (API key auth, `_rtdb_url()` path builder, `_put`/`_post`/`_get` helpers)
**New website page:** Create `.html` file in `public/`, link from `public/index.html`, use Firebase RTDB REST API for dynamic data (same API key pattern as Python modules). All pages use English-only with `lang="en"`; no UA/EN toggle
**New version scheme:** Edit `VERSION`, update `config.load_version()` format handling if needed
