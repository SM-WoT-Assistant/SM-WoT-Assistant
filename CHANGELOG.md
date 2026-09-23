# Changelog

## [1.0.78] - 2026-09-14

### Fixed
- Tank extraction: BigWorld binary XML decoding for vehicle files (WG v.2.4.0.0 format change)
- TTH database regression guard — prevents data loss when parser output is partial
- field_modifications.xml binary decode fix (15 fallback → 26 real entries)
- Manifest path consistency — AppData for all extraction manifests
- Chrome kill race condition — wait for process death before profile cleanup
- Duplicate tank detection on every restart (693 false positives → 0)

### Added
- 62 new tanks with TTH data (G183, G193, G195, R233, R234, Pl38, S37 and others)
- Pending registry for failed builds — prevents infinite re-trigger loops
- Event-driven sync between admin app and website (builds/prompts/version listeners)
- LMB move for drawing elements (no Ctrl needed)
- Ctrl+C/V clipboard for tactical schemes
- Auto-save when editing saved schemes

### Changed
- Class icon checkboxes now filter schemes by vehicle class (no longer stamp icons)
- Mode checkboxes removed from drawing palette (redundant with map selection)
- Alpha → Beta label restored across all releases

---

## [1.0.77] - 2026-09-14

### Fixed
- Verification Phase 0 graceful fallback in dev mode
- Admin window auto-fit for small screens
- CHP equality guard on admin website

### Added
- 8 new prompts (Pl40, Pl44, R233, R234, R236, R239, S37, S41)
- A195_Gorilla slot data
- Compact stat layout with clickable drilldown in admin app

---

## [1.0.76] - 2026-09-14

### Fixed
- Admin manifest path defaults to AppData
- Chrome SingletonLock removal before profile copy

### Added
- Drilldown modals on admin website (search + filter + table)
- Event-driven website updates (no more polling delays)

---

## [1.0.75] - 2026-09-14

### Fixed
- `_check_tank_prompt_match` now merges local + RTDB prompts (was local-only)
- Chrome process wait after kill (prevents WinError 183 profile corruption)
- Tank detection false positives from stale pending registry

### Changed
- Admin website shows 4 stat boxes (builds, prompts, queue, fingerprint)
- `_upload_prompt` always runs after successful build upload

---

## [1.0.74] - 2026-09-14

### Fixed
- `build_database` regression guard — never overwrites larger existing TTH with smaller partial output
- `extract_metadata` now decodes all vehicle XML files (not just list.xml)
- `list.xml` BigWorld binary decoding for all 11 nations

### Added
- New Scheme button with name dialog
- LMB element move without Ctrl
- Auto-save on scheme edit
- Drawing clipboard (Ctrl+C/V with +20px cascade offset)

---

## [1.0.72] - 2026-08-28

### Fixed
- SETUP TTH block width — now matches lower block width on any window size
- Auto-width for tank names (was truncating Ukrainian names)
- Control character sanitization in XML decoder (broke game_entities.json parsing)
- battleAbilities filter — comp7/poi equipment no longer mixed into standard equipment
- Click-through on battle window + Ctrl+click unlock
- Language phase 1 fix — translation cache no longer blanks entire UI

### Added
- Drawing clipboard (Ctrl+C/Ctrl+V)
- Class icon filtering via checkboxes
- Painter undo/redo history stacks
- Overlay position sync timer (500ms)
- Scheme download dialog with multi-select and Source filter
- Group scheme linked overlay (read-only)

### Changed
- Mode checkboxes removed from drawing palette
- Class icons filtered by checkbox state (no longer stamped on elements)
- RTDB builds cleaned from 998 → 995 (removed 3 event clones)
- Alpha → Beta label restored
