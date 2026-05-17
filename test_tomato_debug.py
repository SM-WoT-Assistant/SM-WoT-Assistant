import sys
import json
sys.path.insert(0, '.')
from tomato_scraper import create_scraper, get_tank_info
from PyQt6.QtCore import QUrl, QTimer
import time

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)
url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"

app, view = create_scraper()

result = {}

def on_load_finished(ok):
    print(f"[TOMATO] Page loaded: {ok}")
    if ok:
        QTimer.singleShot(5000, extract_data)
    else:
        app.quit()

def extract_data():
    js_code = """
    (function() {
        // Get all text content
        var text = document.body.innerText;
        // Try to find loadout data in scripts or data attributes
        var scripts = document.querySelectorAll('script');
        var dataObj = null;
        for (var i = 0; i < scripts.length; i++) {
            var content = scripts[i].textContent;
            if (content.includes('loadout') || content.includes('consumable')) {
                console.log('Found script with loadout data');
            }
        }
        // Try to get data from window or global state
        var jsonData = {};
        try {
            // Look for __NEXT_DATA__ or similar
            var nextData = document.getElementById('__NEXT_DATA__');
            if (nextData) {
                jsonData.nextData = JSON.parse(nextData.textContent);
            }
        } catch(e) {}
        return {
            text: text.substring(0, 5000),
            html: document.body.innerHTML.substring(0, 10000),
            hasNextData: !!document.getElementById('__NEXT_DATA__')
        };
    })()
    """

    def js_result(data):
        if data:
            print(f"[TOMATO] Has __NEXT_DATA__: {data.get('hasNextData')}")
            # Save text for analysis
            with open('tomato_text.txt', 'w', encoding='utf-8') as f:
                f.write(data.get('text', ''))
            print("Text saved to tomato_text.txt")
            # Check for consumables keywords in text
            text = data.get('text', '').lower()
            print(f"\n--- SEARCH FOR CONSUMABLES ---")
            for kw in ['large repair', 'small repair', 'first aid', 'extinguisher', 'rations', 'cola', 'chocolate']:
                if kw in text:
                    print(f"  FOUND: {kw}")
                else:
                    print(f"  MISSING: {kw}")
        app.quit()

    view.page().runJavaScript(js_code, js_result)

view.loadFinished.connect(on_load_finished)
print(f"[TOMATO] Loading: {url}")
view.setUrl(QUrl(url))
app.exec()