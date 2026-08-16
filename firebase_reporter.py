"""
firebase_reporter.py — відправка помилок, пінгів і службових подій.
Використовує Realtime Database REST API (працює з API key без OAuth).
"""
import os
import json
import uuid
import time
import sys
import traceback
import platform
import config
import requests


FIREBASE_PROJECT_ID = "sm-wot-assistant"
FIREBASE_API_KEY = "AIzaSyBbZTPygDttChnbxbRB1xfHOACiHN2YStE"

_RTDB_BASE = f"https://{FIREBASE_PROJECT_ID}-default-rtdb.europe-west1.firebasedatabase.app"

_install_id = None


def _get_install_id():
    global _install_id
    if _install_id:
        return _install_id
    try:
        id_path = os.path.join(config.USER_DATA_DIR, "identity.json")
        if os.path.exists(id_path):
            with open(id_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _install_id = data.get("user_id")
    except Exception:
        pass
    if not _install_id:
        _install_id = str(uuid.uuid4())
    return _install_id


def _is_configured():
    return bool(FIREBASE_PROJECT_ID and FIREBASE_API_KEY)


def _to_firestore_value(val):
    """Конвертує Python значення у Firestore REST typed value."""
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": val}
    if isinstance(val, float):
        return {"doubleValue": val}
    return {"stringValue": str(val)}


def _rtdb_url(path):
    if "?" in path:
        base_path, qs = path.split("?", 1)
        qs = qs.replace('"', '%22')
        return f"{_RTDB_BASE}/{base_path}.json?{qs}&auth={FIREBASE_API_KEY}"
    return f"{_RTDB_BASE}/{path}.json?auth={FIREBASE_API_KEY}"


def _put(path, data, timeout=8):
    if not _is_configured():
        return False
    try:
        if data is None:
            # PUT null — видалення вузла (json=None не шле тіло, RTDB повертає 400)
            r = requests.put(_rtdb_url(path), data=b"null",
                             headers={"Content-Type": "application/json"}, timeout=timeout)
        else:
            r = requests.put(_rtdb_url(path), json=data, headers=config.HEADERS, timeout=timeout)
        return 200 <= r.status_code < 300
    except Exception:
        return False


def _post(path, data, timeout=8):
    if not _is_configured():
        return False
    try:
        r = requests.post(_rtdb_url(path), json=data, headers=config.HEADERS, timeout=timeout)
        return 200 <= r.status_code < 300
    except Exception:
        return False


def report_fallback(source, context, error_text, level="warning"):
    """Повідомити про використання fallback замість реальних даних.
    
    Args:
        source: звідки викликано (напр. 'data_manager.load_tank_db')
        context: які дані не вдалося завантажити (напр. 'tank_db.json')
        error_text: опис помилки
        level: 'warning' (non-fatal) або 'critical' (data loss)
    """
    report_error(
        error_type="fallback",
        stage="runtime",
        error_text=f"[{level.upper()}] {source}: {error_text[:300]}",
        blocked=(level == "critical"),
        details={"source": source, "context": context, "fallback_level": level}
    )


def _report_version():
    """Версія для звітів: admin_version.txt якщо це frozen адмінка, інакше основна."""
    try:
        av = os.path.join(config.BUNDLE_DIR, "admin_version.txt")
        if os.path.exists(av) and (
            getattr(sys, "frozen", False)
            or not os.path.exists(os.path.join(config.BUNDLE_DIR, "VERSION"))
        ):
            with open(av, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return config.load_version()


def report_error(error_type, stage, error_text, blocked=False, details=None, message="", stack_trace=""):
    """Відправити помилку в RTDB error_reports/. Повертає True якщо успішно."""
    try:
        report = {
            "type": error_type,
            "version": _report_version(),
            "stage": stage,
            "blocked": blocked,
            "error": (error_text or message or "")[:500],
            "details": details or {},
            "uid": _get_install_id() or "anon",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "app": {
                "os": platform.system() + " " + platform.release(),
                "frozen": getattr(sys, 'frozen', False),
            }
        }
        if stack_trace:
            report["stack_trace"] = stack_trace[:5000]
        result = _post("error_reports", report)
        if not result:
            print(f"[REPORTER] Помилка відправки: {error_type}: {error_text[:80]}")
        return result
    except Exception:
        return False
    return result


def send_service_events(events_batch):
    if not _is_configured() or not events_batch:
        return []

    delivered_ids = []
    for evt in events_batch:
        payload = {
            "category": evt.get("category", ""),
            "message": evt.get("message", ""),
            "level": evt.get("level", "info"),
            "timestamp": evt.get("timestamp", ""),
            "version": config.load_version(),
            "install_id": _get_install_id(),
        }
        if _post("service_events", payload):
            delivered_ids.append(evt.get("id"))
        else:
            break
    return delivered_ids


def ping_version():
    """PUT в installations/{install_id} — оновлює last_seen."""
    install_id = _get_install_id()
    payload = {
        "install_id": install_id,
        "version": config.load_version(),
        "os": platform.system() + " " + platform.release(),
        "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "first_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return _put(f"installations/{install_id}", payload)


def _on_ping_done(result, user_id):
    if result:
        print(f"[REPORTER] Пінг успішно: {user_id}")
    else:
        print(f"[REPORTER] Пінг не вдався (Firebase не налаштовано)")


def ping_version_async(app):
    import threading
    def _ping():
        result = ping_version()
        if hasattr(app, 'root'):
            try:
                app.root.after(0, lambda: _on_ping_done(result, _get_install_id()))
            except RuntimeError:
                pass  # main loop ще не запущений (race з --tray)
    t = threading.Thread(target=_ping, daemon=True)
    t.start()


def setup_global_excepthook(app):
    original_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        try:
            tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            msg = str(exc_value)
            report_error(
                error_type=exc_type.__name__,
                stage="runtime",
                error_text=msg[:500],
                stack_trace=tb_str[:5000],
            )
        except Exception:
            pass
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def try_flush_service_messages(app=None):
    try:
        import service_messages
        pending = service_messages.get_pending()
        if pending:
            delivered = send_service_events(pending)
            if delivered:
                service_messages.mark_delivered(delivered)
                print(f"[REPORTER] Відправлено {len(delivered)} службових подій.")
    except Exception as e:
        print(f"[REPORTER] Помилка відправки подій: {e}")


def set_firebase_config(project_id, api_key):
    global FIREBASE_PROJECT_ID, FIREBASE_API_KEY, _RTDB_BASE
    FIREBASE_PROJECT_ID = project_id
    FIREBASE_API_KEY = api_key
    _RTDB_BASE = f"https://{project_id}-default-rtdb.europe-west1.firebasedatabase.app"


def check_for_updates(on_done=None):
    """Асинхронно перевіряє RTDB versions/ на новішу версію."""
    if not _is_configured():
        if on_done:
            on_done(None)
        return

    import threading

    def _check():
        try:
            url = _rtdb_url("versions")
            r = requests.get(url, headers=config.HEADERS, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data:
                    items = [v for v in data.values() if isinstance(v, dict) and v.get("version")]
                    if items:
                        latest = _pick_latest(items)
                        if on_done:
                            on_done(latest)
                        return
        except Exception as e:
            print(f"[UPDATE] check_for_updates error: {e}")
        if on_done:
            on_done(None)

    t = threading.Thread(target=_check, daemon=True)
    t.start()


def _pick_latest(items):
    if not items:
        return None
    return max(items, key=lambda x: (x.get("release_date", ""), tuple(int(n) for n in x.get("version", "0.0.0").replace("v", "").split("."))))


def check_for_updates_sync():
    """Синхронно перевіряє RTDB versions/ — повертає dict latest релізу або None."""
    if not _is_configured():
        return None
    try:
        url = _rtdb_url("versions")
        r = requests.get(url, headers=config.HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data:
                items = [v for v in data.values() if isinstance(v, dict) and v.get("version")]
                return _pick_latest(items)
    except Exception as e:
        print(f"[UPDATE] check_for_updates_sync error: {e}")
    return None


def compare_versions(current, latest):
    """Порівнює версії. Повертає True якщо latest > current."""
    try:
        def _parts(v):
            clean = v.split()[0]  # "1.0.38 Alpha" → "1.0.38"
            return tuple(int(x) for x in str(clean).replace("v", "").split(".")[:3])
        return _parts(latest) > _parts(current)
    except Exception:
        return False


