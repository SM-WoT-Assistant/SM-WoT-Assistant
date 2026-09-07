"""admin_backend.api - Flask + static asset routes for the webview frontend.

Static assets are pre-loaded at startup into a dict, then served via plain
Response objects. This avoids Flask's static_folder / application context
quirks (Flask 3.x send_static_file needs an active app context, which the
background-thread Flask runner does not provide on first request).
"""
from __future__ import annotations
import os
import sys
import threading
from typing import Optional

try:
    from flask import Flask, Response, jsonify, request
    from flask_cors import CORS
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Flask = None
    jsonify = None
    request = None


_APP: Optional["object"] = None

STATIC_CACHE: dict = {}
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


def _bundle_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_static_files():
    """Pre-load static files into memory.

    Tries admin_web/ subfolder (dev) then bundle root (frozen PyInstaller).
    """
    cache = {}
    bdir = _bundle_dir()
    if not os.path.isdir(bdir):
        return cache
    for base in (os.path.join(bdir, "admin_web"), bdir):
        if not os.path.isdir(base):
            continue
        rel_prefix = "" if base == bdir else "admin_web/"
        try:
            entries = os.listdir(base)
        except Exception:
            continue
        for entry in entries:
            full = os.path.join(base, entry)
            if os.path.isfile(full):
                if entry in ("index.html", "style.css") or entry.endswith(".css"):
                    try:
                        with open(full, "rb") as fp:
                            cache[rel_prefix + entry] = fp.read()
                    except Exception: pass
            elif os.path.isdir(full) and entry in ("css", "js"):
                try:
                    subs = os.listdir(full)
                except Exception:
                    continue
                for sub in subs:
                    sub_full = os.path.join(full, sub)
                    if os.path.isfile(sub_full):
                        try:
                            with open(sub_full, "rb") as fp:
                                cache[rel_prefix + f"{entry}/{sub}"] = fp.read()
                        except Exception: pass
    return cache

def _get_mime(path: str) -> str:
    _, ext = os.path.splitext(path)
    return MIME_TYPES.get(ext.lower(), "application/octet-stream")


def _make_response(body: bytes, path: str = "") -> "Response":
    return Response(body, mimetype=_get_mime(path))


def set_app(app):
    global _APP
    _APP = app


def get_app():
    return _APP


def _create_flask_app():
    if not _HAS_FLASK:
        raise RuntimeError("Flask is not installed. Run: pip install flask flask-cors")

    global STATIC_CACHE
    STATIC_CACHE = _load_static_files()

    flask_app = Flask(__name__)
    CORS(flask_app)

    @flask_app.route("/")
    def index():
        for _k in ("index.html", "admin_web/index.html"):
            if _k in STATIC_CACHE:
                return _make_response(STATIC_CACHE[_k], _k)
        if False:  # placeholder
            return _make_response(STATIC_CACHE["index.html"], "index.html")
        return Response("index.html not found", status=404, mimetype="text/plain")

    @flask_app.route("/<path:filename>")
    def static_file(filename):
        if ".." in filename or filename.startswith("/") or chr(92) in filename:
            return Response("forbidden", status=403, mimetype="text/plain")
        if filename in STATIC_CACHE:
            return _make_response(STATIC_CACHE[filename], filename)
        if ("admin_web/" + filename) in STATIC_CACHE:
            return _make_response(STATIC_CACHE["admin_web/" + filename], "admin_web/" + filename)
        return Response(f"not found: {filename}", status=404, mimetype="text/plain")

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
        try:
            ok, reasons = _APP.start_generation()
            return jsonify({"ok": ok, "reasons": reasons})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @flask_app.route("/api/prompts")
    def api_prompts():
        try:
            from admin_backend.prompts import load_prompts_merged
            return jsonify(load_prompts_merged())
        except Exception as e:
            return jsonify({})

    @flask_app.route("/api/builds")
    def api_builds():
        if _APP is None:
            return jsonify({})
        try:
            return jsonify(_APP.get_builds() or {})
        except Exception:
            return jsonify({})

    @flask_app.route("/api/settings", methods=["GET", "POST"])
    def api_settings():
        if _APP is None:
            return jsonify({})
        if request.method == "GET":
            return jsonify(getattr(_APP, "settings", {}) or {})
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "json object required"}), 400
        current = getattr(_APP, "settings", None)
        if current is None:
            current = {}
            _APP.settings = current
        current.update(data)
        try:
            _APP.save_settings()
            try:
                _APP.apply_launch_with_windows()
            except Exception:
                pass
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @flask_app.route("/api/community")
    def api_community():
        try:
            from admin_backend.community import fetch_all_tiles
            return jsonify(fetch_all_tiles())
        except Exception:
            return jsonify({})

    return flask_app


def run_api(host="127.0.0.1", port=8765):
    """Run Flask API in the current thread (blocking)."""
    app = _create_flask_app()
    app.run(host=host, port=port, debug=False, use_reloader=False)


def run_api_threaded(host="127.0.0.1", port=8765):
    """Start Flask API in a daemon thread, return the Thread."""
    app = _create_flask_app()
    t = threading.Thread(
        target=app.run,
        kwargs={"host": host, "port": port, "debug": False, "use_reloader": False},
        daemon=True,
    )
    t.start()
    return t
