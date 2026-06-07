#!/usr/bin/env python3
"""
ai_webview_gui.py - WebView для отримання даних через Google AI Mode.
Чиста сторінка → JS injection промту → читання відповіді.
"""
import sys
import os
from datetime import date

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile


REAL_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


class AIBrowserWindow(QWidget):
    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt
        self._poll_count = 0
        self._max_polls = 200
        self._response_found = False

        self.setWindowTitle("WoT Assistant — Data Update")
        self.setGeometry(100, 100, 1000, 700)
        self.setStyleSheet("background-color: white;")

        QTimer.singleShot(200, self._hide_taskbar_icon)

        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent(REAL_UA)

        self.browser = QWebEngineView()
        s = self.browser.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.browser)

        self.browser.loadFinished.connect(self.on_loaded)
        self.browser.setUrl(QUrl("https://www.google.com/search?q=&udm=50"))

    def _hide_taskbar_icon(self):
        try:
            import ctypes
            hwnd = int(self.winId())
            if hwnd == 0:
        # QTimer.singleShot(200, self._hide_taskbar_icon)
                return
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x80
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW)
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        except Exception:
            pass

    def on_loaded(self, ok):
        if not ok:
            print("ERROR:Page load failed", flush=True)
            QTimer.singleShot(1000, self.close)
            return
        QTimer.singleShot(3000, self.inject_prompt)

    def inject_prompt(self):
        js_prompt = self.prompt.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
        js = f"""
        (function() {{
            var ta = document.querySelector('div.Txyg0d textarea');
            if (!ta) ta = document.querySelector('div.AgWCw textarea');
            if (!ta) ta = document.querySelector('textarea');
            if (!ta) return;
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value'
            ).set;
            nativeInputValueSetter.call(ta, '{js_prompt}');
            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
            var enterEvent = new KeyboardEvent('keydown', {{
                key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
                bubbles: true, cancelable: true
            }});
            ta.dispatchEvent(enterEvent);
        }})();
        """
        self.browser.page().runJavaScript(js)
        QTimer.singleShot(2000, self.poll_response)

    def poll_response(self):
        self._poll_count += 1
        if self._poll_count > self._max_polls:
            print("ERROR:Timeout waiting for AI response", flush=True)
            QTimer.singleShot(1000, self.close)
            return

        js = """
        (function() {
            var div = document.querySelector('div.jUiaTd');
            if (div && div.textContent.trim().length > 0) return div.textContent.trim();
            var body = document.body.innerText;
            var idx = body.lastIndexOf('Build Generated:');
            if (idx >= 0) {
                var text = body.substring(idx);
                if (text.length > 100 && text.indexOf('[Item') < 0 && text.indexOf('[Count]') < 0 && text.indexOf('(choose ') < 0) return text;
            }
            return '';
        })();
        """
        self.browser.page().runJavaScript(js, self.check_response)

    def check_response(self, text):
        if text and len(text) > 10:
            print(f"[AI Browser] Response received ({len(text)} chars)", flush=True)
            print(text, flush=True)
            print("[AI Browser] RESPONSE_READY", flush=True)
            QTimer.singleShot(500, self.close)
        else:
            QTimer.singleShot(500, self.poll_response)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    prompt = ""
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--prompt' and i + 1 < len(sys.argv):
            prompt = sys.argv[i + 1]; i += 2
        else:
            i += 1

    if not prompt:
        today = date.today().strftime("%Y-%m-%d")
        prompt = f"{today}. In World of Tanks, compile a list of the 50 most popular tanks for tiers 8-11, using the exact tank names as they appear in the game client. List only the tank names, one per line."

    app = QApplication(sys.argv)
    window = AIBrowserWindow(prompt)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
