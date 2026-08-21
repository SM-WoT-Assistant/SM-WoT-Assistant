# Історія змін (changelog)

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

---

## Адмінка v1.0.28 (21.08.2026): браузер знову з'являється (fix kill-race), кеш даних + оновлення при вході та раз на 12 годин, YouTube без автоплею, старт на Overview

Юзер: «Зараз взагалі немає браузера!!!» + «при старті програми і може 1 раз на 12 годин і повинен бути кеш; ручне керування — це про запам'ятовування логіну і завантаження сторінок; по замовченню запускай програму на оверв'ю» + «на YouTube автоматичне відтворення відео — треба вимкнути».

**Корінь «немає браузера» (критичний):** новий код навігації v1.0.27 (`_nav_overview` при вході + `<<NotebookTabChanged>>`) викликає `ensure_browser(fs=True)` ПОКИ браузер ще створюється/вбудовується (`visible=False`) — а `_community_ensure_browser_inner` при visible-mismatch робив `drv.quit()` + перестворення → циклічне вбивство браузера, він ніколи не встигав вбудуватись. Раніше ensure викликався лише з кнопок (після вбудовування) — race не виникав.

**Фікс:**
1. **Критичний:** `_community_ensure_browser_inner` — visible-mismatch гілку ВИДАЛЕНО: наявний драйвер просто повертається (видимістю керує embed/offscreen lifecycle, вбивство під час створення прибрано). Підтверджено тестом: ensure(True) → ensure(False) → ensure(True) = ТОЙ САМИЙ драйвер.
2. **Кеш даних** — `community_cache.json` (AppData): `_load_community_cache`/`_save_community_cache` з валідацією (тільки youtube/reddit/github/kofi dicts); при старті кеш завантажується → плитки/вкладки показують дані миттєво (не «Loading…»); запис після кожного оновлення (фоновий цикл, Refresh, «Зв'язати»).
3. **Оновлення даних:** при вході в Community — ОДНОРАЗОВЕ повне тихе оновлення (`_refresh_community_background` — всі платформи у фонових CDP-вкладках) + запис кешу; фоновий цикл — **1 раз на 12 годин** (43200с); вручну — Refresh/«Зв'язати». Жодних 10 хвилин.
4. **YouTube без автоплею:** видима навігація — НІКОЛИ `watch?v=` (поки channel_id невідомий — `youtube.com` головна; після fetch канал `channel/{id}/videos`); фетчова вкладка — `watch?v=...&autoplay=0` + JS-пауза/мут відео.
5. **При вході — завжди Overview:** `_select_tab("overview")` при вході (скидання останньої вкладки) + браузер на `admin.html`.

Верифікація: AST OK; тест: кеш round-trip з валідацією (junk відфільтрований), ensure-mismatch не вбиває драйвер (той самий), cleanup 0 залишків; build v1.0.28 (8.6 MB, _internal 69) через TMP-обхід; адмінка запущена (21.08, 03:46). Юзер має бачити: браузер вбудовується при вході; плитки/вкладки з даними (з кешу миттєво + свіже при вході); YouTube без відтворення; старт на Overview.

---

## Адмінка v1.0.27 (21.08.2026): кожна вкладка — своя адмін-сторінка; CDP activateTarget — fetch-навігації невидимі

Юзер: «На оверв'ю завантаж адмінсторінку нашого сайту» + «ні одна вкладка не завантажує свою сторінку» + «на Reddit написано Пов'язано, а в браузері завантажується домашня сторінка гугл; спочатку сторінка налаштування редіту, потім чорна сторінка з кодом, потім google». Розбір: (1) навігації fetch (settings/ → submitted.json) відбувались у ВИДИМІЙ вкладці юзера — tab-ізоляція не працювала: CDP createTarget створював/активував вкладку в UI (або CDP падав і спрацьовував fallback new_window = новий таб зі стартовою сторінкою google); (2) навігація при перемиканні вкладок була відсутня зовсім.

**Фікс:**
1. **Навігація при перемиканні вкладок** — `_navigate_platform_tab()` + bind `<<NotebookTabChanged>>`: активна вкладка програми керує браузером (ручне керування):
   - Overview → `https://sm-wot-assistant.web.app/admin.html` (адмін-сторінка сайту)
   - YouTube → канал проєкту (`/channel/{id}/videos`, id визначається автоматично; без id — основне відео `watch?v=`)
   - Reddit → `https://www.reddit.com/user/SM-WoT-Assistant/`
   - GitHub → `https://github.com/SM-WoT-Assistant/SM-WoT-Assistant/releases`
   - Ko-fi → `https://ko-fi.com/Manage/` (дашборд адміна)
   - API Keys / Errors — браузер не чіпають.
   При вході в Community — автоматична навігація на Overview (з retry, поки браузер створюється).
2. **`_open_bg_tab` переписано (метод класу з логом):** CDP `Target.createTarget` + **`Target.activateTarget(main_handle)`** — навіть якщо Chrome активує нову вкладку, UI гарантовано повертається юзеру; `[DEBUG][bgtab] cdp=ok / cdp=fail:<err> -> fallback` в admin.log. Fallback: `new_window("tab")` + негайний `about:blank` (жодної стартової сторінки google). Підтверджено живим тестом: `[DEBUG][bgtab] cdp=ok` + після fetch рівно 1 вкладка (фонова закрита), контекст на вкладці юзера; навігація `_navigate_platform_tab("reddit")` → URL профілю Reddit.

Верифікація: AST OK; живий тест (fetch → 1 вкладка, CDP ok, навігація працює, cleanup 0 залишків); build v1.0.27 (8.6 MB, _internal 69) через TMP-обхід; адмінка запущена (21.08, 03:14). Юзер має бачити: при вході в Community — адмін-сторінка сайту; при перемиканні вкладок — сторінка вкладки; при Refresh/«Зв'язати» — жодних стрибків сторінок (фетч у невидимій фоновій вкладці).

---

## Адмінка v1.0.26 (21.08.2026): повне ручне керування — жодних фоновим циклів оновлення; плитка Reddit; CDP-вкладки; «залізний» зв'язок помилок

Юзер: «Забудь про 10 хвилин! Вимкни це! Треба залізний зв'язок з повідомленням про помилку! Ручне керування — це ж адмінка!» + «немає плитки Reddit» + «при логіні на Ko-fi браузер скидає сторінку на Reddit». 

**Фікс:**
1. **Фонові цикли вимкнено повністю**: платформний цикл (10 хв, `_refresh_community_background`) і RTDB-лічильники (5 хв) видалені з `_start_background`; стартовий `after(8000, _refresh_community_background)` прибрано. Браузер і RTDB НІКОЛИ не чіпаються самі. Лишились лише технічні: heartbeat (60с admin_app/status), 24h cleanup/fill-sweep, моніторинг версії гри (30 хв) — вони не чіпають браузер і не «оновлюють дані».
2. **Ручне керування**: дані платформ — тільки кнопки Refresh / «Зв'язати» на вкладках; при вході в Community — ОДНОРАЗОВЕ тихе оновлення RTDB-лічильників (Installs/Errors плитки) без браузера.
3. **Плитка Reddit** додана в стріп (після Ko-fi): кількість постів + статус-хінт, клік → вкладка Reddit. i18n `tile_reddit` (EN "Reddit" / UK "Редіт"), seed 196/196.
4. **CDP фонові вкладки** — `_open_bg_tab()`: fetch-вкладки створюються через `Target.createTarget` (НЕ активуються в UI, close не перемикає видиму вкладку юзера) — фікс «браузер скидає сторінку на Reddit» (причина: `new_window("tab")` активував вкладку, а close перемикав UI на сусідню — червону Reddit). Fallback на `new_window` якщо CDP недоступний.
5. **«Залізний» зв'язок помилок**: при кожному ручному оновленні (Refresh/«Зв'язати»), якщо результат не ok/empty — `_community_action_needed()`: червоний банер + tray-повідомлення + статус вкладки + admin.log (раніше тільки для needs_*/captcha).

Верифікація: AST OK; seed 196/196 (en_snapshot+uk); fetch-тест з CDP-вкладками: reddit_chrome -> empty, kofi_chrome -> {'total': 0, 'count': 0}, cleanup спрацював (залишків 0); build v1.0.26 (8.6 MB, _internal 69) через TMP-обхід; адмінка запущена (21.08, 02:53). Юзер: вкладки оновлюються тільки кнопками; браузер не стрибає на Reddit; плитка Reddit у стріпі.

---

## Адмінка v1.0.25 (21.08.2026): повна інтеграція браузера — watcher-embed, жодних іконок у таскбарі, кнопка «Зв'язати» з вічною пам'яттю

Юзер: «Браузер має бути повністю вбудованим, без іконок у панелі завдань; програма має чітко бачити сторінки і синхронізувати логін; зроби кнопку „зв'язати", щоб програма запам'ятала назавжди; навіщо чекати 10 хвилин». Діагноз по живих вікнах (EnumWindows pid Chrome 19420): головне вікно Chrome (1400×900) було top-level оф-скрін з іконкою в таскбарі — раніше вбудоване вікно (embed ok 01:44:21) зникло: Chrome перестворив його (корінь — `drv.close()` у tab-ізоляції закривав ОСТАННЮ вкладку → Chrome закриває вікно і створює нове, top-level, без embed). Статус Reddit «BLOCKED» у повноекранному режимі — мій же fs-guard v1.0.24 блокував Chrome-фетчі у фоновому циклі, лишаючи статус від HTTP-шляху.

**Фікс (9 змін):**
1. **Watcher-embed** — `_community_poll_embed` тепер ПОСТІЙНИЙ монітор (кожні 200мс, поки юзер у Community): якщо hwnd Chrome мертвий (перестворення) — знаходить нове головне вікно через `_find_hwnd_by_pid` і вбудовує знову. Вікно браузера НІКОЛИ не «зникає» з фрейму.
2. **`WS_EX_TOOLWINDOW`** — `_toolwindow_hwnd()` + daemon `_start_toolwindow_guard` (кожні 3с, поки живе драйвер): КОЖНЕ top-level вікно Chrome pid отримує TOOLWINDOW → **жодна іконка Chrome в таскбарі неможлива в принципі** (ні головне, ні нові вікна/попапи). Підтверджено тестом: exstyle=0x80 на всіх вікнах.
3. **close-guard у tab-ізоляції** — фетч закриває фонову вкладку тільки при `len(window_handles) > 1` — ніколи не закриває останню (прибирає сам корінь перестворення вікна).
4. **fs-guard прибрано** — фоновий цикл знову запускає Chrome-фетчі у повноекранному Community (tab-ізоляція захищає вкладку юзера) → статус Reddit/Ko-fi автоматичний і чесний (ок/empty замість blocked).
5. **Кнопка «Зв'язати»** (btn_link, зелена) на вкладках Reddit і Ko-fi — миттєва перевірка сесії + дані, без очікування 10-хв циклу (`_community_link_platform`).
6. **Вічна пам'ять зв'язку** — `_remember_linked()` зберігає стан `community_linked` (reddit/kofi: True/False) у `admin_settings.json` після кожного refresh/link; при старті адмінки статус вкладок одразу «✓ Зв'язано» / «Не зв'язано» (`_set_tab_status` linked-гілка).
7. **Баг-фікс з аудиту** — `tg_started` тепер скидається при dead-driver і visible-mismatch скиданні драйвера в `_community_ensure_browser_inner` (інакше TOOLWINDOW-guard не перезапускався б після перестворення драйвера).
8-9. i18n: 3 нові ключі (`btn_link`, `st_linked`, `st_not_linked`) — _TR_EN + admin_uk_seed.json (en_snapshot+uk, 195/195).

Верифікація: AST OK; живий тест TOOLWINDOW (8 top-level вікон Chrome → exstyle 0x80/0x180 на всіх); аудит race-умов (enter-guard, poll-послідовність, close-guard, linked-логіка); build v1.0.25 (8.6 MB, _internal 69) через TMP-обхід; адмінка запущена (21.08, 02:31). Юзер має побачити: браузер стабільно вбудований без іконок; кнопку «Зв'язати» на вкладках Reddit/Ko-fi; статус «✓ Зв'язано» після логіну, що переживає перезапуски.

---

## Адмінка v1.0.24 (21.08.2026): браузер більше не «зникає» — fetch-навігації в окремій фоновій вкладці

Юзер повідомив: «При спробі зайти у обліковий запис Reddit зникає вікно браузера; другий раз — натиснув Refresh — знову зникло». Розбір по admin.log (01:19-01:23): фонові/Refresh-фетчі Reddit викликали `drv.get(settings/)` → `drv.get(submitted.json)` ПРЯМО у вбудованому браузері — сторінка юзера (форма логіну / його робота) навігувалась на технічні сторінки (біла JSON-сторінка), тобто «вікно зникає» = навігації fetch під час роботи юзера. `no such window: target window already closed` у логу — вікно закривалось (ESC/X) під час цих навігацій.

**Фікс (дві частини):**
1. **Tab-ізоляція fetch** — `_fetch_yt_chrome`, `_fetch_reddit_chrome`, `_fetch_kofi_chrome` (і автологіни всередині) тепер працюють у НОВІЙ фоновій вкладці (`drv.switch_to.new_window("tab")`), після завершення — `drv.close()` + `drv.switch_to.window(main_handle)` (вкладка юзера захоплюється на початку). Вкладка юзера НІКОЛИ не навігується — логін/робота в браузері не перебиваються, «зникнення» неможливе. Fallback: якщо `new_window` не підтримується — працює в поточній вкладці, як раніше.
2. **fs-guard у фоновому циклі** — `_refresh_community_background` НЕ запускає Chrome-фетчі (yt_chrome/reddit_chrome/kofi_chrome), поки юзер у повноекранному Community (`not self._community.get("fs")`); у fs оновлення — тільки HTTP/API джерела (github/rtdb/errors/yt_api) та Refresh-кнопки (які теж ізольовані у фоновій вкладці).

Верифікація: AST OK; fetch-тест: reddit_chrome -> empty, kofi_chrome -> {'total': 0, 'count': 0} (ізоляція не змінила результатів); cleanup браузера після тесту (`_community_kill_browser`). Build v1.0.24 (8.6 MB, _internal 69) через TMP-обхід; адмінка запущена (21.08, 01:38). Юзер має бачити: браузер стабільний у фреймі під час логіну і Refresh; фонові фетчі непомітні.

---

## Адмінка v1.0.23 (21.08.2026): програма бачить залогінену сесію Reddit/Ko-fi у вбудованому браузері

Юзер повідомив: «Зайшов на сторінку Reddit і Ko-fi, але програма не підхоплює це» — у статусі вкладки Reddit було `login_form_missing`, Ko-fi — помилка автологіну. Діагноз через живу серію тестів на профілі юзера (headless AdminApp + fetch-методи + HTML-дампи): **перевірка сесії в обох фетчах була хибною** — програма не розпізнавала, що юзер уже залогінений у `community_chrome_profile`, і наосліп лізла в автологін.

Факти (підтверджені дампами реальних сторінок 2026):
1. **Reddit**: `reddit.com/api/v1/me` працює тільки з OAuth-токеном, cookie-сесію браузера НЕ бачить (завжди False); `reddit.com/login/` НЕ редиректить залогіненого юзера (форма-перевірка теж безсила). Натомість `reddit.com/settings/` — приватна: залогінений бачить її, не-залогіненого викидає на `/login`. Публічний `submitted.json` без OAuth — 403+HTML (перевірено живим запитом), АЛЕ з кукі залогіненої сесії браузера повертає валідний JSON.
2. **Ko-fi**: старий шлях донатів `ko-fi.com/manage/donations` — **404 з 2026** (саме тому парсер бачив порожнє). Новий дашборд: залогіненого `ko-fi.com` редиректить на `https://ko-fi.com/Manage/`, самі донати — `/Manage/SupportReceived` (title «Ko-fi | Transactions»), суми — елементи з класом `transaction-row-amount` (тільки CSS у дампі — у юзера транзакцій поки 0; `$12` на сторінці — ціни підписок, не донати).

**Фікс (тільки перевірка сесії + шляхи; парсери відповідно):**
1. `_reddit_logged_in` → `drv.get("https://www.reddit.com/settings/")`; залогінений = url без `login` і title без `404` (редирект на `/login` = не залогінений).
2. `_fetch_reddit_chrome` → замість HTML-парсингу профілю: `drv.get(".../submitted.json")` (з кукі сесії) + JSON-парсинг (той самий формат, що у `_fetch_reddit_http`); 0 постів → статус `empty` (чесний стан, не помилка).
3. `_kofi_logged_in` → `drv.get("https://ko-fi.com/Manage/SupportReceived")`; залогінений = url без `/login` і title без `404`.
4. `_fetch_kofi_chrome` → шлях `/Manage/SupportReceived` замість мертвого `/manage/donations`; **0 донатів на валідній сторінці — нормальний стан** (повертає `{"total": 0, "count": 0}`, статус OK) замість помилки `no_amounts_parsed`.
5. `_parse_kofi_amounts` → додано клас `transaction-row-amount` у regex.
6. [DEBUG]-логи fetch-статусів в admin.log (`[DEBUG][fetch] yt=... red=... kofi=... gh=...` у `_refresh_community_background` + `[DEBUG][fetch] tab=... -> ...` у `_community_refresh_tab`) — статуси тепер видно в логу (раніше не логувались зовсім).

Верифікація: AST OK; тест на профілі юзера: `reddit_chrome -> empty` (сесія розпізнана, 0 постів), `kofi_chrome -> {'total': 0, 'count': 0}` (сесія розпізнана, 0 донатів) — помилок `login_form_missing`/`no_amounts_parsed` більше немає. Build v1.0.23 (8.6 MB, _internal 69) через TMP-обхід; адмінка запущена (21.08). Юзер має побачити вкладки Reddit/Ko-fi зі статусом OK (0 постів/0 донатів — чесний стан, поки даних нема) замість помилок логіну.

---

## Адмінка v1.0.22 (20.08.2026): фікс регресії 1.0.21 — «термінал замість браузера»

Юзер повідомив: «Замість браузера відкрився термінал». Живий лог v1.0.21 (юзерська сесія 20:18) показав: `[DEBUG][locate] pid=16664 hwnd=919816` + `[DEBUG][embed] ok=True` — embed СПРАЦЮВАВ, але вбудував НЕ те вікно. Розбір: у v1.0.21 я «оптимізував» `_locate` — pid брався з `drv.service.process.pid`, але у Selenium `service.process` — це процес **chromedriver, а не Chrome**. chromedriver — консольний процес; selenium запускає його `Popen`-ом без `CREATE_NO_WINDOW`, тому у windowed-адмінці він отримує **видиме консольне вікно**, і `_find_hwnd_by_pid` вбудував саме його (термінал у фреймі), а Chrome лишився поза екраном. У v1.0.18 працювало, бо pid брався через `_chrome_main_pid` (PowerShell → pid саме Chrome).

**Фікс:**
1. `_locate` повернуто на `_chrome_main_pid(_COMMUNITY_PROFILE_DIR)` як єдине джерело pid (видалено `drv.service.process.pid`) — робочий шлях v1.0.18.
2. `webdriver.Chrome(..., service=Service(creation_flags=subprocess.CREATE_NO_WINDOW))` у `_community_ensure_browser_inner` — chromedriver стартує без консольного вікна взагалі (прибирає і «термінал», і мерехтіння; до речі, мерехтіння в 1.0.20/1.0.21 теж було від цього Popen).

Верифікація: AST OK; `Service(creation_flags=0x08000000)` валідний; build v1.0.22 (8.6 MB, _internal 69) — **TMP-обхід спрацював автоматично** («canonical dir locked — building into Admin_TMP_BUILD, then deploying»); адмінка запущена (23:22, «Змін не виявлено»). Чекає живої перевірки юзера: Community → у фреймі Chrome (ко-фі сторінка, НЕ термінал), повторний вхід — вбудовується знову.

---

## Адмінка v1.0.21 (20.08.2026): embed-фікси раунд 2 — правильне вікно + чистий профіль + швидкий старт

Юзер повідомив два залишкові симптоми після v1.0.20: (1) «браузер поза вікном — іконка в таскбарі», (2) «мерехтить термінал», (3) під час дебаг-тесту: «у вікні програми повідомлення про відновлення вікон, а браузер окремо маленьким вікном». Живий дебаг (smoke2: повний AdminApp + автовхід у Community з [DEBUG]-принтами) показав: embed МЕХАНІЧНО працює (SetParent ok, frame_id валідний) — у тому числі у правій колонці; тобто саме перенесення браузера вправо (v1.0.19) embed не ламає. Знайдені реальні корені:

1. **Вбудовувалось НЕ те вікно**: після аварійного вбивства Chrome (силові kill адмінки/Task Manager) профіль має `exit_type=Crashed` + залишки `Last Session`/`Current Session` → Chrome відкриває модальний діалог «Відновити сторінки?» (ігнорує `--window-position`), а `_find_hwnd_by_pid` брав ПЕРШЕ видиме вікно — діалог! У фрейм вбудовувався діалог, головне вікно лишалось окремо. Фікс: `_find_hwnd_by_pid` вибирає НАЙБІЛЬШЕ видиме вікно за площею `GetWindowRect` (діалог 400×150 ніколи не переможе головне 1400×900); `_fix_crashed_profile_prefs` додатково видаляє `Last Session`/`Current Session`/`Last Tabs`/`Last Version` → діалог взагалі не з'являється.
2. **Мерехтіння терміналу**: `subprocess.run(["powershell", ...])` у `_chrome_main_pid` (admin_app.py) та `_kill_chrome_matching` (admin_build_generator.py) БЕЗ `creationflags=CREATE_NO_WINDOW` — у frozen windowed EXE кожен запуск створює консольне вікно. Фікс: `CREATE_NO_WINDOW` в обох (як у ai_engine.py).
3. **Заблокований профіль → довгий старт**: після силових вбивств адмінки залишки Chrome тримають `community_chrome_profile` → `webdriver.Chrome()` retry 20-30с (юзер бачив іконку в таскбарі і йшов до embed). Фікс: `_community_ensure_browser_inner` тепер викликає `_kill_chrome_matching(_COMMUNITY_PROFILE_DIR)` ПЕРЕД стартом драйвера.
4. **`_locate` без PowerShell**: pid береться з `drv.service.process.pid` (Selenium), `_chrome_main_pid` — лише fallback.

[DEBUG]-принти переведені з `print` у `self._log` (admin.log) — у frozen EXE stdout невидимий; прибрати після живого підтвердження (#1463).

**build_admin.py durable fix (#1546):** невидимий хендл на `dist/SM WoT Assistant Admin/_internal` ПОВЕРНУВСЯ (WinError 32 на rmdir, запис всередину ок) — clean() тепер толерантний (`_rmtree_tolerant`: файли видаляє, заблоковану директорію лишає порожньою), а main() при заблокованій канонічній папці збирає в `dist/Admin_TMP_BUILD` і перезаписує поверх (`copytree dirs_exist_ok=True`).

Верифікація: AST OK; тест вибору найбільшого вікна (BIG 800×600 vs small 200×100 → обрано BIG); build v1.0.21 (8.6 MB, _internal 69) через TMP-обхід + деплой у канонічну папку; адмінка запущена (20:16, «Змін не виявлено»). Чекає живої перевірки юзера: Community → браузер справа (ко-фі, не діалог), ESC → вхід → знову вбудовується, мерехтіння терміналу нема.

---

## Адмінка v1.0.20 (20.08.2026): фікс embed браузера — циклічний embed + unembed + Crashed-bubble

Після v1.0.19 юзер повідомив: «Браузер стартує поза вікно програми — бачу тільки іконку в панелі завдань». Діагноз (підтверджено admin.log + поведінкою): Chrome стартує оф-скрін (-32000,-32000) і embed НЕ відбувається, вікно лишається top-level поза екраном з кнопкою в таскбарі. Два корені в embed-ланцюзі:

1. **Одноразовий embed** (`_community_poll_embed`): прапорець `embed_pending` скидався ПЕРЕД спробою, і після неї `visible=True` ставився безумовно — якщо SetParent тихо «вдавався» з `frame_id=0` (фрейм ще не замапований у новій 3-рівневій ієрархії `_comm_root→main→right→_browser_frame`, `winfo_id()`=0 → SetParent(hwnd, 0) = від'єднання, не помилка), повторної спроби НЕ БУЛО НІКОЛИ.
2. **Повторні входи**: `_exit_community` робив лише `SetWindowPos` оф-скрін — Chrome лишався `WS_CHILD`; `EnumWindows` (пошук hwnd у `_locate`) бачить тільки top-level → наступний вхід не міг знайти вікно назавжди.
3. **Бонус — «Відновити сторінки?»**: при аварійному завершенні (вбивство адмінки/Task Manager) профіль Chrome отримує `exit_type=Crashed` → при наступному старті Chrome показує модальний діалог відновлення, який ІГНОРУЄ `--window-position` і з'являється в центрі екрана поверх адмінки.

**Фікси (admin_app.py):**
1. `_embed_hwnd` — повертає `bool`: `SetParent` повертає попередній батько; `None` = фейл → `visible` не ставиться наосліп.
2. `_community_poll_embed` — циклічний embed: повторює спробу кожні 200мс, поки `winfo_id()!=0` і `SetParent` не вдасться; одноразовий `embed_pending`-гейт прибрано.
3. `_unembed_hwnd` (новий) — від'єднання `SetParent(hwnd, NULL)` + повернення `WS_POPUP`; `_community_move_browser_offscreen` викликає його перед зсувом — повторний вхід знову знаходить вікно через EnumWindows.
4. `_fix_crashed_profile_prefs` (новий) + `--disable-session-crashed-bubble` — профіль з `exit_type=Crashed` переписується на `Normal` перед стартом драйвера; діалог відновлення не з'являється.
5. [DEBUG] принти в `_locate`/`_community_poll_embed`/`_embed_hwnd` — тимчасово, до живого підтвердження (#1463).

Верифікація: ast OK; ізольований smoke механіки embed (без Chrome/fullscreen): embed#1 ok=True → unembed → embed#2 ok=True → PASS. Білд `build_admin.py` → 8.6 MB, `_internal` 69; адмінка перезапущена (19:14, «Змін не виявлено»). Чекає живої перевірки юзера (Community → браузер справа, ESC → знову Community).

---

## Адмінка v1.0.19 (20.08.2026): Community Workspace — браузер справа + Errors tab + 401-фікс Installations

Білд: `python build_admin.py` — PyInstaller onedir (`SM WoT Assistant Admin.exe` 8.6 MB, `_internal` 69 entries, guard PASSED), версія з `admin_version.txt` (1.0.19). `build_admin.py clean()` цього разу СПРАЦЮВАВ — невидимий хендл на `dist/SM WoT Assistant Admin/` (#1546) розблокувався після вбиття запущеної адмінки; in-place деплой не знадобився. Адмінка перезапущена: «Танків: 995, Промптів: 996», «Змін не виявлено».

**Що зроблено:**
1. **Браузер справа** (`admin_app.py:_build_community_ui`): замість вертикального паку всього в `_comm_root` — горизонтальний спліт `main` (grid): ліва колонка (hdr + tiles + Notebook + banner, weight 3, minsize 480) і права (`_browser_frame`, weight 2, minsize 480). Embed-ланцюг (`_community_poll_embed`/`_on_browser_frame_configure`/`_sync_browser_geometry`) читає розміри з `_browser_frame` через winfo — позиційно незалежний, без змін. Верифікація (#1463): smoke-геометрія на 1440×900 — left 892px / right 518px / browser_frame 518×886 (скриншот 22KB).
2. **Errors tab** (нова вкладка після API Keys): Treeview (time/type/source/version/error, width dict розширено), Refresh-кнопка + статус, `_fetch_errors_list()` — `error_reports` з `&orderBy="timestamp"&limitToLast=200`, сорт за timestamp desc, останні 200. Оновлення в `_refresh_community_background` + `_community_refresh_tab("errors")`. Tile Errors тепер відкриває вкладку Errors (було overview). Нові i18n ключі: `tab_errors`, `col_time`, `col_source`, `col_version`, `col_error` — `_TR_EN` + `admin_uk_seed.json` (en_snapshot + uk, 192/192 без дифів).
3. **Installations = 0 → 401 фікс** (`_fetch_installations`): `installations/` потребує auth!=null (правила #1529) — read через `admin_auth._rtdb_url_with_token()` (додано `import admin_auth`). Жива перевірка: 264 інсталяції + розбивка по версіях. Без `admin_creds.json` → None → tile «—» (не брехливий 0).
4. **Знайдено і виправлено сусідній баг**: `_cleanup_old_error_reports()` і `_fetch_errors_list()` конкатенували query з `?`, а `_rtdb_url()` вже повертає `?auth=KEY` → RTDB 400 «orderBy must be defined» → автоочищення error_reports старших 60 днів ТИХО не працювало (перші спроби cleanup 400-ились). Фікс: `&orderBy=...`. Підтверджено: запит тепер повертає 59 записів.

---

## Реліз v1.0.71 Alpha (19.08.2026, повний цикл build.py)

Збірка: `python build.py 1.0.71` — PyInstaller (Python 3.12.7, onedir) → copy_data_files (3131 файли) → verify.json (30 танків) + popular_tanks_seed → launcher 35.8 MB (bundle verification PASSED: tcl86t/tk86t/_tkinter) → tray watcher 7.1 MB → NSIS installer 225.8 MB (`SM_WoT_Assistant_Setup_v1.0.71_Alpha.exe`) → portable ZIP 246.9 MB → verification PASSED (52 maps, 68 extracted_maps, 1246 icons) → manifest → **GitHub release v1.0.71 Alpha** (audit PASSED) → RTDB publish (HTTP 200, latest pointer оновлено, audit PASSED).

**Що увійшло в реліз (від v1.0.70):**
1. **Фікси бою** (937ee7d): стейт-машина бою в LogWatcher (`_battle_active` — hangar без бою/дублікат/reset більше не дає хибний battle_ended), скасування пендінгу повернення в edit при новому бою, `toggle_editor` перезаписує позицію (самолікування race), unhide-fallback на countdown (вікно завжди показується з трею перед боєм), drag-race: `save_settings` через `after(0)` + скасування drag при зміні режиму.
2. **Палітра — Download-діалог** (3fc980d, c4e6eaf): список над груповими кнопками (логіка вікна), фіксована висота списку зі скролом (`pack_propagate(False)`, `dl_h = min(320, max(180, (sh-40) - base_h))`), вікно не виходить за екран — кнопки групових схем завжди видимі.
3. **Фокус після малювання + персистенція товщини/розміру** (2bbea59): після створення елемента виділення лишається на ньому, Escape/ЛКП на порожньому знімає; `draw_thickness`/`draw_size` запам'ятовуються в settings.
4. **Сайт**: скриншот вікна малювання (`img/draw.webp`), рядок про підтримку всіх мов гри; задеплоєно на Firebase Hosting.

**Release Cleanup Protocol (#1497) після релізу:** локально dist/ — видалено v1.0.66 (лишились v1.0.67–v1.0.71); GitHub — видалено release v1.0.66 (лишились 5 останніх); RTDB versions/ — PUT null для 1_0_66 (лишились 1_0_67–1_0_71 + latest).

---

## Виконано 19.08.2026: мови на сайті + скриншот вікна малювання + фокус після малювання + персистенція товщини/розміру

1. **Сайт — всі мови гри**: `public/index.html` (підрядок під підзаголовком: "Supports ALL World of Tanks client languages — the app automatically detects your game language") + `reddit_post.md` (рядок з 🌍).
2. **Скриншот вікна малювання**: користувач надав `D:\!WORK\WOT\WOTtraner\IN\Foto\Draw.png` (580×545) → сконвертовано PIL у `public/img/draw.webp` (17.5KB, WEBP quality=85) → картка "Drawing window" в галереї `public/index.html` (після TACTIC, перед Overlay) з описом про фокус/Escape/персистенцію.
3. **Фокус після малювання** (`painter.py` + `painting_palette.py`):
   - `painter.py:674` — після створення об'єкта в `on_release` викликається `_edit_object_at(len(drawings)-1)` — виділення/редагування лишається на намальованому елементі (замість старого `_deactivate_tool()` + показу палітри без виділення).
   - Escape знімає виділення: `painter.py:151` bind `<Escape>` на обох канвасах → `on_escape_deselect` → `palette.exit_edit_mode()`; палітра теж має власний `<Escape>` bind (`painting_palette.py:73`).
   - ЛКП на порожньому місці — вже існувало (`painter.py:261-268`: клік по об'єкту = edit, по порожньому = `exit_edit_mode()`).
4. **Персистенція товщини/розміру**:
   - `painter.py:50` — `_thickness = int(settings.get("draw_thickness", 3))`.
   - `painting_palette.py:59-62` — `_thickness_var`/`_size_var` ініціалізуються з `settings.draw_thickness`/`draw_size`.
   - `_on_thickness_change`/`_on_size_change` пишуть у `app.settings` + `_save_draw_prefs()` → `app.save_settings()`; гвард `_loading_obj` не дає перезаписати налаштування при завантаженні об'єкта в палітру.
   - Нові об'єкти отримують збережені значення: `"thickness": self._thickness` (`painter.py:638`) + `obj["scale"] = self._size_var.get()` через `_write_to_object` (`painting_palette.py:1537, 1565`).
   - **Верифікація (#1471/#1584)**: ast-parse painter.py/painting_palette.py/main.py OK; isolated smoke-тести — відновлення thickness з settings (7), flow on_release → створення → apply_to_new_object(thickness=7, scale=2.0) → load_object → show → `_editing_idx=0`, палітра `_on_thickness_change`/`_on_size_change` → settings + save_settings + гвард `_loading_obj` (7 залишається при завантаженні).

---

## Фікси бою та палітри (19.08.2026): стейт-машина бою, race позиції edit, unhide-fallback, обрізання групових кнопок

**Звіти користувача:** (1) іноді з трею бій стартує, а вікно редагування перед боєм не показується; (2) одного разу після ручного запуску програми edit-вікно "впало" на місце бойового (низ-праворуч); (3) мерехтіння перемикань при завантаженні гри; (4) у палітрі при відкритті Download кнопки групових схем знизу обрізаються.

**Факти з python.log користувача (16 боїв, 18-19.08):** патерн ідеальний `арена → h42 (hangar, 1 лінія) → арена` — дублікатів hangar-ліній НЕМАЄ, фікс b5abb58 працює. АЛЕ перша лінія сеансу гри (рестарт python.log) = hangar → хибний `on_battle_ended` з `last_battle_map` з пам'яті → несподіване перемикання в edit на старті гри. Ре-queue мінімум 21с — race after(200) не підтверджено, але клас закрито.

**Корінь проблеми (1)-(3):** `LogWatcher` фірив `on_battle_ended` на КОЖНУ hangar-лінію без стейту бою — хибні battle_ended на старті гри (reset файлу) та при дублікатах hangar. Дрейф позиції edit (2): `save_settings()` викликався з фонового drag-потоку — race зі зміною `self.mode` під час `toggle_editor` записував бойову позицію в `edit_x/edit_y`. Непоказ edit-вікна (1): unhide робив ТІЛЬКИ `on_battle_detected` (arena-лінія) — при загубленій лінії вікно лишалось у треї до countdown, який вікно не показував.

**Фікси:**
1. **log_reader.py — стейт-машина бою:** `_battle_active` (арена → True, hangar → fire `battle_ended` тільки якщо був бій; hangar без бою / дублікат / reset — тихо скидає стан); countdown фіриться лише при `_battle_active`.
2. **main.py:** `_battle_edit_return` — `on_battle_detected` скасовує пендінг `after(200)` повернення в edit; `toggle_editor` після `geometry()` перезаписує `edit_x/y/cx/cy` (або norm_) актуальними значеннями (самолікування race-мусору); **unhide-fallback** — `on_battle_countdown_started` показує вікно з трею (`_restore_from_tray` + `_restored_by_battle=True`), якщо arena-виявлення не встигло.
3. **window_manager.py:** кінець drag → `root.after(0, save_settings)` (не з фонового потоку); `_drag_mode` — drag прив'язаний до режиму початку, при зміні `mode` скасовується (Alt+ЛКМ hook — той самий захист).
4. **painting_palette.py:** `_show_download_dialog` — висота за контентом `target_h = min(max(winfo_reqheight(), 780), screenheight - 120)` замість жорсткого `580x780` — групові кнопки завжди видимі (DPI-масштабовані дисплеї), список скролиться.

**Верифікація (#1471):** ast-parse 4 модулів OK; smoke-тести стейт-машини на реальному LogWatcher: старт гри (hangar → без detected/ended), бій (detected→countdown→ended ×1), дублікат hangar (h42+hangar_v4 → ended ×1), countdown без арени (без фірингу), ре-queue (2 бої → 2 ended, 2 countdown); формула висоти палітри (3 кейси). [BATTLE]-принти розширені прапорами (`hidden`, `mode`, `unhide_on_battle`) для живого підтвердження перемикань юзером.

### Доповнення: Download-діалог остаточно (перевірка юзера, той самий день)

Перший фікс виявився неповним — юзер побачив: "видно тільки напис Групові схеми, кнопки обрізаються, кнопки Download/Cancel видавлюють меню груп". **Корінь:** `req_h` вимірювався з ПОРОЖНІМ `download_frame` (список будується асинхронно через `after(0)`), а `_build_download_ui` потім додає фільтри + tree + **ряд кнопок Download/Cancel** (~280px) — повний контент перевищує вікно → pack зрізає найнижчі елементи = групове меню.

**Фінальне рішення (після відхилення юзером перестановки `after=group_mgmt` — "кнопки групових схем повинні бути в низу палітри щоб зберегти логіку цього вікна"):**
- `download_frame` знову пакуються **над** групами (`before=self._status_lbl`) — логіка вікна збережена
- **`pack_propagate(False)` + фіксована висота** списку: `dl_h = min(320, max(180, (screenheight - 40) - base_h))` — фільтри + tree + кнопки Download/Cancel скроляться **всередині** своєї зони (tree має scrollbar) і не роздувають вікно
- `_resize_for_download()` переписаний: `target_h = min(base_h + dl_h, screenheight - 40)` де `base_h` = висота палітри БЕЗ списку (включно з групами, виміряна з порожнім download_frame) — **групи завжди в межах вікна на будь-якому DPI/екрані**; вікно піднімається якщо виходить за екран
- після-наповнення перерахунок (`after(50)` у `_build_download_ui`) прибрано — висота списку фіксована, перерахунок більше не потрібен
- **Верифікація:** емпіричний тест у пам'яті (реальна палітра + mock-список з 20 рядками + кнопки Download/Cancel): `list above groups: True (892 <= 920)`, `groups visible: True (973 <= 978)`, вікно в межах екрана, компактна геометрія (580x549) відновлюється при закритті

---

## Фікси Community Workspace: embed браузера з потоку + вставка в поля API-ключів (19.08.2026, адмінка v1.0.18)

**Звіти користувача:** (1) вікно браузера не видно у вікні адмінки — висить на панелі завдань, перемкнутись неможливо; (2) неможливо вставити API-ключі з буфера обміну у відповідні поля.

**Корінь проблеми №1 (підтверджено admin.log):** рядок `Помилка фона: main thread is not in main loop` одразу після `Community: browser started`. `_community_show_browser()` викликався з **фонового демон-потоку** (через `_community_ensure_browser` → `_refresh_community_background` / `_community_refresh_tab` — всі fetch-шляхи працюють у daemon-потоці), а всередині робив Tkinter-виклики `winfo_id()/winfo_width()/winfo_height()`. Це кидало `RuntimeError: main thread is not in main loop`, яке ковталося голим `except Exception: pass` — embed тихо не відбувався. Chrome лишався оф-скрін (-32000,-32000), видимий на панелі завдань, і як окреме top-level вікно перехоплював фокус клавіатури → поля API-ключів не отримували Ctrl+V (проблема №2).

**Фікс (admin_app.py):**
1. `_community_show_browser()` переписано — тепер thread-safe: важкий пошук HWND (PowerShell/ctypes) виконується у worker-потоку `_locate`, який лише виставляє прапорець `embed_pending`; жодних Tkinter-викликів з фонового потоку.
2. Новий `_community_poll_embed()` — виконується на головному потоці через `root.after(200, ...)`: робить embed (`_embed_hwnd` + winfo-виклики), ставить `visible=True` лише після успіху і зупиняється; перезапускається на кожному `_enter_community`.
3. `_enter_community()` тепер активно запускає браузер (thread `_community_ensure_browser(True)`), якщо driver ще не створений — раніше браузер стартував лише лазі-фетчем, і при вході з трея фрейм був порожній.
4. Гвард `creating` у `_community_ensure_browser()` — серіалізація створення driver (два потоки більше не створюють два webdriver.Chrome з тим самим профілем).
5. У кінці створення driver embed викликається якщо `visible or fs` (раніше лише `visible`).

**Фікс проблеми №2:** новий `_bind_entry_menu()` — ПКМ-контекстне меню Cut/Copy/Paste/Select All для всіх полів вкладки API Keys (патерн ui_manager.py:564-575 головної програми). Плюс нові i18n-ключі `menu_cut`/`menu_paste` у `_TR_EN` та `admin_uk_seed.json` (en_snapshot + uk).

**Верифікація (#1471, #1584):**
- ast-parse admin_app.py, json.load обох seed-файлів, юніт-тест дифа `_load_uk_translations` (2 нові ключі детектуються)
- Живий smoke (Python 3.12, головний потік у mainloop): `_enter_community()` → Chrome стартує → HWND знайдено → **GetParent(hwnd) == frame_id** (вбудовано!) → `visible=True`; вихід та повторний вхід — re-embed також успішний (embed2=True)
- `_bind_entry_menu`: кожне Entry поля API-ключів має `<Button-3>` біндінг
- Тестові процеси прибрані (Chrome community-профілю не лишилось), мутекс-поведінка при запущеній старій адмінці підтверджена (exit 0)

**Збірка:** admin_version.txt → 1.0.18 (#1446), `python build_admin.py` (перед цим убити запущену адмінку).

---

## Community Workspace в адмінці — плитки, вбудований Chrome, статистика, DPAPI-vault (18.08.2026, адмінка v1.0.17)

**Що зроблено:** новий розділ в адмінці (admin_app.py, 1104 → 2389 рядків) + новий модуль admin_vault.py.

1. **Плитки** в головному вікні (YT views | GH downloads | Ko-fi | Installs | Errors) + помаранчеві хінт-повідомлення коли канал потребує підключення (`needs API key` / `needs login` / `blocked` / `action needed`); клік → повноекранний Community-режим.
2. **Повноекранний режим** (кнопка Community / ESC вихід): плитки + 6 вкладок (Overview / YouTube / Reddit / GitHub / Ko-fi / API Keys) + червоний банер дій + **вбудований браузер**: Selenium-Chrome з постійним профілем `%APPDATA%/SM WoT Assistant/community_chrome_profile/` (сід 1 раз з реального профілю, логини переживають рестарти), у fullscreen вшивається через `SetParent` + WS_CHILD у frame адмінки — жодних окремих вікон; у треї Chrome не працює (kill при мінімізації).
3. **Ланцюг джерел**: YouTube API (key з vault) → Chrome `ytInitialData` (новий 2026 формат `lockupViewModel` + legacy `videoRenderer`); Reddit `submitted.json` → Chrome (сесія-чек + автологін, CAPTCHA → дія); Ko-fi Chrome автологін → best-effort парс донатів; GitHub публічний API; RTDB лічильники (installations по версіях, errors, schemes, users, builds/version).
4. **admin_vault.py** — Windows DPAPI-сховище (`CryptProtectData`/`CryptUnprotectData`, ctypes), файл `admin_vault.json` в AppData, service→field, розшифровка на вимогу, ніколи не логується. Вкладка API Keys: YouTube key, Reddit username/password, Ko-fi email/password/client_id/secret/refresh_token (масковані "•••", порожнє поле = видалити) + Reset browser data. Firebase admin_creds.json не зачіпається (рішення користувача).
5. **Потік дій**: детект капчі/логін-форми → трей-балун + червоний банер + хінт плитки → адмін розв'язує у вбудованому браузері → продовження (поллінг на наступному циклі).
6. **i18n**: +83 ключі в `_TR_EN` (185), `admin_uk_seed.json` — 183 UK + свіжий en_snapshot (нуль Google-запитів на свіжій інсталяції).
7. **Верифікація (#1471)**: ast + метод-аудит (0 missing), юніт-тести парсерів (обидва формати ytInitialData, shreddit-post, kofi, `_parse_views` EN/UK/RU) + vault round-trip, живий smoke (Python 3.12): fullscreen 6 вкладок → SetParent hwnd вбудовано → YouTube сторінка + ytInitialData → GitHub 6 downloads → Reddit грейс `needs_reddit_creds` → yt chrome fetch 1 відео (12 переглядів) → чистий kill.
8. **Збірка**: admin_version.txt → 1.0.17, `python build_admin.py`.

**Примітки для майбутніх сесій:**
- YouTube 2026: канал-вкладка /videos віддає `lockupViewModel` (title в `metadata.lockupMetadataViewModel.title.content`, статистика в `contentMetadataViewModel.metadataRows[*].metadataParts[*].text.content`, videoId з thumbnail `/vi/{id}/`), старий `videoRenderer` підтримується для сумісності.
- Смок-тести адмінки ганяти Python 3.12 (`C:\Users\PRO\AppData\Local\Programs\Python\Python312\python.exe`) — selenium 4.41 стоїть там, а `.venv` (3.14) його не має.
- Reddit публічний `.json` зараз блокується (Content-Type HTML) — Chrome-шлях з логіном обов'язковий; статус грейс-стану перевірено живим запуском.
- Ko-fi парс — best-effort (`class*="amount|donation"` + валюта); якщо дашборд змінить структуру — статус `no_amounts_parsed`, налаштувати під живе (потрібен вхід з креденціалами користувача).
- `community_chrome_profile` може розростатись — кнопка Reset browser data на вкладці API Keys.

---

## Спонсорство: Ko-fi + Monobank банка (17.08.2026)

**Рішення:** Reddit API відмовив у доступі (не вписуємось у політику); Buy Me a Coffee та GitHub Sponsors **не працюють для України** (BMC — тільки Stripe-виплати, України немає в списку; GH Sponsors — Ukraine на waitlist, підтверджено в github discussion #67578). PayPal.me відсутній (обмеження для України).

**Вибрано:** Ko-fi (виплати через PayPal — працює в Україні) + Monobank банка (приймає картки всього світу).

**Зміни:**
- `.github/FUNDING.yml` (новий) — `ko_fi: smwotassistant` + `custom: ["https://send.monobank.ua/jar/WqyWjTRpy"]` — кнопка Sponsor у репо
- `public/index.html` — секція "Support the project": Ko-fi віджет (`kofiwidget2`, офіційний скрипт storage.ko-fi.com) + картка Monobank з QR-кодом (`public/img/qr_monobank.png`, згенерований через api.qrserver.com, 600×600)
- `public/img/qr_monobank.png` (новий) — QR на банку WqyWjTRpy
- `reddit_post.md` — секція "☕ Support" (Ko-fi, банка, QR) — для ручної публікації в браузері (API немає)
- Деплой hosting (#1303), main fast-forward + push — FUNDING.yml на default гілці

**Перевірка:** сайт віддає секцію Support + Ko-fi + QR (200 OK), FUNDING.yml у main через GitHub API (75 байт), дерево чисте на api-integration (b96e105).

**Доповнення (17.08.2026, коміти 21cf183, 2a99427, ee35a18):**
- Ko-fi віджет оновлено: `kofiwidget2.init('Support me on Ko-fi', '#f26900', 'T0T1258SJ2')` (ID сторінки з дашборду; vanity-URL лишається `smwotassistant`)
- Картка PayPal: `public/img/paypal_qr.png` (з `D:\!WORK\WOT\WOTtraner\IN\PayPalQR.png`, QR згенерований самим застосунком PayPal — акаунт nkc@ukr.net)
- QR Ko-fi: `public/img/qr_kofi.png` (api.qrserver.com, 600×600) — тепер усі 3 картки мають QR
- Footer: посилання на Reddit профіль `reddit.com/user/SM-WoT-Assistant` (живий, HTTP 200)
- `reddit_post.md` — 3 QR у секції Support (Ko-fi, Monobank, PayPal); комплект PNG для ручної публікації: `%TEMP%\opencode\reddit_upload\` (5 скріншотів + img_qr + img_kofi + img_paypal)
- Кнопку "Watch on YouTube" видалено з сайту (iframe відео лишився) — ee35a18
- Всі зміни сайту задеплоєні та перевірені (200 OK)

---

## Перенесення репозиторію в організацію SM-WoT-Assistant (17.08.2026)

**Зміна:** репозиторій перенесено з `nkcgml-boop/SM-WoT-Assistant` в організацію `SM-WoT-Assistant/SM-WoT-Assistant` (GitHub автоматично редиректить старі URL — старі посилання не зламались).

**Переналагодження (виконано):**
- `git remote set-url origin https://github.com/SM-WoT-Assistant/SM-WoT-Assistant.git`
- `build.py:747,869,928` — hardcoded GitHub шлях у `verify_release_artifacts()` / `audit_rtdb_entry()` / `write_version_to_rtdb()` замінено на новий (AST OK)
- `public/index.html:63,145` — кнопка Download + `GITHUB_RELEASES` → задеплоєно (`firebase deploy --only hosting`, сайт віддає новий URL)
- `docs/release.md:78` — команда Release Cleanup Protocol оновлена
- `reddit_post.md` — посилання оновлено (untracked)

**Не потребувало змін:** RTDB `versions/` (старі `download_url` валідні через redirect, нові білди запишуть новий шлях), лаунчер/auto-update (читає `download_url` з RTDB), asset-імена.

**Перевірка:** `gh api` — репо в організації (public, main, релізи v1.0.66–v1.0.70 на місці), сайт віддає новий URL, старого `nkcgml-boop` у дереві не лишилось.

---

## Реліз v1.0.70 Alpha (16.08.2026)

**Реліз:** повний цикл build.py (PyInstaller → NSIS → ZIP → verify → manifest → GitHub release → RTDB publish + аудити 4 фаз) — PASSED.

**Вміст релізу:**
- `339d896` — старт бою з трею: завжди вікно редагування + Tk тільки в main-потоці (фікс мерехтіння)
- `d4ccc92` — фікс блимання термінала під час інсталяції (nsExec::ExecToStack)
- `8a6fac7` — bump VERSION → 1.0.70 (авто-коміт build.py), тег `v1.0.70` (пуш)
- `265fa2a` (Beta→Alpha), `9cf8f69` (сайт: скріншоти+lightbox, задеплоєно раніше)

**Передбілдна перевірка (#1471):** AST-parse main.py + LogWatcher smoke (4 бої) + dev smoke ×3 (`python main.py`: старт чистий, splash → трей, стабільний 4+ хв, stderr порожній) — PASSED.

**Release Cleanup Protocol (#1497):** лишились 5 останніх — v1.0.66–v1.0.70: dist/ (папки + Setup/Portable/manifest), GitHub релізи (v1.0.65 видалено, тег лишається), RTDB versions/ (1_0_65 — PUT null адмін-токеном через `admin_auth._rtdb_url_with_token`; API-ключ → 401 після правил #1529 — клієнтським ключем видалення неможливе).

**Адмінка:** не мінялась (v1.0.16) — перезбірка не потрібна.

---

## Фікс старту бою з трею: вікно редагування + прибирання мерехтіння (16.08.2026, раунд 2)

**Скарга (вдруге за день):** мерехтить з одного режима на інший, коли ще завантажується гра — не повинно бути ніяких перемикань; і після фіксу b5abb58 (раунд 1) перестала показувати вікно редагування після початку бою, коли програма відкривається із згорнутого стану.

**Очікувана поведінка (спека користувача, #1561):** згорнутий → старт бою → вікно редагування → бойове вікно перед самим боєм → згорнутий по завершенню бою. Якщо програма перед боєм у режимі редагування — поведінка випливає з цього стану.

**Докази (реальний python.log користувача, 16.08, 8 боїв):** `Loading space: spaces/XX` (T0) → `WaitingSpace→BattleLoadingSpace` (T0+2с) → `BattleLoadingSpace→BattleSpace` + `arena period: 2` (T0+12-15с = старт відліку) → бій → `BattleSpace→WaitingSpace` → `Loading space: spaces/h42_Wot_Bday_2026` (+15с, hangar). Налаштування користувача: `start_minimized=true, unhide_on_battle=true, auto_battle=true`.

**Кореневі причини (2 баги):**
1. **Зникло вікно редагування:** b5abb58 прибрав `toggle_editor` на детекті. Після 1-го бою програма згортається в норм-режимі (туди її перекинув відлік), і на 2-му+ бою розгортається вже в бойовому вікні — вікно редагування більше ніколи не з'являється. Зламаний проєктний ланцюг 0ba70f5 «edit на старті → norm на відліку».
2. **Мерехтіння:** `on_battle_detected` викликав `_restore_from_tray()` напряму з потоку LogWatcher (main.py:1372) — важкі Tk-операції (deiconify/lift/focus_force/show_view з update_idletasks, операції оверлея) ганялися з Tk mainloop (tkinter не thread-safe) → нестабільний стан вікна. Всі інші колбеки бою вже робили `root.after(...)` — цей єдиний був прямим.

**Фікс (мінімальний диф, тільки main.py):**
- `main.py:1380` — `self._restore_from_tray()` → `self.root.after(0, self._battle_restore_from_tray)` (усі Tk-операції в головному потоці — race прибрано).
- `main.py:1041` — новий метод `_battle_restore_from_tray()`: `_restore_from_tray()` + `if self.mode != "edit": self.toggle_editor()` — старт бою з трею ЗАВЖДИ показує вікно редагування з картою бою, незалежно від режиму, в якому програму згорнули. Видимі norm-користувачі не зачіпаються (restore-шляху немає → фліпу немає → подвійне мерехтіння раунду 1 не повертається).

**Підсумкова поведінка:** згорнутий → старт бою → **вікно редагування** (карта бою) → відлік (~12с, «перед самим боєм») → **бойове вікно** → кінець бою → згорнутий. Видимий edit-користувач: edit → відлік → norm → після бою → edit (без змін). Норм-користувач — без змін.

**Верифікація (#1471):** AST-parse main.py OK; LogWatcher smoke-тест (синтетичний лог: 4 бої, включаючи той самий мап-повтор, event-hangar h42/h33, hangar_v4, fallback-маркер `arena period: 2` без BattleSpace) — arena рівно 1× на бій, countdown 1× на арену (dedup працює), hangar 4×, event-hangar НЕ детектиться як арена — PASSED. Прямих Tk-викликів у потоці watcher не лишилось (статична перевірка). Жива перевірка повного циклу — гра користувача.

---

## Фікс блимання термінала під час інсталяції (16.08.2026)

**Скарга:** під час інсталяції блимає термінал.

**Діагноз:** `installer.nsi:31` — `ExecWait 'taskkill /f /im "SM WoT Assistant Tray Watcher.exe"'`. `taskkill.exe` — консольна програма, а NSIS `ExecWait` запускає її у видимому консольному вікні → чорне вікно блимає на початку інсталяції. Інші кандидати виключені: головний EXE `console=False` (wot_assistant.spec:117), Launcher/Tray Watcher `--windowed` (build.py:372, 443), uninstall-секція без консольних викликів.

**Фікс:** `ExecWait` → `nsExec::ExecToStack` (стандартний плагін NSIS, перевірено `Plugins\x86-unicode\nsExec.dll`): прихований запуск консольної програми + синхронне очікування (File /r має побачити трей-вочер мертвим).

**Рішення користувача:** реліз v1.0.69 НЕ перезбирається і не змінюється — перевірка фіксу на наступному релізі.

---

## Перехід Beta → Alpha у всіх релізах (16.08.2026)

**Рішення користувача:** напис "Beta" замінюється на "Alpha" у цьому та всіх наступних релізах.

**Змінені файли (8):**
- `config.py:19` — `load_version()` повертає `" Alpha"` замість `" Beta"` (заголовки вікон → "SM WoT Assistant v1.0.69 Alpha")
- `build.py` — механічний rename `is_beta` → `is_alpha`; `" Beta"` → `" Alpha"` (GitHub release title `v1.0.69 Alpha`, RTDB `display_version`); `_Beta` → `_Alpha` (назви installer/portable: `SM_WoT_Assistant_Setup_v1.0.69_Alpha.exe`); `--prerelease` лишається True (Alpha = prerelease); змінні в snake_case (`alpha_exe`/`alpha_zip`/`alpha_suffix`); докстрінг почищено від застарілого `--beta`
- `launcher.py:88` + `main.py:2468` — regex EXE-імен приймає `(?: Beta| Alpha)?` (легасі-сумісність; реальні EXE завжди чисті)
- `firebase_reporter.py:304` — коментар (код `split()[0]` працює з будь-яким суфіксом)
- `AGENTS.md:54`, `ARCHITECTURE.md` (5 місць), `STRUCTURE.md` (2 місця) — документація оновлена

**Верифікація (#1471):** AST-parse 5 модулів OK; regex-тест 4 кейсів OK; `load_version()` → "1.0.68 Alpha"; кирилиця в коментарях не пошкоджена (0 replacement chars). BOM, доданий PowerShell-ом при write, видалено.

**Реліз:** v1.0.69 Alpha — повний цикл build.py (GitHub release + RTDB publish) + Release Cleanup Protocol (#1497).

---

## Сайт: скріншоти секцій замість текстових карток + lightbox (16.08.2026)

**Зміни на `public/index.html` (задеплоєно на Firebase Hosting):**
1. Секцію Features (4 текстові картки SETUP/MAPS/TACTIC/Overlay) **видалено** — на її місці секція **Screens** з 5 блоками (зображення + заголовок + опис англійською):
   - `img/start.webp` → Start (загальний опис програми)
   - `img/setup.webp` → SETUP (без згадки ШІ-інструментів)
   - `img/maps.webp` → MAPS
   - `img/tactic.webp` → TACTIC + посилання `<a href="https://wotmapsbyyaya.com/maps">` (джерело карт)
   - `img/minimap.webp` → Overlay (бойовий режим)
2. **Lightbox без бібліотек**: клік по зображенню → затемнений оверлей (max 92vw/92vh), клік/Esc → закриття. Зображення з `loading="lazy"` + `width/height` (без стрибків лейауту).
3. **WebP замість PNG** (стиснення PIL, quality=82, method=6): 5 файлів ~4 MB → ~410 KB (start 36KB, setup 68KB, maps 117KB, tactic 126KB, minimap 63KB). Оригінали PNG лишились недоторканими в `D:\!WORK\WOT\WOTtraner\IN\Foto`. WebM — відеоформат, для статичних знімків використано WebP.
4. Видалено невикористані CSS-класи `.features`/`.feature-card`.
5. Верифікація після деплою: index 200, всі 5 webp віддаються як `image/webp`, посилання на wotmapsbyyaya.com присутнє.

---

## Фікс івент-хангара + стабілізація авто-перемикання бою (16.08.2026)

**Скарга користувача:** 1) авто-перемикання в бойовий режим на початку бою іноді мерехтить; 2) якщо програма згорнута в трей і розгортається з початком бою, то після бою має повертатись у згорнутий режим — а зараз повертається в режим редагування.

**Діагноз (2 кореневі причини):**
1. **Івент-хангар ламає hangar-детект** — клієнт з 14.08.2026 грузить хангар як `Loading space: spaces/h42_Wot_Bday_2026` (святковий хангар), а не `spaces/hangar`. `hangar_re` ніколи не матчився → `on_battle_ended` не викликався → `_restored_by_battle` лишався True → програма ніколи не поверталась у трей. Гірше: `arena_re` матчив `h42_Wot_Bday_2026` (гвард `startswith("hangar")` його не ловив) → повернення в хангар трактувалось як бойова арена → `on_battle_detected("h42_Wot_Bday_2026")` → `toggle_editor` (mode=="norm") → EDIT MODE. Це і є «повертається у режим редагування».
2. **Потрійний повний ребілд UI на старті бою** — `safe_battle_sync` → `switch_to_maps(2)` → `show_view("maps")` (повна перебудова навіть коли вже в maps-в'ю) + `toggle_editor` на детекті (norm→edit) + `toggle_editor` на відліку (edit→norm) = 2-3 повні перебудови зі зміною геометрії та альфа-спалахом за ~11 секунд. «Іноді» = коли користувач у norm-режимі на момент детекту.

**Зміни:**
1. **log_reader.py:24** — `hangar_re` → `r"Loading space: spaces/(?:hangar\w*|h\d+_\w+)"` (покриває hangar, hangar_v4, hangar_v4_last_stand, h33_comp7, h33_battle_royale_2021, h42_Wot_Bday_2026 — всі підтверджені в map_data.json + python.log; реальні арени завжди починаються з цифри — перевірено по всіх 67 просторах).
2. **log_reader.py:122** — гвард арени: `not (map_id.startswith("hangar") or re.match(r"h\d+_\w+", map_id))` — без цього h42 все одно летів би в `on_battle_detected` (арена-гілка виконується після hangar-гілки для того ж рядка).
3. **main.py `on_battle_detected`** — прибрано `toggle_editor` на детекті: norm-користувачі лишаються в norm (оверлей вже показує карту бою через safe_battle_sync), edit-користувачі лишаються в edit; єдиний світч — на відліку (countdown → norm), як задумано в 0ba70f5 «auto-battle edit->norm sequence».
4. **main.py `safe_battle_sync`** — `switch_to_maps(2)` лише якщо не `active_view=="maps" and map_mode==2` (прибирає зайвий повний ребілд при кожному детекті; список мап при зміні режиму бою оновлюється через trace `_on_battle_mode_changed` → `load_map_list`).

**Верифікація (#1471, до змін):** AST-parse 4 модулів чистий; ізольований тест regex на 7 реальних рядках python.log (6 арен — без змін, h42 — hangar замість арени); класифікація всіх 67 просторів map_data.json — 0 конфліктів. Після змін: AST чистий, smoke-тест LogWatcher на темповому логу (бій → h42-хангар → новий бій) — hangar-подія настала, фальшивої арени для h42 немає, ланцюг наступного бою не зламаний. Тестовий лог видалено.

---

## Зламаний dist-бандл адмінки + гвард перебірки (адмінка v1.0.16, 13.08.2026)

**Проблема:** адмінка не запускалась — bootloader: `Failed to load Python DLL '...\dist\SM WoT Assistant Admin\_internal\python312.dll'. LoadLibrary: Не найден указанный модуль`.

**Діагноз (прямий огляд файлів):** `dist\SM WoT Assistant Admin\_internal` — порожній (0 файлів, 0 МБ); EXE в dist — старий білд (13.08 0:33:16, 8 967 927 Б), тоді як останній успішний збір v1.0.15 (EXE 03:53:28, 8 973 177 Б) існував лише в робочому каталозі `build\admin_app\...` — результат у dist не долетів. Це продовження інциденту v1.0.14/v1.0.15: dist був заблокований невидимим хендлом (WinError 32 на rename/delete, ймовірно AV-мініфільтр) → попередні збірки йшли в `%TEMP%\opencode\admin_build14\` і `admin_build15\`; часткова спроба clean()/COLLECT лишила `_internal` вичищеним (mtime 1:04:58) при старому EXE. «Успішні» запуски 01:05/03:53 (admin.log) були саме з %TEMP%-копій; автозапуск HKCU\Run → dist → фейл bootloader.

**Зміни:**
1. **Перебірка v1.0.16** — лок зник (clean() пройшов повністю): `dist\SM WoT Assistant Admin` тепер повний — `_internal` 1192 файли / 179.2 MB, python312.dll присутній, бандл `_internal\admin_version.txt` = 1.0.16.
2. **Гвард у build_admin.py** (`build_admin_exe`, після перевірки EXE): `_internal` має існувати, бути непустим і містити `python312.dll`, інакше `[BUILD] FATAL` + exit(1); при успіху друкує `Admin EXE: X MB, _internal: N entries`. Зламаний COLLECT більше не лишиться непоміченим.

**Верифікація (#1471):** білд v1.0.15 → smoke (процес живий PID 14920, admin.log «Танків: 995, Промптів: 996»); білд v1.0.16 з гвардом («Admin EXE: 8.6 MB, _internal: 69 entries») → smoke (PID 12268, log 16:09:35) → тестові процеси закриті.

**Примітка:** `%TEMP%\opencode\admin_build14/15` (2×187.8 MB) видалено — канонічна папка розблокована, копії зайві. Якщо «Failed to load Python DLL» повториться — перш за все перевірити `_internal\python312.dll` у dist.

---

## WHY стає ВИДИМИМ + повністю фонова генерація (адмінка v1.0.15, 13.08.2026)

**Мета (запит користувача):** 1) щоб клас багів «тихий FAILED + вічний ре-детект» більше ніколи не повторювався; 2) всі процеси генерації — повністю у фоні: жодних вікон/терміналів поверх інших.

**Частина 1 — fix forever (причини в 5 видимих каналах):**
1. `generate_builds()` тепер повертає `(ok, done_tags, reasons)` — `reasons = {tag: "категорія: деталь"}` для КОЖНОГО невдалого танка + `reasons["summary"]`. Категорії явні: `unknown_tank`, `client_parse_fail`, `no_prompt`, `ai_no_response`, `ai_parse_fail`, `upload_fail` — жодна не колапсується в голий `False`. Причини йдуть у 5 каналів: консольний принт, admin.log + GUI-лог + трей-балун (в адмінці v1.0.15 замість голого «Генерація FAILED»), повідомлення RTDB `pending_updates/builds` (status="error", message=summary), й `report_fallback(source="admin_generation", ...)` → `error_reports/` (секція Errors на admin.html).
2. **Fail-реєстр** у `.tank_extract_manifest.json` (`_failures: {tag: {count, fp}}`): `update_manifest_failures()` інкрементує лічильник для неаплоаднутих тегів (ключ — фінгерпринт scripts.pkg-файла танка), `exclude_failed_tags()`/детект відсікають танк при `count >= 3`. Скидання: успішна генерація (через `update_manifest_for_tags`) або зміна фінгерпринта (новий гарячий фікс гри дає свіжу спробу). Вічна петля FAILED неможлива; при цьому новий патч гри автоматично дає танку шанс.
3. Інші захисти класу: `detect_changed_tanks` повідомляє про відсутність scripts.pkg через `report_fallback` замість тихого `[]`; `_tank_record_from_client` КИДАЄ `RuntimeError("list.xml parse failed: ...")` замість тихого `None` (причина `client_parse_fail` доходить до всіх каналів); `_fill_progress.json` перенесено в `config.USER_DATA_DIR` + гвард `start_idx >= len(all_tags) → 0`; прибрано подвійний бамп `builds/version` у `_do_generate` (бібліотека бампить лише при `ok_count > 0`).
4. Свеп неповних білдів (GUI `_run_build_fill_sweep`) фільтрується через `exclude_failed_tags` — танки з 3+ послідовними фейлами не зациклюють щоденну регенерацію.

**Частина 2 — повністю у фоні:**
1. Chrome ВСЕГДИ оф-скрін: `--window-position=-32000,-32000` замість `--start-maximized` (колишнє повноекранне вікно поверх інших). Сторінка AI Mode повністю рендериться оф-скрін (перевірено скріншотом).
2. Адмінка за замовчуванням стартує у системному треї: `start_minimized: True` для нових інсталяцій (X → у трей, повний вихід через Settings, автозапуск через `--tray`).
3. Dev-запуски генерації без терміналів — `pythonw.exe` (консольна версія більше не потрібна; причини фейлів і так у admin.log + RTDB).

**Верифікація (#1471):** ast 4 модулі (`admin_build_generator`, `admin_app`, `tank_extractor`, `firebase_reporter`); 8 ізольованих юніт-тестів fail-реєстру (виключення count≥3 / детект при count<3 / скидання по успіху / скидання по зміні fp / інкремент 2→3 з ключем fp / exclude_failed_tags 3 сценарії / unknown-шлях віддає reasons / stale-index гвард у force-прогоні); probe RTDB: `report_fallback` з адмін-контексту → запис у `error_reports` (деталь у `details.context`); probe Chrome: `_create_driver()` → позиція вікна `(-32000, -32000)`, сторінка рендериться (скріншот 27KB). Жива адмінка v1.0.15: запуск у треї, «Танків: 995, Промптів: 996», «Змін не виявлено» (маніфест не ре-детектує закриті танки).

**Примітка:** знову зібрано у `%TEMP%\opencode\admin_build15\` — `dist/SM WoT Assistant Admin` досі заблокований невидимим хендлом (див. v1.0.14). Своп у канонічну папку — після розблокування. Застарілий кореневий `_fill_progress.json` видалено (мертвий шлях).

---

## Новий танк Ch45_WZ_114_CFE_D: 3 кореневі баги в адмін-генерації (адмінка v1.0.14, 13.08.2026)

**Проблема:** о 22:28 12.08 гарячий фікс гри додав у scripts.pkg новий китайський танк Ch45_WZ_114_CFE_D (WZ 114 CFE D, tier 9, HT). Адмінка детектувала його (періодичне сканування "1 змінених танків!" о 23:27, 23:34, 00:27), але генерація падала "Генерація FAILED" без жодної помилки. Три окремі кореневі причини ланцюгом:

1. **list.xml: новий маркер ціни `&lt;( ` від WG.** У `&lt;price&gt;`-блоках танків без ціни WG раніше ставив `&amp;`, тепер `&lt;( ` (невалідний XML). `ET.fromstring(china/list.xml)` → "invalid token" → `_tank_record_from_client()` повертав **None** → танк ішов у `unknown` → `total=0` → тихий `(False, [])`. Маніфест не просувався → танк ре-детектувався щогодини → вічний цикл FAILED. (Той самий латентний мінування був і в `tank_extractor.py` — наступна повна екстракція тихо загубила б китайський лист, ремейк бага F141_Durendal #1519.)

2. **Застарілий `_fill_progress.json`.** `generate_builds()` для queue-шляху брав `start_idx = prog["index"]` з файлу прогресу попередньої сесії (07.08, index=1) → `to_process` порожній → цикл не виконувався взагалі (ok=1 зі старого файлу) → теж тихий `(False, [])`.

3. **Race гідрації сторінки AI Mode (Chrome 151).** Після фіксу 1+2 танк доходив до `_submit_to_ai`, але textarea знаходилась у напів-ініціалізованому стані: селектори ловили прихований textarea (0×0, `is_enabled()`=True без `is_displayed()`), а `click()` одразу після знахідки падав "element not interactable" (React-гідрація замінює ноди — стейл-референс ніколи не стає клікабельним). Два RECONNECT-цикли (2×60с таймаути) → `[FAIL] no response`.

**Зміни:**
1. `admin_build_generator.py::_clean_xml` — додано ескейп сирого `<`: `re.sub(r'<(?![\w/!?-])', '&lt;', text)` (після `&amp;`-ескейпу).
2. `tank_extractor.py::_sanitize_list_xml` (новий модульний хелпер, використано в обох місцях парсингу list.xml: `build_database` + `update_compact_descr`) — ескейп `&amp;` + `&lt;` + зріз UTF-8 BOM (ламав парсинг на column 3).
3. `generate_builds()` — свіжий прогрес для queue/single_tag: `{"pass":1,"index":0,...}`; `load_progress()` лишився лише для force/batch (легасі crash-resume). Застарілий `_fill_progress.json` більше не впливає на queue-шляхи.
4. `_submit_to_ai()` — (а) readyState-гейт у циклі пошуку: textarea приймається лише при `document.readyState == "complete"`; (б) приймаються лише `is_enabled() AND is_displayed()` (відсікає прихований 0×0 інпут); (в) клік-ретрай 20×1с з ПОВТОРНИМ пошуком елемента кожну спробу (React замінює ноди).
5. `_update_builds_version()` викликається лише при `ok_count > 0` — failed-рани більше не бамплять `builds/version` і не форсують у всіх клієнтів повний ре-синк незмінених даних (до фіксу кожен FAILED-цикл бампав версію 15→16→17 без жодного аплоаду).

**Верифікація (#1471):** ast 3 модулі; dev: `_tank_record_from_client` → запис `{"name": "WZ 114 CFE D", tier 9, HT, China, is_premium: true, compact_descr: 64305}`; `_slots_and_crew_from_client` OK; повний dev-прогон `generate_builds(queue=['Ch45_WZ_114_CFE_D'])` → `[OK] uploaded` → RTDB `builds/tanks/Ch45_WZ_114_CFE_D` повний (ammo AP/APCR/HE, consumables, equipment improvedhardening/gunrammer/verticalstabilizer, crew 5 ролей з перками, field_mods), `builds/version` 17, промпт в RTDB (6070 chars) + `prompts_cache.json` → 996. AppData `.tank_extract_manifest.json` просунуто для Ch45 → старт v1.0.14: "Змін не виявлено" — цикл закритий.

**Обмеження/примітки:** `dist/SM WoT Assistant Admin` на момент білда був заблокований невидимим хендлом (не процес, не Explorer, не Restart Manager — ймовірно AV-мініфільтр; rename/delete → WinError 32, запис усередину працює) → v1.0.14 зібрано в `%TEMP%\opencode\admin_build14\` (перевірено: `_internal\admin_version.txt` = 1.0.14, EXE 8.6MB) і запущено адмінку звідти; своп у канонічну папку — після розблокування. Білд у dev-дереві: tank_db.json 1141, tank_slots_full.json 1268 (+35, комічено), crew_builds.json 1141 — Ch45 увійде в наступний реліз бандла (патерн F141_Durendal #1528).

---

## Стійкість до частих оновлень Chrome (адмінка v1.0.12, 12.08.2026)

**Проблема:** Chrome автооновлюється регулярно (02:54 12.08 — 151.0.7922.109). Після v1.0.11 (always-copy, #1542) сам DevToolsActivePort-клас вилікуваний, але залишались дірки на оновлення: (1) SM-помилки драйвера (офлайн, `Could not obtain version`) не входили в ретрай — падали одразу; (2) вікно "новий major Chrome, драйвер ще не випущений" давало `This version of ChromeDriver only supports...` і ретрай повторював ту саму помилку; (3) смерть сесії ПІД час генерації (`WebDriverException` у `_submit_to_ai`) не ловилась — весь цикл падав, решта черги чекала до наступного свепу; (4) версії браузера/драйвера ніде не логувались — діагностика інциденту займала години.

**Зміни (тільки `admin_build_generator.py`):**
1. `_DRIVER_RETRY_MARKERS` — 7 класів помилок, що лікуються ретраєм: `session not created`, `This version of ChromeDriver only supports`, `Could not obtain version`, `Could not successfully connect to the driver manager`, `Error communicating with the remote browser`, `Local file not found`, `se-manager`.
2. `_create_driver()`: 3 спроби (було 2) з паузами 3с/15с; неретраябельні помилки кидаються одразу; після 3 спроб — RuntimeError з чітким текстом "Chrome був оновлений, драйвер ще не опублікований — повторіть пізніше".
3. Лог версій на старті сесії: `[CHROME] session OK: chrome=151.0.7922.109 chromedriver=151.0.7922.138` (з капабіліті сесії) — діагностика будь-якого майбутнього інциденту за 1 рядок.
4. Авто-reconnect у `generate_builds()`: `WebDriverException` з `_submit_to_ai` → `driver.quit()` + kill лефтоверів + `_create_driver()` + повтор поточного танка (максимум 1 reconnect поспіль; повторний фейл → fail танка + в чергу через save_progress).

**Верифікація (#1471):** ast-parse OK (1281 рядків); ізольований тест маркерів 11/11 (7 retryable — всі реальні тексти помилок SM/драйвера, 4 не-retryable — ConnectionResetError/InvalidArgumentError/NoSuchDriver/Chrome crash — кидаються одразу); живий smoke reconnect (детермінований, окрема копія профілю, RTDB-записи замокано): round 1 → фейковий WebDriverException → `[RECONNECT]` → реальна нова сесія → round 2 реальний AI-запит → `ok=True done=['A01_T1_Cunningham']` за 240с — цикл відновлення пройдено повністю. Живий бандл v1.0.12: старт 18:26:50, свіп знайшов 16 неповних після генерації 40 (строгий чек #1540 — цикл продовжується), генерація іде. Проміжна спроба smoke зі зовнішнім kill chrome виявилась недостовірною (AI відповів за 26с — kill прилетів після завершення танка) — замінено на детермінований фейк-виняток.

**Обмеження:** reconnect не лікує "драйвер ще не опублікований" (там чесний шлях — дочекатись публікації, повтор через щоденний свеп або ручну кнопку Generate); 3 спроби з паузами додають до ~20с до старту сесії у разі тимчасового фейлу.

---

## DevToolsActivePort-інцидент: ізольована копія профілю завжди (адмінка v1.0.11, 12.08.2026)

**Проблема:** 12.08 16:12–16:21 три генерації підряд падали з `session not created: DevToolsActivePort file doesn't exist` (таймаут 60с) — 40 неповних білдів недогенеровані. Симптом-аналіз: Chrome стартує (browser-процес живий, extension GC працює, Crashpad порожній), але **ніколи не пише DevToolsActivePort**. Ізольовані тести (#1471): копія профілю + будь-який драйвер (.77/.138) = OK за ~3с; **реальний профіль + будь-який драйвер = відтворення бага** (62с таймаут ×2). Корінь: сучасний Chrome (136+) **блокує remote-debugging на дефолтному user-data-dir** — браузер запускається без девтулс-порту, chromedriver чекає файл 60с. Драйвер не винен (.77 і .138 поводяться однаково; Selenium Manager оновив .77→.138 16:12:53 наявно збіглось). Додатково: при фейлі `_create_driver()` spawn-нутий chrome.exe витікав і тримав профіль → каскад: наступні спроби копіювали профіль під живим процесом, або отримували hand-off вихід `Chrome instance exited`.

**Зміни (тільки `admin_build_generator.py`):**
1. `_create_driver()`: **завжди ізольована копія профілю** (`_copy_chrome_profile` у `%TEMP%\sm_wot_admin_chrome_profile`) — гілка "реальний профіль" видалена. Копія зберігає CAPTCHA-free логін (`Default`), старт на не-дефолтній директорії → remote-debugging працює завжди, чи відкритий Chrome, чи ні.
2. `_kill_chrome_matching(pattern)` — прицільний kill chrome.exe за CommandLine (Get-CimInstance + Stop-Process, PowerShell); викликається перед копією і в ретраї; користувацький Chrome не чіпається (верифіковано: 33 його процеси вціліли при вбивстві 13 лефтоверів).
3. Ретрай: 2 спроби; на `session not created` — kill лефтоверів + rmtree копії + свіжа копія + 3с пауза.
4. `_PROFILE_SKIP`: + `"lockfile"` (Chrome 151+), + `"Profile *"`, + `"Guest Profile"` (швидкість копії; інші профілі не потрібні — запускається `--profile-directory=Default`).
5. Видалено `_chrome_running()` — мертвий код після always-copy (грep-верифікація).
6. Вручну розблоковано RTDB `pending_updates/builds` (застряглий `status=generating` від мертвого процесу 16:21 блокував свеп #1540) → `status=error` з поясненням.

**Верифікація (#1471/#1463):** матриця ізольованих тестів: копія+.77 OK, копія+.138 OK, копія з живим lockfile OK (lock не заважає), реальний профіль+.77 FAIL 62с, реальний профіль+.138 FAIL 62с — баг відтворено, драйвер виключено; каскад "другий екземпляр на зайнятій копії" відтворено (`Chrome instance exited`) і виліковано kill-хелпером (13→0, користувацький Chrome недоторканий); фінальний тест у прод-сценарії: Chrome закритий + `_create_driver()` = OK за 53.7с (копія ~50с + сесія 3с). Живий бандл v1.0.11 (build_admin.py): адмінка стартує, свеп 40 танків запущено 17:35:04, RTDB progress дійшов до 4/40 (17:40), 18 chrome-процесів на копії — повний цикл (сесія→генерація→RTDB) працює в замороженому EXE.

**Обмеження:** копія профілю на кожен старт генерації (~50с, ~1-2 ГБ) — ціна стабільності; при фейлі копії (наприклад, диск заповнений) — явний RuntimeError, не тихий фейл.

---

## Щоденний авто-свіп неповних білдів (адмінка v1.0.10, 11.08.2026)

**Проблема:** нові танки отримують перші білди від ШІ з пропущеними секціями (обладнання/спорядження/перки екіпажу), бо інформація про танк з'являється в мережі поволі. Гейт повноти `_is_build_complete` перевіряє лише `equipment_1` + `consumables_1` — білд без перків екіпажу проходить, аплоадиться і ніколи не перегенеровується. Аудит 995 білдів RTDB проти клієнтських слотів (`tank_slots_full.json`): **118 неповних** — J20_Type_2605 без crew взагалі, 113 без перків лоадера, 4 без водія, 3 без радиста, 1 без командира, 1 без навідника. Обладнання/спорядження — 0 неповних.

**Зміни:**
1. `admin_build_generator.py`: `_normalize_crew_role()` (loader_radio→loader+radioman, `gunner_2`→gunner, регістр), `strict_build_incomplete(tag, build_data)` — строгий чек: всі 4 слоти `equipment_1/2` + `consumables_1/2` непусті + кожна роль екіпажу з клієнта (`_gp.tank_slots`/crew_roles) присутня в білді з непустими перками; `scan_incomplete_builds()` — 1 GET `builds/tanks.json` + порівняння → `{tag: [missing]}`; `_run_daily_sweep()` — пише `pending_updates/builds` {status: generating, queue: неповні} для демона.
2. `listen_mode`: таймер `_last_sweep` (24 год, перший — одразу при старті демона); гвард пропускає свіп якщо генерація вже йде: `pending_updates/builds.status == "generating"` АБО `admin_app/status == "generating"` зі свіжим `last_seen` (<180 с, захист від застряглого статусу після падіння GUI).
3. `admin_app.py`: `_run_build_fill_sweep()` у `_start_background` (24 год; перший — ~120 с після старту... фактично негайно, див. нюанс нижче) — сканує неповні та генерує **напряму** (без pending-тригера), щоб паралельно запущений демон не підхопив ту саму чергу і не подвоїв генерацію; запуск у потоці (`threading.Thread`, патерн авто-детекту); `_do_generate` вже має штатний флоу (RTDB status, manifest по done_tags, last_generated_at, нотифікації). Нові ключі i18n: `log_sweep_queued`, `log_sweep_error`.
4. Нюанс: `self._last_sweep = -86280.0` порівнюється з `time.time()` (epoch) → свіп спрацьовує фактично одразу при старті GUI (як `_last_cleanup = 0.0` — #1485), а не через 120 с. Результат: адмінка заповнює неповні білди при КОЖНОМУ старті (якщо генерація не йде) — відповідає меті, але ініціалізацію навмисного дельта-затримання не реалізує.

**Верифікація (#1471):** ast-parse обох модулів; smoke `strict_build_incomplete` (Durendal→[], J20→всі crew missing, M48A2→['crew:loader'], Type 59 loader_radio→[], gunner_2 білд-роль→[], порожні перки→missing, equipment_2 порожній→missing); сухий scan → 118 неповних (відповідає аудиту). Білд v1.0.10 (build_admin.py, стара інстанція вбита перед перезбіркою, #1491). Живий запуск EXE: «Танків: 995, Промптів: 995»; о 18:03:50 свіп спрацював — «Генерую 118 білдів...»; RTDB `pending_updates/builds` status=generating. Генерація ~118 білдів триває (1.5–3 год, Chrome).

**Відомі обмеження (успадковані, не регресії):**
- `_do_generate` пише `pending_updates/builds` БЕЗ поля queue (#1443) → якщо паралельно працює демон `--listen`, він побачить queue=None і форс-регенерує ВСІ 995 танків. Раса існувала з ручною кнопкою Generate; авто-свіп підвищує ймовірність. Не вмикати демон одночасно з GUI-генерацією (або фіксувати окремо).
- Застряглий статус "generating" після падіння GUI блокує авто-свіп обох сторін (гвард); лікується демоном (споживає trigger) або ручною кнопкою Generate. Патерн pending_updates успадкований.
- Цикл самолікування: неповний білд → свіп → регенерація → все ще неповний → наступного дня знову, поки всі секції не заповняться.

---

## Реліз v1.0.68 (11.08.2026)

**Мета:** бандл тепер містить оновлені дані з робочого дерева — `tank_db.json` 1140 (з **F141_Durendal**), `tank_slots_full.json` 1267, `crew_builds.json` 1140. У встановленому застосунку F141_Durendal видимий у списку SETUP (закрито #1528). Клієнтський код не змінювався з v1.0.67; реліз просуває дані.

**Зміни в бандлі (порівняно з v1.0.67):**
1. `_internal/tank_db.json` = 1140 записів (було 1139 у v1.0.67), Durendal присутній — верифіковано.
2. `_internal/tank_slots_full.json` = 1267 (Durendal), `_internal/crew_builds.json` = 1140 танків (Durendal).
3. `ai_builds_cache.json` — сід version 0 < RTDB 7 → при першому запуску форс-синк усіх білдів (за #1528 не чіпали).
4. Нові правила RTDB (10.08) працюють: `build.py:write_version_to_rtdb` опублікував версію через `admin_auth` (ID-токен, HTTP 200).

**Процес:** dev-перевірка перед білдом (#1471): ast-parse 11 клієнтських модулів + живий запуск main.py — 0 помилок, tank_db 1140, RTDB-пінг успішний, `pending_updates/builds` signaled (ET ParseError optional_devices.xml — відомий до-існуючий, #1532). Білд повний цикл PASSED (GitHub release v1.0.68 Beta + audit, RTDB publish 200 + audit). Smoke: v1.0.68 EXE коректно завершився по мутексу (вже запущена встановлена v1.0.67, PID 13252 — single-instance працює).

**Cleanup (#1497):** локально dist/ → 5 папок (1.0.64–1.0.68) + manifest/Setup/Portable; GitHub → 5 релізів (v1.0.63 видалено, тег лишився); RTDB versions/ → 5 ключів (1_0_64..1_0_68) + latest (PUT null через `_put_json`, ID-токен).

**Після релізу:** встановлений застосунок оновиться через launcher при наступному запуску (RTDB latest = 1.0.68).

---

## Самолікування prompts_cache.json: 995 танків / 995 промптів (11.08.2026)

**Проблема:** стартовий лог адмінки «Танків: 995, Промптів: 994» — розбіжність рівно в один ключ: `prompts_cache.json` — статичний файл, згенерований разово архівованим `builds_table.py`, ніколи не оновлювався при житті. Танк **F141_Durendal** (доданий 07.08.2026, #1526) мав білд і промпт у RTDB (`prompts/tanks/F141_Durendal`, 5945 символів — підтверджено живим GET), але в локальний кеш промпт не потрапляв.

**Зміни:**
1. **Бекфіл:** промпт F141_Durendal скопійовано з RTDB у кінець `prompts_cache.json` (збережено історичний порядок ключів, без sort_keys) → 995/995.
2. **`admin_build_generator.py:save_prompt(tag, prompt)`** (новий): у `generate_builds()` після успішного `_upload_prompt()` (гейт на результат аплоаду — інакше недолетілий у RTDB промпт міг би "замаскуватися" локальним кешем, `prompt_new=False` назавжди) дописує новий промпт у `PROMPTS_FILE` — файл більше не дрейфує від tank_db. Валідація на load і write (#1346): пошкоджений/не-dict кеш скидається, невалідні промпти (<50 символів, не str) не пишуться.
3. **`load_prompts()`** став толерантним: пошкоджений JSON або не-dict значення → `{}` замість необробленого JSONDecodeError (краш адмінки на старті при пошкодженому файлі).
4. `admin_version.txt` 1.0.7 → **1.0.9** (1.0.8 — самолікування; 1.0.9 — гейт `_upload_prompt` → `save_prompt`), перезбірка `build_admin.py` (#1531 — зміна admin_build_generator.py обов'язково = перезбірка EXE).

**Верифікація (#1471, #1479):** ast-parse обох файлів; 6 smoke-тестів `save_prompt`/`load_prompts` (roundtrip, пошкоджений кеш на обох шляхах, невалідні промпти, порядок ключів, не-dict JSON); бандл `_internal/prompts_cache.json` = 995 (Durendal присутній), `admin_version.txt` = 1.0.9; живий запуск нового EXE → `admin.log`: «Танків: 995, Промптів: 995». Адмінка запущена і працює (після вбивтя старої інстанції для перезбірки, #1491).

---

## Захист RTDB правилами + реальний Auth для адмін-тулінгу (10.08.2026)

**Проблема:** лист Firebase «база містить незахищені правила» — `database.rules.json` мав кореневий `.read/.write: true` (будь-хто з URL бази міг читати/записувати все).

**Дослідження (empirical):** RTDB НЕ валідує `auth=` параметр (real key / garbage / без auth → усі 200) — API-ключ НЕ є автентифікацією; застосунок і публічний сайт у правилах оцінюються як `auth == null`. Єдиний компонент з реальним Auth — admin.html (`signInWithEmailAndPassword`). Auth-користувач підтверджено: `smwotassistant@gmail.com`, UID `W0bTk96xJMeVEEbplvMbxtl5igo2` (signInWithPassword → `INVALID_LOGIN_CREDENTIALS`, не `EMAIL_NOT_FOUND`).

**Зміни:**
1. `admin_auth.py` (новий, корінь): `get_id_token()` — `accounts:signInWithPassword` з `%APPDATA%/SM WoT Assistant/admin_creds.json` (`{email, password}`, gitignored), кеш + авто-рефреш по refreshToken (~1 год); `_rtdb_url_with_token()` — ЗРІЗАЄ наявний `?auth=` перед додаванням токена, бо RTDB використовує ПЕРШИЙ auth-параметр (API-ключ → 401). Без креденціалів → `None` + одне попередження.
2. `admin_build_generator.py:_put_json` — записи через ID-токен; без креденціалів → видимий фейл (False + повідомлення). `_get_json` не змінювався (читання відкриті).
3. `build.py:write_version_to_rtdb` — `?auth=<idToken>`; без креденціалів → False + повідомлення (білд не падає, RTDB-крок пропускається).
4. `admin_app.py` НЕ змінювався (імпортує `_put_json` з генератора) — **але зібраний адмін-EXE v1.0.6 пише API-ключем і тепер отримує 401 — потребує перезбірки `build_admin.py`** (див. нижче).
5. `database.rules.json` (задеплоєно `firebase deploy --only database` 10.08.2026):
   - корінь `.read/.write: false`;
   - `versions/builds/prompts/popular_tanks` — read open, **write тільки `auth != null && auth.uid == 'W0bTk96xJMeVEEbplvMbxtl5igo2'`** (клієнт їх лише читає);
   - `installations`/`service_events` — read `auth != null`, write open (клієнтський ping/flush);
   - `admin_app` — read+write `auth != null` (читає лише admin.html, пише адмін-EXE з токеном);
   - `error_reports` — read open, write через **wildcard `$id`: `!data.exists() || auth != null`** (create для клієнта POST, delete/overwrite тільки з токеном — адмін-cleanup #1485);
   - `schemes`/`groups`/`user_groups`/`users`/`pending_updates` — open (клієнтський контент + trigger від клієнта);
   - `drawings` — read-only (легасі).

**Нюанс правил для push (empirical):** append-only правило на рівні НОДИ для POST оцінюється НА САМІЙ НОДІ — `data.exists()` = true (нода існує) → 401. Тільки wildcard `$id` дає create-семантику для push.

**Верифікація (#1471):** ast-аудит змінених модулів; smoke signIn (токен 940 симв.); curl-матриця: всі відкриті читання 200 (versions/builds/schemes/users/pending_updates/error_reports/drawings/popular_tanks), auth-читання 401 (installations/service_events/admin_app), записи адмін-нод без токена 401, PUT/DELETE з токеном 200 (через `_put_json` → True), error_reports: create 200 / overwrite без auth 401 / delete з токеном 200; installations PUT/DELETE 200; service_events POST 200. Dev-запуск `main.py`: `[REPORTER] Пінг успішно` + `[MAP_MGR] pending_updates/builds signaled` — клієнтські write-шляхи живі з новими правилами.

**ВАЖЛИВО (операційно):** задеплоєний адмін-EXE `dist/SM WoT Assistant Admin` (v1.0.6) має старий `_put_json` (API-ключ) → записи в `builds/prompts/popular_tanks/versions/admin_app` тепер 401. Перед наступним використанням адмінки: бамп `admin_version.txt` → 1.0.7 та `python build_admin.py`. Демон `--listen` запускається з сирців — підхоплює зміну без перезбірки.

---

## Канонічні ARCHITECTURE.md / STRUCTURE.md у корені (07.08.2026)

**Рішення:** кореневі `ARCHITECTURE.md` (48 KB) і `STRUCTURE.md` (33 KB) — канонічні project-docs (opencode інжектить їх у контекст як `<project-docs>`; вони свіжіші за фактами: WotXmlParser/decode_xml, is_beta unconditionally, актуальні версії). `docs/architecture.md` + `docs/structure.md` (вербатім-копії від 04.08, містять застарілі факти: WotXmlDecoder, ai_webview_gui, VERSION 1.0.65) переміщено в `_archive/docs/` (`git mv`, історія збережена). AGENTS.md docs index оновлено на кореневі файли. Версійні факти в кореневих синхронізовано (admin_version.txt 1.0.4 → 1.0.6) + додано опис done_tags-механізму в секцію AI Pipeline.

---

## Фікс механізму оновлення білдів + новий танк F141_Durendal (07.08.2026, адмінка v1.0.6)

**Проблема:** після оновлення гри до v2.3.1.1 (#910, 06.08) адмінка повідомила «Генерація завершена!» (06.08 19:06, 82с), але білд нового танка F141_Durendal НЕ потрапив у RTDB, а манифест змін `%APPDATA%/SM WoT Assistant/.tank_extract_manifest.json` вже містив його fingerprint → detect назавжди приховував танк від автооновлення.

**Корінь (2 дефекти в одному ланцюзі):**
1. `tank_db.json` застарів (29.07, без F141_Durendal): головний застосунок у stability_mode викликає лише `extract_metadata` (копіює XML у `extracted_data`), а не `build_database()`. `generate_builds` фільтрував queue-тег по tank_db (`all_tags = [t for t in queue if t in tank_db]`) → total=0 → `return True` («All tanks already cached!») — хибний успіх.
2. `admin_app._do_generate` при ok=True оновлював манифест для ВСЬОГО queue (`update_manifest_for_tags(..., queue)`), включно з незгенерованими тегами — «з'їдений» танк.
3. Додатково: `generate_prompt` резолвить танк через `tank_slots_full.json` (1266 записів, без F141) → навіть свіжий tank_db.json не допоміг би («Tank not found»).

**Фікс (admin_build_generator.py + admin_app.py):**
- `generate_builds` повертає `(ok, done_tags)` — список тегів, реально завантажених у RTDB; хибний успіх при total=0 прибрано (`(False, [])`).
- Манифест оновлюється ТІЛЬКИ для `done_tags` (admin_app.py:892, слухач listen_mode).
- Теги з queue, відсутні в tank_db, добудовуються з клієнта: `_tank_record_from_client` (list.xml: tier/class/nation/premium/compact_descr), `_slots_and_crew_from_client` (vehicle XML: crew roles, supplySlots→equipment_slots + slot_types + consumable_slots, postProgressionTree, customRoleSlotOptions, optDevsOverrides). Записи вносяться в module-level словники `generate_prompt_v2` (tank_db/tank_slots/crew_builds) і зберігаються в локальні JSON (`_persist_client_tank_data`).
- Прибрано debug-дамп `ai_response_dump.txt` (після верифікації навігаційного ретраю).

**Дані:** tank_db.json (1140), tank_slots_full.json (1267, +F141), crew_builds.json (1140) оновлені з клієнта; ключ `F141_Durendal.xml` видалено з манифесту.

**Верифікація (живий цикл):** detect → `['F141_Durendal']` → `--builds F141_Durendal` → RTDB `builds/tanks/F141_Durendal` = повний білд (equipment_1: verticalstabilizer/improvedaiming/coatedoptics; consumables_1: largerepairkit/largefirstaidkit/automaticfireextinguisher; без `#artefacts:` сміття, #1452) → манифест оновлено по done_tags → detect = 0 змін. `builds/version` → v7.

**Перезбірка адмінки:** admin_version.txt → 1.0.6 (#1446), `python build_admin.py` → `dist/SM WoT Assistant Admin/` (onedir). Головний застосунок не чіпався. Повний опис — docs/admin.md.

---

## Chrome profile isolation в адмін-генераторі (07.08.2026)

**Проблема:** `admin_build_generator.py:_create_driver()` (спільний для демона `--listen` і адмінки через `admin_app.py:24`) використовував реальний профіль Chrome. При запущеному Chrome → `session not created: Chrome instance exited` (профіль заблокований SingletonLock) → після оновлення гри демон падав на генерації білдів кожен цикл.

**Фікс:** при запущеному Chrome профіль копіюється в `%TEMP%\sm_wot_admin_chrome_profile` з виключенням кешів і Singleton-локів (`_chrome_running()` tasklist + `_copy_chrome_profile()`); неповна копія → RuntimeError; при закритому Chrome — як раніше. Верифікація: AST + smoke 11/11. Повний опис — docs/admin.md (07.08.2026).

**Перезбірка адмінки:** admin_version.txt → 1.0.5 (#1446), `python build_admin.py` → `dist/SM WoT Assistant Admin/` (onedir). Головний застосунок не чіпався.

---

## v1.0.67 (06.08.2026)

**Зміни після v1.0.66 (коміти 9990b5e..446bc4e, гілка api-integration):**
- Повернуто 2 мапи (59_asia_great_wall / Кордон Імперії, 37_caucasus / Перевал) — прибрано з `_EVENT_MAP_IDS`; 44 мапи в Standard (ctf).
- Назви мап завжди в мові клієнта гри: `regenerate_map_dictionary(_lang_module)` на кожному старті (деталі нижче, розділ 04.08.2026).
- Фікс дрейфу позиції вікна редагування: `WindowManager._cursor_over_app()` WindowFromPoint + GetParent-ланцюг, mode-гейт drag (деталі нижче).
- Аудит 04.08: 125 мертвих модулів → `_archive/scripts/`, чистка dist/GitHub/RTDB (5 останніх), реорганізація docs (13 тематичних файлів).
- Реліз: повний цикл build.py (PyInstaller → NSIS → ZIP → verify → manifest → GitHub release → RTDB) + Release Cleanup Protocol (лишились v1.0.63–v1.0.67).
- Адмінка не змінювалась (v1.0.4, onedir).

---

## Виправлення мап та дрейфу позиції вікна (04.08.2026)

**Назви мап завжди в мові клієнта гри (language_module.py):**
- **Проблема:** `regenerate_map_dictionary(lm)` запускалась ТІЛЬКИ при зміні мови клієнта (гілка "rebuilding"). Коли мова не змінювалась — «no change, skipping rebuild» — словник назв мап не оновлювався. Тому dev-словник лишався англійським від епохи EN-клієнта (03.08) назавжди: dev-запуск показував англійські назви, встановлений бандл — українські.
- **Фікс:** виклик `regenerate_map_dictionary(_lang_module)` перенесено після популяції `_lang_module` з кешу (крізь обидві гілки) — словник перегенерується з клієнта (arenas.mo) у мові клієнта на КОЖНОМУ старті. Гварди: `dictionaries.get("arenas")` + try/except + «10+ валідних записів» у самій функції (порожні дані не зіпсують словник). У no-change гілці `lm.dictionaries` порожні (#1451) — тому використовується `_lang_module`, а не `lm`.
- **Ефект:** назви мап завжди з клієнта в мові клієнта (зараз uk: «Кордон імперії», «Перевал», «Карелія»); dev і встановлений консистентні; хардкоджений `MAP_NAMES_EN` не використовується для відображення (тільки тактичні папки/публікація).
- Верифікація: AST; ізольована регенерація з uk-кешу (89 мап, укр. назви); живий запуск — регенерація відбулась навіть при «no change»; `t_map` повертає укр. назви.

**Повернуто дві мапи, які не показувались у MAPS/TACTIC (аудит: 59 мап клієнта vs список програми):**
- `59_asia_great_wall` (Кордон Імперії / Empire's Border) — прибрано з `_EVENT_MAP_IDS` (map_manager.py:19). Мапа жива в клієнті (ctf, CRC збігається), всі дані є (мінімапа, тактична картинка `maps/Empires_Border/map.webp`, словник) — виключав лише застарілий хардкод-сет із v1.0.54.
- `37_caucasus` (Перевал / Mountain Pass) — прибрано з `_EVENT_MAP_IDS` + виправлено назву в `config.py:100`: `"Pass"` → `"Mountain Pass"` (назва з клієнтського .mo `arenas.mo`; тактична папка `maps/Mountain_Pass` існує, але `_resolve_tactic_folder` не знаходила її через хибну назву `"Pass"`).
- Підтверджено правильно сховані (клієнтські XML через WotXmlParser): sm24/nom (StoryMode/NewOnboarding-сценарії), `*_scc` (SCC), `*_ls26_*` (Last Stand, у arenas.mo взагалі немає назв), epic/BR, `140/141/142`, `*_wt` (не в клієнті).
- Після фіксу: 44 мапи в Standard (ctf).

**Усунено дрейф позиції вікна редагування (window_manager.py):**
- **Корінь:** регресія `a70e476` (25.06.2026) прибрала mode-гейт у `_monitor_mouse_drag.drag_ready` → F8 (клейке Lock/форматування) + будь-яке ЛКМ у грі (приціл, мінімапа) тягнуло вікно за курсором; `save_settings()` на відпуск ЛКМ назавжди зберігав зсув у `edit_x/edit_y` → вікно "з часом" опинялось на місці бойового вікна (низ-праворуч). Попередні фікси (7b3faf7, 2707d98) правили лише save/restore-симптоми.
- **Фікс:** новий `WindowManager._cursor_over_app()` (WindowFromPoint + winfo_id/GetParent, чистий ctypes, потокобезпечний) + гейт: глобальний drag дозволений у norm-режимі (фіча перетягування click-through вікна) і в edit — лише коли курсор над вікном програми. Той самий гейт застосовано до Alt+ЛКМ хука `_setup_mouse_drag` (живий у dev; у білді `mouse` не бандлиться).
- **Другий раунд (живий дебаг, #1463):** перша версія гейта блокувала drag по канвасу — WindowFromPoint над канвасом повертає hwnd ОВЕРЛЕЯ `_po_win` (він покриває весь канвас; map рендериться на ньому), а не рута → гейт не розпізнавав вікно → "вікно редагування взагалі не переміщується". Діагностика на живому застосунку (EnumWindows + WFP-проби + тимчасові [DEBUG]-принти в моніторі) виявила ще дві пастки: (1) WFP повертає дочірні WS_CHILD hwnd (canvas/entry — 2 рівні нижче клієнтського), (2) кеш hwnd оверлея заповнювався нулем на старті (до створення `_po_win`) і більше не перевірявся. **Фінальний фікс:** `_cursor_over_app()` піднімається ланцюгом `GetParent` до 8 рівнів і порівнює з {клієнтський/wrapper рута, клієнтський/wrapper оверлея}; нульовий кеш оверлея не закріплюється (перевірка повторюється); продовження drag розв'язане від `over_app` (тягнемо поки затиснута ЛКМ — перетин межі вікна не обриває drag).
- Верифікація (живий застосунок, 4 фази): F8 ON + drag по ЦЕНТРУ КАНВАСА → рухається ✓; топ-бар → рухається ✓; поза вікном → НЕ рухається ✓ (анти-drift); F8 OFF + канвас → НЕ рухається ✓. Позиція вікна відновлена, [DEBUG]-принти прибрані, AST-аудит чистий.

---

## Аудит файлів і сховищ (04.08.2026)

**Локальні файли (97.8 GB → 8.6 GB, -89.2 GB):**
- 125 мертвих модулів → `_archive/scripts/` (git mv, історія збережена): старий AI-пайплайн (ai_assistant/ai_normalizer/ai_scraper×3/ai_triple_scrape/ai_webview_gui), старі промпти (generate_prompt v1, generate_prompt_is7), легасі-декодер (bw_xml, decode_vehicle_xml, __decode_defs, __decode_and_search_grid, decode_xml.orig, debug_decode_xml), old_stats_ai, patch_* ×11, fix* ×4, check_* ×14, debug-скрипти, find_* ×7, deep_* ×3, analyze_* ×4, tomato/selenium/click-ера ×23 (tomato_selenium, open_tomato_consumables, explore_tomato_sections...), try_*/get_*/search_* ×9, arc_* ×2, разові утиліти (quick_parse, read_arenas, parse_decoded, parse_slots×2, repair_tth, temp_extract, tmp_test, generate_chars, diagnostic, AUTO_UPDATE_GUIDE, field_mods_report), екстрактори-разовики (extract_vehicle_slots×2, extract_slots_from_decoded, extract_full_tank_data, extract_all_client_data, build_field_mod_pairs_by_tank, create_tank_slots_db, create_english_names, add_english_tank_names, add_field_mods, parse_mo_localization), builds_table.py, network_requests.py, test.py, xvm_chars.png, show_xvm.html, run_test.bat, temp_list.xml, scripts.pkg.zip (бекап клієнтського пакета).
- 23 тестові артефакти — git rm: tomato_*.html ×12, tomato_*.json ×6, scraper_test_out.html, vehicle_slots_test.json, vehicle_slots_v2.json, tui.json.
- Untracked: temp_scripts.zip (162 MB), *.log, *_err/_out.txt ×10, tmp/, __pycache__ — видалено.
- extracted_gui/ (1.26 GB, розпакований gui-part1.pkg — застосунок не читає) — видалено.
- dist/: 90.3 GB → 4.8 GB (лишились v1.0.62-v1.0.66 + Admin).

**Збережені (перевірено імпорти):** tth_updater, extract_equipment_loadouts, build_crew_builds, name_localizer, map_updater, ukrainian_map_names.json, map_links.json, ai_engine (AI_CONS_MAP для generate_prompt_v2:382), .client_update_manifest.json.

**GitHub (50.64 GB → 2.88 GB):** видалено 60 старіших релізів (v1.0.1-v1.0.61), лишились v1.0.62-v1.0.66 (теги збережені).

**RTDB versions/ (45 → 6 ключів):** видалено 1_0_22-1_0_61 + легасі-вузол admin (адмінка без auto-update з #1431); лишились 1_0_62-1_0_66 + latest.

**Нові правила:** AGENTS.md — Release Cleanup Protocol (dist/GitHub/RTDB → 5 останніх після кожного релізу) + No dead code (новий .py без імпортерів → одразу в _archive/scripts/; тестові виводи не комітити). docs/release.md — розділ з повною процедурою.

## Single-instance mutex fix (04.08.2026, v1.0.66)
1. **Баг**: `ctypes.windll.kernel32.CreateMutexW` + `ctypes.windll.kernel32.GetLastError()` — GetLastError читається через windll-хендл БЕЗ `use_last_error=True`, тому ЗАВЖДИ повертає 0 → перевірка `== 183` ніколи не спрацьовувала → single-instance тихо не працював: стартували дублі процесів (два tray_watcher.exe, два admin.exe — підтверджено в дикій природі).
2. **Фікс** (4 файли: main.py:83, launcher.py:68, tray_watcher.py:211, admin_app.py:1034): патерн `_k32 = ctypes.WinDLL("kernel32", use_last_error=True)` + `_k32.CreateMutexW.argtypes = (c_void_p, c_bool, c_wchar_p)` + `_k32.CreateMutexW.restype = c_void_p` + перевірка `ctypes.get_last_error() == 183`.
3. **Перевірено** (03-04.08.2026): smoke — 2-й інстанс main.py виходить за ~8с; 2-й dev tray_watcher виходить; встановлені старі EXE (v1.0.65) дають дублі — новий реліз лікує.
4. **tray_watcher.py:13** — `DEBUG = False` (релізна гігієна; DEBUG-принти залишаються в коді).
5. **Реліз**: v1.0.66 (03.08-батч: мутекс-фікс ×4, PUT null у firebase_reporter.py:66/admin_build_generator.py:45, захист дублікатів назв груп firebase_groups.py, автовисота DrawingPalette painting_palette.py, [SYNC]-теги stats_ai.py, чищення тестових залишків). admin_version.txt → 1.0.4.


## Реорганізація документації (04.08.2026)
- AGENTS.md (51 КБ, 30 секцій) розбито: правила лишились у AGENTS.md (~140 рядків), тематичні знання → docs/ (13 файлів), історія → docs/changelog.md.
- ARCHITECTURE.md → docs/architecture.md, STRUCTURE.md → docs/structure.md (як є, без змін вмісту).
- Застарілі .md (tomato, AI browser, Orion, чеклісти, PROJECT_*) → _archive/docs/.

## 03-04.08.2026 (v1.0.66, адмінка v1.0.4)
1. Мутекс-фікс ×4 (#1474): main.py, launcher.py, tray_watcher.py, admin_app.py — WinDLL(use_last_error=True) + get_last_error()==183.
2. PUT null видалення (#1470): firebase_reporter.py:66, admin_build_generator.py:45.
3. Захист дублікатів назв груп (#1469): firebase_groups.py create/join.
4. Автовисота DrawingPalette: painting_palette.py (3 правки: _saved_pos, _refresh_linked_schemes_list, _adapt_palette_height).
5. Лог-теги [AI Browser]→[SYNC]: stats_ai.py.
6. Чищення тестових залишків: opencode — копія.json, пусті папки public/admin/, temp_scripts/decoded_test/, DEBUG=False (tray_watcher.py:13).
7. Реліз v1.0.66: build.py повний цикл (PyInstaller → NSIS → ZIP → GitHub release → RTDB) + firebase deploy --only hosting.
8. Адмінка v1.0.4: build_admin.py → onedir у dist/SM WoT Assistant Admin/ (канонічна точка; root-однофайловик прибрано; clean() чистить папку і root).

## Історія до 04.08.2026 (з архівованого CHANGELOG.md, 22.05)
# WoT Assistant - AI Build Display Fixes

## Підсумок змін (2026-05-10)

### Мета
Виправити UI для відображення AI білдів - додати індикатори номерів (1 і 2) перед секціями обладнання, потім знову увімкнути AI запити.

### Що було зроблено

#### 1. AI Engine
- Переключено з 3 запитів на 1 запит для Google AI
- Вимкнено local database fallback (AI only)
- Додано логіку закінчення кешу через 30 днів
- Використовується Google AI режим через WebEngineView (без API ключів)

#### 2. UI Fixes (stats_ai.py)

**Виправлення IndentationError (лінія 1999):**
- Видалено зайвий відступ у секції loading_labels
- Код `icon_box.pack...` був неправильно відступлений

**Виправлення geometry manager конфлікту (grid/pack):**
- Додано індикатори номерів 1 і 2 перед обладнанням
- Використовується `pack` для цифр (в батьківському фреймі)
- Обладнання тепер рендериться в окремих фреймах (`equip_grid_frame_1`, `equip_grid_frame_2`) з `grid`
- Це вирішує помилку: "cannot use geometry manager grid inside ... which already has slaves managed by pack"

#### 3. Видалено дублікати коду
- Видалено повторювані блоки створення міток 1 і 2
- Код тепер чистіший і не дублюється

### Структура коду

```python
# Цифра 1 перед обладнанням (використовує pack)
self._loadout_num_label.pack(side="left", padx=(0, 2))

# Оборудование в отдельном фрейме с grid
equip_grid_frame_1 = tk.Frame(equip_body, bg="#111111")
equip_grid_frame_1.pack(side="left", fill="none", expand=False)
render_items(equip_grid_frame_1, build_data.get("equipment_1", []), "artefacts")

# Цифра 2 перед обладнанням (використовує pack)
self._loadout_num_label_2.pack(side="left", padx=(0, 2))

# Оборудование в отдельном фрейме с grid
equip_grid_frame_2 = tk.Frame(equip_body_2, bg="#111111")
equip_grid_frame_2.pack(side="left", fill="none", expand=False)
render_items(equip_grid_frame_2, build_data.get("equipment_2", []), "artefacts")
```

### Наступні кроки
1. Перевірити чи працює UI після фіксу
2. Ввімкнути AI запити в ai_engine.py
3. При потребі відновити loading placeholders

### Файли
- `stats_ai.py` - Основний UI з виправленнями
- `ai_engine.py` - AI двигун (запити вимкнені)
- `ai_scraper_triple.py` - Скрейпер для Google AI режиму
- `MMM25_AI_BUILD_GENERATOR.md` - Документація

### Ключові рішення
- Single request замість triple для швидшої відповіді
- Cache expiry: 30 днів
- Використання WebEngineView для Google AI
