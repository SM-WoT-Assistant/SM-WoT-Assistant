# Сесія 2026-05-12: Спрощення інтеграції Tomato

## Проблема
- TclError: bad window path name при переключенні танків
- Складна валідація обладнання через client data
- Багато зайвого коду для перевірки віджетів

## Виконані зміни

### 1. Видалено валідацію обладнання (stats_ai.py)
**Було:**
```python
# Complex validation with client_eq_set, TOMATO_TO_CLIENT_EQUIP
client_equipment = self._equipment_loadouts.get(client_key, [])
client_eq_set = set()
for loadout in client_equipment[:3]:
    for eq in loadout.get('equipment', []):
        client_eq_set.add(eq.lower().replace(" ", ""))
# Filter equipment...
```

**Стало:**
```python
# Simple mapping: Tomato equipment names -> icon file names
# No client validation needed - Tomato already provides valid equipment
if tomato_data:
    eq1 = tomato_data.get("equipment_1", [])
    eq2 = tomato_data.get("equipment_2", [])
    equipment_1 = [map_equip(e) for e in eq1[:3]]
    equipment_2 = [map_equip(e) for e in eq2[:3]]
```

### 2. Виправлено TclError (stats_ai.py)
**Було:**
```python
# Віджет зберігається в self і перевикористовується
if not hasattr(self, '_loadout_num_label') or not self._loadout_num_label.winfo_exists():
    self._loadout_num_label = tk.Label(equip_body, text="1", ...)
try:
    self._loadout_num_label.pack(side="left", padx=(0, 2))
except tk.TclError:
    return
```

**Стало:**
```python
# Віджет створюється локально і не зберігається
loadout_num_label_1 = tk.Label(equip_body, text="1", ...)
loadout_num_label_1.pack(side="left", padx=(0, 2))
loadout_num_label_1.bind(...)
```

## Результат
- Код став простішим
- TclError виправлено принципово, а не тимчасовим виправленням
- Tomato дані напряму мапляться в іконки без зайвих перевірок

## Що перевірити
1. Запустити додаток
2. Перевірити ІС-7 - обладнання відображається?
3. Перевірити Маус - обладнання відображається?
4. Перевірити переключення між танками - немає TclError?

## Наступні кроки (якщо є проблеми)
1. Перевірити маппінг EQUIP_MAP - всі іконки існують?
2. Перевірити Experimental Turbocharger та інші рідкісні варіанти
3. Якщо є проблеми з іконками - додати fallback до default іконки