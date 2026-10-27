"""admin_backend.site_watch - монітор змін зображень мап на сайті wotmapsbyyaya.

Відстежує ЗМІНИ фонів тактичних мап на сайті БЕЗ жодного завантаження:
- url_changed - сайт залив новий timestamped-об'єкт (pilsen<ts>.webp): головний
  клас змін, який НЕ видно за ETag старого URL (клієнтський If-None-Match sweep
  отримує 304, бо старий об'єкт лишається незмінним);
- content_changed - той самий URL, інший ETag/size (HEAD);
- new_map / removed_map - карта з'явилася/зникла в списку сайту.

Перший запуск = базлайн (log, без балона). Зміни -> балон + Log в адмінці
(адміністрування доставляє _bg_poll у головному потоці, правило #1598).

Парсер карток свідомо дублює клієнтський map_updater._card_entry: клієнтські
модулі не входять до адмін-бандлу (build_admin тягне лише admin_ui/admin_backend)
- два незалежні deployment-таргети, як це вже зроблено для іконок (#1904).
"""
from __future__ import annotations

import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

import requests

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
MANIFEST_FILE = os.path.join(APPDATA_DIR, "site_maps_watch.json")
MAPS_PAGE_URL = "https://wotmapsbyyaya.com/maps"
INTERVAL = 7 * 86400          # раз на тиждень (рішення користувача 27.10.2026)
MIN_RETRY = 3600              # після помилки - повтор не раніше ніж за годину
PARTIAL_RATIO = 0.8           # менше 80% попередньої кількості => збій парсингу
PROFILE_DIR = os.path.join(os.environ.get("TEMP", "."), "sm_wot_site_watch_profile")

_FETCH_TIMEOUT = 8            # сек на один HEAD
_DRIVER_RETRY_MARKERS = (
    "session not created", "DevToolsActivePort", "cannot connect",
    "Chrome failed to start", "chrome not reachable",
)


def _name_from_href(href):
    """/map/El%20Halluf -> «El Halluf» (fallback, коли data-name/id немає)."""
    if not href or "/map/" not in href:
        return None
    seg = href.split("/map/")[-1].strip("/")
    return html.unescape(unquote(seg)) if seg else None


def _card_entry(card):
    """(назва, URL) з картки списку мап або None, якщо назви немає.

    Назва: data-name -> href -> id (legacy, картки 27.10 без id).
    URL: <img src> без Card-суфікса (прев'ю того самого об'єкта); шаблон від
    назви - лише fallback."""
    map_name = (card.get_attribute("data-name")
                or _name_from_href(card.get_attribute("href"))
                or card.get_attribute("id"))
    if not map_name:
        return None
    clean_name = html.unescape(map_name.strip())
    img_url = None
    try:
        imgs = card.find_elements("css selector", "img")
        src = imgs[0].get_attribute("src") if imgs else None
        if src:
            img_url = (src[:-len("Card.webp")] + ".webp"
                       if src.endswith("Card.webp") else src)
    except Exception:
        img_url = None
    if not img_url:
        safe = clean_name.lower().replace(' - ', '_').replace(' ', '_')
        img_url = f"https://images.wotmapsbyyaya.com/maps/{safe}.webp"
    return clean_name, img_url


def _create_driver():
    """Headless Chrome з ІЗОЛЬОВАНИМ профілем.

    Не спільний дефолтний user-data-dir: інакше тижневий тік впаде, коли на
    машині вже відкритий Chrome користувача (або працює Community-вкладка з
   іншим профілем). Окремий TEMP-профіль - жодних локів і чужих cookies."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--log-level=3")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])

    last_err = None
    for attempt in (1, 2, 3):
        try:
            return webdriver.Chrome(options=opts)
        except Exception as e:
            last_err = e
            if not any(m in str(e).lower() for m in _DRIVER_RETRY_MARKERS):
                raise
            time.sleep(3 if attempt < 3 else 15)
            _kill_chrome(PROFILE_DIR)
    raise RuntimeError(f"Chrome driver failed after 3 attempts: {str(last_err)[:120]}")


def _kill_chrome(pattern):
    """Kill chrome.exe з профілем pattern (після аварійного завершення)."""
    from admin_backend.browser import _kill_chrome_matching
    _kill_chrome_matching(pattern)


def fetch_site_urls(timeout_wait=20):
    """{name: url} зі сторінки /maps сайту. Піднімає headless Chrome.

    Якщо парсер не знайшов жодної картки - кидає RuntimeError: мовчазний зрив
    скрейперів (розмітка сайту без id, 27.10.2026) має бути чутним."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    driver = None
    try:
        driver = _create_driver()
        driver.get(MAPS_PAGE_URL)
        WebDriverWait(driver, timeout_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".btn-select-map")))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        out = {}
        for card in driver.find_elements(By.CSS_SELECTOR, ".btn-select-map"):
            try:
                entry = _card_entry(card)
            except Exception:
                entry = None
            if entry:
                out[entry[0]] = entry[1]
        if not out:
            raise RuntimeError("0 map cards parsed - site markup changed?")
        return out
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def _head_info(url):
    """HEAD -> {etag, size} або None (не 200 / мережа)."""
    try:
        r = requests.head(url, timeout=_FETCH_TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None
        return {
            "etag": (r.headers.get("ETag") or "").strip(),
            "size": str(r.headers.get("Content-Length") or "").strip(),
        }
    except Exception:
        return None


def _load_manifest(path=MANIFEST_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("maps"), dict):
            return data
    except Exception:
        pass
    return None


def _save_manifest(data, path=MANIFEST_FILE):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[SITE_WATCH] manifest save error: {e}")


def should_run(path=MANIFEST_FILE, now=None):
    """True: базлайну немає, минув тиждень від last_checked І >= 1 год від
    last_attempt (після збою - повтор не частіше ніж раз на годину)."""
    now = time.time() if now is None else now
    data = _load_manifest(path)
    if data is None:
        return True
    if now - float(data.get("last_checked", 0)) >= INTERVAL:
        if now - float(data.get("last_attempt", 0)) >= MIN_RETRY:
            return True
    return False


def _report(error_text, level="warning"):
    try:
        from admin_backend import report
        report.report_fallback("admin.site_watch", "check", error_text, level)
    except Exception:
        pass


def _diff(old_maps, live, heads):
    """Зміни між маніфестом і живим станом. heads: {name: {etag,size}|None}."""
    changes = []
    new_maps = {}
    for name, url in live.items():
        h = heads.get(name) or {}
        old = old_maps.get(name)
        if old is None:
            changes.append({"kind": "new_map", "name": name,
                            "detail": f"New map on site: {name}"})
        elif old.get("url") != url:
            changes.append({"kind": "url_changed", "name": name,
                            "detail": (f"URL changed: {name} -> "
                                       f"{os.path.basename(url)}")})
        elif h and h.get("etag") and old.get("etag") and h["etag"] != old["etag"]:
            changes.append({"kind": "content_changed", "name": name,
                            "detail": f"Image changed: {name}"})
        elif h and h.get("size") and old.get("size") and h["size"] != old["size"]:
            changes.append({"kind": "content_changed", "name": name,
                            "detail": (f"Image changed: {name} "
                                       f"(size {old['size']} -> {h['size']})")})
        new_maps[name] = {"url": url,
                          "etag": h.get("etag", ""),
                          "size": h.get("size", "")}
    for name in old_maps:
        if name not in live:
            changes.append({"kind": "removed_map", "name": name,
                            "detail": f"Removed from site: {name}"})
    return changes, new_maps


def check(path=MANIFEST_FILE, now=None):
    """Один повний цикл: fetch -> HEAD -> diff -> маніфест.

    Повертає {status: baseline|changed|unchanged|error, lines, text, maps}.
    text - для балона (порожній, коли сповіщати нічого); lines - для Log."""
    now = time.time() if now is None else now
    result = {"status": "error", "lines": [], "text": "", "maps": 0}
    data = _load_manifest(path)
    old_maps = data.get("maps", {}) if data else {}

    # last_attempt ПЕРЕД роботою: збій не має закручувати retry-цикл (should_run
    # утримує наступну спробу на MIN_RETRY).
    stamp = {"updated_at": data.get("updated_at", now) if data else now,
             "last_checked": data.get("last_checked", 0) if data else 0,
             "last_attempt": now,
             "maps": old_maps}
    _save_manifest(stamp, path)

    try:
        live = fetch_site_urls()
    except Exception as e:
        msg = f"fetch failed: {str(e)[:160]}"
        result["lines"].append(f"[SITE WATCH] ERROR {msg}")
        result["text"] = f"Site watch failed: {msg}"
        _report(msg)
        return result

    if len(live) < PARTIAL_RATIO * max(len(old_maps), 1):
        # Частковий рендер сторінки не має генерувати хибі removed_map.
        msg = (f"partial parse: {len(live)} of {len(old_maps)} maps - "
               f"site/markup problem?")
        result["lines"].append(f"[SITE WATCH] ERROR {msg}")
        result["text"] = f"Site watch failed: {msg}"
        _report(msg)
        return result

    names = list(live)
    with ThreadPoolExecutor(max_workers=8) as ex:
        heads = dict(zip(names, ex.map(lambda n: _head_info(live[n]), names)))

    if data is None:
        maps = {n: {"url": u, "etag": (heads.get(n) or {}).get("etag", ""),
                    "size": (heads.get(n) or {}).get("size", "")}
                for n, u in live.items()}
        _save_manifest({"updated_at": now, "last_checked": now,
                        "last_attempt": now, "maps": maps}, path)
        result.update(status="baseline", maps=len(maps),
                      lines=[f"[SITE WATCH] baseline: {len(maps)} maps tracked"])
        return result

    changes, new_maps = _diff(old_maps, live, heads)
    if changes:
        _save_manifest({"updated_at": now, "last_checked": now,
                        "last_attempt": now, "maps": new_maps}, path)
        lines = [f"[SITE WATCH] {c['detail']}" for c in changes]
        kinds = {}
        for c in changes:
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
        summary = ", ".join(f"{v} {k}" for k, v in sorted(kinds.items()))
        text = (f"{len(changes)} site map changes ({summary}): "
                + "; ".join(c["detail"] for c in changes[:4])
                + ("..." if len(changes) > 4 else ""))
        result.update(status="changed", maps=len(new_maps), lines=lines, text=text)
        return result

    _save_manifest({"updated_at": now, "last_checked": now,
                    "last_attempt": now, "maps": new_maps}, path)
    result.update(status="unchanged", maps=len(new_maps),
                  lines=[f"[SITE WATCH] no changes ({len(new_maps)} maps)"])
    return result
