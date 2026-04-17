import google.genai as genai
import json
import os

# === ВСТАВТЕ ВАШ КЛЮЧ НИЖЧЕ, ЩОБ КОРИСТУВАЧІ НІЧОГО НЕ ВВОДИЛИ ===
DEFAULT_KEY = "AIzaSyDLm-MXve9ECuE_3uoMurzpV1KQmY6Ql4g" 
# =============================================================

CACHE_FILE = "ai_cache.json"

class AIAssistant:
    def __init__(self, api_key=None):
        self.api_key = api_key or DEFAULT_KEY
        self.client = None
        self.cache = self.load_cache()
        if self.api_key:
            self.configure(self.api_key)

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
        except:
            pass

    def configure(self, api_key):
        real_key = api_key or DEFAULT_KEY
        if not real_key:
            self.client = None
            return
        self.api_key = real_key
        genai.configure(api_key=self.api_key)
        self.client = genai.Client()

    def get_tank_build(self, tank_name):
        # 1. Перевіряємо кеш (пам'ять)
        if tank_name in self.cache:
            return self.cache[tank_name]

        # 2. Якщо в кеші немає — робимо запит до ШІ
        if not self.client:
            return {"error": "API Key not configured. Please add your Gemini API Key in settings."}

        prompt = f"""
        Ти - професійний аналітик гри World of Tanks. 
        Знайди та усередни актуальні топові збірки для танку "{tank_name}" з ресурсів Tomato.gg, Tanks.gg та Skill4ltu Index.
        Видай результат СУВОРО у форматі JSON (чистий об'єкт без Markdown-розмітки):
        {{
            "tank": "{tank_name}",
            "equipment": ["Обладнання 1", "Обладнання 2", "Обладнання 3"],
            "field_mod": ["Рівень 2: Назва", "Рівень 4: Назва", "..."],
            "crew_skills": ["Командир: Назва", "Навідник: Назва", "..."],
            "ammo": "Основний/Голда/Фугас (процентне співвідношення)",
            "summary": "Короткий висновок про стиль гри на цій збірці."
        }}
        Відповідь має бути українською мовою.
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=prompt
            )
            
            text = response.text.replace('```json', '').replace('```', '').strip()
            if '{' in text:
                text = text[text.find('{'):text.rfind('}')+1]
                
            data = json.loads(text)
            
            # 3. Зберігаємо в кеш при успіху
            self.cache[tank_name] = data
            self.save_cache()
            
            return data
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                return {"error": "ШІ ПЕРЕВАНТАЖЕНИЙ: Вичерпано безкоштовний ліміт запитів (15/хв або денний ліміт).\n\nЗараз діє безкоштовний ключ. Будь ласка, зачекайте 1 хвилину."}
            return {"error": f"Помилка ШІ: {err_msg}"}

# Популярні танки
POPULAR_TANKS = [
    "Object 277", "IS-7", "Leopard 1", "E 100", "Object 140", "T110E5", "M-V-Y", 
    "Vz. 55", "Kranvagn", "60TP Lewandowskiego", "Super Conqueror", "AMX 50 B",
    "B-C 25 t", "TVP T 50/51", "CS-63", "STB-1", "Strv 103B", "T110E3", "Object 268 4",
    "Grille 15", "EBR 105", "T-100 LT", "Manticore", "Sheridan"
]
