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
    if not tex.extract_metadata(force_full=True):
        print("[ERROR] extract_metadata failed")
        return

    # 2) Python-декодування для всіх XML + TTH
    tex.update_tth_database_safe(allow_decode_retry=True)


if __name__ == "__main__":
    main()
