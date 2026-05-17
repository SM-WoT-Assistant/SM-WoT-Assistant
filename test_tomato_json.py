import sys
import json
sys.path.insert(0, '.')
from tomato_scraper import create_scraper, get_tank_info
from PyQt6.QtCore import QUrl, QTimer

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

app, view = create_scraper()

def on_load_finished(ok):
    print(f"[TOMATO] Page loaded: {ok}")
    if ok:
        QTimer.singleShot(3000, extract_data)
    else:
        app.quit()

def extract_data():
    js_code = """
    (function() {
        var nextData = document.getElementById('__NEXT_DATA__');
        if (nextData) {
            return JSON.parse(nextData.textContent);
        }
        return null;
    })()
    """

    def js_result(data):
        if data:
            # Save full JSON
            with open('tomato_next_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("Next data saved to tomato_next_data.json")

            # Search for consumables in the JSON
            def search(obj, path=""):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        search(v, f"{path}.{k}")
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        search(item, f"{path}[{i}]")
                elif isinstance(obj, str):
                    lower = obj.lower()
                    if 'consum' in lower or 'repair' in lower or 'medkit' in lower or 'extinguisher' in lower or 'ration' in lower:
                        print(f"  Found at {path}: {obj[:100]}")

            print("\n--- SEARCH FOR CONSUMABLES IN JSON ---")
            search(data)
        app.quit()

    view.page().runJavaScript(js_code, js_result)

view.loadFinished.connect(on_load_finished)
print(f"[TOMATO] Loading: {url}")
view.setUrl(QUrl(url))
app.exec()