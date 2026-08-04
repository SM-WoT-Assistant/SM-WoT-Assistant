# World of Tanks Assistant — Project Overview

## 1. ПЕРЕД ПОЧАТКОМ РОБОТИ — Перевірка модулів

Запустити в консолі (з кореня проекту):
```
python -c "import PyQt6; from PyQt6.QtWebEngineWidgets import QWebEngineView; from PIL import Image; import keyboard; print('ALL MODULES OK')"
```

Якщо помилка — встановити відсутні модулі:

| Команда | Якщо потрібен |
|---------|--------------|
| `pip install PyQt6 PyQt6-WebEngine` | Chromium браузер для Google AI Mode |
| `pip install pillow` | Зображення, іконки, сплеш |
| `pip install keyboard` | Гарячі клавіші (F1, F10, E...) |

## 2. Структура проекту

| Файл | Роль |
|------|------|
| `main.py` | Точка входу. WotAssistantHQ — головний клас. Завантаження даних, ініціалізація UI, цикл подій |
| `ui_manager.py` | Побудова UI: top_bar, filter_panel, canvas, browser_container. show_view() — перемикання трьох екранів |
| `stats_ai.py` | SETUP вкладка. Сітка популярних танків, деталі танка (ТТХ, обладнання, екіпаж). Запуск AI браузера, парсинг відповіді |
| `ai_webview_gui.py` | Chromium WebView (PyQt6). Окремий процес, велике вікно для тестування Google AI Mode. Вводить промт, зчитує відповідь |
| `stats_data.py` | Словники: EQUIP_MAP (обладнання), CONS_MAP (витратні), CREW_SKILL_MAP (перки) |
| `data_manager.py` | Завантаження/збереження JSON, завантаження tank_db з клієнта |
| `config.py` | Константи, шляхи до файлів |
| `map_manager.py` | Оновлення мап, авто-визначення WoT шляху, перевірка версії клієнта |
| `painter.py` | Малювання маркерів/тексту на карті |
| `service_messages.py` | Черга службових подій (невидима користувачу). Накопичує повідомлення про збої для майбутньої відправки на сервер |

## 3. Логіка запуску програми

```
main.py:880 → WotAssistantHQ.__init__
  │
  ├── data_mgr.load_tank_db()              # 1009 танків з клієнта
  ├── ui_mgr.setup_ui()
  │   ├── top_bar, filter_panel, canvas    # Базові віджети
  │   ├── browser_container                # Контейнер для Chromium внизу вікна
  │   └── stats_ai.StatsAI()               # Будує грід + деталі SETUP
  ├── splash + startup_checks              # 2+ секунди
  └── finish_startup_splash()
      ├── root.deiconify()                 # Показує головне вікно
      └── stats_ai_module.schedule_browser()
          └── after(500ms) → launch_ai_browser()
              └── subprocess: ai_webview_gui.py
                  ├── PyQt6 QApplication
                  ├── Chromium WebView (1000×700, Chrome 125 UA)
                  ├── google.com/search?q=&udm=50
                  ├── JS → textarea → Enter → поллінг відповіді
                  └── stdout → process_ai_response()
```

## 4. Три екрани (show_view в ui_manager.py)

| Назва | Кнопка | Вміст |
|-------|--------|-------|
| `maps` (TACTIC/MAPS) | Дві кнопки в топбарі | canvas (карта) + filter_panel + status_label |
| `stats` | — | browser_frame (застаріло, порожньо) |
| `ai_stats` (SETUP) | Кнопка SETUP в топбарі | ai_frame (грід/деталі) + status_label |

Кожен `show_view()`: pack_forget() всього → pack() тільки потрібного.

## 5. Popular Tanks — механізм

```
1. Старт програми
   → _load_popular_tank_cache() перевіряє popular_tanks_cache.json
   → _is_cache_expired(updated)?
       → Ні (< 30 днів) → self.popular_tanks = cache → сплеш 100% → закрито без AI
       → Так → AI запускається

2. AI фаза (тільки якщо кеш прострочений або відсутній)
   → launch_ai_browser() → subprocess: ai_webview_gui.py
   → Chromium WebView (PyQt6) з Chrome 125 User-Agent
   → google.com/search?q=&udm=50
   → JS → textarea → Enter → поллінг відповіді

3. Обробка відповіді
   → Успіх: process_ai_response() парсить назви
           → _find_tank_tag() зіставляє з tank_db (4 стратегії)
           → self.popular_tanks заповнений
           → cache записано з fail_count=0
           → refresh_ai_view() показує сітку

   → Невдача: _handle_ai_failure()
           → fallback до кешу (навіть простроченого)
           → fail_count++ (зберігається в cache)
           → fail_count % 3 == 0 → service_messages.log_event()
           → refresh_ai_view() з кешованими танками

4. Кеш: popular_tanks_cache.json
   ENABLE_POPULAR_TANK_CACHE = True
   Термін дії: 30 днів
   Кеш НІКОЛИ не видаляється автоматично
```

## 6. Chromium WebView — деталі

| Властивість | Значення |
|-------------|----------|
| Бібліотека | PyQt6 + PyQt6-WebEngine |
| Режим вікна | Звичайне, з рамкою (тестовий режим) |
| Розмір | 1000×700, окреме вікно |
| Позиція | (100, 100) від лівого верхнього кута екрану |
| User-Agent | `Chrome/125.0.0.0` (приховує PyQt6) |
| Промт | JS injection в div.Txyg0d textarea на сторінці, не в URL |
| Відповідь | Поллінг div.jUiaTd (30с) → body.innerText (потім) |
| Таймаут | 90 секунд на весь процес |
| Закриття | Авто після отримання відповіді, або по Ctrl+C

## 7. Правила роботи з AI сесіями

- **Перед роботою обов'язково перевірити модулі** (пункт 1)
- `ai_webview_gui.py` — окремий процес, не блокує Tkinter
- При закритті програми: `stop_browser()` → terminate subprocess
- Chromium вікно: згорнуте (`showMinimized()`), без іконки в панелі (`WS_EX_TOOLWINDOW`), працює під час сплешу
- **Кеш**: 30 днів. Якщо свіжий — AI не запускається. Якщо прострочений — AI оновлює
- **Fallback**: при невдачі AI використовується кеш (навіть прострочений)
- **Службові повідомлення**: кожні 3 невдачі → `service_messages.log_event()` — невидимо для користувача
- Якщо `ai_webview_gui.py` не запускається → перевірити `pip install PyQt6 PyQt6-WebEngine`

## 8. Розшифровка назв танків (4 стратегії)

У `_find_tank_tag()`:
1. Exact match (оригінальний тег)
2. Case-insensitive
3. Substring (назва містить тег або тег містить назву)
4. Word-overlap (≥2 спільних слів)

---

*Останнє оновлення: 2026-05-22*

## 9. Service Messages

Файл `service_messages.py` — черга внутрішніх службових подій.

### Призначення
- Накопичувати інформацію про збої, які потребують уваги розробника
- Користувач НІКОЛИ не бачить ці повідомлення
- У майбутньому: відправка на сервер (`get_pending()` → POST → `mark_delivered()`)
- Формат: `service_messages.json`

### Тригер
```python
# stats_ai.py — при невдачі AI після кожних 3 спроб:
from service_messages import log_event
if fc > 0 and fc % 3 == 0:
    log_event("popular_tanks",
              f"Не вдалося оновити популярні танки після {fc} спроб.",
              level="warning")
```

### API
| Функція | Опис |
|---------|------|
| `log_event(category, message, level)` | Додати подію в чергу |
| `get_pending()` | Повернути undelivered події |
| `mark_delivered(ids)` | Позначити як доставлені |
