# config_4_13.py
import os, sys

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()

LOGO_FILE = "logo.png" 
MAPS_DIR = os.path.join(BASE_DIR, "maps")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
DRAWINGS_FILE = os.path.join(BASE_DIR, "map_drawings.json")
MAP_LIST_FILE = os.path.join(BASE_DIR, "map_list.json") 
MAP_LINKS_FILE = os.path.join(BASE_DIR, "map_links.json")
TECH_IDS_FILE = os.path.join(BASE_DIR, "map_tech_ids.json")
CUSTOM_NAMES_FILE = os.path.join(BASE_DIR, "custom_names.json")
BG_COLOR = "#000000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

TECH_MAPS_STAGING = {
    "01_karelia": "Karelia", "02_malinovka": "Malinovka", "03_campania": "Province",
    "04_himmelsdorf": "Himmelsdorf", "05_prohorovka": "Prokhorovka", "06_ensk": "Ensk",
    "07_lakeville": "Lakeville", "08_ruinberg": "Ruinberg", "10_hills": "Mines",
    "11_murovanka": "Murovanka", "13_erlenberg": "Erlenberg", "14_siegfried_line": "Siegfried Line",
    "17_munchen": "Westfield", "18_cliff": "Cliff", "19_monastery": "Abbey",
    "22_slough": "Swamp", "23_westfeld": "Westfield", "28_desert": "Sand River",
    "29_el_halluf": "El Halluf", "29_el_hallouf": "El Halluf", "31_airfield": "Airfield", 
    "33_fjords": "Fjords", "33_fjord": "Fjords",
    "34_redshire": "Redshire", "35_steppes": "Steppes", "36_fishing_bay": "Fishermans Bay",
    "37_caucasus": "Cliff", "38_mannerheim_line": "Mannerheim Line", "44_north_america": "Highway",
    "45_north_america": "Port", "47_canada_a": "Serene Coast", "59_asia_great_wall": "Empire's Border",
    "60_asia_mundra": "Mountain Pass", "60_asia_miao": "Pearl River", "63_tundra": "Tundra", 
    "83_kharkiv": "Kharkov", "92_stalingrad": "Fiery Salient", "95_lost_city_ctf": "Ghost Town", 
    "99_poland": "Studzianki", "101_dday": "Overlord",
    "105_germany": "Berlin", "111_paris": "Paris", "112_eiffel_tower": "Paris", "112_stalingrad": "Stalingrad", 
    "114_czech": "Pilsen", "115_sweden": "Glacier", "127_j_city": "Pearl River", 
    "127_japort": "Safe Haven", "128_last_frontier": "Outpost", "137_tierra_del_fuego": "Outpost", 
    "121_lost_paradise": "Oyster Bay", "144_oyster_bay": "Oyster Bay", 
    "120_graf_zeppelin": "Graf Zeppelin",
    "Live Oaks": "Live Oaks", "Glacier": "Glacier"
}

LANG_DATA = {
    "ua": {
        "ui": {
            "show": "ПОКАЗАТИ", "bind": "ПРИВ'ЯЗАТИ", "tomato": "СТАТС",
            "draw": "МАЛЮВАТИ", "clear": "ОЧИСТИТИ ВСЕ", "marker": "Маркер",
            "arrow": "Стрілка", "class": "Клас:", "set_path": "Вказати файл python.log",
            "rename_map": "Перейменувати карту",
            "ai_stats": "СТАТ АІ", "stats": "СТАТ", "maps_1": "МАПИ I", "maps_2": "МАПИ II",
            "map_not_found": "КАРТА НЕ ЗНАЙДЕНА", "wot_assistant_editor": "WoT Assistant [РЕДАКТОР]",
            "editor_help": "Ctrl+ЛКМ: Рух | Alt+ЛКМ: Рух (бій) | Alt+↕: Розмір | Alt+↔: Прозорість | Alt+Shift+↕: Контраст",
            "hotkeys_help": "F10: Показати/Приховати  |  E: БОЕВИЙ/РЕДАКТОР",
            "assault": "Штурм", "encounter": "Зустріч", "region": "Регіон",
            "text_sign": "Текст / ЗНАК", "map_not_found_msg": "Мапу {} не знайдено",
            "battle_mode": "БОЙОВИЙ РЕЖИМ", "press_e_to_exit": "Натисни [ E ] для виходу"
        },
        "maps": {
            "Karelia": "Карелія", "Malinovka": "Малинівка", "Province": "Провінція", 
            "Himmelsdorf": "Хіммельсдорф", "Prokhorovka": "Прохорівка", "Ensk": "Енськ", 
            "Lakeville": "Ласвілль", "Ruinberg": "Руїнберг", "Mines": "Копальні", 
            "Murovanka": "Мурованка", "Erlenberg": "Ерленберг", "Siegfried Line": "Лінія Зігфрида", 
            "Cliff": "Круча", "Abbey": "Монастир", "Swamp": "Топ'я", "Westfield": "Вестфілд", 
            "Sand River": "Піщана річка", "El Halluf": "Ель-Халлуф", "Airfield": "Аеродром", 
            "Fjords": "Фйорди", "Redshire": "Редшир", "Steppes": "Степи", 
            "Fishermans Bay": "Рибацька бухта", "Mannerheim Line": "Лінія Маннергейма", 
            "Highway": "Хайвей", "Port": "Порт", "Serene Coast": "Тихий берег", 
            "Empire's Border": "Кордон імперії", "Empires Border": "Кордон імперії", 
            "Mountain Pass": "Перевал", "Tundra": "Тундра", 
            "Kharkiv": "Харків", "Kharkov": "Харків", "Fiery Salient": "Вогняна дуга", 
            "Ghost Town": "Загублене місто", 
            "Overlord": "Оверлорд", "Stalingrad": "Сталінград", "Pilsen": "Промзона", 
            "Studzianki": "Студзянки", "Pearl River": "Перлинна річка", "Live Oaks": "Лайв Окс", 
            "Berlin": "Берлін", "Paris": "Париж", "Safe Haven": "Стара гавань", 
            "Berlin": "Берлін", "Paris": "Париж", "Safe Haven": "Стара гавань", 
            "Outpost": "Застава", "Oyster Bay": "Устрична затока", "Glacier": "Льодовик",
            "Minsk": "Мінськ", "Nordskar": "Нордскар", "Widepark": "Вайдпарк",
            "Graf Zeppelin": "Граф Цепелін"
        }
    },
    "en": {
        "ui": {
            "show": "SHOW", "bind": "BIND", "tomato": "STATS",
            "draw": "DRAW", "clear": "CLEAR ALL", "marker": "Marker",
            "arrow": "Arrow", "class": "Class:", "set_path": "Set python.log file",
            "rename_map": "Rename map",
            "ai_stats": "AI STATS", "stats": "STATS", "maps_1": "MAPS I", "maps_2": "MAPS II",
            "map_not_found": "MAP NOT FOUND", "wot_assistant_editor": "WoT Assistant [EDITOR]",
            "editor_help": "Ctrl+LMB: Move | Alt+LMB: Move (battle) | Alt+↑↓: Size | Alt+←→: Opacity | Alt+Shift+↑↓: Contrast",
            "hotkeys_help": "F10: Show/Hide  |  E: BATTLE/EDITOR",
            "assault": "Assault", "encounter": "Encounter", "region": "Region",
            "text_sign": "Text / SIGN", "map_not_found_msg": "Map {} not found",
            "battle_mode": "BATTLE MODE", "press_e_to_exit": "Press [ E ] to exit"
        },
        "maps": {
            "Karelia": "Karelia", "Malinovka": "Malinovka", "Province": "Province", 
            "Himmelsdorf": "Himmelsdorf", "Prokhorovka": "Prokhorovka", "Ensk": "Ensk", 
            "Lakeville": "Lakeville", "Ruinberg": "Ruinberg", "Mines": "Mines", 
            "Murovanka": "Murovanka", "Erlenberg": "Erlenberg", "Siegfried Line": "Siegfried Line", 
            "Cliff": "Cliff", "Abbey": "Abbey", "Swamp": "Swamp", "Westfield": "Westfield", 
            "Sand River": "Sand River", "El Halluf": "El Halluf", "Airfield": "Airfield", 
            "Fjords": "Fjords", "Redshire": "Redshire", "Steppes": "Steppes", 
            "Fishermans Bay": "Fisherman's Bay", "Mannerheim Line": "Mannerheim Line", 
            "Highway": "Highway", "Port": "Port", "Serene Coast": "Serene Coast", 
            "Empire's Border": "Empire's Border", "Empires Border": "Empire's Border", 
            "Mountain Pass": "Mountain Pass", "Tundra": "Tundra", 
            "Kharkiv": "Kharkiv", "Kharkov": "Kharkov", "Fiery Salient": "Fiery Salient", 
            "Ghost Town": "Ghost Town", 
            "Overlord": "Overlord", "Stalingrad": "Stalingrad", "Pilsen": "Pilsen", 
            "Studzianki": "Studzianki", "Pearl River": "Pearl River", "Live Oaks": "Live Oaks", 
            "Berlin": "Berlin", "Paris": "Paris", "Safe Haven": "Safe Haven", 
            "Berlin": "Berlin", "Paris": "Paris", "Safe Haven": "Safe Haven", 
            "Outpost": "Outpost", "Oyster Bay": "Oyster Bay", "Glacier": "Glacier",
            "Minsk": "Minsk", "Nordskar": "Nordskar", "Widepark": "Widepark",
            "Graf Zeppelin": "Graf Zeppelin"
        }
    },
    "ru": {
        "ui": {
            "show": "ПОКАЗАТЬ", "bind": "ПРИВЯЗАТЬ", "tomato": "СТАТЫ",
            "draw": "РИСОВАТЬ", "clear": "ОЧИСТИТЬ ВСЕ", "marker": "Маркер",
            "arrow": "Стрелка", "class": "Класс:", "set_path": "Указать файл python.log",
            "rename_map": "Переименовать карту",
            "ai_stats": "СТАТ АИ", "stats": "СТАТЫ", "maps_1": "КАРТЫ I", "maps_2": "КАРТЫ II",
            "map_not_found": "КАРТА НЕ НАЙДЕНА", "wot_assistant_editor": "WoT Assistant [РЕДАКТОР]",
            "editor_help": "Ctrl+ЛКМ: Двигать | Alt+ЛКМ: Двигать (бой) | Alt+↑↓: Размер | Alt+←→: Прозрачность | Alt+Shift+↑↓: Контраст",
            "hotkeys_help": "F10: Показать/Скрыть  |  E: БОЙ/РЕДАКТОР",
            "assault": "Штурм", "encounter": "Встреча", "region": "Регион",
            "text_sign": "Текст / ЗНАК", "map_not_found_msg": "Карта {} не найдена",
            "battle_mode": "БОЕВОЙ РЕЖИМ", "press_e_to_exit": "Нажми [ E ] для выхода"
        },
        "maps": {
            "Karelia": "Карелия", "Malinovka": "Малиновка", "Province": "Провинция", 
            "Himmelsdorf": "Химмельсдорф", "Prokhorovka": "Прохоровка", "Ensk": "Энск", 
            "Lakeville": "Лейквилл", "Ruinberg": "Руйенберг", "Mines": "Шахты", 
            "Murovanka": "Мурованка", "Erlenberg": "Эрленберг", "Siegfried Line": "Линия Зигфрида", 
            "Cliff": "Утёс", "Abbey": "Аббатство", "Swamp": "Болото", "Westfield": "Вестфилд", 
            "Sand River": "Песчаная река", "El Halluf": "Эль-Халлуф", "Airfield": "Аэродром", 
            "Fjords": "Фьорды", "Redshire": "Редшир", "Steppes": "Степи", 
            "Fishermans Bay": "Рыбацкая бухта", "Mannerheim Line": "Линия Маннергейма", 
            "Highway": "Шоссе", "Port": "Порт", "Serene Coast": "Тихий берег", 
            "Empire's Border": "Граница империи", "Empires Border": "Граница империи", 
            "Mountain Pass": "Горный перевал", "Tundra": "Тундра", 
            "Kharkiv": "Харьков", "Kharkov": "Харьков", "Fiery Salient": "Огненная дуга", 
            "Ghost Town": "Город-призрак", 
            "Overlord": "Оверлорд", "Stalingrad": "Сталинград", "Pilsen": "Промзона", 
            "Studzianki": "Студзянки", "Pearl River": "Жемчужная река", "Live Oaks": "Лайв Окс", 
            "Berlin": "Берлин", "Paris": "Париж", "Safe Haven": "Старая гавань", 
            "Berlin": "Берлин", "Paris": "Париж", "Safe Haven": "Старая гавань", 
            "Outpost": "Застава", "Oyster Bay": "Устричная бухта", "Glacier": "Ледник",
            "Minsk": "Минск", "Nordskar": "Нордскар", "Widepark": "Вайдпарк",
            "Graf Zeppelin": "Граф Цеппелин"
        }
    }
}
# config_4_13.py