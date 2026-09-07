"""admin_backend.api - Flask + SSE endpoints for the webview frontend.

STUB — full implementation pending. This module sets up Flask routes
for the admin web UI. See admin_backend.build_generator for build API.
"""
from __future__ import annotations
import json
import os
import sys
import threading
import time
from typing import Optional

# Try to import Flask (optional)
try:
    from flask import Flask, Response, jsonify, request
    from flask_cors import CORS
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Flask = None

try:
    import admin_auth
except ImportError:
    admin_auth = None

try:
    from admin_backend.core import Application
except ImportError:
    Application = None

_APP = None  # type: ignore


def _bundle_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def set_app(app):
    """Attach the Application instance to the API."""
    global _APP
    _APP = app


def get_app():
    return _APP


def _create_flask_app():
    if not _HAS_FLASK:
        raise RuntimeError("Flask is not installed. Run: pip install flask flask-cors")
    flask_app = Flask(__name__, static_folder=_bundle_dir(), static_url_path="")
    CORS(flask_app)

    @flask_app.route("/")
    def index():
        return flask_app.send_static_file("index.html")

    @flask_app.route("/api/status")
    def api_status():
        if _APP is None:
            return jsonify({"running": False, "wot_path": ""})
        return jsonify(_APP.get_status())

    @flask_app.route("/api/log")
    def api_log():
        if _APP is None:
            return jsonify({"lines": []})
        return jsonify({"lines": _APP._log_buffer[-100:]})

    @flask_app.route("/api/scan", methods=["POST"])
    def api_scan():
        if _APP is None:
            return jsonify({"ok": False, "error": "no app"})
        changed = _APP.start_scan()
        return jsonify({"ok": True, "changed": changed})

    @flask_app.route("/api/generate", methods=["POST"])
    def api_generate():
        if _APP is None:
            return jsonify({"ok": False, "error": "no app"})
        ok, reasons = _APP.start_generation()
        return jsonify({"ok": ok, "reasons": reasons})

    @flask_app.route("/api/prompts")
    def api_prompts():
        from admin_backend.prompts import load_prompts_merged
        return jsonify(load_prompts_merged())

    return flask_app


def run_api(host="127.0.0.1", port=8765):
    """Run Flask API in the current thread (blocking)."""
    app = _create_flask_app()
    app.run(host=host, port=port, debug=False, use_reloader=False)


def run_api_threaded(host="127.0.0.1", port=8765):
    """Start Flask API in a daemon thread, return the Thread."""
    app = _create_flask_app()
    t = threading.Thread(target=app.run, kwargs={"host": host, "port": port, "debug": False, "use_reloader": False}, daemon=True)
    t.start()
    return t
