# План: Community Workspace — вбудований браузер + вставка в поля API ключів (#1593)

Дата: 19.08.2026 · Модуль: `admin_app.py` · Компонент: Community Workspace (повноекранний режим)

## Проблеми користувача (2)

1. Вікно браузера (Chrome, профіль `_COMMUNITY_PROFILE_DIR`) НЕ вбудоване у вікно програми —
   висить на панелі завдань, на нього неможливо перемкнутись. Очікування: браузер рендериться
   всередині вікна програми у фреймі `_browser_frame`.
2. Неможливо вставити (Ctrl+V / контекстне меню) API-ключ та іншу інформацію з буфера обміну
   у поля вкладки API Keys.

## Діагноз (підтверджено admin.log)

`[15:12:06] Помилка фона: main thread is not in main loop` — одразу після
`[15:12:00] Community: browser started`.

Корінь обох проблем — одна і та ж точка: `_community_show_browser()` (admin_app.py:1654).

- `_community_show_browser()` викликається з `_community_ensure_browser()` (рядок 1651),
  який виконується у **фоновому демон-потоці** (`_refresh_community_background()` / `_community_refresh_tab()`
  → `threading.Thread(target=_work, daemon=True).start()`).
- Всередині `_community_show_browser()` робляться виклики Tkinter:
  `self._browser_frame.winfo_id()`, `winfo_width()`, `winfo_height()`.
- Виклики Tkinter з не-головного потоку → `RuntimeError: main thread is not in main loop`
  → ловиться голим `except Exception: pass` → embed мовчки не відбувається.
- Chrome залишається на `--window-position=-32000,-32000` (оф-скрін), видимий на панелі завдань,
  але недосяжний.
- Бонус: невбудований Chrome (окреме top-level вікно) може перехоплювати клавіатурний фокус —
  тому вставка в поля API-ключів не працює надійно навіть коли користувач клікнув поле.

Додатково: поля API-ключів (`_build_apikeys_tab`, admin_app.py:1403) не мають контекстного меню
Cut/Copy/Paste/Select All (у головному застосунку такий патерн є — ui_manager.py:564-575).

## Виправлення

### Фікс A — потік-безпечний embed браузера (`_community_show_browser`)

Розділити важку частину (пошук HWND — thread-safe: PowerShell + ctypes) і частину з Tkinter
(embed) так, щоб Tkinter виконувався ТІЛЬКИ на головному потоці:

1. `_community_show_browser()` — робить лише перевірку driver/visible та запускає worker-потік
   `_locate()`, який поллить появу вікна Chrome (до 10 спроб × 1с).
2. При знаходженні HWND — зберігає `self._community["hwnd"]` і пушить embed на головний потік:
   `self.root.after(0, lambda: self._embed_browser_into_frame(hwnd))`.
3. Новий метод `_embed_browser_into_frame(hwnd)` — виконується на головному потоці, робить
   `winfo_id/winfo_width/winfo_height` + `_embed_hwnd()`, ставить `visible=True` лише після успіху.

`time` вже імпортований (використовується в `_community_ensure_browser`, рядок 1633).

### Фікс B — контекстне меню для полів API-ключів (`_build_apikeys_tab`)

Додати у цикл створення `tk.Entry` (admin_app.py:1419-1429) прив'язку `<Button-3>`:
меню Cut/Copy/Paste/Select All через `event_generate`, за патерном ui_manager.py:564-575.

### Фікс C — переклади для нових ключів меню

Додати ключі `menu_cut` ("Cut") і `menu_paste` ("Paste") у:
- `admin_app.py` `_TR_EN` (після `menu_select_all`, рядок 78)
- `admin_uk_seed.json` — секція `en_snapshot` (після `menu_select_all`, рядок 27)
- `admin_uk_seed.json` — секція `uk` (після `menu_select_all`, рядок 214):
  `menu_cut: "Вирізати"`, `menu_paste: "Вставити"`.

Механізм `_load_uk_translations()` (admin_app.py:284) сам перекладе нові ключі через Google
Translate у кеш при першому запуску (diff en_snapshot), seed дозволяє уникнути запитів на
свіжій інсталяції.

## Файли

| Файл | Зміна |
|---|---|
| `admin_app.py` | `_community_show_browser` (1654) → worker-потік + `after(0, _embed_browser_into_frame)`; новий `_embed_browser_into_frame`; контекстне меню в `_build_apikeys_tab`; +2 ключі в `_TR_EN` |
| `admin_uk_seed.json` | +2 ключі в `en_snapshot` і `uk` |

## Верифікація

1. `python -c "import ast; ast.parse(open('admin_app.py', encoding='utf-8').read())"` — синтаксис.
2. `python admin_app.py` (dev) → Community → браузер з'являється всередині фрейму, не на панелі.
3. Вкладка API Keys → клік правою кнопкою на полі → меню з Paste → вставка працює.
4. Жодного `main thread is not in main loop` в admin.log.
5. Спека `admin_uk_seed.json` валідна (json.load).

## Ризики

- Мінімальні: зміни локальні (embed + контекстне меню), не чіпають основний пайплайн
  генерації білдів/сканування.
- `after` з фонового потоку дозволений (вже використовується: admin_app.py:1766, 1800).
- `_embed_browser_into_frame` толерантний до відсутності `_browser_frame` (try/except).

## Документація

Після верифікації — запис у `docs/changelog.md` (дата, опис, коміт) + оновлення `docs/admin.md`
(розділ Community Workspace).