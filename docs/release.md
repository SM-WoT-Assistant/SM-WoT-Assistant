# Релізний механізм і збірка

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

## Релізний механізм (09.06.2026)

### Створення релізу
Кожен білд автоматично створює GitHub release + публікує в RTDB.
1. `python build.py` — білд + GitHub release + RTDB (поточна VERSION)
2. `python build.py 1.0.2` — оновити VERSION → білд + GitHub release + RTDB
3. `python build.py 1.0.2 --date=2026-06-21` — білд з кастомною датою релізу

### Фази білду (build.py)
1. **Pre-flight** — валідація semver (X.Y.Z), Python 3.12+PyInstaller, NSIS (makensis.exe), gh CLI, критичні файли (main.py, VERSION, wot_assistant.spec, logo.png), git status
2. **Clean** — видалення `dist/SM WoT Assistant/` та `build/`
3. **PyInstaller** (onedir) → `copy_data_files()` (root JSONs, fonts, `.mo`, logo/icon, `sm_tactics.wotmod`, `extracted_maps/`, `extracted_icons/`, `extracted_data/common/post_progression/`) → NSIS installer
4. **Rename** onedir: `dist/SM WoT Assistant/` → `dist/SM WoT Assistant vX.Y.Z/`
5. **Portable ZIP**: `SM_WoT_Assistant_Portable_vX.Y.Z.zip` (~340 MB)
6. **Verify**: EXE, Launcher EXE, Tray Watcher EXE, 10 critical JSONs, VERSION, fonts, `extracted_maps/`≥60, `extracted_icons/`≥8, `extracted_data/`≥1
7. **Manifest**: `dist/build_manifest_vX.Y.Z.txt` (усі файли + розміри)

### Артефакти релізу в dist/
- `SM WoT Assistant vX.Y.Z/` — версіонований onedir (~510 MB, ~5400 файлів)
- `SM_WoT_Assistant_Setup_vX.Y.Z_Beta.exe` — NSIS інсталер (~298 MB)
- `SM_WoT_Assistant_Portable_vX.Y.Z_Beta.zip` — portable ZIP (~339 MB)
- `build_manifest_vX.Y.Z.txt` — маніфест білду

### Інструменти для білду
- Python: Python 3.12 (PyInstaller 6.20.0) — Python 3.14 має баг DATA TOC
- NSIS: `C:\Program Files (x86)\NSIS\makensis.exe` (build.py:find_nsis auto-detect)
- GitHub CLI: `gh` (обов'язково)
- `PyInstaller 6.x` баг: DATA entries з Analysis не потрапляють у COLLECT → обхід: `copy_data_files()` копіює дані вручну після PyInstaller

### Включення файлів у бандл (copy_data_files)
- Усі `*.json` з кореня проєкту, КРІМ: `opencode.json`, `magic-context.jsonc`, `_fill_progress.json`, `.*_manifest.json` (3), `tomato_*.json` (6), `ukrainian_map_names.json`, `vehicle_slots_*.json` (2)
- `VERSION`, TTF шрифти (xvmsymbol.ttf, fontawesome-webfont.ttf), .mo файли (3), `logo.png`, `icon.ico`
- `sm_tactics.wotmod` (збирається `build_mod.py`; без нього білд попереджає, що мод НЕ включено)
- `extracted_maps/` (63 файли, крім `ukrainian_map_names_cache.json` і `.map_extract_manifest.json`), `extracted_icons/` (8 піддиректорій), `extracted_data/common/post_progression/`
- `maps/` (TACTIC) більше НЕ входить у бандл (видалено у v2.0)
- `wot_assistant.spec` — синхронізований exclusion-list (довідково, не використовується через баг)

### Версія у вікнах програми
- Головне вікно: `main.py:3468` — `root.title(f"SM WoT Assistant v{config.load_version()}")`
- Splash: `main.py:3125` — `config.load_version()`
- Редактор (водяний знак): `map_renderer.py:315` — `config.load_version()`
- Довідка (F1): `help_system.py:96` — `config.load_version()` (через import config)

### Seeding файлів у AppData (перший запуск)
- `config.DEFAULT_FILES` (config.py:34) = `["settings.json", "locales.json", "map_drawings.json", "service_messages.json", "popular_tanks_cache.json", "ai_builds_cache.json"]`
- `main.py:1093-1101` — копіює з `config.BUNDLE_DIR` в `config.USER_DATA_DIR` якщо файл ще не існує
### Auto-commit версії

build.py автоматично комітить усі змінені файли (`git add -A`) перед білдом через `commit_version_files()` — VERSION, installer.nsi, `public/verify.json`, `popular_tanks_seed.json`, `base_schemes.json` тощо. Окремо комітити не треба; до запуску білда робоче дерево має бути чистим (preflight).

### Порядок дій для нового релізу

`python build.py X.Y.Z` робить все: білд + GitHub release + RTDB. Verify phase перевіряє автоматично.
Після білду запустити `dist/SM WoT Assistant vX.Y.Z/SM WoT Assistant.exe` — smoke test.


## Admin build layout onedir (04.08.2026, admin v1.0.4)1. **build_admin.py** збирає адмінку як **--onedir** у `dist/SM WoT Assistant Admin/` (EXE + `_internal/` з бандлом: admin_version.txt, admin_uk_seed.json, tiers_devices_decoded.xml тощо). Раніше був --onefile у корінь dist — міняли через плутанину двох EXE з однаковою назвою (dist root та стара папка).
2. **PyInstaller onedir** додає ім'я програми до distpath (`distpath/<name>/`) — тому `--distpath` = корінь `dist`, а не `dist/SM WoT Assistant Admin` (інакше подвійне вкладення).
3. **clean()** перед збіркою: `shutil.rmtree(dist/SM WoT Assistant Admin)` + видалення старих `dist/SM WoT Assistant Admin*.exe` з кореня. Канонічна точка запуску: `dist/SM WoT Assistant Admin/SM WoT Assistant Admin.exe`.
4. **Перед перезбіркою** вбити запущену адмінку (працюючий EXE заблокований Windows → clean() падає з PermissionError WinError 5; стара інстанція також блокує нову через мутекс).

## Release Cleanup Protocol (після КОЖНОГО релізу, 04.08.2026)

Правило: лишити **5 останніх** білдів/версій скрізь, решту прибрати. Порядок (спочатку перевірити, що новий реліз працює!):

1. **Локально dist/** — лишити 5 останніх версіонованих папок (`SM WoT Assistant vX.Y.Z/`) + їх Setup/Portable/manifest; видалити:
   ```powershell
   $keep = @("1.0.79","1.0.80","1.0.81","1.0.82","2.0.0")  # поточні 5
   Get-ChildItem dist -Directory | Where-Object { $_.Name -match "v(\d+\.\d+\.\d+)" -and $matches[1] -notin $keep -and $_.Name -notmatch "Admin" } | Remove-Item -Recurse -Force
   Get-ChildItem dist -File | Where-Object { $_.Name -match "v(\d+\.\d+\.\d+)" -and $matches[1] -notin $keep } | Remove-Item -Force
   ```
2. **GitHub** — видалити релізи старші 5 останніх (assets видаляються разом з релізом; теги лишаються):
   ```powershell
   $keep = @("v1.0.79","v1.0.80","v1.0.81","v1.0.82","v2.0.0")
   gh api "repos/SM-WoT-Assistant/SM-WoT-Assistant/releases?per_page=100" --jq ".[] | select(.name | split(\" Beta\")[0] as \$n | ($keep | index(\$n)) | not) | .tag_name" 
   # після перевірки списку — видалити кожен: gh api -X DELETE "repos/SM-WoT-Assistant/SM-WoT-Assistant/releases/$id"
   ```
3. **RTDB versions/** — лишити 5 останніх + `latest`, решту PUT null (правило #1470):
   ```python
   # keys < 5 останніх + 'admin' → PUT null, див. firebase_reporter._rtdb_url()
   ```
4. **Інші розхідники**: `temp_scripts.zip`, `*.log`, `*_err.txt`, `*_out.txt`, `extracted_gui/` — видаляти одразу після екстракцій; новий .py без імпортерів → `_archive/scripts/` (правило No dead code).

Перевірка після чистки: `gh api .../releases` = 5, `versions.json` = 6 ключів (5 версій + latest), dist ≤ ~5 GB.


