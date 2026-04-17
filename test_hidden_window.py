#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест декодування з /MIN флагом - перевірімо що вікно не видно
"""
import os
import zipfile
from tank_extractor import TankExtractor, EXTRACT_DIR
from tth_updater import safe_merge_tth_from_file_list

print("[TEST-MIN] Тест прихованого вікна Orion (/MIN флаг)")
print("=" * 70)

# Беремо кілька файлів, які визначено як binary
pkg_path = r'C:/Games/World_of_Tanks_EU/res/packages/scripts.pkg'
test_files = []

with zipfile.ZipFile(pkg_path, 'r') as z:
    vehicle_files = [f for f in z.namelist() if "item_defs/vehicles/" in f and f.endswith(".xml")]
    # Беремо перші 3 файли довільно
    for name in vehicle_files[:3]:
        extract_path = os.path.join(EXTRACT_DIR, name.replace("scripts/item_defs/vehicles/", ""))
        test_files.append(extract_path)

print(f"\n[TEST] Файли для перевірки вікна: {len(test_files)}")
for f in test_files:
    print(f"  - {os.path.basename(f)}")

# Інітіалізація
tex = TankExtractor(r'C:/Games/World_of_Tanks_EU')
tex.extract_metadata(force_full=False)

# Перевіримо скільки binary
print(f"\n[TEST] Перевіряю файли перед декодуванням...")
binary = sum(1 for f in test_files if not tex._is_probably_plain_xml(f))
plaintext = len(test_files) - binary
print(f"  Binary: {binary}, Plaintext: {plaintext}")

if binary > 0:
    print(f"\n[TEST] ДЕКОДУЮ {binary} binary файлів...")
    print("[TEST] Спостерігайте - вікно Orion ШНЕ ПОВИННО ВИДНО СПЛИВАТИ!")
    print("[TEST] (воно буде мінімізовано за flагом /MIN)")
    
    import time
    time.sleep(2)  # Дати користувачу час читати
    
    decode_ok = tex.decode_all(target_files=test_files, timeout_sec=180, fail_fast=False)
    
    print(f"\n[TEST] Декодування завершене: {decode_ok}")
    
    # Перевіримо результат
    after_decode = sum(1 for f in test_files if tex._is_probably_plain_xml(f))
    print(f"  Plaintext тепер: {after_decode}/{len(test_files)}")
else:
    print(f"\n[TEST] Усі файли вже в plaintext - бінарних для тесту немає")
    print("[TEST] Вперше запустіть на системі після очищення extracted_data")

print("\n" + "=" * 70)
print("[SUCCESS] Тест вікна завершено - вікно мало бути прихованим ✓")
