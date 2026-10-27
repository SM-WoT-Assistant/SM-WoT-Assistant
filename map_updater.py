# map_updater_4_01.py
import os
import json
import time
import io
import requests
import html
import urllib3
from PIL import Image

# Імпорт нашого модуля конфігурації
import config as config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def sync_all(callback_status=None):
    """
    Виконує повний цикл оновлення мап.
    callback_status: функція для передачі тексту статусу в консоль або GUI.

    Selenium імпортується ЛИВЕ всередину (лені): модуль має бути доступний
    через `import map_updater` без Chrome — download_single_map() та клієнтський
    трекінг мап (map_manager) працюють на requests без selenium.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    def log(text):
        print(text)
        if callback_status:
            callback_status(text)

    log("ІНІЦІАЛІЗАЦІЯ БРАУЗЕРА...")
    driver = None
    try:
        # Завантажуємо існуючі посилання для перевірки змін
        old_links = {}
        if os.path.exists(config.MAP_LINKS_FILE):
            with open(config.MAP_LINKS_FILE, "r", encoding="utf-8") as f:
                old_links = json.load(f)
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        driver = webdriver.Chrome(options=chrome_options)
        
        log("ОЧІКУВАННЯ ЗАВАНТАЖЕННЯ САЙТУ...")
        driver.get("https://wotmapsbyyaya.com/maps")
        
        # Чекаємо появи карток мап
        try: 
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn-select-map")))
        except Exception as e: 
            log(f"Помилка очікування: {e}")
        
        # Прокрутка для завантаження всіх елементів
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2) 
        
        cards = driver.find_elements(By.CSS_SELECTOR, ".btn-select-map")
        
        new_links = {}
        for card in cards:
            try:
                map_name = card.get_attribute("id")
                if map_name:
                    clean_name = html.unescape(map_name.strip())
                    safe_url_name = clean_name.lower().replace(' - ', '_').replace(' ', '_')
                    img_url = f"https://images.wotmapsbyyaya.com/maps/{safe_url_name}.webp"
                    new_links[clean_name] = img_url
            except: 
                continue
                
        driver.quit() 
        
        if not new_links:
            log("ПОМИЛКА: МАПИ НЕ ЗНАЙДЕНО")
            return False

        log(f"Знайдено мап на сайті: {len(new_links)}")
        
        # Якщо URL змінився — видаляємо старий файл, щоб перекачати його
        for name, new_url in new_links.items():
            if name in old_links and old_links[name] != new_url:
                safe_folder = name.replace('?', '').replace(':', '').replace('|', '').replace(' - ', '_').replace(' ', '_')
                file_path = os.path.join(config.MAPS_DIR, safe_folder, "map.webp")
                if os.path.exists(file_path):
                    os.remove(file_path) 
        
        # Зберігаємо дані в JSON
        with open(config.MAP_LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_links, f, indent=4)
            
        map_list = sorted(list(new_links.keys()))
        with open(config.MAP_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(map_list, f, indent=4)

        # Завантаження файлів зображень
        log("ПЕРЕВІРКА ТА ЗАВАНТАЖЕННЯ ЗОБРАЖЕНЬ...")
        downloaded = 0
        errors = 0
        
        for i, name in enumerate(map_list):
            safe_folder = name.replace('?', '').replace(':', '').replace('|', '').replace(' - ', '_').replace(' ', '_')
            target_dir = os.path.join(config.MAPS_DIR, safe_folder)
            os.makedirs(target_dir, exist_ok=True)
            file_path = os.path.join(target_dir, "map.webp")
            
            # Пропускаємо існуючі (щоб не навантажувати сайт)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                continue
            url = new_links.get(name)
            try:
                res = requests.get(url, headers=config.HEADERS, timeout=15, verify=False)
                if res.status_code == 200 and len(res.content) > 1000:
                    # Перевірка, чи це не помилка "AccessDenied" у форматі XML
                    if b"AccessDenied" not in res.content[:150]:
                        ok, score = verify_image_for_name(name, res.content)
                        if not ok:
                            errors += 1
                            _guard_report(
                                "sync_all",
                                f"{name}: сайт віддав картинку, що не збігається "
                                f"з мінікартою клієнта (corr={score:.2f}) — відмова")
                            # Старий файл могло бути видалено вище (зміна URL),
                            # а байти ми відхилили — відновлюємо фон з клієнта
                            # одразу, а не чекаючи наступного старту.
                            for _mid in _folder_owners(
                                    _safe_folder(_resolve_tactic_folder(name))):
                                if ensure_map_background(_mid) != "skipped":
                                    break
                            time.sleep(0.1)
                            continue
                        with open(file_path, "wb") as f:
                            f.write(res.content)
                        downloaded += 1
                        log(f"  [{i+1}/{len(map_list)}] Завантажено: {name}")
                else:
                    errors += 1
            except: 
                errors += 1
            time.sleep(0.1)

        log(f"ОБРОБКА ЗАВЕРШЕНА. Нових: {downloaded}, помилок: {errors}")
        return True
                
    except Exception as e:
        if driver:
            try: driver.quit()
            except: pass
        log(f"КРИТИЧНА ПОМИЛКА МОДУЛЯ: {e}")
        return False

if __name__ == "__main__":
    # Код для автономного запуску модуля
    print("--- АВТОНОМНИЙ ТЕСТ МОДУЛЯ ОБНОВЛЕННЯ ---")
    sync_all()
    input("\nНатисніть Enter для виходу...")


def download_single_map(eng_name: str, url: str) -> bool:
    """Завантажує одну мапу з сайту (без Chrome)."""
    safe_folder = eng_name.replace('?', '').replace(':', '').replace('|', '').replace(' - ', '_').replace(' ', '_')
    target_dir = os.path.join(config.MAPS_DIR, safe_folder)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, "map.webp")

    try:
        res = requests.get(url, headers=config.HEADERS, timeout=15, verify=False)
        if res.status_code == 200 and len(res.content) > 1000:
            if b"AccessDenied" not in res.content[:150]:
                # Verifікація вмісту проти мінікарти клієнта: байти НЕ
                # пишемо, якщо це не та мапа (див. image_guard в кінці файлу).
                ok, score = verify_image_for_name(eng_name, res.content)
                if not ok:
                    _guard_report(
                        "download_single_map",
                        f"{eng_name}: сайт віддав картинку, що не збігається "
                        f"з мінікартою клієнта (corr={score:.2f}) — відмова")
                    return False
                with open(file_path, "wb") as f:
                    f.write(res.content)

                # Оновлюємо map_list.json
                map_list_path = config.MAP_LIST_FILE
                map_list = []
                if os.path.exists(map_list_path):
                    try:
                        with open(map_list_path, "r", encoding="utf-8") as f:
                            map_list = json.load(f)
                    except Exception:
                        pass
                if eng_name not in map_list:
                    map_list.append(eng_name)
                    map_list.sort()
                    with open(map_list_path, "w", encoding="utf-8") as f:
                        json.dump(map_list, f, indent=4)

                # Оновлюємо map_links.json
                links_path = config.MAP_LINKS_FILE
                links = {}
                if os.path.exists(links_path):
                    try:
                        with open(links_path, "r", encoding="utf-8") as f:
                            links = json.load(f)
                    except Exception:
                        pass
                links[eng_name] = url
                with open(links_path, "w", encoding="utf-8") as f:
                    json.dump(links, f, indent=4)

                return True
    except Exception as e:
        print(f"[MAP_DOWNLOAD] Помилка завантаження {eng_name}: {e}")
    return False


# ══════════════════════════════════════════════════════════════════════
# IMAGE GUARD — верифікація тактичних фонів проти мінікарти клієнта
# ══════════════════════════════════════════════════════════════════════
# Чому: фони TACTIC-режиму беруться зі стороннього сайту
# (wotmapsbyyaya.com) за назвою мапи і приймались будь-які байти —
# достатньо HTTP 200 + >1000 байт. Звірки з грою не було, тому:
#   * pilsen.webp містив терен Редширу (corr 0.186 проти 0.879 у
#     валідних) — у TACTIC замість Промзони малювався Редшир;
#   * мап, яких немає на сайті (44 з 91 арени), лишалось без фону і
#     з 23.10.2026 вони переносились у кінець списку (Нібельбурґ).
# Правило: клієнт гри — джерело істини, сайт дає ТІЛЬКИ накреслення
# поверх мінікарти. Тому фон звіряється з extracted_maps/<id>.png;
# невалідний відхиляється при завантаженні (байти не пишуться),
# відсутній/битий відновлюється з мінікарти клієнта.
#
# Виміряні значення Pearson (96×96 сірих, 43 фони): валідні
# 0.730..0.968 (медіана 0.908), чужі 0.186 і 0.397 → поріг 0.5.
_GUARD_THRESHOLD = 0.5
_GUARD_SIZE = 96
_GUARD_OUT = 1024
_GUARD_REPORTED = set()
_ref_cache = {}


def _guard_report(stage, detail, level="warning"):
    """Одне повідомлення на унікальний випадок: консоль + error_reports."""
    if detail in _GUARD_REPORTED:
        return
    _GUARD_REPORTED.add(detail)
    print(f"[MAP_GUARD] {level.upper()}: {detail}")
    try:
        import firebase_reporter
        firebase_reporter.report_fallback(
            "map_updater.image_guard", stage, detail, level)
    except Exception:
        pass


def _signature(image, size=_GUARD_SIZE):
    """Відцентрована сигнатура: 96×96 сірих мінус середнє."""
    px = list(image.convert("L").resize((size, size)).tobytes())
    mean = sum(px) / len(px)
    return [p - mean for p in px]


def _corr(a, b):
    num = sum(x * y for x, y in zip(a, b))
    da = sum(x * x for x in a) ** 0.5
    db = sum(x * x for x in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def _safe_folder(name):
    """Той самий трансформ, що й у download_single_map/sync_all."""
    return (name.replace('?', '').replace(':', '').replace('|', '')
                .replace("'", '').replace(' - ', '_').replace(' ', '_'))


def _resolve_tactic_folder(eng_key):
    """Дзеркало MapManager._resolve_tactic_folder (map_manager.py:1036).

    Потрібне без імпорту map_manager: той лени-імпортує цей модуль
    (selenium), тож прямий імпорт був би циклічним. Обидві функції
    читають лише config.TECH_MAPS_STAGING — міняти разом.
    """
    f = config.TECH_MAPS_STAGING.get(eng_key)
    if f:
        return f
    for suf in ('_v', '_big', '_sm24', '_sm25', '_nom', '_scc', '_ctf'):
        if eng_key.endswith(suf):
            f = config.TECH_MAPS_STAGING.get(eng_key[:-len(suf)])
            if f:
                return f
    return eng_key


def _folder_owners(folder):
    """Арени, чий TACTIC-фон лежить у цій папці (буває спільна: Nordskar)."""
    return [mid for mid, eng in config.MAP_NAMES_EN.items()
            if _safe_folder(_resolve_tactic_folder(eng)) == folder]


def _client_ref(map_id):
    """Сигнатура мінікарти клієнта extracted_maps/<id>.png (кеш у пам'яті)."""
    if map_id in _ref_cache:
        return _ref_cache[map_id]
    ref = None
    path = os.path.join(config.BASE_DIR, "extracted_maps", f"{map_id}.png")
    if os.path.exists(path):
        try:
            with Image.open(path) as im:
                ref = _signature(im)
        except Exception:
            ref = None
    _ref_cache[map_id] = ref
    return ref


def _background_path(folder, eng_name):
    """Як і MapRenderer.load_and_resize_map: map.webp, потім <eng>.jpg/.png."""
    base = os.path.join(config.MAPS_DIR, folder)
    for name in ("map.webp", f"{eng_name}.jpg", f"{eng_name}.png"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def _score(path, ref):
    """corr фону з еталоном; -1 якщо файл битий/нечитабельний."""
    if not path:
        return -1.0
    try:
        with Image.open(path) as im:
            return _corr(_signature(im), ref)
    except Exception:
        return -1.0


def verify_image_for_name(eng_name, data):
    """(ok, score) для ЗАВАНТАЖЕНИХ байтів: чи це справді мапа eng_name.

    ok=True зі score=-1, якщо еталона в клієнті немає (перевірити не можемо).
    """
    try:
        with Image.open(io.BytesIO(data)) as im:
            sig = _signature(im)
    except Exception:
        return False, -1.0
    best = -1.0
    for mid in _folder_owners(_safe_folder(_resolve_tactic_folder(eng_name))):
        ref = _client_ref(mid)
        if ref is not None:
            best = max(best, _corr(sig, ref))
    if best < 0:
        return True, -1.0
    return best >= _GUARD_THRESHOLD, best


def verify_map_background(map_id):
    """(ok, score) для вже наявного локального фону арени."""
    ref = _client_ref(map_id)
    if ref is None:
        return True, -1.0
    eng = config.MAP_NAMES_EN.get(map_id, map_id)
    path = _background_path(_safe_folder(_resolve_tactic_folder(eng)), eng)
    if path is None:
        return False, -1.0
    score = _score(path, ref)
    return score >= _GUARD_THRESHOLD, score


def ensure_map_background(map_id):
    """Створює або ремонтує maps/<folder>/map.webp з мінікарти клієнта.

    Повертає 'created' | 'repaired' | 'ok' | 'skipped'.
    """
    ref = _client_ref(map_id)
    if ref is None:
        return "skipped"
    eng = config.MAP_NAMES_EN.get(map_id, map_id)
    folder = _safe_folder(_resolve_tactic_folder(eng))
    base = os.path.join(config.MAPS_DIR, folder)
    target = os.path.join(base, "map.webp")
    existing = _background_path(folder, eng)
    if existing is not None:
        score = _score(existing, ref)
        if score >= _GUARD_THRESHOLD:
            return "ok"
        action = "repaired"
    else:
        score, action = -1.0, "created"
    try:
        src = os.path.join(config.BASE_DIR, "extracted_maps", f"{map_id}.png")
        with Image.open(src) as im:
            out = im.convert("RGB").resize(
                (_GUARD_OUT, _GUARD_OUT), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            out.save(buf, format="WEBP", quality=90)
        os.makedirs(base, exist_ok=True)
        with open(target, "wb") as f:
            f.write(buf.getvalue())
    except Exception as e:
        _guard_report("ensure_map_background", f"{map_id}: фон не відновлено — {e}")
        return "skipped"
    if action == "repaired":
        _guard_report(
            "ensure_map_background",
            f"{map_id}: невалідний фон (corr={score:.2f}) замінено мінікартою клієнта")
    return action


def ensure_local_backgrounds(map_ids):
    """Валідація всіх наявних фонів + відсутніх з мінікарти клієнта.

    Працює офлайн (мережа не потрібна) — викликається перед
    мережевим sweep у MapManager._detect_pending_tactic_maps.
    """
    rep = {"checked": 0, "ok": 0, "created": 0, "repaired": 0, "skipped": 0}
    for mid in map_ids:
        rep["checked"] += 1
        try:
            st = ensure_map_background(mid)
        except Exception as e:
            _guard_report("ensure_local_backgrounds", f"{mid}: {e}")
            st = "skipped"
        rep[st] = rep.get(st, 0) + 1
    return rep


# map_updater_4_01.py
