import json, os
db = json.load(open('tank_db.json', encoding='utf-8'))
icons = os.listdir('extracted_icons')
popular = ['R155_Object_277', 'R45_IS-7', 'GB91_Super_Conqueror', 'Cz17_Vz_55', 'Pl21_CS_63', 'Pl15_60TP_Lewandowskiego', 'G89_Leopard1', 'F108_Panhard_EBR_105', 'GB100_Manticore', 'Ch47_BZ_176', 'F116_Bat_Chatillon_Bourrasque', 'Cz14_Skoda_T-56', 'It08_Progetto_M40_mod_65', 'It13_Progetto_M35_mod_46', 'R97_Object_140', 'R148_Object_430_U', 'A16_M18_Hellcat', 'G119_Panzer58', 'A80_T26_E4_SuperPershing', 'S11_Strv_103B']

print("Missing popular:")
for p in popular:
    found = False
    base = p.lower().replace('-', '_')
    for icon in icons:
        icon_base = icon.lower().replace('-', '_').replace('.png', '')
        if icon_base in [base, f"ussr_{base}", f"uk_{base}", f"germany_{base}", f"france_{base}", f"usa_{base}"]: 
            found = True
            break
    if not found:
        print(p)

print("\r\nMissing all DB:")
missing_all = 0
for k, v in db.items():
    found = False
    base = k.lower().replace('-', '_')
    for icon in icons:
        icon_base = icon.lower().replace('-', '_').replace('.png', '')
        if base in icon_base: 
            found = True
            break
    if not found:
        missing_all += 1
print(f"Missing overall: {missing_all} out of {len(db)}")
