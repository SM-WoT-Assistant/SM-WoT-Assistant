import sys
import json
sys.path.insert(0, '.')
from tomato_scraper import create_scraper, get_tank_info
from PyQt6.QtCore import QUrl, QTimer

tank_code = 'R45_IS-7'
tank_id, tank_slug = get_tank_info(tank_code)

app, view = create_scraper()

def on_load_finished(ok):
    print(f"[TOMATO] Page loaded: {ok}")
    if ok:
        QTimer.singleShot(5000, extract_data)
    else:
        app.quit()

def extract_data():
    js_code = """
    (function() {
        // Check all network requests
        var resources = performance.getEntriesByType('resource');
        var apiCalls = [];
        for (var i = 0; i < resources.length; i++) {
            var url = resources[i].name;
            if (url.includes('api') || url.includes('loadout') || url.includes('consumable')) {
                apiCalls.push(url);
            }
        }
        // Also check window.__NEXT_DATA__ for loadouts section
        var nextData = document.getElementById('__NEXT_DATA__');
        if (nextData) {
            var data = JSON.parse(nextData.textContent);
            var props = data.props.pageProps;
            return {
                keys: Object.keys(props),
                loadoutKeys: props.loadouts ? Object.keys(props.loadouts) : 'NO LOADOUTS',
                equipKeys: props.equipment ? Object.keys(props.equipment) : 'NO EQUIPMENT',
                apiCalls: apiCalls.slice(0, 20)
            };
        }
        return null;
    })()
    """

    def js_result(data):
        if data:
            print(f"Keys in pageProps: {data.get('keys')}")
            print(f"Loadouts: {data.get('loadoutKeys')}")
            print(f"Equipment: {data.get('equipKeys')}")
            print(f"\nAPI calls found:")
            for c in data.get('apiCalls', [])[:10]:
                print(f"  {c}")
        app.quit()

    view.loadFinished.connect(on_load_finished)
    url = f"https://tomato.gg/tanks/{tank_id}/{tank_slug}/EU"
    print(f"[TOMATO] Loading: {url}")
    view.setUrl(QUrl(url))
    app.exec()