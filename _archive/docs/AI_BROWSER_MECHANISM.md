# AI Browser Mechanism — Chromium Google AI Mode

## Мета
Отримати список популярних танків через Google AI Mode (`udm=50`) з реального Chromium WebView — без капчі та бану.

## Архітектура

```
main.py → finish_startup_splash() → schedule_browser()
                                          ↓
stats_ai.py → launch_ai_browser() → subprocess
                                          ↓
                ai_webview_gui.py (PyQt6 Chromium WebView)
                                          ↓
          https://www.google.com/search?q=&udm=50 (чиста сторінка)
                                          ↓
          JS injection промту в div.Txyg0d textarea → Enter
                                          ↓
          Поллінг div.jUiaTd (30с) → body.innerText (потім)
                                          ↓
          Відповідь → stdout → stats_ai.py → process_ai_response()
                                          ↓
          tank_db → _find_tank_tag() → self.popular_tanks → refresh_ai_view()
```

## Файли

| Файл | Роль |
|------|------|
| `ai_webview_gui.py` | Chromium WebView (PyQt6). Відкриває окреме вікно 1000×700, завантажує Google AI Mode, вводить промт, зчитує відповідь |
| `stats_ai.py` | Запускає `ai_webview_gui.py` як subprocess при старті, читає stdout, парсить назви через `process_ai_response()`, оновлює UI |
| `stats_data.py` | Мапінги обладнання, перків, витратних |
| `popular_tanks_cache.json` | Кеш популярних танків |

## Chromium вікно (`ai_webview_gui.py`)

### Візуал
- **Звичайне вікно** з рамкою, заголовком "Google AI Mode — WoT Assistant"
- **Розмір**: 1000×700, позиція (100, 100) — окреме вікно
- **User-Agent**: `Chrome/125.0.0.0` (реальний Chrome, не QtWebEngine)
- Для тестування: видиме, прокручується, можна вирішити капчу вручну
- У майбутньому: frameless, маленьке, накладене поверх програми

### Промт
- Формується автоматично з поточною датою: `2026-05-22. In World of Tanks, compile a list...`
- Передається через аргумент `--prompt`
- Вводиться в textarea на сторінці через JavaScript

### Введення промту
1. Завантаження `https://www.google.com/search?q=&udm=50` (чиста сторінка)
2. Чекати 3 секунди (ініціалізація JS)
3. JS: `document.querySelector('div.Txyg0d textarea')` → вставити текст → Enter

### Зчитування відповіді
1. Поллінг кожні 500ms:
   - Перші 30 секунд: `div.jUiaTd` → `div.AgWCw`
   - Після 30 секунд: `document.body.innerText` (парсинг рядків)
2. При знаходженні тексту (>10 символів) → вивести в stdout → закрити вікно
3. Таймаут: 100 секунд (200 * 500ms)

## `launch_ai_browser()` у `stats_ai.py`

### Запуск
- **При старті програми**: `finish_startup_splash()` → `schedule_browser()` → `after(500ms)` → `launch_ai_browser()`
- Запускається з MAPS view (перший екран)
- Жодних кнопок/полів в UI — все автоматично

### Потік
- Запустити `ai_webview_gui.py --prompt "..."` як subprocess
- Чекати завершення (timeout 90s)
- Прочитати stdout → відфільтрувати `[AI Browser]` та `ERROR:` рядки
- Викликати `process_ai_response()` з текстом відповіді

### Захист
- `_ai_fetch_in_progress` — блокує повторні запуски
- `_ai_browser_process` — зберігається для `stop_browser()`

## `process_ai_response()`

1. Приймає текст з відповіді AI
2. Для кожного рядка:
   - Видалити нумерацію (`1.`, `2)`, `* `)
   - Видалити markdown (`**`, `*`)
   - Видалити дужки `(Tier X)`
   - Відфільтрувати службові рядки (skip words)
   - Валідувати regex: `^[\w\s\'\-\.\/\,\:\(\)\&]+$`
3. Для кожної назви: `_find_tank_tag(normalized_name)` — exact → case-ins → substring → word-overlap (≥2)
4. Зберегти теги в `self.popular_tanks`
5. Оновити кеш: `_save_popular_tank_cache()`
6. Оновити UI: `refresh_ai_view()`

## Кешування популярних танків

- `ENABLE_POPULAR_TANK_CACHE = True` — кеш увімкнено
- **Файл**: `popular_tanks_cache.json` — ніколи не видаляється автоматично
- **Термін дії**: 30 днів. Після 30 днів при наступному запуску AI запускається знову
- **Якщо кеш свіжий**: AI пропускається, сплеш одразу закривається
- **Якщо AI не вдався**: використовується прострочений кеш (fallback), `fail_count` інкрементується
- **Кожні 3 невдачі**: `service_messages.log_event()` — повідомлення для майбутнього сервера

### Формат cache:
```json
{
  "tanks": [{"name": "IS-7", "tag": "R93_IS-7"}],
  "updated": "2026-05-21T15:30:00",
  "fail_count": 0
}
```

### Логіка при старті

```
Старт програми
  → _load_popular_tank_cache() → (tags, updated, fail_count)
  → _is_cache_expired(updated)?
      → Ні (< 30 днів) → self.popular_tanks = tags
                         self._cache_fresh = True
                         → AI пропущено, сплеш 100% → закрито
      → Так (>= 30 днів або немає) → AI запускається
          → Успіх → process_ai_response() → fail_count=0
          → Невдача → _handle_ai_failure()
                      → fallback до кешу (навіть простроченого)
                      → fail_count++
                      → fail_count % 3 == 0 → log_event()
```

## Чому не Playwright / Selenium / Headless
- Google банить headless браузери та ботів
- Капча з'являється при автоматизованих запитах без реального браузера
- PyQt6 WebEngine = реальний Chromium → Google не бачить різниці з реальним користувачем
- User-Agent на `Chrome/125.0.0.0` приховує PyQt6

## Поширені проблеми

| Проблема | Причина | Рішення |
|----------|---------|---------|
| Жодного танку в гриді | Назви з AI не мапляться на tank_db | Перевірити `_find_tank_tag()` + `_build_name_to_tag_lookup()` |
| Капча від Google | User-Agent або підозрілий Chromium | Перевірити REAL_UA в `ai_webview_gui.py`, вирішити капчу вручну |
| Chromium не відкривається | PyQt6/PyQt6-WebEngine не встановлено | `pip install PyQt6 PyQt6-WebEngine` |
| Немає відповіді | Селектор `div.jUiaTd` змінився | Додати новий селектор в JS поллінг |
| "Unknown tank" | Назва не знайдена в БД | Додати назву в tank_db або посилити fuzzy matching |
| Браузер не закривається після виходу | Процес не терміновано | `stop_browser()` → terminate в `quit_app()` |
