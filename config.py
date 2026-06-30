import os, sys

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = BUNDLE_DIR

def _appdata_dir():
    base = os.environ.get('APPDATA', BUNDLE_DIR)
    return os.path.join(base, 'SM WoT Assistant')

USER_DATA_DIR = _appdata_dir()

def load_version():
    try:
        with open(os.path.join(BUNDLE_DIR, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

LOGO_FILE = os.path.join(BUNDLE_DIR, "logo.png")
MAPS_DIR = os.path.join(BUNDLE_DIR, "maps")

SETTINGS_FILE = os.path.join(USER_DATA_DIR, "settings.json")
DRAWINGS_FILE = os.path.join(USER_DATA_DIR, "map_drawings.json")
MAP_LIST_FILE = os.path.join(BUNDLE_DIR, "map_list.json")
MAP_LINKS_FILE = os.path.join(BUNDLE_DIR, "map_links.json")
TECH_IDS_FILE = os.path.join(BUNDLE_DIR, "map_tech_ids.json")
CUSTOM_NAMES_FILE = os.path.join(USER_DATA_DIR, "custom_names.json")
LOCALES_FILE = os.path.join(USER_DATA_DIR, "locales.json")

DEFAULT_FILES = ["settings.json", "locales.json", "map_drawings.json", "service_messages.json", "popular_tanks_cache.json", "ai_builds_cache.json"]
GROUP_CACHE_FILE = os.path.join(USER_DATA_DIR, "group_schemes_cache.json")

BG_COLOR = "#000000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

TECH_MAPS_STAGING = {
    "01_karelia": "Karelia", "02_malinovka": "Malinovka", "03_campania": "Province",
    "04_himmelsdorf": "Himmelsdorf", "05_prohorovka": "Prokhorovka", "06_ensk": "Ensk",
    "07_lakeville": "Lakeville", "08_ruinberg": "Ruinberg", "10_hills": "Mines",
    "11_murovanka": "Murovanka", "13_erlenberg": "Erlenberg", "14_siegfried_line": "Siegfried Line",
    "17_munchen": "Widepark", "18_cliff": "Cliff", "19_monastery": "Abbey",
    "22_slough": "Swamp", "23_westfeld": "Westfield", "28_desert": "Sand River",
    "29_el_halluf": "El Halluf", "29_el_hallouf": "El Halluf", "31_airfield": "Airfield", 
    "33_fjords": "Fjords", "33_fjord": "Fjords",
    "34_redshire": "Redshire", "35_steppes": "Steppes", "36_fishing_bay": "Fishermans Bay",
    "37_caucasus": "Cliff", "38_mannerheim_line": "Mannerheim Line", "44_north_america": "Live Oaks",
    "45_north_america": "Highway", "47_canada_a": "Serene Coast", "59_asia_great_wall": "Empire's Border",
    "60_asia_mundra": "Mountain Pass", "60_asia_miao": "Pearl River", "63_tundra": "Tundra", 
    "83_kharkiv": "Kharkov", "92_stalingrad": "Fiery Salient", "95_lost_city_ctf": "Ghost Town", 
    "99_poland": "Studzianki", "101_dday": "Overlord",
    "105_germany": "Berlin", "111_paris": "Paris", "112_eiffel_tower": "Paris", "112_stalingrad": "Stalingrad", 
    "114_czech": "Pilsen", "115_sweden": "Glacier", "127_j_city": "Pearl River", 
    "127_japort": "Safe Haven", "128_last_frontier": "Outpost", "137_tierra_del_fuego": "Outpost", 
    "121_lost_paradise": "Oyster Bay", "144_oyster_bay": "Oyster Bay", 
     "120_graf_zeppelin": "Nordskar", "120_graf_zeppelin_scc": "Nordskar",
    "Live Oaks": "Live Oaks", "Glacier": "Glacier"
}

MAP_NAMES_EN = {
    "01_karelia": "Karelia", "02_malinovka": "Malinovka", "03_campania_big": "Province",
    "04_himmelsdorf": "Himmelsdorf", "05_prohorovka": "Prokhorovka", "06_ensk": "Ensk",
    "06_ensk_big": "Ensk Region", "07_lakeville": "Lakeville", "08_ruinberg": "Ruinberg",
    "08_ruinberg_sm24": "Lauerberg", "101_dday": "Overlord", "101_dday_sm24": "Omaha Beach",
    "105_germany": "Berlin", "105_germany_sm24": "Fallenstadt", "108_normandy_nom": "Oder",
    "10_hills": "Mines", "112_eiffel_tower_ctf": "Paris", "114_czech": "Pilsen",
    "115_sweden": "Glacier", "11_murovanka": "Murovanka", "120_graf_zeppelin": "Nordskar",
    "120_graf_zeppelin_scc": "Nordskar", "121_lost_paradise_v": "Oyster Bay",
    "127_japort": "Safe Haven", "128_last_frontier_v": "Outpost", "13_erlenberg": "Erlenberg",
    "140_fall_tanks": "Old School", "141_dash_to_go": "New School", "142_road_to_dash": "Battle School",
    "14_siegfried_line": "Siegfried Line", "14_siegfried_line_nom": "West Wall",
    "17_munchen": "Widepark", "18_cliff": "Cliff", "19_monastery": "Abbey",
    "208_bf_epic_normandy": "Normandy", "209_wg_epic_suburbia": "Kraftwerk",
    "210_bf_epic_desert": "Fata Morgana", "212_epic_random_valley_sm25": "Nibelburg",
    "217_er_alaska": "Klondike", "23_westfeld": "Westfield", "250_br_battle_city2-1": "Zone 404",
    "251_br_battle_city3": "Arzaghir 4.04", "252_br_battle_city4": "Firnulfir",
    "28_desert": "Sand River", "29_el_hallouf": "El Halluf", "31_airfield": "Airfield",
    "33_fjord": "Fjords", "34_redshire": "Redshire", "35_steppes": "Steppes",
    "36_fishing_bay": "Fishermans Bay", "37_caucasus": "Pass",
    "38_mannerheim_line": "Mannerheim Line", "44_north_america": "Live Oaks",
    "45_north_america": "Highway", "47_canada_a": "Serene Coast",
    "59_asia_great_wall": "Empire's Border", "60_asia_miao": "Pearl River",
    "63_tundra": "Tundra", "95_lost_city_ctf": "Ghost Town", "99_poland": "Studzianki",
}
