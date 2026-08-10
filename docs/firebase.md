# Firebase / Cloud (RTDB, identity, groups, admin статус)

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

## Захист RTDB правилами + адмін-Auth (10.08.2026)

**Передісторія:** лист Firebase про незахищені правила (корінь `.read/.write: true`). Факти: RTDB не валідує `auth=` — API-ключ (публічний у клієнті і сайті) НЕ є автентифікацією, усі запити застосунку/сайту у правилах = `auth == null`. Єдиний компонент з реальним Auth — admin.html (email/password). Auth-акаунт адміна: `smwotassistant@gmail.com` / UID `W0bTk96xJMeVEEbplvMbxtl5igo2`.

**Схема авторизації:**
| Нода | Read | Write |
|---|---|---|
| `versions`, `builds`, `prompts`, `popular_tanks` | open (клієнт читає) | **тільки адмін-UID** (`auth.uid == 'W0bTk96xJMeVEEbplvMbxtl5igo2'`) |
| `error_reports` | open | wildcard `$id`: `!data.exists() \|\| auth != null` (create open, delete тільки адмін) |
| `installations`, `service_events` | тільки `auth != null` (admin.html) | open (клієнтський ping/flush) |
| `admin_app` | тільки `auth != null` | тільки `auth != null` (адмін-EXE з токеном) |
| `schemes`, `groups`, `user_groups`, `users`, `pending_updates` | open | open (клієнтський контент + trigger) |
| `drawings` | open | заборонено (легасі) |

**Адмін-тулінг (build.py, admin_build_generator.py, admin_app.py)** пише в RTDB через ID-токен: `admin_auth.get_id_token()` — `accounts:signInWithPassword` з `%APPDATA%/SM WoT Assistant/admin_creds.json` (`{"email": ..., "password": ...}`, gitignored), кеш + refresh по refreshToken. `admin_auth._rtdb_url_with_token()` зрізає існуючий `?auth=` (RTDB бере ПЕРШИЙ auth-параметр — API-ключ дає 401). Клієнтський застосунок НЕ використовує admin_auth — він працює з відкритими клієнтськими нодами без auth.

**Операційні правила:**
- Якщо Auth-акаунт перестворити — UID зміниться, правила доведеться оновити (гейт на UID, не на email).
- Адмін-EXE після змін admin_auth/admin_build_generator обов'язково перезбирати (`admin_version.txt` бамп + `build_admin.py`) — старий EXE пише API-ключем і отримує 401.
- `admin_creds.json` — секрет, gitignored; без нього адмін-тулінг не пише RTDB (видима помилка, не тиха).

**Верифіковано (10.08.2026):** повна curl-матриця (відкриті читання 200 / auth-читання 401 / адмін-записи без токена 401 / з токеном 200; error_reports create-open, overwrite-auth, delete-auth; installations/service_events write open) + dev-запуск main.py (ping + pending_updates сигнал — клієнтські шляхи живі).

---

## Картка танка
1. Вся інформація про білд — з Firebase RTDB (`builds/tanks/{tag}`), кешується локально в `ai_builds_cache.json`.
2. Якщо Firebase недоступний і кеш порожній — показувати пусті секції (без фалбеків).
3. Промпти для генерації білдів зберігаються на Firebase (`prompts/tanks/{tag}`), використовуються адміном.
4. Кешування включаємо тільки за прямим наказом і документуємо у цей файл всі кеші які працюють у проекті.


## Система груп та схем (30.06.2026)
1. **firebase_groups.py** — модуль управління групами в RTDB. Функції: `create_group()`, `join_group()`, `leave_group()`, `get_user_groups()`, `publish_to_group()`, `update_group_scheme()`, `get_group_schemes()`, `get_group_schemes_meta()`, `import_between_groups()`.
2. **RTDB структура:** `groups/{group_id}/{name, description, invite_code, members/{uid}, schemes/{drawing_id}}`. `user_groups/{uid}/{gid}` — швидкий пошук груп користувача.
3. **Group selector** (ui_manager.py:setup_ui) — `ttk.Combobox` в `map_toolbar` після `draw_btn`. Показує "Public" та список груп. Другий віджет — `group_token_btn` з інвайт-кодом (officer) або 🔒 (member). Показується тільки для зареєстрованих.
4. **Фільтр мап:** коли вибрана не-Public група, `load_map_list()` (map_manager.py:400) фільтрує список мап — тільки ті, що мають схеми у вибраній групі.
5. **Фільтр схем:** `painter.py:redraw()` рендерить тільки схеми з group_id == active_group_id.
6. **Group management** (painting_palette.py:_build_ui) — секція Groups на дні палітри (після _status_lbl). Кнопки Create/Join/Manage відкривають `overrideredirect(True)` кастомні діалоги (через `dialog_utils._DragHelper`).
7. **Кастомні діалоги:** всі діалоги груп (Create, Join, Manage) використовують `overrideredirect(True)` + кастомний темний header (`bg="#2a2a2a"`, title + ✕ close button) + `dialog_utils._DragHelper` для перетягування.
8. **Групова схема** — публікується в `groups/{gid}/schemes/{drawing_id}`, не потрапляє в публічні `schemes/`. Сайт (schemes.html) не бачить групових схем.
9. **Вибір публікації:** якщо активна група != public → Publish публікує в групу. Якщо public → у публічні schemes/ (як раніше).
10. **Download діалог** (painting_palette.py:_download_populate, _build_download_ui): завантажує публічні схеми + схеми з груп користувача. Додано колонку Source (Group/Public) та фільтр Source.
11. **Link (auto-sync)** — групові схеми можна встановити як посилання (painter._group_schemes), вони відображаються разом з локальними малюнками і автоматично оновлюються при зміні на сервері.
12. **Sync polling 60s** (main.py:_start_group_sync, _sync_cycle): перевіряє updated_at в RTDB кожні 60с. При зміні показує `overrideredirect(True)` сповіщення "Scheme updated by OfficerName. Download now?".
13. **Кеш групових схем** (config.GROUP_CACHE_FILE = `group_schemes_cache.json` в USER_DATA_DIR): зберігається при завершенні, завантажується при старті.
14. **database.rules.json** — додано індекси для `groups/` (invite_code, created_at) та `user_groups/`.
15. **_DragHelper** (dialog_utils.py:17-25) — клас для перетягування `overrideredirect` вікон. Параметри: `toplevel`, `frame`. Використовується в усіх кастомних діалогах.
16. **Токен групи:** інвайт-код з кнопкою Copy на top_bar поруч з group_selector. Для officer — показує код (#ffaa00) + clipboard copy. Для member — 🔒. Для Public — прихований.
17. **_show_group_sync_notification** (main.py:1815) — `overrideredirect(True)` + кастомний header + `_DragHelper`.
18. **Захист від дублікатів назв груп** (03.08.2026): у одного користувача не може бути двох груп з однаковою назвою. `create_group()` (firebase_groups.py) перевіряє `get_user_groups(uid)` перед PUT — при збігу назви (case-insensitive) повертає (None, "Ви вже маєте групу з такою назвою") БЕЗ створення. `join_group()` — та сама перевірка назви цільової групи ПІСЛЯ гілки "вже член" (повторний join своєї групи працює). UI не змінювався — do_create/do_join вже показують повернену помилку через status_var. Причина бага: користувач створив дві групи "001" (5eb72871/5147D4 та 98e53f80/B22858) → `_group_id_map` (ui_manager.py:199) колізія ключа label → обидва items селектора вели до однієї групи → "однаковий інвайт". Дубль 5eb72871 видалено з RTDB.
19. **`_put(path, None)` фікс** (03.08.2026, firebase_reporter.py:66, admin_build_generator.py:45 `_put_json`): `requests.put(json=None)` не шле тіло → RTDB 400 → ВСІ видалення тихо не працювали (leave_group, kick_member, delete_group, delete_group_scheme, admin `_cleanup_old_error_reports`). Тепер `data is None` → `requests.put(url, data=b"null", headers={"Content-Type": "application/json"})` → 200. DELETE-еквівалент: PUT null.


## Firebase Distribution Architecture (25.07.2026)
1. **Всі AI білди та промпти** зберігаються на Firebase RTDB — клієнт більше НЕ запускає AI WebView.
2. **Білди:** `builds/tanks/{tag}`, версія `builds/version`, склад `builds/scripts_fingerprint`.
3. **Промпти:** `prompts/tanks/{tag}`, `prompts/popular_tanks` — для адміна (генерація).
4. **Popular tanks:** `popular_tanks/data`, `popular_tanks/version`.
5. **Pending updates:** `pending_updates/popular_tanks/` та `pending_updates/builds/` — тригери для адміна.
6. **stats_ai.py:** AI WebView ВИДАЛЕНО (`launch_ai_browser`, `process_ai_response`, `_handle_ai_failure`, `_re_enable_ui`). Замінено на `_sync_popular_tanks()` та `_sync_builds()` — Firebase fetch при старті.
7. **stats_ai.py `needs_ai_refresh()`** — завжди повертає `False` (AI не використовується).
8. **stats_ai.py `stop_browser()`** — no-op.
9. **main.py:** AI стартап видалено (`_start_ai_phase`, `_ai_progress_creep`, `_on_ai_ready`, `_cancel_ai_timers`, `_ai_safety_timeout`). `_on_startup_ready()` → `finish_startup_splash()` → фоновий `_start_firebase_sync()`.
10. **main.py:** `--ai-webview` CLI handling ВИДАЛЕНО.
11. **Кеші залишаються:** `ai_builds_cache.json` (994 білди, включено в бандл), `popular_tanks_cache.json` (сідається з `popular_tanks_seed.json`).
12. **`_load_ai_build_cache()`** тепер повертає 5 значень: `(builds, updated, fail_count, version, scripts_fingerprint)`.
13. **`_save_ai_build_cache_bulk()`** — новий bulk save для Firebase.
14. **builds_table.py** — one-time скрипт для початкової заливки всіх білдів + промптів + популярних танків у Firebase.
15. **prompts_cache.json** — 994 промпти, згенеровані `builds_table.py`, включено в бандл (не в DEFAULT_FILES — використовується тільки адміном).


## Rebalance detection chain (27.07.2026, оновлено 07.08.2026)
1. **map_manager.py:check_game_version()** — при виявленні зміни версії гри (`version_changed=True`) або зміни вмісту `scripts.pkg` (`ext.has_changed()`) записує тригер у Firebase: `firebase_reporter._put("pending_updates/builds", {status:"idle", version, scripts_pkg_changed:true})`.
2. **admin_build_generator.py --listen** — полінг `pending_updates/builds` кожні 10с. При появі `status=="generating"` запускає `generate_builds(driver, tank_db, prompts, queue=..., wot_path=...)` — генерація змінених танків з ігноруванням кешу.
3. **`_update_builds_version()`** — після генерації оновлює `builds/version` (інкремент) та `builds/scripts_fingerprint` (MD5 від `{ver, ts}`).
4. **stats_ai.py:_sync_builds()** — при старті клієнта порівнює `remote_version != local_version` → force re-sync ALL танків.
5. **Повний ланцюжок:** `scripts.pkg змінився → client detect → pending_updates → admin --listen pick up → generate_all → bump version+fingerprint → client sync`.
6. **07.08.2026 (фікс "з'їденого" танка F141_Durendal):** `generate_builds` повертає `(ok, done_tags)` — лише теги, реально завантажені в RTDB; `update_manifest_for_tags` оновлює манифест тільки для них (не для всього queue). Теги без запису в tank_db добудовуються з клієнта (`_tank_record_from_client` + `_slots_and_crew_from_client`) — нові танки гри більше не губляться манифестом.


## admin.html changes (27.07.2026)
1. **Видалено**: кнопка "Regenerate All Builds" (непрактично — 994 танки через AI).
2. **Видалено**: `#builds-table-container` (незавершений placeholder "Loading...").
3. **Auto-expand**: секції (Errors, Schemes, Releases, AI Builds) з новими даними відкриваються автоматично, заголовок отримує `✦` та колір `#ff4500`.
4. **Highlight**: нові рядки (`isFresh()` перевірка по `admin_last_visit`) отримують CSS клас `row-new` з анімацією затемнення 3s.
5. **`_lastBuildsVersion`** — зберігається в `localStorage`, при зміні секція AI Builds авто-розкривається.


## Admin app RTDB статус (01.08.2026)
1. **Новий вузол `admin_app/`** — адмінка публікує свою інфу в RTDB: `version` (з admin_version.txt), `last_seen` (epoch-секунди, heartbeat кожні 60с у `_start_background` + при старті), `status` (`idle`/`generating`/`offline`), `last_generation` (`{at: ISO, count, ok}`).
2. **Дата оновлення бази/промптів** — при успіху генерації (`_do_generate`) адмінка пише `builds/last_generated_at` + `prompts/last_generated_at` (однаковий ISO — білди і промпти генеруються разом) та `popular_tanks/last_generated_at` при успіху `_do_popular`.
3. **Живий статус генерації на сайті** — `_do_generate` тепер пише `pending_updates/builds` через `_update_pending_status` (generating/done/error) — раніше це робив тільки CLI-демон `--listen`, GUI-генерація сайт не показувала.
4. **admin.html** — секція "Admin App (Desktop)" стала живою: Admin Version, Status (Online якщо `last_seen` < 5 хв, зелений/червоний), Activity (Idle/Generating), Last Generation (кількість + дата), Builds/Prompts/Popular updated (формат `YYYY-MM-DD HH:MM` без timezone-конвертації — таймстемпи пишуться локальним часом адмінки). `loadAdminAppData()` — при ініціалізації + поллінг кожні 60с.
5. **`_exit_app`** пише `status=offline` (daemon thread — не блокує вихід). При hard-kill статус застаріє через 5 хв за `last_seen`.
6. **RTDB rules** — змін не треба (`.read/.write: true` відкриті). Вузол `admin_app/` не конфліктує з клієнтським синком (stats_ai читає тільки `builds/` та `popular_tanks/`).

