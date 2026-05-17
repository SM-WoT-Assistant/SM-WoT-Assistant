#!/usr/bin/env python3
"""
=================================================================================================
generate_prompt_v2.py - Prompt Generator for World of Tanks Competitive Builds
=================================================================================================

ОПИС:
    Генерує AI-промт для створення competitive build з реальними даними з клієнта гри World of Tanks.
    Промт містить два варіанти build (Main і Advanced) для кожного танка.

ДЖЕРЕЛА ДАНИХ (з клієнта гри):
    - tank_slots_full.json: Кількість слотів обладнання для кожного танка
    - tank_db.json: Tier, клас та нація танка
    - crew_builds.json: Склад екіпажу, пули перків (_role_skill_pools), політика перків (_perk_policy)
    - game_entities_english.json: Англійські назви обладнання, витратних матеріалів, раціонів

ЛОГІКА РОБОТИ:
    1. ОБЛАДНАННЯ:
       - Tier 1-4 використовують обладнання Tier 3 (7-10 предметів)
       - Tier 5-7 використовують обладнання Tier 2 (10-12 предметів)
       - Tier 8-10 використовують обладнання Tier 1 + експериментальне (28 предметів)
       - SPG виключає Vertical Stabilizer та Grousers (не можуть використовувати)
       
    2. ВИТРАТНІ МАТЕРІАЛИ:
       - Main: повний набір (включає пожежогасіння)
       - Advanced: без пожежогасіння + nation-specific ration в слоті 3
       - Назви з клієнта: Small/Large Repair Kit, Small/Large First Aid Kit,
         Manual/Automatic Fire Extinguisher, Strong Coffee, Chocolate, Cola
       
    3. НАЦІОНАЛЬНІ РАЦІОНИ (з клієнта):
       - USSR: Extra Rations
       - USA: Cola
       - Germany: Chocolate
       - UK: Pudding and Tea
       - Japan: Onigiri
       - China: Improved Combat Rations
       - Czech: Buchty
       - Italy: Spaghetti with Meat Sauce
       - Poland: Bread with Smalec
       - Sweden: Coffee with Cinnamon Buns
       
    4. ЕКІПАЖ:
       - Перки беруться з _role_skill_pools клієнта
       - Кількість перків за tier з _perk_policy (Tier 10 = 6 перків)
       - loader_radio показується окремо: Loader (6 перків) + Radioman (4 перки)
       - Пріоритет перків: repairs, camouflage, brotherhood (базові для всіх)

    5. ПОЛЯ МОДИФІКАЦІЙ:
       - Level II: All-Terrain Suspension / Lightweight Suspension / No Modification
       - Level IV: Parallax Adjustment / Refined Powder / Left/Right-Side Periscope / No Modification
       - Level VI: Right-Angle Optics / Anti-Reflective Lenses / Reinforced/Anti-Fragmentation Lining / No Modification
       - Level VIII: Power Supply Tuning / Electrical System Shielding / Additional Forward/Reverse Gears / No Modification

ВИКОРИСТАННЯ:
    python generate_prompt_v2.py "Tank Name"
    Приклад: python generate_prompt_v2.py "Super Conqueror"

=================================================================================================
"""
import json
from datetime import datetime

# ==============================================================================
# ЗАВАНТАЖЕННЯ ДАНИХ З КЛІЄНТА ГРИ
# ==============================================================================

with open('tank_slots_full.json', 'r', encoding='utf-8') as f:
    tank_slots = json.load(f)

with open('tank_db.json', 'r', encoding='utf-8') as f:
    tank_db = json.load(f)

with open('game_entities_english.json', 'r', encoding='utf-8') as f:
    game_entities = json.load(f)

with open('crew_builds.json', 'r', encoding='utf-8') as f:
    crew_builds = json.load(f)

# ==============================================================================
# ДАНІ ПРО ПЕРКИ З _role_skill_pools (клієнт гри)
# ==============================================================================

ROLE_SKILL_POOLS = crew_builds.get('_role_skill_pools', {})
PERK_POLICY = crew_builds.get('_perk_policy', {})
DEFAULT_PRIMARY_PERK_COUNT = PERK_POLICY.get('default_primary_perk_count', 6)
PRIMARY_PERK_COUNT_BY_TIER = PERK_POLICY.get('primary_perk_count_by_tier', {})

# Мапінг ID перків на англійські назви (з game_entities_english.json)
PERK_NAME_MAP = {
    'commander_sixthSense': 'Sixth Sense',
    'commander_practical': 'Eagle Eye',
    'commander_eagleEye': 'Eagle Eye',
    'commander_enemyShotPredictor': 'Enemy Shot Predictor',
    'gunner_sniper': 'Snap Shot',
    'gunner_focus': 'Designated Target',
    'gunner_rancorous': 'Rancorous',
    'gunner_smoothTurret': 'Smooth Turret',
    'driver_smoothDriving': 'Smooth Driving',
    'driver_badRoadsKing': 'Off-Road Driving',
    'driver_virtuoso': 'Virtuoso',
    'driver_rammingMaster': 'Ramming Master',
    'loader_pedant': 'Safe Stowage',
    'loader_desperado': 'Desperado',
    'loader_intuition': 'Intuition',
    'radioman_finder': 'Relayer',
    'improvedRadioCommunication': 'Improved Radio Communication',
    'smokeSignal': 'Smoke Signal',
    'repair': 'Repairs',
    'camouflage': 'Concealment',
    'brotherhood': 'Brothers in Arms',
    'fireFighting': 'Firefighting'
}

# ==============================================================================
# ОБЛАДНАННЯ ПО TIER (з клієнта гри: стандартне + експериментальне)
# ==============================================================================

EQUIPMENT_BY_TIER = {
    1: [
        "camouflageNet_tier3", "coatedOptics_tier3", "enhancedAimDrives_tier3",
        "grousers_tier3", "improvedVentilation_tier3", "improvedSights_tier3",
        "stereoscope_tier3"
    ],
    2: [
        "camouflageNet_tier3", "coatedOptics_tier3", "enhancedAimDrives_tier3",
        "grousers_tier3", "improvedVentilation_tier3", "improvedSights_tier3",
        "stereoscope_tier3"
    ],
    3: [
        "camouflageNet_tier3", "coatedOptics_tier3", "enhancedAimDrives_tier3",
        "grousers_tier3", "improvedVentilation_tier3", "improvedSights_tier3",
        "stereoscope_tier3", "tankRammer_tier3", "binocularTelescope_tier3"
    ],
    4: [
        "camouflageNet_tier3", "coatedOptics_tier3", "enhancedAimDrives_tier3",
        "grousers_tier3", "improvedVentilation_tier3", "improvedSights_tier3",
        "stereoscope_tier3", "tankRammer_tier3", "binocularTelescope_tier3"
    ],
    5: [
        "camouflageNet_tier2", "coatedOptics_tier2", "enhancedAimDrives_tier2",
        "grousers_tier2", "improvedVentilation_tier2", "improvedSights_tier2",
        "stereoscope_tier2", "tankRammer_tier2", "binocularTelescope_tier2",
        "improvedConfiguration_tier2", "improvedRotationMechanism_tier2"
    ],
    6: [
        "camouflageNet_tier2", "coatedOptics_tier2", "enhancedAimDrives_tier2",
        "grousers_tier2", "improvedVentilation_tier2", "improvedSights_tier2",
        "stereoscope_tier2", "tankRammer_tier2", "binocularTelescope_tier2",
        "improvedConfiguration_tier2", "improvedRotationMechanism_tier2"
    ],
    7: [
        "camouflageNet_tier2", "coatedOptics_tier2", "enhancedAimDrives_tier2",
        "grousers_tier2", "improvedVentilation_tier2", "improvedSights_tier2",
        "stereoscope_tier2", "tankRammer_tier2", "binocularTelescope_tier2",
        "improvedConfiguration_tier2", "improvedRotationMechanism_tier2",
        "aimingStabilizer_tier2", "additionalInvisibilityDevice_tier2"
    ],
    8: [
        "camouflageNet_tier1", "coatedOptics_tier1", "enhancedAimDrives_tier1",
        "grousers_tier1", "improvedVentilation_tier1", "improvedSights_tier1",
        "stereoscope_tier1", "tankRammer_tier1", "binocularTelescope_tier1",
        "improvedConfiguration_tier1", "improvedRotationMechanism_tier1",
        "aimingStabilizer_tier1", "additionalInvisibilityDevice_tier1",
        "turbocharger_tier1", "extraHealthReserve_tier1",
        "antifragmentationLining_tier1",
        # Експериментальне (deluxe)
        "deluxRammer", "deluxCoatedOptics", "deluxAimingStabilizer",
        "deluxEnhancedAimDrives", "deluxImprovedConfiguration", "deluxImprovedVentilation",
        "deluxeTurbocharger", "deluxeExtraHealthReserve", "deluxeImprovedRotationMechanism",
        "deluxeImprovedSights", "deluxeAdditionalInvisibilityDevice", "deluxeStereoscope",
        "deluxeCamouflageNet"
    ],
    9: [
        "camouflageNet_tier1", "coatedOptics_tier1", "enhancedAimDrives_tier1",
        "grousers_tier1", "improvedVentilation_tier1", "improvedSights_tier1",
        "stereoscope_tier1", "tankRammer_tier1", "binocularTelescope_tier1",
        "improvedConfiguration_tier1", "improvedRotationMechanism_tier1",
        "aimingStabilizer_tier1", "additionalInvisibilityDevice_tier1",
        "turbocharger_tier1", "extraHealthReserve_tier1",
        "antifragmentationLining_tier1",
        # Експериментальне (deluxe)
        "deluxRammer", "deluxCoatedOptics", "deluxAimingStabilizer",
        "deluxEnhancedAimDrives", "deluxImprovedConfiguration", "deluxImprovedVentilation",
        "deluxeTurbocharger", "deluxeExtraHealthReserve", "deluxeImprovedRotationMechanism",
        "deluxeImprovedSights", "deluxeAdditionalInvisibilityDevice", "deluxeStereoscope",
        "deluxeCamouflageNet"
    ],
    10: [
        "camouflageNet_tier1", "coatedOptics_tier1", "enhancedAimDrives_tier1",
        "grousers_tier1", "improvedVentilation_tier1", "improvedSights_tier1",
        "stereoscope_tier1", "tankRammer_tier1", "binocularTelescope_tier1",
        "improvedConfiguration_tier1", "improvedRotationMechanism_tier1",
        "aimingStabilizer_tier1", "additionalInvisibilityDevice_tier1",
        "turbocharger_tier1", "extraHealthReserve_tier1",
        "antifragmentationLining_tier1",
        # Експериментальне (deluxe)
        "deluxRammer", "deluxCoatedOptics", "deluxAimingStabilizer",
        "deluxEnhancedAimDrives", "deluxImprovedConfiguration", "deluxImprovedVentilation",
        "deluxeTurbocharger", "deluxeExtraHealthReserve", "deluxeImprovedRotationMechanism",
        "deluxeImprovedSights", "deluxeAdditionalInvisibilityDevice", "deluxeStereoscope",
        "deluxeCamouflageNet"
    ]
}

# ==============================================================================
# ВИКЛЮЧЕННЯ ОБЛАДНАННЯ ЗА КЛАСОМ ТАНКА
# SPG не може використовувати Vertical Stabilizer та Grousers (з клієнта гри)
# ==============================================================================

EQUIPMENT_EXCLUDE_BY_CLASS = {
    "SPG": ["aimingStabilizer_tier1", "aimingStabilizer_tier2", "aimingStabilizer_tier3",
            "grousers_tier1", "grousers_tier2", "grousers_tier3", "additionalGrousers"],
    "LT": [],  # Light tanks - немає виключень
    "MT": [],  # Medium tanks - немає виключень
    "HT": [],  # Heavy tanks - немає виключень
    "TD": []   # Tank destroyers - немає виключень
}

# ==============================================================================
# НАЗВИ ОБЛАДНАННЯ З КЛІЄНТА ГРИ (файл artefacts_en.mo) - БЕЗ Class І ЦИФР
# ==============================================================================

# Тут використовуємо FALLBACK_EQUIPMENT_NAMES як основний словник
# ==============================================================================

FALLBACK_EQUIPMENT_NAMES = {
    # Стандартне обладнання (Tier 1-3)
    "tankRammer_tier1": "Gun Rammer",
    "tankRammer_tier2": "Gun Rammer",
    "tankRammer_tier3": "Gun Rammer",
    "improvedVentilation_tier1": "Improved Ventilation",
    "improvedVentilation_tier2": "Improved Ventilation",
    "improvedVentilation_tier3": "Improved Ventilation",
    "aimingStabilizer_tier1": "Vertical Stabilizer",
    "aimingStabilizer_tier2": "Vertical Stabilizer",
    "aimingStabilizer_tier3": "Vertical Stabilizer",
    "enhancedAimDrives_tier1": "Enhanced Gun Laying Drive",
    "enhancedAimDrives_tier2": "Enhanced Gun Laying Drive",
    "enhancedAimDrives_tier3": "Enhanced Gun Laying Drive",
    "coatedOptics_tier1": "Coated Optics",
    "coatedOptics_tier2": "Coated Optics",
    "coatedOptics_tier3": "Coated Optics",
    "turbocharger_tier1": "Turbocharger",
    "turbocharger_tier2": "Turbocharger",
    "turbocharger_tier3": "Turbocharger",
    "improvedRotationMechanism_tier1": "Improved Rotation Mechanism",
    "improvedRotationMechanism_tier2": "Improved Rotation Mechanism",
    "improvedSights_tier1": "Improved Aiming",
    "improvedSights_tier2": "Improved Aiming",
    "improvedSights_tier3": "Improved Aiming",
    "improvedConfiguration_tier1": "Modified Configuration",
    "improvedConfiguration_tier2": "Modified Configuration",
    "additionalInvisibilityDevice_tier1": "Low Noise Exhaust System",
    "additionalInvisibilityDevice_tier2": "Low Noise Exhaust System",
    "additionalInvisibilityDevice_tier3": "Low Noise Exhaust System",
    "extraHealthReserve_tier1": "Improved Hardening",
    "extraHealthReserve_tier2": "Improved Hardening",
    "extraHealthReserve_tier3": "Improved Hardening",
    "antifragmentationLining_tier1": "Superheavy Spall Liner",
    "antifragmentationLining_tier2": "Heavy Spall Liner",
    "antifragmentationLining_tier3": "Medium Spall Liner",
    "antifragmentationLining_tier4": "Light Spall Liner",
    "camouflageNet_tier1": "Camouflage Net",
    "camouflageNet_tier2": "Camouflage Net",
    "camouflageNet_tier3": "Camouflage Net",
    "grousers_tier1": "Additional Grousers",
    "grousers_tier2": "Additional Grousers",
    "grousers_tier3": "Additional Grousers",
    "stereoscope_tier1": "Binocular Telescope",
    "stereoscope_tier2": "Binocular Telescope",
    "stereoscope_tier3": "Binocular Telescope",
    "binocularTelescope_tier1": "Binocular Telescope",
    "binocularTelescope_tier2": "Binocular Telescope",
    "binocularTelescope_tier3": "Binocular Telescope",
    # Експериментальне (Deluxe)
    "deluxRammer": "Innovative Loading System",
    "deluxCoatedOptics": "Experimental Optics",
    "deluxAimingStabilizer": "Stabilizing Equipment System",
    "deluxEnhancedAimDrives": "Wear-Resistant Gun Laying Drive",
    "deluxImprovedConfiguration": "Improved Configuration",
    "deluxImprovedVentilation": "Venting System",
    "deluxeTurbocharger": "Improved Compressor",
    "deluxeExtraHealthReserve": "Increased Shell Resistance",
    "deluxeImprovedRotationMechanism": "Improved Final Drive",
    "deluxeImprovedSights": "Innovative Targeting",
    "deluxeAdditionalInvisibilityDevice": "Stealth Exhaust Unit",
    "deluxeStereoscope": "Telescopic Observation System",
    "deluxeCamouflageNet": "Tactical Concealment Net",
    # Додаткові з клієнта
    "additionalInvisibilityDevice": "Low Noise Exhaust System",
    "camouflageNet": "Camouflage Net",
    "invisibilityBonus": "Invisibility Bonus",
}

# ==============================================================================
# ФУНКЦІЇ ДЛЯ ГЕНЕРАЦІЇ ПРОМТУ
# ==============================================================================

def get_equipment_for_tank(tank_id, tier, tank_class):
    """
    Повертає список обладнання для танка З КЛІЄНТА ГРИ.
    Використовує стандартне обладнання за tier танка.
    """
    # Отримуємо стандартне обладнання за tier танка
    equipment_list = EQUIPMENT_BY_TIER.get(tier, EQUIPMENT_BY_TIER[5])
    
    # Фільтруємо за класом танка (SPG виключає Stabilizer, Grousers)
    excluded = EQUIPMENT_EXCLUDE_BY_CLASS.get(tank_class, [])
    filtered = [eq for eq in equipment_list if eq not in excluded]
    
    # Конвертуємо ID в назви з клієнта
    result = []
    for eq_id in filtered:
        name = FALLBACK_EQUIPMENT_NAMES.get(eq_id, eq_id)
        if name not in result:
            result.append(name)
    
    return result


def get_ammo_types():
    """
    Повертає список типів снарядів (з клієнта гри).
    Джерело: game_entities_english.json
    """
    return ["Armor Piercing (AP)", "Armor Piercing Composite Rigid (APCR)",
            "High Explosive Anti-Tank (HEAT)", "High Explosive (HE)"]


# ==============================================================================
# НАЦІОНАЛЬНІ РАЦІОНИ (з клієнта гри - game_entities_english.json)
# ==============================================================================
# ВАЖЛИВО: Ці дані взяті з клієнта гри, не з лабораторних припущень!
# Кожен раціон підвищує ефективність екіпажу на +10% і діє автоматично весь бій.
# Доступні лише для техніки відповідної нації.
# ==============================================================================

NATION_RATIONS = {
    "ussr": "Extra Rations",        # Тільки для СССР (раніше: Додатковий пайок)
    "usa": "Cola",                  # Тільки для США (раніше: помилково Chocolate)
    "germany": "Chocolate",         # Тільки для Німеччини
    "uk": "Pudding and Tea",        # Тільки для Великобританії (раніше: Pudding із чаєм)
    "japan": "Onigiri",            # Тільки для Японії
    "china": "Improved Combat Rations",  # Тільки для Китаю (раніше: Поліпшений раціон)
    "czech": "Buchty",              # Тільки для Чехословаччини
    "italy": "Spaghetti with Meat Sauce",  # Тільки для Італії
    "poland": "Bread with Smalec",  # Тільки для Польщі (раніше: Хліб зі смальцем)
    "sweden": "Coffee with Cinnamon Buns",  # Тільки для Швеції (раніше: Кава з печивом)
}


def get_consumables_list(nation="ussr"):
    """
    Повертає список витратних матеріалів для Main loadout (з клієнта гри).
    Включає ВСІ доступні предмети: ремкомплекти, аптечки, пожежогасіння, посилення.
    Цей список використовується для Main (звичайного) набору.
    """
    base = [
        "Small Repair Kit", "Large Repair Kit",
        "Small First Aid Kit", "Large First Aid Kit",
        "Manual Fire Extinguisher", "Automatic Fire Extinguisher",
        "Strong Coffee", "Chocolate", "Cola"
    ]
    return base


def get_nation_ration(nation="ussr"):
    """
    Повертає nation-specific ration для нації (для Advanced слот 3).
    Цей раціон підставляється замість пожежогасіння в Advanced наборі.
    """
    nation_ration = NATION_RATIONS.get(nation.lower())
    return nation_ration if nation_ration else None


def get_crew_data_for_tank(tank_id, tier):
    """
    Повертає дані про екіпаж танка з crew_builds.json.
    - Члени екіпажу беруться з 'tanks' -> tank_id -> 'crew_members'
    - Перки беруться з _role_skill_pools (пули перків для кожної ролі)
    - Кількість перків за tier з _perk_policy -> primary_perk_count_by_tier
    """
    with open('crew_builds.json', 'r', encoding='utf-8') as f:
        crew_builds = json.load(f)
    
    tank_crew = crew_builds.get('tanks', {}).get(tank_id, {})
    crew_members = tank_crew.get('crew_members', [])
    role_skill_pools = crew_builds.get('_role_skill_pools', {})
    perk_policy = crew_builds.get('_perk_policy', {})
    
    # Кількість перків за tier з _perk_policy (Tier 10 = 6 перків)
    primary_perk_count = perk_policy.get('primary_perk_count_by_tier', {}).get(str(tier), 6)
    
    result = {
        'crew_members': [],
        'perk_count': primary_perk_count,
        'available_perks': {}
    }
    
    for member in crew_members:
        role = member.get('role', '')
        also = member.get('also', [])
        
        roles_to_check = [role] + also
        
        perks_for_member = set()
        for r in roles_to_check:
            if r in role_skill_pools:
                for perk_id in role_skill_pools[r]:
                    perk_name = PERK_NAME_MAP.get(perk_id, perk_id)
                    perks_for_member.add(perk_name)
        
        result['crew_members'].append({
            'role': role,
            'also': also,
            'perks': sorted(list(perks_for_member))
        })
    
    return result


def get_field_mods():
    """
    Повертає список польових модернізацій (з клієнта гри).
    Ці модифікації доступні на різних рівнях прокачки танка.
    """
    return [
        "All-Terrain Suspension", "Lightweight Suspension",
        "Parallax Adjustment", "Refined Powder", "Left-Side Periscope", "Right-Side Periscope",
        "Right-Angle Optics", "Anti-Reflective Lenses", "Reinforced Spall Liner", "Anti-Fragmentation Lining",
        "Power Supply Tuning", "Electrical System Shielding", "Additional Forward Gears", "Additional Reverse Gears",
        "No Modification"
    ]


def generate_prompt(tank_id, tank_name=None):
    """
    Основна функція генерації AI-промту для competitive build.

    ПАРАМЕТРИ:
        tank_id: ID танка (наприклад, 'R45_IS-7', 'GB91_Super_Conqueror')
        tank_name: Назва танка для відображення (опціонально)

    ПОВЕРТАЄ:
        Промт для AI з двома варіантами build:
        - Main: стандартний набір обладнання, витратних матеріалів, перків
        - Advanced: максимальні параметри з експериментальним обладнанням,
                    nation ration замість пожежогасіння в слоті 3

    ДЖЕРЕЛА ДАНИХ (з клієнта гри):
        - tank_slots_full.json: кількість слотів обладнання
        - tank_db.json: tier, клас, нація танка
        - crew_builds.json: склад екіпажу, перки, політика перків
        - game_entities_english.json: англійські назви обладнання

    ЛОГІКА ФОРМУВАННЯ:
        1. Обладнання: стандартне + експериментальне для Tier 8-10
        2. Витратні:
           - Main: повний набір (включає пожежогасіння)
           - Advanced: слот 3 = nation ration, без пожежогасіння
        3. Перки: з _role_skill_pools клієнта, кількість за tier
        4. Поля модифікацій: 4 рівні з різними опціями
    """
    tank_data = tank_slots.get(tank_id)
    tank_info = tank_db.get(tank_id)
    
    if not tank_data:
        return f"Tank {tank_id} not found"
    
    if not tank_name:
        tank_name = tank_data.get('name_english', tank_id)
    
    tier = tank_info.get('tier', 8) if tank_info else 8
    tank_class = tank_info.get('class', 'MT') if tank_info else 'MT'
    nation = tank_info.get('nation', 'ussr') if tank_info else 'ussr'
    
    equip_slot_count = tank_data.get('equipment_slots', 3)
    equipment_list = get_equipment_for_tank(tank_id, tier, tank_class)
    ammo_list = get_ammo_types()
    consumables_list = get_consumables_list(nation)
    nation_ration = get_nation_ration(nation)
    
    consumables_advanced_list = [c for c in consumables_list if c not in ["Manual Fire Extinguisher", "Automatic Fire Extinguisher"]]
    if nation_ration and nation_ration not in consumables_advanced_list:
        consumables_advanced_list.append(nation_ration)
    crew_data = get_crew_data_for_tank(tank_id, tier)
    field_mods = get_field_mods()
    
    primary_perk_count = crew_data['perk_count']
    
    # Знаходимо члени екіпажу з ролью loader_radio або loader з also=['radioman']
    combined_roles = [m for m in crew_data['crew_members'] 
                      if m['role'] == 'loader_radio' or 
                      (m['role'] == 'loader' and 'radioman' in m.get('also', []))]
    has_combined_loader_radio = len(combined_roles) > 0
    
    crew_perks_section = ""
    crew_roles_output = ""
    for member in crew_data['crew_members']:
        role = member['role']
        also = member.get('also', [])
        perks = member['perks']
        
        # Перевіряємо чи це комбінована роль loader_radio
        is_combined = (role == 'loader_radio') or (role == 'loader' and 'radioman' in also)
        
        # Якщо є комбінована роль - показуємо Loader-Radioman
        if is_combined and has_combined_loader_radio:
            loader_perks = ROLE_SKILL_POOLS.get('loader', [])
            radioman_perks = ROLE_SKILL_POOLS.get('radioman', [])
            
            loader_perk_names = [PERK_NAME_MAP.get(p, p) for p in loader_perks]
            radioman_perk_names = [PERK_NAME_MAP.get(p, p) for p in radioman_perks]
            
            crew_perks_section += f"loader: {', '.join(loader_perk_names)}\n"
            crew_perks_section += f"radioman: {', '.join(radioman_perk_names)}\n"
            
            loader_perks_list = ", ".join([f"Perk {i+1}" for i in range(6)])
            radioman_perks_list = ", ".join([f"Perk {i+1}" for i in range(4)])
            crew_roles_output += f"   * Loader-Radioman: [{loader_perks_list}] (choose 6)\n"
            crew_roles_output += f"      └─ Radioman: [{radioman_perks_list}] (choose 4)\n"
        # Якщо це звичайний loader і є комбінована роль десь - пропускаємо
        elif role == "loader" and has_combined_loader_radio:
            continue
        # Звичайні ролі
        else:
            crew_perks_section += f"{role}: {', '.join(perks)}\n"
            display_role = role
            perks_list = ", ".join([f"Perk {i+1}" for i in range(primary_perk_count)])
            crew_roles_output += f"   * {display_role}: [{perks_list}] (choose {primary_perk_count})\n"
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    slots_line = " | ".join([f"Slot {i+1}: [Item {i+1}]" for i in range(equip_slot_count)])
    
    prompt = f"""Current date: {current_date}.

[INSTRUCTION CONTEXT & PURPOSE]
This instruction acts as a configuration generator for the game World of Tanks. Its purpose is to process the requested tank name and output a highly precise, machine-readable competitive build. This output will be directly parsed by a downstream Python application.

Generate the optimal competitive build data for the tank: {tank_name}.

You must ONLY use the exact names and terms provided in the lists below. Begin your response exactly with the phrase "Build Generated:" followed immediately by a markdown code block containing the requested data. Do not include any other conversational text or explanations outside or inside the code block.

1. EQUIPMENT (Select EXACTLY {equip_slot_count} items for EACH variant - Main and Advanced):
- Loadout 1 (Main): Select {equip_slot_count} equipment items for optimal performance
- Loadout 2 (Advanced): Select {equip_slot_count} equipment items (different from Main) - choose items that maximize all parameters combining both standard AND experimental equipment options
Available items: {', '.join(equipment_list)}.

2. AMMO TYPES (Select for EACH variant - Main and Advanced):
- Loadout 1 (Main): Select ammo types and counts
- Loadout 2 (Advanced): Select ammo types and counts (different from Main)
Available types: {', '.join(ammo_list)}.

3. CONSUMABLES (Select for EACH variant - Main and Advanced):
- Loadout 1 (Main): Select 3 consumable items (any from list)
- Loadout 2 (Advanced): Select 3 consumable items (different from Main) - Slot 1-2: NO fire extinguishers | Slot 3: MUST be nation ration
Available items (Main): {', '.join(consumables_list)}.
Available items (Advanced): {', '.join(consumables_advanced_list)}.

4. CREW PERKS (Select {crew_data['perk_count']} perks for each role from these lists):
{crew_perks_section}
5. FIELD MODIFICATIONS (Select one option per level from this list):
Level II: "All-Terrain Suspension" OR "Lightweight Suspension" OR "No Modification"
Level IV: "Parallax Adjustment" OR "Refined Powder" OR "Left-Side Periscope" OR "Right-Side Periscope" OR "No Modification"
Level VI: "Right-Angle Optics" OR "Anti-Reflective Lenses" OR "Reinforced Spall Liner" OR "Anti-Fragmentation Lining" OR "No Modification"
Level VIII: "Power Supply Tuning" OR "Electrical System Shielding" OR "Additional Forward Gears" OR "Additional Reverse Gears" OR "No Modification"

OUTPUT FORMAT:
Build Generated:
```text
1. Equipment:
   * Loadout 1 (Main): {slots_line}
* Loadout 2 (Advanced): {slots_line}
 2. Ammo:
   * Loadout 1 (Main): [Type 1]: [Count] shells | [Type 2]: [Count] shells | [Type 3]: [Count] shells
   * Loadout 2 (Advanced): [Type 1]: [Count] shells | [Type 2]: [Count] shells | [Type 3]: [Count] shells
 3. Consumables:
   * Loadout 1 (Main): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
   * Loadout 2 (Advanced): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3] (include nation ration)
4. Crew Perks (same for both loadouts):
{crew_roles_output}
5. Field Modification: Level II: [Choice] | Level IV: [Choice] | Level VI: [Choice] | Level VIII: [Choice]
```"""
    
    return prompt


# ==============================================================================
# ЗАПУСК ПРОГРАМИ
# ==============================================================================
# Використання:
#     python generate_prompt_v2.py "Tank Name"
#
# Приклади:
#     python generate_prompt_v2.py "Super Conqueror"
#     python generate_prompt_v2.py "IS-7"
#     python generate_prompt_v2.py "M4 Sherman"
#
# Вихідний файл: prompt_{TankName}_v5.txt
# ==============================================================================

if __name__ == "__main__":
    import sys

    # Отримання назви танка з аргументу командного рядка
    if len(sys.argv) > 1:
        tank_name_arg = sys.argv[1]
    else:
        tank_name_arg = "Super Conqueror"  # Значення за замовчуванням

    tank_id = None
    tank_name = None

    # Пошук танка за назвою (підтримка кирилиці та різних форматів)
    # Нормалізуємо: видаляємо дефіси, пробіли, конвертуємо кирилицю (йс/ис -> is)
    search_term = tank_name_arg.lower().replace('-', '').replace(' ', '')
    
    for tid, tinfo in tank_db.items():
        name = tinfo.get('name', '')
        name_normalized = name.lower().replace('-', '').replace(' ', '').replace('йс', 'is').replace('ис', 'is')
        id_normalized = tid.lower().replace('_', '').replace('-', '')
        
        # Порівнюємо нормалізовану назву та ID танка
        if search_term in name_normalized or search_term in id_normalized:
            tank_id = tid
            tank_name = name
            break

    # Якщо танк не знайдено - виводимо помилку
    if not tank_id:
        print(f"Tank not found: {tank_name_arg}")
        sys.exit(1)

    # Генерація промту
    prompt = generate_prompt(tank_id, tank_name)

    # Збереження промту у файл
    output_file = f"prompt_{tank_name.replace(' ', '_')}_v5.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    
    # Вивід інформації про танк
    tank_info = tank_db.get(tank_id, {})
    tank_slots_info = tank_slots.get(tank_id, {})
    
    print(f"Tank: {tank_name}")
    print(f"Tier: {tank_info.get('tier', 'N/A')}")
    print(f"Class: {tank_info.get('class', 'N/A')}")
    print(f"Equipment slots: {tank_slots_info.get('equipment_slots', 0)}")
    
    equipment = get_equipment_for_tank(tank_id, tank_info.get('tier', 10), tank_info.get('class', 'HT'))
    print(f"Available equipment: {len(equipment)} items")
    
    print(f"\nSaved to {output_file}")