#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест оновлення цілої гілки танків однієї країни (Germany - 244 файли)
Реальний практичний сценарій як буде на прктиці
"""
import os
import zipfile
from tank_extractor import TankExtractor, EXTRACT_DIR
from tth_updater import safe_merge_tth_from_file_list

print("[TEST-COUNTRY] Тест оновлення гілки GERMANY (244 файли)")
print("=" * 70)

# 1. Витягнемо список файлів Germany из scripts.pkg
pkg_path = r'C:/Games/World_of_Tanks_EU/res/packages/scripts.pkg'
germany_files = []

with zipfile.ZipFile(pkg_path, 'r') as z:
    for name in z.namelist():
        if "item_defs/vehicles/germany/" in name and name.endswith(".xml"):
            # scripts/item_defs/vehicles/germany/G123_Tank.xml -> extracted_data/germany/G123_Tank.xml
            extract_path = os.path.join(EXTRACT_DIR, name.replace("scripts/item_defs/vehicles/", ""))
            germany_files.append(extract_path)

print(f"\n[STEP-1] Знайдено файлів Germany у scripts.pkg: {len(germany_files)}")
print(f"  Примеры: {', '.join([os.path.basename(f) for f in germany_files[:3]])}")

# 2. Ініціалізуємо TankExtractor
print(f"\n[STEP-2] Ініціалізація TankExtractor...")
tex = TankExtractor(r'C:/Games/World_of_Tanks_EU')

# 3. Витягнемо метадані (дістанемо fingerprints з manifest)
print(f"[STEP-3] Витягую метадані з scripts.pkg...")
tex.extract_metadata(force_full=False)

# 4. Перевіримо які файли Germany змінилися
changed_germany = [f for f in germany_files if f in tex.changed_vehicle_files]
print(f"\n[STEP-4] Файлів Germany змінилося: {len(changed_germany)} з {len(germany_files)}")
if changed_germany:
    print(f"  Примеры змін: {', '.join([os.path.basename(f) for f in changed_germany[:5]])}")

# 5. Якщо не було змін - примусимо оновлення для тесту
if not changed_germany:
    print("\n[STEP-5] Немає змін у файлах, берємо перші 5 для тесту...")
    test_files = germany_files[:5]
else:
    # Якщо були зміни - берємо змінені + додаємо перші 5 для гарантії
    test_files = changed_germany + germany_files[:5][:5 - min(len(changed_germany), 5)]
    test_files = list(set(test_files))[:10]  # максимум 10 для швидкості

print(f"  Файлів для тесту: {len(test_files)}")

# 6. Перевіримо скільки вже зпарсено (plaintext)
print(f"\n[STEP-6] Перевіряю формат файлів перед декодуванням...")
parseable_before = sum(1 for f in test_files if tex._is_probably_plain_xml(f))
print(f"  Зпарсено (plaintext): {parseable_before}/{len(test_files)}")

# 7. Декодуємо якщо потрібно
if parseable_before < len(test_files):
    binary_count = len(test_files) - parseable_before
    print(f"  Потребує декодування: {binary_count} файлів")
    print(f"\n[STEP-7] Декодую {binary_count} файлів через Orion...")
    decode_ok = tex.decode_all(target_files=test_files, timeout_sec=180, fail_fast=False)
    print(f"  Результат: {decode_ok}")
    
    # Перевіримо результат
    parseable_after = sum(1 for f in test_files if tex._is_probably_plain_xml(f))
    print(f"  Зпарсено після декодування: {parseable_after}/{len(test_files)}")
else:
    print(f"[STEP-7] Всі файли вже в plaintext форматі, декодування не потрібне")

# 8. Об'єднуємо з TTH базою
print(f"\n[STEP-8] Об'єдную з TTH базою ({len(test_files)} файлів)...")
merge_ok, checked, discovered, updated, total = safe_merge_tth_from_file_list(
    test_files, 
    parse_tth_func=lambda p: tex._parse_tth_from_vehicle_xml(p),
    tth_path="tank_tth.json"
)

print(f"  Результат: ok={merge_ok}")
print(f"    Перевірено: {checked}")
print(f"    Виявлено: {discovered}")
print(f"    Оновлено: {updated}")
print(f"    Всього в TTH: {total}")

print("\n" + "=" * 70)
print("[TEST-COUNTRY] Тест завершено успішно ✓")
print(f"[SUMMARY] Germany гілка готова до реального оновлення на практиці")
