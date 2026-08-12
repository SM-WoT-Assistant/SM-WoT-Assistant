# Історія змін (changelog)

> Джерело: AGENTS.md (реорганізація документації, 04.08.2026). Секції перенесені вербатім.

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
