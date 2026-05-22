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

# config_4_13.py