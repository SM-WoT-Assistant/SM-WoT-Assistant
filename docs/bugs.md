# Відомі невирішені баги (bugs)

## Системні (не наш код)
- **BSOD bugcheck 0x1A MEMORY_MANAGEMENT** — 03.08 16:09 (під час E2E-тестів), 04.08 10:58 та 11:07 (без жодних тестів) — 3 краші за ~19 год. Параметри 0x41790/0x125/0x126, дамп у C:\Windows\MEMORY.DMP (2.5 ГБ). Висновок: залізо/драйвери (RAM), не застосунок.

## Overlay / вікна
- Z-order конкуренція між layered-оверлеєм (_po_win) і topmost-діалогами — не вирішено (#1259). SetParent/SetWindowLongPtrW/WS_CHILD/PIL-композиція/DXGI/transparentcolor-блендінг — гірші трейдофи, не замінюють архітектуру.

## Firebase / дані
- Open task (#1452): перевірити RTDB `builds/tanks/*` на сміттєві назви раціонів (`#artefacts:ration_uk/name`) від генерацій 01-02.08.2026 (до R2-промптів); перегенерувати постраждалі танки. Після R2-промптів — чисто.

## Відкладене
- **'My Garage'** (#1455): Favorites (manual toggle, settings.json favorite_tanks) + Garage data (WG API wg_api.py або preferences.xml парсинг) + toggle "Мої танки"/"Всі танки" + детальний вигляд двоколонковий (AI vs фактичний). Потребує фіксованого compact_descr, авто-оновлюваних game_entities, динамічних stats_data мап.

## Суміжні документи
- docs/cache.md — валідація кешів (#1346): захист від корупції на load і save.
- docs/painter.md — overlay startup fix (6 пунктів), двовіконна архітектура (#1259).
- docs/admin.md — Chrome profile isolation (07→12.08): завжди ізольована копія профілю, Chrome може бути відкритий чи закритий (#1436).
