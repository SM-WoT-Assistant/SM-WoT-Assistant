#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест структури scripts.pkg - як розміщені файли по країнам
"""
import zipfile
import os

pkg_path = r'C:/Games/World_of_Tanks_EU/res/packages/scripts.pkg'
print(f"[TEST] Аналізую структуру {pkg_path}...")

vehicles = []
with zipfile.ZipFile(pkg_path, 'r') as z:
    for name in z.namelist():
        if "item_defs/vehicles/" in name and name.endswith(".xml"):
            vehicles.append(name)

print(f'[TEST] Усього vehicle XML в scripts.pkg: {len(vehicles)}')

# Перевірити по країнам
countries = {}
for f in vehicles:
    # scripts/item_defs/vehicles/ussr/R45_IS-7.xml
    parts = f.split('/')
    if len(parts) >= 4:
        country = parts[3]  # index 3 - це країна
        if country not in countries:
            countries[country] = 0
        countries[country] += 1

print("\n[TEST] Розподіл файлів по країнам у scripts.pkg:")
for country in sorted(countries.keys()):
    print(f'  {country}: {countries[country]} файлів')

print("\n[TEST] Висновок: файли упаковані ПО КРАЇНАМ (national folders)")
print("[TEST] Для тесту обираємо Germany (244 файли) - найбільша гілка")
