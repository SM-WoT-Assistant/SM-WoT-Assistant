import re

with open('stats_ai.py', 'r', encoding='utf-8') as f:
    src = f.read()

# Fix nation.lower()
src = src.replace('correct_ration = ration_map.get(nation)', 'correct_ration = ration_map.get(nation.lower())')

with open('stats_ai.py', 'w', encoding='utf-8') as f:
    f.write(src)
    
print("Patched stats_ai.py nation.lower()")

with open('ai_engine.py', 'r', encoding='utf-8') as f:
    src_ai = f.read()

target_fetch = """    def fetch_build_async(self, tag, tank_name, callback):
        # Always check cache first to return immediately if available
        with self._lock:
            if tag in self.cache:
                callback(self._normalize_build(self.cache[tag]), True) # True = from cache
                return

        def run_scraper():"""

repl_fetch = """    def fetch_build_async(self, tag, tank_name, callback):
        def run_scraper():"""

src_ai = src_ai.replace(target_fetch, repl_fetch)

target_scraper_end = """                if json_str:
                    data = json.loads(json_str)
                    with self._lock:
                        self.cache[tag] = data
                        self._save_cache()
                    # Return normalized build
                    callback(self._normalize_build(data), False)
                else:
                    callback(self._normalize_build({}), False)
            except Exception as e:
                print("Scraper err:", e)
                callback(self._normalize_build({}), False)

        threading.Thread(target=run_scraper, daemon=True).start()"""

repl_scraper_end = """                if json_str:
                    data = json.loads(json_str)
                    with self._lock:
                        self.cache[tag] = data
                        self._save_cache()
                    # Return normalized build
                    callback(self._normalize_build(data), False)
                else:
                    # Fallback to cache if scraper failed
                    with self._lock:
                        if tag in self.cache:
                            callback(self._normalize_build(self.cache[tag]), True)
                        else:
                            callback(self._normalize_build({}), False)
            except Exception as e:
                print("Scraper err:", e)
                with self._lock:
                    if tag in self.cache:
                        callback(self._normalize_build(self.cache[tag]), True)
                    else:
                        callback(self._normalize_build({}), False)

        threading.Thread(target=run_scraper, daemon=True).start()"""

src_ai = src_ai.replace(target_scraper_end, repl_scraper_end)

with open('ai_engine.py', 'w', encoding='utf-8') as f:
    f.write(src_ai)
print("Patched ai_engine.py logic")
