from polib import mofile

path = r'C:/Games/World_of_Tanks_EU/res/text/lc_messages/arenas.mo'
po = mofile(path)

print("Українські назви мап з arenas.mo:")
for entry in po:
    if entry.msgid.startswith('#arenas:') and entry.msgid.endswith('/name'):
        print(f"{entry.msgid}: {entry.msgstr}")

# Особлива перевірка для Graf Zeppelin
graf_key = '#arenas:120_graf_zeppelin/name'
for entry in po:
    if entry.msgid == graf_key:
        print(f"\nGraf Zeppelin: {entry.msgstr}")
        break
else:
    print(f"\nGraf Zeppelin ({graf_key}) не знайдено.")