# Admin app, генератор, промпти

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

## Patreon у Community Workspace + скрізь (21.08.2026, адмінка v1.0.34)

**Джерело:** публічний legacy-API `https://www.patreon.com/api/campaigns/16413892` (campaign id з og:image teaser patreon.com/cw/SMWoTAssistant) — **без auth, без Chrome, без vault** (як GitHub): `patron_count`, `paid_member_count`, `campaign_pledge_sum`, `creation_count` (пости), `created_at`. Якщо API зламається — статус http_*/error, tile "—".

**У адмінці:** плитка **Patreon** (патрони) після Ko-fi; вкладка **Patreon** (field/value: Patrons/Paid members/Monthly pledge/Posts/Created); навігація браузера → `https://www.patreon.com/cw/SMWoTAssistant`; Overview → посилання в рядку Donations; `_fetch_patreon()`; кеш `community_cache.json` (+patreon); i18n `tile_patreon`/`tab_patreon`/`col_field`/`col_value`/`col_patrons`/`col_paid`/`col_pledge`/`col_posts`/`col_created`; seed 206/206. Правило #1570-1572 дотримано: тільки read-only публічні дані, дашборд не автоматизується.

**Скрізь:** сайт `public/index.html` — 4-та картка Support (QR `img/qr_patreon.png`, api.qrserver.com 600×600, файли без деплою); `.github/FUNDING.yml` — `patreon: SMWoTAssistant` (на main, #1588); `reddit_post.md` — секція Support + `img_patreon.png` у reddit_upload.

---

## Розбіжність «Танків/Промптів» + Ctrl+V у вбудованому браузері (21.08.2026, адмінка v1.0.33)

**Моніторинг розбіжності (користувач: «Танків 995 а промптів 996 — слідкувати щоб цифри співпадали, при розбіжності видавати помилку»):**
- `admin_build_generator.py`: `_BAD_TAG_MARKERS` (єдина точка правди; був інлайн-список у `load_tank_db`) + `_is_bad_tag(tag)` + `check_prompt_tank_mismatch(tank_db, prompts)` → `(prompts_only, tanks_only)` — диф по ключах.
- Запобігання (клас-рішення): `detect_changed_tanks()` і `scan_incomplete_builds()` пропускають `_is_bad_tag` теги → івент-клони (CFE/7x7/FL/SH/StoryMode…) ніколи не генеруються, розбіжність неможлива в принципі. Нові регулярні танки (F141_Durendal-style) детектяться як завжди.
- `admin_app.py`: картка **«Tanks / Prompts»** (ліва колонка, зелена при співпадінні / червона при розбіжності, `_update_cards`); `_check_tank_prompt_match()` — на старті (замість голого `log_tanks_prompts`) та після кожного `_do_generate` (finally) — при розбіжності `[ERROR]`-рядки в лог з конкретними тегами. i18n: `card_tp`, `log_tp_mismatch`, `log_tp_orphan_prompt`, `log_tp_orphan_tank` (UK-кеш перекладається автоматично).
- **Інцидент 995/996 вирішено:** зайвим був `Ch45_WZ_114_CFE_D` (CFE-клон WZ-114, згенерований 13.08 — коміт c04e20f; відфільтрований з tank_db → невидимий). Видалено: ключ з `prompts_cache.json` (996→995) + RTDB `prompts/tanks/Ch45_WZ_114_CFE_D` + `builds/tanks/Ch45_WZ_114_CFE_D` (PUT null через `_put_json`, верифіковано GET → null).

**Ctrl+V у вбудованому браузері (після v1.0.32 все ще «іноді не працювало»):** корінь — фокус Chrome давався лише (1) разово через 150 мс після embed і (2) після кліку над браузером; hover+Ctrl+V без кліку → ввід у Tk root. Фікс: `_community_poll_embed` — **безперервна асерція**: поки курсор над embedded Chrome (`_cursor_over_hwnd`), `SetFocus(hwnd)` КОЖЕН полл (200 мс); one-shot таймер і клік-гейт прибрані. Обмеження: сайти з блоком clipboard-permission не лікуються.

---

## Фікси Community Workspace: embed браузера + вставка API-ключів (19.08.2026, адмінка v1.0.18)

**Проблеми:** (1) браузер не вшивався у вікно адмінки (висів на панелі завдань оф-скрін); (2) неможливо вставити API-ключі з буфера у поля вкладки API Keys.

**Корінь:** `_community_show_browser()` викликався з фонового daemon-потоку (усі fetch-шляхи — `_refresh_community_background`/`_community_refresh_tab` → `_community_ensure_browser` → `_community_show_browser`) і робив Tkinter-виклики `winfo_id/width/height` → `RuntimeError: main thread is not in main loop` (видно в admin.log як "Помилка фона") → голе `except Exception: pass` ковтало → embed ніколи не відбувався. Chrome лишався окремим видимим вікном і перехоплював фокус клавіатури → Ctrl+V не доходив до полів.

**Фікс:**
1. `_community_show_browser()` — thread-safe: пошук HWND у worker-потоку `_locate` (PowerShell/ctypes, thread-safe), лише прапорець `embed_pending`; жодних Tk-викликів з фонового потоку.
2. `_community_poll_embed()` — головний потік (`root.after(200, ...)`): ПОСТІЙНИЙ watcher-цикл (поки юзер у Community): виконує `_embed_hwnd`, `visible=True` лише після успіху; якщо hwnd Chrome мертвий (перестворення вікна) — знаходить нове головне через `_find_hwnd_by_pid` і вбудовує знову (v1.0.25). Рестарт на кожному `_enter_community`; при `fs=False` цикл зупиняється.
3. `_enter_community()` — активно стартує браузер (thread `_community_ensure_browser(True)`), якщо driver ще нема (раніше — лише лазі-фетч).
4. Гвард `creating` у `_community_ensure_browser()` — два потоки не створюють два driver одночасно.
5. Після створення driver: embed якщо `visible or fs`.
6. `_bind_entry_menu()` — ПКМ Cut/Copy/Paste/Select All для полів API Keys (+ ключі `menu_cut`/`menu_paste` в `_TR_EN` та `admin_uk_seed.json`).

**Правило на майбутнє:** жодних Tkinter-викликів (winfo/insert/after) з фонового потоку — тільки прапорці/черги + `root.after(0/200, ...)` на головному потоці. Клас цього бага — "Tk з не-головного потоку" (#1593-родина).

**Верифікація:** живий smoke — GetParent(hwnd)==frame_id після входу в Community, re-embed після exit/re-enter; ПКМ-меню прив'язане до всіх полів; тестові процеси прибрані.

**Збірка:** admin_version.txt → 1.0.18, `python build_admin.py`.

---

## Community Workspace — плитки, вбудований Chrome-браузер, статистика платформ (18.08.2026, адмінка v1.0.17)

**Що це:** розділ в адмінці для моніторингу соцмереж/донатів/статистики + зашифроване сховище креденціалів.

### 1. Плитки (головне вікно, завжди видимі)
- Ряд плиток під статус-баром (v1.0.34): **Overview | YouTube views | Reddit posts | GitHub downloads | Ko-fi total | Patreon patrons | Installs | Errors**
- Хінт на плитці (помаранчевий, `⚠`) якщо канал потребує підключення: `needs API key` / `needs login` / `blocked` / `action needed` — текст зі статусу фетча (`_tile_hint`, admin_app.py)
- Клік по плитці → повноекранний Community-режим на відповідній вкладці
- Оновлення: RTDB-лічильники 300с, платформи 600с (фоновий цикл `_start_background`; `_fetch_rtdb_counters`/`_refresh_community_background`)
- У треї: Chrome НЕ працює — `_on_close` вбиває браузер (`_community_kill_browser`); Chrome-фетчі тільки при видимому вікні (`_app_visible()`), HTTP/API джерела працюють і в треї

### 2. Повноекранний Community-режим
- Кнопка **Community** в топбарі (поруч із ⚙) → `_enter_community()`: `root.attributes("-fullscreen", True)` + overlay-frame `place(relx=0,rely=0,relwidth=1,relheight=1)` поверх звичайного контенту (pack-лейаут не чіпається, `place_forget` при виході; ESC — вихід)
- Склад: плитки (повторний ряд `_build_tile_strip`) + tk.Notebook (8 вкладок: Overview / YouTube / Reddit / GitHub / Ko-fi / Patreon / API Keys / Errors; ttk clam-тема, Treeview dark) + червоний банер дій + вбудований браузер-фрейм. Розкладка (20.08.2026, v1.0.19): горизонтальний спліт grid — ліва колонка (плитки + Notebook + банер, weight 3, minsize 480), права (`_browser_frame`, weight 2, minsize 480); embed-ланцюг позиційно-незалежний (winfo-розміри з `_browser_frame`)
- Вкладки з Treeview-списками матеріалів: YouTube (Відео|Дата|Views|Likes|Comments), Reddit (Пост|Дата|Score|Comments), GitHub (Реліз|Дата|Downloads), Ko-fi (сума + останні), Errors (Час|Тип|Джерело|Версія|Помилка) — кнопка Refresh на кожній вкладці (`_community_refresh_tab`); Errors: `_fetch_errors_list()` читає `error_reports` (`&orderBy="timestamp"&limitToLast=200`, сорт desc), оновлюється у фоновому циклі + Refresh; tile Errors відкриває вкладку Errors

### 3. Вбудований браузер (без окремих вікон)
- Selenium-Chrome запускається з **постійним профілем** `%APPDATA%/SM WoT Assistant/community_chrome_profile/` (НЕ %TEMP% копія #1542 — цей профіль переживає рестарти, сід 1 раз з реального профілю через `_copy_chrome_profile`)
- Стартує завжди оф-скрін; у fullscreen — `SetParent(chrome_hwnd, browser_frame.winfo_id())` + WS_CHILD через `_embed_hwnd` (WinAPI), ресайз за Configure-подіями (`_sync_browser_geometry`) — Chrome стає дочірнім вікном адмінки
- **Надійність embed (20.08.2026, v1.0.20-1.0.21):** `_community_poll_embed` циклічно повторює спробу кожні 200мс поки фрейм не замапований (`winfo_id()!=0`) і `SetParent` не поверне успіх (bool-результат `_embed_hwnd`); при виході (`_community_move_browser_offscreen`) вікно ВІД'ЄДНУЄТЬСЯ (`_unembed_hwnd` → SetParent NULL + WS_POPUP) — інакше повторний вхід не знайде WS_CHILD вікно через EnumWindows
- **Вибір вікна (v1.0.21-1.0.22):** `_find_hwnd_by_pid` вибирає НАЙБІЛЬШЕ видиме вікно pid за площею (GetWindowRect) — модальний діалог Chrome ніколи не переможе головне вікно; pid завжди з `_chrome_main_pid` (PowerShell, CREATE_NO_WINDOW). УВАГА: `drv.service.process.pid` — це pid CHROMEDRIVER, не Chrome — НЕ використовувати для пошуку вікна (регресія 1.0.21: вбудовувалась консоль драйвера — «термінал замість браузера»; виправлено в 1.0.22)
- **Консоль драйвера**: `webdriver.Chrome(..., service=Service(creation_flags=subprocess.CREATE_NO_WINDOW))` — chromedriver (консольний процес) стартує без видимого консольного вікна у windowed EXE
- **«Відновити сторінки?»**: після аварійного вбивства профіль отримує `exit_type=Crashed` + залишки сесійних файлів → модальний діалог Chrome ігнорує `--window-position` і з'являється на екрані; `_fix_crashed_profile_prefs()` переписує Preferences на `Normal` + ВИДАЛЯЄ `Last Session`/`Current Session`/`Last Tabs`/`Last Version` + прапор `--disable-session-crashed-bubble`; перед стартом драйвера `_kill_chrome_matching(профіль)` прибирає залишки (інакше webdriver retry 20-30с — «браузер не вбудовується»)
- **Мерехтіння консолі**: ВСІ `subprocess.run(["powershell", ...])` (`_chrome_main_pid`, `_kill_chrome_matching`) — з `creationflags=CREATE_NO_WINDOW`, інакше у frozen windowed EXE кожен виклик блимає консольним вікном
- `_find_chrome_hwnd_by_pid` → PowerShell Get-CimInstance (cmdline містить профіль-дир, без `--type=`) → EnumWindows
- Потік дій: `_community_action_needed(msg)` → трей-балун + червоний банер + хінт плитки (CAPTCHA, потрібен логін); `_community_clear_action()` після розв'язання

### 4. Ланцюг джерел даних (на кожну платформу)
- **YouTube**: API key з vault → `videos?part=snippet&id=4JlDkM65PxY` → channelId → uploads playlist (`UU`+channelId[2:]) → playlistItems (пагінація) → statistics batch (~12 units/оновлення). Без ключа → Chrome: `/channel/{id}/videos` → `ytInitialData` → `_parse_yt_videos` (2026 формат `lockupViewModel`: title=`metadata.lockupMetadataViewModel.title.content`, views=`contentMetadataViewModel.metadataRows[*].metadataParts[*].text.content`; старий `videoRenderer` теж підтримується; videoId з `/vi/{id}/` thumbnail-URL)
- **Reddit** (v1.0.23, 21.08.2026): публічний `submitted.json` з UA — **403+HTML з 2026** (без OAuth) → Chrome фолбек: сесія-чек `_reddit_logged_in` — **`reddit.com/settings/`** (приватна: залогінений бачить її, іншого викидає на `/login`; `/api/v1/me` не бачить cookie-сесію — тільки OAuth; `/login/` НЕ редиректить залогіненого) → автологін `_login_reddit` (vault username/password; ранній вихід `ok`, якщо сесія вже є) → **`submitted.json` через браузер** (кукі залогіненого працюють; парс JSON з `<pre>`, той самий формат що у HTTP-шляху; 0 постів → статус `empty`)
- **Ko-fi** (v1.0.23, 21.08.2026): Chrome: сесія-чек `_kofi_logged_in` — **`https://ko-fi.com/Manage/SupportReceived`** (title «Ko-fi | Transactions»; старий `/manage/donations` = **404 з 2026**; залогінений = url без `/login` і title без `404`) → автологін `_login_kofi` (vault email/password; ранній вихід `ok` при живій сесії) → `_parse_kofi_amounts` (класи `amount|donation|transaction-row-amount` + валюта) — **0 донатів на валідній сторінці = нормальний стан** (`{"total": 0, "count": 0}`, статус OK, НЕ `no_amounts_parsed`)
- **GitHub**: публічний API `api.github.com/repos/SM-WoT-Assistant/SM-WoT-Assistant/releases` → per-release downloads (сума assets), total
- RTDB лічильники: `installations/` (всього + розбивка по версіях), `error_reports/`, `schemes/`, `users/`, `builds/version` + `last_generated_at`
- УВАГА (20.08.2026, v1.0.19): `installations/` має read `auth != null` (#1529) — лічильник читається через `admin_auth._rtdb_url_with_token()` (`_fetch_installations`); bare API key дає 401 → «0». Без `admin_creds.json` → tile «—». Також: `_rtdb_url()` вже містить `?auth=KEY` — query-параметри (orderBy/endAt/limitToLast) треба додавати через `&`, інакше RTDB 400 «orderBy must be defined» (баг `_cleanup_old_error_reports` та перших версій `_fetch_errors_list`)
- Усі фетчі в daemon-потоках + `root.after(0, ...)`, статус кожного джерела: Loading… / ok / no_key / blocked / needs_* / error (ніколи не падає)
- **Повне ручне керування (v1.0.26, 21.08.2026):** фонові цикли оновлення платформ (10 хв) і RTDB (5 хв) ВИМКНЕНО — дані тільки через кнопки Refresh/«Зв'язати» на вкладках; при вході в Community — одноразові RTDB-лічильники; лишились лише технічні цикли (heartbeat 60с, 24h cleanup/sweep, WG-версія 30 хв). Помилки ручних оновлень → `_community_action_needed` (банер + tray + статус + лог)
- **Кеш + оновлення (v1.0.28, 21.08.2026):** `community_cache.json` (AppData) — кеш даних платформ з валідацією; при старті кеш завантажується (плитки миттєво); при вході в Community — одноразове повне оновлення (фонові CDP-вкладки); фоновий цикл — 1 раз на 12 годин (43200с); вручну — Refresh/«Зв'язати». При вході завжди вкладка Overview. ensure_browser НЕ вбиває драйвер при visible-mismatch (критичний фікс kill-race)
- **Плитка Reddit** (v1.0.26): кількість постів + статус-хінт, клік → вкладка Reddit; tile_reddit i18n
- **Tab-ізоляція (v1.0.24-1.0.27, 21.08.2026):** `_fetch_yt_chrome`/`_fetch_reddit_chrome`/`_fetch_kofi_chrome` працюють у НОВІЙ фоновій вкладці — вкладка юзера ніколи не навігується; v1.0.27: `_open_bg_tab` (метод) — CDP `Target.createTarget` + **`Target.activateTarget(main)`** (UI гарантовано повертається юзеру навіть якщо Chrome активує нову вкладку; `[DEBUG][bgtab] cdp=ok/fail` в admin.log; fallback `new_window` + `about:blank` — без стартової сторінки google); close-guard: закриває фонову вкладку тільки якщо вкладок > 1
- **Кожна вкладка — своя адмін-сторінка (v1.0.27, 21.08.2026):** `_navigate_platform_tab` + `<<NotebookTabChanged>>` — перемикання вкладки програми навігує видимий браузер: Overview → sm-wot-assistant.web.app/admin.html, YouTube → канал проєкту, Reddit → user/SM-WoT-Assistant/, GitHub → releases, Ko-fi → /Manage/; API Keys/Errors не чіпають; при вході в Community — Overview автоматично
- **Watcher-embed + TOOLWINDOW (v1.0.25, 21.08.2026):** `_community_poll_embed` — постійний монітор (перестворене вікно Chrome негайно вбудовується знову); `_start_toolwindow_guard` (daemon, 3с) застосовує `WS_EX_TOOLWINDOW` до ВСІХ top-level вікон pid → жодної іконки Chrome в таскбарі ніколи; `tg_started` скидається при скиданні драйвера
- **Кнопка «Зв'язати» (v1.0.25):** на вкладках Reddit/Ko-fi (`_community_link_platform`) — миттєва перевірка сесії без 10-хв циклу; стан `community_linked` зберігається в `admin_settings.json` НАЗАВЖДИ (`_remember_linked`) → статус вкладок «✓ Зв'язано»/«Не зв'язано» при старті (переживає перезапуски)

### 5. Зашифроване сховище admin_vault.py (DPAPI)
- Новий модуль: `CryptProtectData`/`CryptUnprotectData` (crypt32.dll через ctypes, `CRYPTPROTECT_UI_FORBIDDEN`), прив'язка до Windows-акаунта
- Файл `%APPDATA%/SM WoT Assistant/admin_vault.json`: `{"youtube": {"api_key": "<base64 DPAPI>"}, "reddit": {...}, "kofi": {...}}` — API: `vault_get/vault_set/vault_has/vault_delete_field/vault_delete`
- Розшифровка лише на вимогу, значення ніколи не логуються; вкладка API Keys (поля `show="*"`, масковані "•••", порожнє поле = видалити) + кнопка **Reset browser data** (kill браузера + видалення профілю)
- Firebase `admin_creds.json` НЕ зачіпається (#1219-принцип, рішення користувача)

### 6. Логіни
- Спершу сесії з постійного профілю (куки з реального Chrome при першому сіді); протухли → vault-автологін (Reddit/Ko-fi); Google — ручний (автологін блокується захистом Google, ризик блокування акаунта)
- Входи зберігаються в профілі → наступний запуск без авторизації (куки протухають на стороні серверів — повторна авторизація раз на кілька місяців норма)

### 7. i18n
- +83 ключі до `_TR_EN` (185 всього): плитки, вкладки, колонки, статуси, API-ключі, дії, help-секція `h_sec_community` (5 пунктів)
- `admin_uk_seed.json` оновлено: 183 UK-переклади + свіжий `en_snapshot` (механізм `_load_uk_translations` — нуль Google-запитів на свіжій інсталяції)

### 8. Верифікація (#1471)
- ast-аудит (2389 рядків) + метод-аудит (53 викликані/88 визначених, 0 missing)
- Юніт: parsers (ytInitialData обох форматів, shreddit-post, kofi amounts, `_parse_views` EN/UK/RU множники), vault round-trip (DPAPI-шифрування на диску, жодного plaintext)
- Live smoke (Python 3.12): UI → fullscreen (6 вкладок) → драйвер (постійний профіль) → **SetParent hwnd знайдено і вбудовано** → YouTube сторінка + ytInitialData → GitHub API (6 downloads) → Reddit блок грейс-стан → yt chrome fetch (1 відео, 12 переглядів) → чистий kill
- Жива проба Reddit-шляху: статус `needs_reddit_creds` + ACTION-сповіщення (без креденціалів у vault)

### 9. Збірка
- `admin_version.txt` 1.0.16 → **1.0.17**, `python build_admin.py` (Python 3.12, `_internal`-гвард)

---

## Гвард перебірки + інцидент зламаного dist-бандла (13.08.2026, build_admin.py, адмінка v1.0.16)
1. **Інцидент**: адмінка не стартувала — bootloader «Failed to load Python DLL ...\dist\SM WoT Assistant Admin\_internal\python312.dll». Причина: `_internal` порожній (0 файлів) + старий EXE в dist — продовження задокументованого в v1.0.14/v1.0.15 блокування dist невидимим хендлом (WinError 32): збірки v1.0.14/15 йшли в `%TEMP%\opencode\admin_build14/15\`, а частковий clean()/COLLECT лишив dist зламаним. Автозапуск HKCU\Run → dist → фейл.
2. **Фікс**: перебірка v1.0.16 (лок пішов) + **гвард у build_admin.py::build_admin_exe** — перевірка `_internal` (існує, непустий, python312.dll присутній) після білда, інакше `[BUILD] FATAL` + exit(1); успіх друкує `Admin EXE: X MB, _internal: N entries`.
3. **Верифікація**: 2 повні білди (v1.0.15, v1.0.16) + 2 smoke-запуски (процес живий, admin.log оновлюється), тестові процеси закриті.
4. **Примітки**: temp-копії admin_build14/15 видалено; при повторі помилки перш за все перевіряти `_internal\python312.dll`.

---

## Причини FAILED видимі у 5 каналах + повністю фонова генерація (13.08.2026, адмінка v1.0.15)

1. **generate_builds > (ok, done_tags, reasons)**: reasons = `{tag: "категорія: деталь"}` для КОЖНОГО невдалого танка + `reasons["summary"]`. Категорії явні: `unknown_tank` / `client_parse_fail` / `no_prompt` / `ai_no_response` / `ai_parse_fail` / `upload_fail`. Канали: консольний принт, admin.log + GUI-лог + трей-балун (замість голого «Генерація FAILED»), RTDB `pending_updates/builds` (status=error, message=summary), `report_fallback` > `error_reports` (admin.html Errors).
2. **Fail-реєстр** у `.tank_extract_manifest.json` (`_failures: {tag: {count, fp}}`): `update_manifest_failures()` / `exclude_failed_tags()`, поріг 3 > танк виключається з детекту і щоденного свепу; скидання лічильника — успішна генерація (через `update_manifest_for_tags`) або зміна фінгерпринта його scripts.pkg-файла (новий патч гри = свіжа спроба). Вічна петля silent FAILED неможлива.
3. **Захист класу**: `detect_changed_tanks` повідомляє про відсутність scripts.pkg (`report_fallback`) замість тихого `[]`; `_tank_record_from_client` КИДАЄ `RuntimeError("list.xml parse failed: ...")` замість тихого `None`; `_fill_progress.json` > `config.USER_DATA_DIR` + гвард `start_idx >= len(all_tags) > 0`; `builds/version` бампиться лише при `ok_count > 0` (дубль у `_do_generate` прибрано); свеп фільтрується через `exclude_failed_tags`.
4. **Повністю у фоні**: Chrome ВСЕГДИ оф-скрін (`--window-position=-32000,-32000` замість `--start-maximized` — жодного вікна поверх інших); адмінка стартує в системному треї (`start_minimized: True` для нових інсталяцій, X > у трей, вихід через Settings); dev-запуски — `pythonw.exe` (без термінальних вікон; причини фейлів і так у admin.log + RTDB).
5. **Верифікація (#1471)**: ast 4 модулі + 8 ізольованих юніт-тестів fail-реєстру + live-проби (RTDB `error_reports` запис, Chrome позиція `(-32000, -32000)`), адмінка v1.0.15 у треї «Танків: 995, Промптів: 996», «Змін не виявлено».

---

## Щоденний авто-свіп неповних білдів (11.08.2026, адмінка v1.0.10)

**Проблема:** гейт `_is_build_complete` перевіряє лише `equipment_1` + `consumables_1` → білд без перків екіпажу проходить і ніколи не перегенеровується. Аудит 995 білдів RTDB проти клієнтських `crew_roles` (tank_slots_full.json): 118 неповних (J20_Type_2605 без crew, 113 без перків лоадера та ін.).

**Механізм:**
1. `strict_build_incomplete(tag, build_data)` (admin_build_generator.py) — строгий чек: `equipment_1/2` + `consumables_1/2` непусті; кожна роль клієнта присутня в білді з непустими перками. Нормалізація ролей `_normalize_crew_role()`: `loader_radio`→loader+radioman, `loader_2/gunner_2/radioman_2`→базова роль, регістр. Клієнтські ролі з `_gp.tank_slots` (module-level dict generate_prompt_v2; для loader_radio-танків tank_slots_full містить ТІЛЬКИ первинну роль — радист покривається, не вимагається).
2. `scan_incomplete_builds()` — 1 GET `builds/tanks.json` + порівняння → `{tag: [missing]}` (~118 зараз, обладнання 0 проблем).
3. **Демон `--listen`:** таймер `_last_sweep` (24 год, перший — одразу) → `_run_daily_sweep()` пише `pending_updates/builds` {status: generating, queue: неповні} — існуюча механіка черги генерує. Гвард: пропуск якщо `pending_updates/builds.status=="generating"` АБО `admin_app/status=="generating"` зі свіжим `last_seen` (<180 с — захист від застряглого статусу після падіння GUI).
4. **Адмінка GUI:** `_run_build_fill_sweep()` у `_start_background` — генерує напряму (thread), БЕЗ pending-тригера, щоб демон не підхопив ту саму чергу (подвійна генерація). Гвард: `self._generating` + pending status.
5. **Взаємне виключення:** GUI пише `admin_app/status=generating` (наявний патерн #1443) — демон по ньому + last_seen пропускає свій свіп; GUI перевіряє pending (демон активний → пропуск).
6. **Цикл самолікування:** неповний білд → свіп (24 год / при старті) → регенерація → все ще неповний (ШІ ще не знає) → наступний свіп знову, поки всі секції не заповняться.
7. **Верифікація:** smoke strict-чека (Durendal→[], J20→усі crew, M48A2→crew:loader, Type 59 loader_radio→[], gunner_2→[], порожні перки→missing, equipment_2→missing); сухий scan=118; живий запуск v1.0.10 — «Генерую 118 білдів...», RTDB pending status=generating.

**Відомі обмеження (успадковані):**
- `_do_generate` пише pending БЕЗ queue (#1443) → демон, побачивши status=generating, міг би форс-регенерувати ВСЕ (queue=None). Раса існує з ручною кнопкою Generate; не запускати демон одночасно з GUI-генерацією.
- Застряглий `pending_updates/builds.status="generating"` після падіння генератора блокує обидва свіпи (гвард); лікується демоном або ручним Generate.
- `self._last_sweep = -86280.0` порівнюється з `time.time()` (epoch) → свіп при старті GUI спрацьовує негайно (як `_last_cleanup`, #1485), а не через 120 с — заповнення йде при КОЖНОМУ старті, що відповідає меті.

---

## Механізм оновлення білдів: done_tags + добудова з клієнта (07.08.2026, admin_build_generator.py, адмінка v1.0.6)
1. **Проблема (F141_Durendal, гра v2.3.1.1 #910)**: адмінка повідомила «Генерація завершена!» (06.08 19:06), але білд нового танка НЕ потрапив у RTDB, а манифест змін уже містив його fingerprint → танк назавжди схований від автооновлення. Корінь: (а) `tank_db.json` застарів (головний застосунок у stability_mode викликає лише `extract_metadata`, не `build_database`) → `generate_builds` фільтрував queue по tank_db → total=0 → `return True` («All tanks already cached!») — хибний успіх; (б) `admin_app._do_generate` при ok=True оновлював манифест для ВСЬОГО queue; (в) `generate_prompt` резолвить танк через `tank_slots_full.json`, який теж не мав нового танка («Tank not found» навіть зі свіжим tank_db.json).
2. **Фікс**:
   - `generate_builds` повертає `(ok, done_tags)` — теги, реально завантажені в RTDB; при total==0 повертає `(False, [])` замість хибного True.
   - `update_manifest_for_tags(..., done_tags)` — манифест оновлюється ТІЛЬКИ для згенерованих (admin_app.py:892; те саме в listen_mode).
   - Теги queue без запису в tank_db добудовуються з клієнта: `_tank_record_from_client(tag, wot_path)` — list.xml (tier/class/nation/premium/compact_descr, обробка unescaped `&` у `<gold>`); `_slots_and_crew_from_client(tag, wot_path)` — vehicle XML через WotXmlParser (crew roles з `also`-ролями, supplySlots → equipment_slots/equipment_slot_types/consumable_slots, postProgressionTree, customRoleSlotOptions, optDevsOverrides).
   - `_persist_client_tank_data` — записи зберігаються в tank_db.json (indent=4), tank_slots_full.json (indent=2, як оригінал), crew_builds.json (`tanks`-вузол), плюс оновлюються module-level словники `generate_prompt_v2` (tank_db/tank_slots/crew_builds) для поточного процесу.
3. **Верифікація (живий цикл)**: detect → `['F141_Durendal']` → `--builds F141_Durendal` → RTDB повний білд (3 equipment + 7 consumables, без `#`-сміття) → манифест по done_tags → detect = 0 змін; `builds/version` → v7. Дані: tank_db.json 1140, tank_slots_full.json 1267, crew_builds.json 1140.
4. **Перезбірка**: admin_version.txt → 1.0.6 (#1446), `python build_admin.py` → `dist/SM WoT Assistant Admin/`.

---

## Chrome profile isolation (07.08.2026 → 12.08.2026, admin_build_generator.py, адмінка v1.0.5 → v1.0.11)
1. **Проблема (07.08)**: `_create_driver()` використовував реальний профіль Chrome `C:\Users\PRO\AppData\Local\Google\Chrome\User Data` + `--profile-directory=Default`. Коли Chrome уже запущений — новий chrome.exe віддає URL існуючому інстансу і виходить → `session not created: Chrome instance exited` (профіль заблокований SingletonLock). Після оновлення гри (тригер `pending_updates/builds`) демон `admin_build_generator.py --listen` падав на генерації кожен цикл.
2. **Фікс (07.08)** (admin_build_generator.py): при запущеному Chrome (`_chrome_running()` — tasklist-перевірка; невідомо → вважаємо залоченим) профіль КОПІЮЄТЬСЯ в `%TEMP%\sm_wot_admin_chrome_profile` (`_copy_chrome_profile()`, shutil.copytree) з виключенням кешів і локів (Cache/Code Cache/GPUCache/DawnCache/GraphiteDawnCache/ShaderCache/GrShaderCache/component_crx_cache/SingletonLock/SingletonCookie/SingletonSocket), залочені файли пропускаються. Свіжа копія не має SingletonLock → драйвер тримає власний інстанс. Перевірка наявності `Default/` + `Local State` (неповна копія → RuntimeError зі зрозумілим текстом). При закритому Chrome — як раніше, реальний профіль. Пункт 6 розділу 31.07.2026 ("Генерація вимагає закритий Chrome") — застарів.
3. **`_create_driver()` єдиний** — його імпортує і адмінка (`admin_app.py:24`), і демон; фікс входить у frozen admin EXE з перезбіркою.
4. **Верифікація (07.08)**: AST-аудит + ізольований smoke-тест (11/11): `_chrome_running()` bool, копія з exclude-патернами, перезапис існуючого dst, RuntimeError при браку Local State, FileNotFoundError при відсутньому src.
5. **Нюанс**: `CHROME_COPY_DIR` спільний для демона й адмінки — одночасний запуск обох із відкритим Chrome конкурує за директорію (на практиці працює один).
6. **DevToolsActivePort-інцидент (12.08, адмінка v1.0.11)** — ЗМІНА СТРАТЕГІЇ: гілка "реальний профіль при закритому Chrome" ВИДАЛЕНА. Сучасний Chrome (136+) блокує remote-debugging на дефолтному user-data-dir: браузер стартує, але НІКОЛИ не пише `DevToolsActivePort` → 60с таймаут `session not created: DevToolsActivePort file doesn't exist` (відтворено ізольовано: реальний профіль + .77/.138 = FAIL 62с ×2; копія профілю + будь-який драйвер = OK ~3с). Тепер **завжди** ізольована копія: `_create_driver()` → `_kill_chrome_matching(CHROME_COPY_DIR)` (прицільний kill chrome.exe за CommandLine, Get-CimInstance+Stop-Process; користувацький Chrome не чіпається) → `_copy_chrome_profile()`; ретрай 2 спроби (при `session not created` — kill лефтоверів + rmtree + свіжа копія). `_PROFILE_SKIP` розширено: `lockfile` (Chrome 151+), `Profile *`, `Guest Profile`. `_chrome_running()` видалено (мертвий код). Повний розбір — docs/changelog.md (12.08.2026).
7. **Стійкість до частих оновлень Chrome (12.08, адмінка v1.0.12)** — оновлення Chrome більше не валить генерацію: `_DRIVER_RETRY_MARKERS` (7 класів ретраябельних помилок: session not created, driver-manager, se-manager, верс-місматч), `_create_driver()` робить 3 спроби (паузи 3с/15с) зі свіжою копією профілю; RuntimeError з текстом "драйвер ще не опублікований — повторіть пізніше" замість глухої помилки; лог версій `[CHROME] session OK: chrome=X driver=Y` після старту сесії; авто-reconnect у `generate_builds()` — WebDriverException під час танка → quit + новий `_create_driver()` + повтор танка (max 1 поспіль). Верифікація: маркери 11/11, живий smoke reconnect (фейк-виняток round 1 → реальна нова сесія round 2 → tank done).


## Зміна в генерації промпту (28.05.2026)
1. `generate_prompt_v2.py:575` — "Current date: 2026-05-28." замінено на "2026 year"
   - Причина: рядок "Current date: ..." блокував AI відповідь для окремих танків (Google AI Mode ігнорував запит з повною датою для певних назв)
   - Рік динамічний: `datetime.now().strftime("%Y")`
2. `generate_prompt_v2.py:610` — крапку після year прибрано ("2026 year." → "2026 year")
   - Причина: крапка блокувала AI відповідь для T-46, BT-SV, Ram II, WZ-111 (та сама проблема що й з повною датою)


## Admin app fixes (31.07.2026)
1. **WoT path auto-detect** (admin_app.py:_resolve_wot_path) — ланцюг: CLI `--wot-path` → admin_settings.json → головний `%APPDATA%/SM WoT Assistant/settings.json` wot_path → common paths (той самий список що map_manager.py). Валідація через `version.xml`. Знайдений шлях зберігається в admin_settings.json.
2. **Хрестик → трей** — `_on_close()` робить `root.withdraw()` (програма живе, фоновий цикл працює). Повний вихід — вікно → ⚙ → **Exit** (з 31.07.2026, вечір; раніше був трей-меню).
3. **Трей-іконка — тільки показати вікно** — ЛКМ (0x0202) або даблклік (0x0203) → `deiconify()+lift()` прямо у wndproc. **КОНТЕКСТНОГО МЕНЮ НЕМАЄ.** Причина: три незалежні спроби меню (tk_popup, menu.post, кастомний Toplevel) падали з крахом `abort()` 0xC0000409 в ucrtbase (offset 0x7286e — функція abort; підтверджено Event Log Id 1000). Корінь: reentrant Tk-виклики / file I/O зсередини трей-callback (wndproc виконується в dispatch-контексті Tk). **Правило: трей wndproc = чистий форвардер — тільки простий присвоєння/деiconify, жодного Tk, жодного I/O, жодної логіки поза try/except.**
4. **Балон при старті в трей** — "Running in tray (WoT: ...)" через `tray.show_notification()`.
5. **build_admin.py selenium hidden imports** — `selenium.webdriver.chrome.webdriver` (критичний, lazy-import selenium 4), `selenium.webdriver.chrome.service`, `selenium.webdriver.chrome.options`, `selenium.webdriver.common.service`, `selenium.webdriver.common.selenium_manager`, `selenium.webdriver.common.driver_finder`. Без них frozen EXE падав: `No module named 'selenium.webdriver.chrome.webdriver'` — генерація НЕ працювала ніколи.
6. **Генерація вимагає закритий Chrome** — `_create_driver()` використовує реальний профіль `C:\Users\PRO\AppData\Local\Google\Chrome\User Data` + `--profile-directory=Default`; якщо Chrome запущений — "session not created: Chrome instance exited" (профіль заблокований).
7. **Маніфест змін танків у AppData** (admin_app.py:_resolve_manifest) — `.tank_extract_manifest.json` тепер живе в `%APPDATA%/SM WoT Assistant/`, НЕ в CWD. Причина: frozen onefile CWD = `%TEMP%\_MEIxxxxx`, відносний шлях маніфесту не знаходився → `old={}` → detect завжди повертав ВСІ 1309 танків → авто-генерація при кожному старті/таймері (30 хв WG / 60 хв scan) → вікна Chrome з домашньою сторінкою (handoff у запущений Chrome) + балон "Chrome instance exited" вічно. Сід при першому запуску: CWD-копія ТІЛЬКИ якщо свіжа (detect по ній == 0), інакше snapshot поточного scripts.pkg (`snapshot_manifest()`) → перший запуск завжди = 0 змін. Всі 3 виклики `detect_changed_tanks()` передають `manifest_path=self._manifest_path`.
8. **Оновлення маніфесту після генерації** — `update_manifest_for_tags(wot_path, manifest_path, tags)` (admin_build_generator.py): після `ok=True` записи згенерованих тегів оновлюються поточними fingerprint-ами → танки не редетектуються вічно кожні 60 хв. Семантика збігається з існуючим pop queue. `_MANIFEST_LOCK` (threading.Lock) захищає читання detect + записи (snapshot/update).
9. **⚙ шестірня → випадаюче меню** — `_show_settings_menu()` (tk.Menu tk_popup під кнопкою, той самий паттерн що в головній програмі): чекбокси Start with Windows / Start minimized to tray + пункт "WoT Path..." → `_show_wot_path_dialog()` (маленький Toplevel з полем шляху + Save). З 31.07.2026 (вечір) додано **Exit** в кінці меню — єдиний шлях повного виходу. Старого діалогу Admin Settings зі всіма налаштуваннями більше немає.


## Admin app i18n + log (01.08.2026)
1. **Реверс логу** (admin_app.py:_log) — нові повідомлення вставляються в `"1.0"` (зверху), автоскрол `see("1.0")`, обрізання `delete("1000.0", tk.END)` (макс. 1000 рядків у widget). Файл `admin.log` НЕ змінюється (як був append).
2. **Копіювання повідомлень** — ПКМ на логу (і на тексті хелпу) → контекстне меню Copy / Select All (будується свіжим при кожному popup — завжди актуальна мова). `_copy_selection(widget)` → clipboard. Ctrl+C працює штатно.
3. **i18n EN/UK** — авторитетний словник `_TR_EN` (99 ключів) в admin_app.py. `self.t(key, **fmt)` повертає поточну мову (`_lang` з admin_settings.json ключ `lang`, default "en"). Кнопка-перемикач EN/UK у топбарі поруч із ⚙ (текст = мова, в яку перемикає). `_apply_lang()` оновлює всі widget-референси з `_tr_widgets` (кнопки, карти, статус).
4. **Кеш української** — `%APPDATA%/SM WoT Assistant/admin_uk_cache.json` = `{"en_snapshot", "uk", "updated_at"}`. `_load_uk_translations()`: при збігу `en_snapshot` з `_TR_EN` → використовує кеш БЕЗ запитів до Google; при зміні ключів → перекладає ТІЛЬКИ змінені/нові через `deep_translator.GoogleTranslator` (`_translate_en2uk`, фолбек на англ). Офлайн → англійська.
5. **Seed** — `admin_uk_seed.json` в репо (згенеровано при розробці, 99 ключів + вручну виправлені криві переклади Google), бандлиться в EXE (`build_admin.py --add-data`), при відсутності кешу використовується як джерело → на свіжій інсталяції нуль запитів.
6. **Захист перекладу** — `_shield()/_unshield()`: плейсхолдери `{n}`, `{path}` і токени (SM WoT Assistant, scripts.pkg, WoT, WG, AI, F1, Ctrl...) захищаються від перекручення Google. Кнопкові мітки перекладаються (не в списку токенів).
7. **Хелп по F1** — `_show_help()`: темний Toplevel 680×560 з read-only ScrolledText, контент `_help_text()` з `_TR_EN` (розділи: Кнопки, Налаштування, Трей, Фонова автоматизація, Лог, F1). Той самий діалог — з меню ⚙ → **Help**. Контент генерується при відкритті (актуальна мова).
8. **Що НЕ перекладається** — `root.title` "SM WoT Assistant Admin vX.Y.Z" (mutex `FindWindowW` шукає за title — second-instance restore), трей tip, назва програми в топбарі.
9. **build_admin.py** — додано `--hidden-import deep_translator` + `--add-data admin_uk_seed.json`. deep_translator підтягує requests/certifi/charset_normalizer автоматично; опційні pypdf/docx2txt/openai не потрібні (GoogleTranslator їх не використовує).
10. **Логіка перекладу з фонових потоків** — `self.t()` тільки читає dict (thread-safe), трей-сповіщення і логи в `_do_scan`/`_do_generate`/`_start_background` перекладаються при виклику.


## Admin tiers_devices з клієнта (01.08.2026, вечір)
1. **Причина fallback-спаму** (`parse_tiers_devices returned empty`): frozen адмін EXE не мав `temp_scripts/decoded/tiers_devices_decoded.xml` та `temp_scripts2/scripts/.../tiers_devices.xml` (не бандлялись у build_admin.py) → `load_tiers_devices()` повертала `{}` → generate_prompt_v2 падав у hardcoded fallback з `report_fallback` при КОЖНІЙ генерації (8 помилок на сайті за 2 дні).
2. **Виправлення**: `parse_tiers_devices.py` — НОВИЙ перший кандидат: `{wot_path}/res/packages/scripts.pkg` (шлях з `config.SETTINGS_FILE` = AppData settings.json, патерн map_extractor.py:16-18) → `zipfile.ZipFile` (scripts.pkg — це ZIP, запис `scripts/item_defs/vehicles/common/optional_devices/tiers_devices.xml`, 31031 B, бінарний BigWorld `45 4e a1 62`) → `_ensure_decoded` з вихідною директорією `config.USER_DATA_DIR` (писемна; старий шлях `base_dir/temp_scripts/decoded/` ніхто більше не читає) → парс. `_try_client_pkg()` повертає шлях кешованої raw-копії (`tiers_devices_raw.xml` в AppData) або None.
3. **Версія `0.0.0` у звітах**: `firebase_reporter._report_version()` — якщо в `BUNDLE_DIR` є `admin_version.txt` І (frozen АБО немає `VERSION`) → версія з нього (`1.0.2`); інакше `config.load_version()`. Frozen main не змінився (admin_version.txt не бандлиться), dev main не змінився (VERSION є), dev admin = main version (прийнятний компроміс).
4. **build_admin.py** — додано `--add-data temp_scripts/decoded/tiers_devices_decoded.xml → temp_scripts/decoded/` (статичний резерв на випадок зміни структури pkg).
5. **Автоочищення error_reports**: `admin_app.py:_cleanup_old_error_reports()` — REST-запит `error_reports.json?orderBy="timestamp"&endAt="{now-60d UTC}"` (тільки старі записи) → `PUT null` по кожному ключу (патерн delete_group_scheme), подвійна перевірка парсингом `%Y-%m-%dT%H:%M:%SZ` (непарсибельні НЕ видаляються). Запуск: перша ітерація `_start_background` + кожні 24 год (`_last_cleanup`). Лог через ключ `log_cleanup_done` ("Cleaned {n} old error reports (>60 days)").


## mo_maps cache fix + ration source fix (02.08.2026)
1. **R1 (language_module.py:380)**: `generate_mo_maps(lm, lang)` → `generate_mo_maps(src, lang)` де `src = _lang_module if _lang_module is not None else lm`. Причина: у гілці "no change" (кеш `localization/<lang>` існує) `lm.dictionaries` порожній → generate_mo_maps очищав EQUIP_MAP/CONS_MAP/CREW_SKILL_MAP і перезаписував `mo_maps_{lang}.json` ПОРОЖНІМ при кожному повторному запуску. `_lang_module` гарантовано заповнений через `load_cache()` в обох гілках. Перевірено: smoke-запуск створив `mo_maps_uk.json` (26 КБ) на повторному запуску з наявним кешем.
2. **R2 (generate_prompt_v2.py:382)**: `_cons_rev_map()` тепер реверсить `ai_engine.AI_CONS_MAP` (той самий словник, що парсер відповідей) замість `stats_data.CONS_MAP`. Причина: адмінський процес не викликає `generate_mo_maps` → CONS_MAP порожній → `_build_nation_rations()` і `_get_consumables_from_game_data()` (список витратних для Main/Advanced loadout) падали на fallback з `game_entities.json`, де `name = "#artefacts:ration_uk/name"` (нерезолвлені ключі) — сміття в НОВИХ промптах: `Slot 3: MUST be "#artefacts:ration_uk/name"`. Після фіксу NATION_RATIONS = 11 націй з англійськими назвами ("Pudding and Tea", "Bread with Lard", "Improved Rations"...), 0 назв з `#` у списку витратних. Loadout 2 (Advanced) слот 3 завжди = національний раціон (generate_prompt_v2.py:557-561, 660, 674).
3. **admin_version.txt** → 1.0.3 (правило #1446: зміни адмін-програми після 1.0.2 вимагають бамп).

---

## Prompt Generator (з README_PROMPT_GENERATOR.md, 22.05)

# Prompt Generator for World of Tanks Competitive Builds

## Опис
Генерує AI-промт з реальними даними з клієнта гри World of Tanks. Промт містить два варіанти build (Main і Alternate).

## Джерела даних (з клієнта гри)
- **tank_slots_full.json**: Кількість слотів обладнання для кожного танка
- **tank_db.json**: Tier та клас танка
- **crew_builds.json**: Склад екіпажу, пули перків (_role_skill_pools), політика перків (_perk_policy)
- **game_entities_english.json**: Англійські назви обладнання

## Основні функції
1. **Обладнання залежить від tier танка**
   - Tier 1-4 = Tier 3 equipment
   - Tier 5-7 = Tier 2 equipment
   - Tier 8-10 = Tier 1 equipment

2. **Фільтрація за класом танка**
   - SPG виключає: Vertical Stabilizer, Grousers

3. **Перки з клієнта гри**
   - Беруться з _role_skill_pools
   - Кількість перків за tier з _perk_policy:
     - Tier 1-4: 1 перк
     - Tier 5-6: 2 перки
     - Tier 7: 4 перки
     - Tier 8-10: 6 перків

4. **loader_radio обробка**
   - Показується як Loader (6 перків) + Radioman (4 перки)
   - Два рядки з підказкою що це одна людина

## Структура виводу
1. **Equipment**: Main + Alternate (різні набори обладнання)
2. **Ammo**: Main + Alternate (різні типи/кількість снарядів)
3. **Consumables**: Main + Alternate (різні витратні)
4. **Crew Perks**: однакові для обох варіантів (екіпаж один)
5. **Field Modifications**: однакові для обох варіантів

## Використання
```bash
python generate_prompt_v2.py
```

## Приклад виводу
- Файл: prompt_is7_v3.txt
- Танк: IS-7 (Tier 10, HT)
- Слоти обладнання: 3
- Доступне обладнання: 15 найменувань

## Підтримувані танки
Всі танки з tank_slots_full.json (близько 1264 танка)
