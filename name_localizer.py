"""
name_localizer.py — Читає .mo файли клієнта WoT та оновлює tank_db.json
правильними внутрішньоігровими назвами танків.

Використання:
    python name_localizer.py          # оновити tank_db.json
    python name_localizer.py --check  # показати статистику без збереження
"""

import struct
import os
import json
import re
import argparse

# Назви .mo файлів для кожної нації
NATION_MO_MAP = {
    "USA":        "usa_vehicles.mo",
    "USSR":       "ussr_vehicles.mo",
    "Germany":    "germany_vehicles.mo",
    "France":     "france_vehicles.mo",
    "UK":         "gb_vehicles.mo",
    "Japan":      "japan_vehicles.mo",
    "China":      "china_vehicles.mo",
    "Czech":      "czech_vehicles.mo",
    "Sweden":     "sweden_vehicles.mo",
    "Italy":      "italy_vehicles.mo",
    "Poland":     "poland_vehicles.mo",
    "Multi":      "multinational_vehicles.mo",  # ігор. техніка декількох націй
}

# Суфікси, які ми стрипаємо при пошуку базової назви (порядок важливий)
STRIP_SUFFIXES = [
    "_7x7", "_fl", "_mk", "_sh", "_gold", "_prem", "_b", "_ig", 
    "_ic4_3dst", "_cfe_a", "_rush_ep1",
    "_7x7_2", "_beijing_opera", "_mod_1971b_mk",
]


def read_mo(filepath: str) -> dict[str, str]:
    """Парсить GNU .mo бінарний файл та повертає словник {msgid: msgstr}."""
    try:
        with open(filepath, "rb") as f:
            data = f.read()

        magic = struct.unpack("<I", data[:4])[0]
        if magic == 0x950412DE:
            endian = "<"
        elif magic == 0xDE120495:
            endian = ">"
        else:
            print(f"[WARN] Невідомий формат .mo: {filepath}")
            return {}

        num_strings = struct.unpack(endian + "I", data[8:12])[0]
        orig_offset = struct.unpack(endian + "I", data[12:16])[0]
        trans_offset = struct.unpack(endian + "I", data[16:20])[0]

        result = {}
        for i in range(num_strings):
            o_len, o_off = struct.unpack(endian + "II", data[orig_offset + i * 8: orig_offset + i * 8 + 8])
            t_len, t_off = struct.unpack(endian + "II", data[trans_offset + i * 8: trans_offset + i * 8 + 8])
            msgid  = data[o_off:  o_off  + o_len].decode("utf-8", errors="ignore")
            msgstr = data[t_off:  t_off  + t_len].decode("utf-8", errors="ignore")
            if msgid and msgstr:
                result[msgid] = msgstr
        return result
    except Exception as e:
        print(f"[WARN] Не вдалося прочитати {filepath}: {e}")
        return {}


def build_name_dict(mo_dir: str) -> dict[str, str]:
    """
    Будує загальний словник {tank_tag: display_name} зі всіх .mo файлів.
    Правило: ключ відповідає тегу у tree XML (наприклад A67_T57_58),
    значення — відображувана назва гравцю (T57 Heavy).

    Виключаємо суфіксні записи (_descr, _short, _long_special і т.д.),
    а також записи тюнінгу (Chassis_, Turret_, Gun_, Engine_, _<caliber>mm).
    """
    name_dict: dict[str, str] = {}

    SKIP_PREFIXES = ("Chassis_", "Turret_", "Gun_", "Engine_", "Radio_",
                     "Suspension_", "Sticker_", "Inscription_")
    SKIP_SUFFIXES = ("_descr", "_short", "_long_special", "_short_special",
                     "_kind", "_nation", "_class")
    # Underscore-prefixed names that ARE vehicle names (e.g. _Hotchkiss_H35)
    # We allow them but filter calibre-pattern keys like _57mm_

    for nation, mo_name in NATION_MO_MAP.items():
        mo_path = os.path.join(mo_dir, mo_name)
        if not os.path.exists(mo_path):
            print(f"[INFO] Не знайдено: {mo_name} — пропускаємо")
            continue

        strings = read_mo(mo_path)
        count = 0
        for msgid, msgstr in strings.items():
            # Фільтр: метадані і частини устаткування
            if any(msgid.startswith(p) for p in SKIP_PREFIXES):
                continue
            if any(msgid.endswith(s) for s in SKIP_SUFFIXES):
                continue
            # Фільтр: рядки для снарядів (_57mm_...), двигунів, ін.
            if re.match(r"^_\d+", msgid):
                continue
            name_dict[msgid] = msgstr
            count += 1

        print(f"[MO] {mo_name}: завантажено {count} назв")

    return name_dict


def find_name(tag: str, name_dict: dict[str, str]) -> str | None:
    """
    Шукає відображувану назву для тегу танка.
    1. Точне співпадіння:       A67_T57_58        → T57 Heavy
    2. Стрипування суфіксів:   A67_T57_58_Gold   → шукає A67_T57_58
    3. Стрип нумерного префікса: F03_D2           → шукає D2
    4. З підкресленням:        F12_Hotchkiss_H35  → шукає _Hotchkiss_H35
    5. Fuzzy: остання частина  Ch41_WZ_111_QL    → шукає Ch41_WZ_111
    """
    import re as _re

    # 1. Точний збіг
    if tag in name_dict:
        return name_dict[tag]

    # 2. Стрипування відомих суфіксів (case-insensitive порівняння)
    tag_lower = tag.lower()
    for suffix in STRIP_SUFFIXES:
        if tag_lower.endswith(suffix):
            base = tag[: len(tag) - len(suffix)]
            if base in name_dict:
                return name_dict[base]

    # 3. Стрипування нумерного нац-префіксу  (F03_D2 → D2, A57_M8A1 → M8A1)
    stripped = _re.sub(r'^[A-Za-z]{1,3}\d+_', '', tag)
    if stripped and stripped != tag:
        if stripped in name_dict:
            return name_dict[stripped]
        # Також спробуємо з prefix-underscore  (_Hotchkiss_H35)
        under = "_" + stripped
        if under in name_dict:
            return name_dict[under]

    # 4. Underscore-prefix fallback (_Hotchkiss_H35 стиль)
    under = "_" + tag
    if under in name_dict:
        return name_dict[under]

    # 5. Fuzzy: відкидаємо останній сегмент (Ch41_WZ_111_QL → Ch41_WZ_111)
    parts = tag.rsplit("_", 1)
    if len(parts) == 2 and parts[0] in name_dict:
        return name_dict[parts[0]]

    return None


def update_tank_db(wot_path: str, db_path: str = "tank_db.json", dry_run: bool = False) -> None:
    """
    Основна функція: завантажує .mo словники і оновлює name у tank_db.json.
    """
    mo_dir = os.path.join(wot_path, "res", "text", "lc_messages")
    if not os.path.isdir(mo_dir):
        print(f"[ERROR] Не знайдено папку lc_messages: {mo_dir}")
        return

    print(f"[INFO] Читаємо локалізаційні файли з: {mo_dir}")
    name_dict = build_name_dict(mo_dir)
    print(f"[INFO] Загальний словник: {len(name_dict)} записів\n")

    if not os.path.exists(db_path):
        print(f"[ERROR] Не знайдено {db_path}")
        return

    with open(db_path, "r", encoding="utf-8") as f:
        tank_db: dict = json.load(f)

    updated = 0
    not_found = []

    for tag, data in tank_db.items():
        real_name = find_name(tag, name_dict)
        if real_name:
            if data.get("name") != real_name:
                if not dry_run:
                    data["name"] = real_name
                updated += 1
        else:
            not_found.append(tag)

    total = len(tank_db)
    found = total - len(not_found)
    print(f"[RESULT] Знайдено: {found}/{total} ({100*found/total:.1f}%)")
    print(f"[RESULT] Оновлено назв: {updated}")
    if not_found:
        print(f"[WARN] Не знайдено назв для {len(not_found)} танків:")
        for t in not_found[:20]:
            print(f"         {t} (поточна назва: '{tank_db[t].get('name', '?')}')")
        if len(not_found) > 20:
            print(f"         ... та ще {len(not_found) - 20}")

    if not dry_run:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(tank_db, f, ensure_ascii=False, indent=4)
        print(f"\n[SUCCESS] {db_path} оновлено!")
    else:
        print("\n[DRY-RUN] Зміни НЕ збережено (режим --check)")


# ─────────────────────────────────────────────────────────────────
# Публічний API для виклику з tank_extractor.py або main.py
# ─────────────────────────────────────────────────────────────────

def localize_tank_db(wot_path: str, db_path: str = "tank_db.json") -> None:
    """Викликається після build_database() для підстановки реальних назв."""
    update_tank_db(wot_path, db_path, dry_run=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Оновити назви танків у tank_db.json із файлів гри.")
    parser.add_argument("--check", action="store_true", help="Показати статистику без збереження")
    parser.add_argument("--db", default="tank_db.json", help="Шлях до tank_db.json")
    args = parser.parse_args()

    try:
        with open("settings.json", "r") as f:
            settings = json.load(f)
        wot_path = settings.get("wot_path", "")
        if not wot_path:
            print("[ERROR] wot_path не заповнено у settings.json")
        else:
            update_tank_db(wot_path, args.db, dry_run=args.check)
    except FileNotFoundError:
        print("[ERROR] settings.json не знайдено")
    except Exception as e:
        print(f"[ERROR] {e}")
