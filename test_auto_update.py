#!/usr/bin/env python3
"""
Інструмент для тестування автоматичного оновлення TTH при зміні версії клієнта.
Дозволяє мокувати нову версію та перевіряти, що:
1. Версія коректно детектується
2. Змінені файли правильно ідентифікуються
3. Декодування запускається автоматично (тільки для змінених файлів)
4. Результати логуються та доступні для аналізу
"""

import os
import json
import sys
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
MANIFEST_FILE = os.path.join(BASE_DIR, ".tank_extract_manifest.json")


def log_test(msg, level="INFO"):
    """Логування з часовою міткою."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{timestamp}] [{level}]"
    print(f"{prefix} {msg}")


def load_json(path):
    """Завантажує JSON файл."""
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_test(f"Помилка читання {path}: {e}", "ERROR")
            return {}
    return {}


def save_json(path, data):
    """Зберігає JSON файл."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log_test(f"Зберігаю {os.path.basename(path)}")
        return True
    except Exception as e:
        log_test(f"Помилка запису {path}: {e}", "ERROR")
        return False


def mock_new_version(new_version):
    """
    Мокує нову версію клієнта, змінюючи гру_version у settings.json
    та очищаючи manifest для перевикликання версійної перевірки.
    """
    log_test("=" * 60)
    log_test("МОКУВАННЯ НОВОЇ ВЕРСІЇ КЛІЄНТА")
    log_test("=" * 60)
    
    settings = load_json(SETTINGS_FILE)
    old_version = settings.get("game_version", "невідома")
    
    log_test(f"Старта версія: '{old_version}'")
    log_test(f"Нова версія: '{new_version}'")
    
    # Змінюємо версію
    settings["game_version"] = new_version
    settings["tth_schema_version"] = 1  # Знижуємо схему, щоб зробити rebuild обов'язковим
    
    if save_json(SETTINGS_FILE, settings):
        log_test(f"✓ Версія змінена на '{new_version}'", "SUCCESS")
        return True
    else:
        log_test("✗ Не вдалося змінити версію", "ERROR")
        return False


def analyze_manifest_changes():
    """
    Аналізує manifest файли для виявлення тісяч змінених файлів.
    """
    log_test("=" * 60)
    log_test("АНАЛІЗ ЗМІНЕНИХ ФАЙЛІВ")
    log_test("=" * 60)
    
    manifest_file = os.path.join(BASE_DIR, ".tank_extract_manifest.json")
    manifest = load_json(manifest_file)
    
    if not manifest:
        log_test("Manifest пустий або не знайдено", "WARN")
        return {"total": 0, "changed": 0, "by_nation": {}}
    
    # Групуємо за країною
    by_nation = {}
    for path_key, fp in manifest.items():
        if "vehicles/" not in path_key:
            continue
        
        parts = path_key.split('/')
        if len(parts) >= 2:
            nation = parts[0].lower()
            if nation not in by_nation:
                by_nation[nation] = {"total": 0, "samples": []}
            by_nation[nation]["total"] += 1
            if len(by_nation[nation]["samples"]) < 3:
                by_nation[nation]["samples"].append(path_key)
    
    total_entries = len(manifest)
    log_test(f"Всього записів у manifest: {total_entries}")
    log_test("\nКількість файлів по країнах:")
    for nation in sorted(by_nation.keys()):
        stats = by_nation[nation]
        log_test(f"  {nation.upper()}: {stats['total']} файлів")
    
    return {"total": total_entries, "by_nation": by_nation}


def check_extract_dir():
    """
    Перевіряє вміст extracted_data директорії.
    """
    log_test("=" * 60)
    log_test("СТАТУС ВИТЯГНУТИХ ДАНИХ")
    log_test("=" * 60)
    
    extract_dir = os.path.join(BASE_DIR, "extracted_data")
    if not os.path.exists(extract_dir):
        log_test(f"✗ Директорія {extract_dir} не існує", "WARN")
        return False
    
    nations = []
    total_files = 0
    for nation in os.listdir(extract_dir):
        nation_path = os.path.join(extract_dir, nation)
        if os.path.isdir(nation_path):
            count = 0
            for root, dirs, files in os.walk(nation_path):
                count += len([f for f in files if f.endswith('.xml')])
            nations.append((nation, count))
            total_files += count
    
    log_test(f"Знайдено {len(nations)} країн(и)")
    for nation, count in sorted(nations):
        log_test(f"  {nation.upper()}: {count} XML файлів")
    
    log_test(f"♦ Всього XML файлів: {total_files}")
    return True


def check_tanks_db():
    """
    Перевіряє статус базового файлу tank_db.json та tank_tth.json
    """
    log_test("=" * 60)
    log_test("СТАТУС БАЗ ДАНИХ ТАНКІВ")
    log_test("=" * 60)
    
    files_to_check = {
        "tank_db.json": "Основна база танків",
        "tank_tth.json": "Database технічних характеристик"
    }
    
    for filename, description in files_to_check.items():
        filepath = os.path.join(BASE_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            data = load_json(filepath)
            
            if isinstance(data, dict):
                count = len(data)
                log_test(f"✓ {filename}: {count} записів ({size:,} байт)")
            else:
                log_test(f"✗ {filename}: неважливий формат ({size:,} байт)", "WARN")
        else:
            log_test(f"✗ {filename}: НЕ ЗНАЙДЕНО", "WARN")


def simulate_update_check():
    """
    Симулює процес перевірки оновлення, який запускається при старті програми.
    Показує, які кроки буде виконано.
    """
    log_test("=" * 60)
    log_test("СИМУЛЯЦІЯ ПЕРЕВІРКИ ОНОВЛЕННЯ")
    log_test("=" * 60)
    
    settings = load_json(SETTINGS_FILE)
    game_version = settings.get("game_version", "невідома")
    tth_schema = int(settings.get("tth_schema_version", 0))
    
    log_test(f"Поточна версія клієнта (settings): {game_version}")
    log_test(f"Поточна TTH схема: {tth_schema}")
    
    # Спробуємо імпортувати map_extractor для перевірки реальної версії
    try:
        sys.path.insert(0, BASE_DIR)
        import map_extractor
        
        ext = map_extractor.MapExtractor()
        real_version = ext.get_version()
        log_test(f"Реальна версія з game (game/version.xml): {real_version}")
        
        if real_version:
            if real_version == game_version:
                log_test("✓ Версії відповідають - оновлення НЕ потрібне")
                return "match"
            else:
                log_test(f"✗ ВЕРСІЯ ЗМІНИЛАСЯ: {game_version} → {real_version}", "WARN")
                return "mismatch"
        else:
            log_test("✗ Не вдалося прочитати версію з game/version.xml", "ERROR")
            return "error"
    except Exception as e:
        log_test(f"⚠ Не вдалося перевірити реальну версію: {e}", "WARN")
        log_test("  (Це нормально, якщо шлях до гри неправильний)")
        return "unknown"


def print_recommendations():
    """
    Виводить рекомендації щодо наступних кроків.
    """
    log_test("=" * 60)
    log_test("РЕКОМЕНДАЦІЇ ЩОДО ТЕСТУВАННЯ")
    log_test("=" * 60)
    
    print("""
1. МОКУВАННЯ ВЕРСІЇ:
   Скрипт мокує нову версію у settings.json. На наступному старті,
   програма детектує зміну версії і запустить автооновлення.

2. АВТООНОВЛЕННЯ:
   - На старті програма (main.py) запускає перевірку версії в фоні
   - Якщо версія змінилася, запускається map_extractor та tank_extractor
   - У stability_mode=True (за замовчуванням), виконується безпечне TTH оновлення
   - Орион автоматично викликається для декодування XML (у скритому режимі)

3. СПОСТЕРЕЖЕННЯ:
   - Дивіться на логи в консолі (повинні бути повідомлення [EXTRACTION], [DECODER])
   - Перевіріть tank_tth.json: має бути оновлений з новими значеннями полів
   - Дивіться скрин AI STATS редстаба - TTH значення мають прирости

4. ПЕРЕВІРКА ЗМІН ФАЙЛІВ:
   - Кількість "Змінені XML техніки" має бути > 0
   - Орион запускається тільки для змінених файлів (батчами по 24)
   - Якщо немає змін, декодування пропускається (оптимізація)

5. ПОВТОРНЕ ТЕСТУВАННЯ:
   - Щоб повернутися до попередньо версії, відредагуйте settings.json вручну
   - Або запустіть цей скрипт з іншою версією: python test_auto_update.py <нова_версія>
     """)


def main():
    """Основна функція."""
    print("\n")
    log_test("╔════════════════════════════════════════════════════════════╗", "")
    log_test("║         ТЕСТ АВТОМАТИЧНОГО ОНОВЛЕННЯ TTH                  ║", "")
    log_test("╚════════════════════════════════════════════════════════════╝", "")
    print()
    
    # Якщо передана версія як аргумент, мокуємо її
    if len(sys.argv) > 1:
        new_version = " ".join(sys.argv[1:])
        if not mock_new_version(new_version):
            sys.exit(1)
        time.sleep(1)
    
    # Аналізуємо поточний стан
    check_extract_dir()
    print()
    analyze_manifest_changes()
    print()
    check_tanks_db()
    print()
    simulate_update_check()
    print()
    print_recommendations()
    
    log_test("=" * 60)
    log_test("ТЕСТ ЗАВЕРШЕНО", "SUCCESS")
    log_test("=" * 60)


if __name__ == "__main__":
    main()
