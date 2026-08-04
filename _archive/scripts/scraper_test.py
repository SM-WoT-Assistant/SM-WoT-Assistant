import sys
import time
import urllib.parse
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView

app = QApplication(sys.argv)
view = QWebEngineView()

def on_load_finished(ok):
    print(f"Page loaded: {ok}")
    if not ok:
        app.quit()
        return

    # Try to extract text after a delay
    def extract_html():
        view.page().toHtml(lambda html: print_html(html))
        
    def print_html(html):
        print(f"HTML length: {len(html)}")
        with open('scraper_test_out.html', 'w', encoding='utf-8') as f:
            f.write(html)
        app.quit()
        
    QTimer.singleShot(5000, extract_html)

prompt = "Hello AI, what is 2+2?"
url = f"https://www.google.com/search?q={urllib.parse.quote(prompt)}&udm=50"
print(f"Loading {url}")
view.loadFinished.connect(on_load_finished)
view.load(QUrl(url))

# Start
QTimer.singleShot(30000, app.quit) # timeout
app.exec()
