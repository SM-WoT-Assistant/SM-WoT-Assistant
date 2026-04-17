# map_updater_4_01.py
import os
import json
import time
import requests
import html
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Імпорт нашого модуля конфігурації
import config as config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def sync_all(callback_status=None):
    """
    Виконує повний цикл оновлення мап.
    callback_status: функція для передачі тексту статусу в консоль або GUI.
    """
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
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--log-level=3")
        
        # Використовуємо перевірений метод (вікно за межами екрана)
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_window_position(-2000, 0)
        
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
                img_element = card.find_element(By.TAG_NAME, "img")
                img_url = img_element.get_attribute("src")
                if map_name and img_url:
                    clean_name = html.unescape(map_name.strip())
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
            
            # Якщо файл вже є і він нормального розміру — пропускаємо
            if os.path.exists(file_path) and os.path.getsize(file_path) > 1000: 
                continue 
                
            url = new_links.get(name)
            try:
                res = requests.get(url, headers=config.HEADERS, timeout=15, verify=False)
                if res.status_code == 200 and len(res.content) > 1000:
                    # Перевірка, чи це не помилка "Access Denied" у форматі XML
                    if b"AccessDenied" not in res.content[:150]:
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

# map_updater_4_01.py
