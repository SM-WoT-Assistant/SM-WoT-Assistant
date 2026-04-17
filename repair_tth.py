import json
from tank_extractor import TankExtractor


def main():
    with open("settings.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
    wot_path = settings.get("wot_path", "")

    if not wot_path:
        print("[ERROR] Немає wot_path у settings.json")
        return

    tex = TankExtractor(wot_path)

    # 1) Оновлюємо metadata, щоб мати актуальні XML у extracted_data
    if not tex.extract_metadata(force_full=False):
        print("[ERROR] extract_metadata failed")
        return

    # 2) Безпечний merge (без Orion)
    tex.update_tth_database_safe(allow_decode_retry=False)

    # 3) Точковий ремонт відсутніх TTH через Orion батчами
    tex.repair_missing_tth_with_orion(batch_size=20, timeout_sec=75)


if __name__ == "__main__":
    main()
