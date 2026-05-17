ЦЕ НОВА КОНЦЕПЦІЯ ОТРИМАННЯ ІНФОРМАЦІЇ ТА СТВОРЕННЯ ЗБІРОК ДЛЯ SETUP ЗА ДОПОМОГОЮ ШІ.
Знайти у клієнті гри назви всіх можливих варіантів обладнання, снарядів, витратних, перків екіпажу, польової модернізації і іконок до них.
Співпоставити всі назви з людськими назвами у грі англійсько бо промт у запиті треба писати людською мовою, а не системними назвамиє.
Знайти у клієнті гри інформацію по кожному танку - яка кількість слотів обладнання, які саме обладнання може бути встановлене (це важливо!), яка кількість слотів перків екіпажу і які саме слоти (командир, навідник, , мехвод, заряджаючий, радист), яка польова модернізація і які саме слоти.
Створити базу даних цієї інформації для кожного танку, щоб програма могла користуватися нею локально, без інтернету. База даних має бути у форматі json.
Зробити механізм зтворення структурованих запитів до щі конкретно для кожного танку в залежності від його слотів, перків екіпажу та польової модернізації. 
Ось приблизний опис промту - Нижче наведено повну структуру: спочатку текстовий промт англійською мовою (готовий до копіювання), а потім детальний розбір — що і чому в ньому прописано.

Plaintext
Current date: {current_date}.

<system_instruction>
You are an advanced, non-conversational data extraction engine for World of Tanks game configurations. Your sole purpose is to process the vehicle name inside the <target_vehicle> tag, match it against your internal technical database, and generate a competitive setup using ONLY the authorized terms provided in the <allowed_entities> block. 

CRITICAL SAFETY FILTERS:
1. Start your response immediately with the exact string "Build Generated:".
2. Right after the string, open a single markdown text block (```text) and put all configuration data inside it.
3. Do not generate any preface, greetings, meta-commentary, or closing remarks.
4. Any term used in the output that is not physically present in the <allowed_entities> lists will cause a synchronization failure.
</system_instruction>

<allowed_entities>
  <equipment>
    Gun Rammer, Improved Ventilation, Vertical Stabilizer, Turbocharger, Improved Hardening, Low-Noise Exhaust System, Coated Optics, Binocular Telescope, Camouflage Net, Spall Liner, Modified Configuration, Improved Rotation Mechanisms, Enhanced Gun Laying Drives, Improved Aiming, Grousers, Additional Grousers, Experimental Turbocharger, Experimental Hardening, Experimental Optics, Experimental Fire-Control System, Experimental Mobility System, Experimental Survival Suite
  </equipment>
  
  <ammo>
    Armor Piercing (AP), Armor Piercing Composite Rigid (APCR), High Explosive Anti-Tank (HEAT), High Explosive (HE)
  </ammo>
  
  <consumables>
    Small Repair Kit, Large Repair Kit, Small First Aid Kit, Large First Aid Kit, Manual Fire Extinguisher, Automatic Fire Extinguisher, Extra Rations, Case of Cola, Chocolate, Pudding and Tea, Strong Coffee, Improved Rations, Bread with Lard, Smoked Lard, Buchty, Spaghetti with Meat Sauce, Onigiri, Coffee with Cinnamon, Sweet Milk, Boiled Cabbage, Roasted Turkey
  </consumables>
  
  <crew_perks>
    Brothers in Arms, Repairs, Concealment, Firefighting, Sixteenth Sense, Eagle Eye, Sound Detection, Jack of All Trades, Armorer, Snap Shot, Designated Target, Smooth Ride, Off-Road Driving, Clutch Braking, Controlled Impact, Preventative Maintenance, Safe Stowage, Adrenaline Rush, Intuition, Situational Awareness, Call for Vengeance, Signal Boosting, Relayer, Expert, Mentor, Camouflage
  </crew_perks>
  
  <field_modifications>
    All-Terrain Suspension, Lightweight Suspension, Parallax Adjustment, Refined Powder, Left-Side Periscope, Right-Side Periscope, Right-Angle Optics, Anti-Reflective Lenses, Reinforced Spall Liner, Anti-Fragmentation Lining, Power Supply Tuning, Electrical System Shielding, Additional Forward Gears, Additional Reverse Gears, No Modification
  </field_modifications>
</allowed_entities>

<target_vehicle>
  {tank_name}
</target_vehicle>

<required_output_format>
Build Generated:
```text
1. Equipment:
   * Loadout 1 (Main): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
   * Loadout 2 (Alternate): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
2. Ammo:
   * Loadout 1 (Main): [Type 1]: [Count] shells | [Type 2]: [Count] shells | [Type 3]: [Count] shells
   * Loadout 2 (Alternate): [Type 1]: [Count] shells | [Type 2]: [Count] shells | [Type 3]: [Count] shells
3. Consumables:
   * Loadout 1 (Main): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
   * Loadout 2 (Alternate): Slot 1: [Item 1] | Slot 2: [Item 2] | Slot 3: [Item 3]
4. Crew Perks:
   * [Actual Crew Member Role 1]: [Perk 1, Perk 2, Perk 3, ...]
   * [Actual Crew Member Role 2]: [Perk 1, Perk 2, ...]
5. Field Modification:
   * [First Available Level Name/Number]: [Choice]
   * [Second Available Level Name/Number]: [Choice]
</required_output_format>


---

### Пояснення: Що і як працює у цьому запиті

1. **Ізоляція за допомогою XML-тегів (`<system_instruction>`, `<allowed_entities>`)**:
   Моделі нового покоління, такі як Antigravity, використовують теги для чіткого розділення логіки. ШІ бачить, де закінчуються правила системи, де лежить "словник" дозволених слів, і де вказано сам танк. Це повністю виключає ситуацію, коли ШІ починає використовувати слова з тексту інструкції як назви обладнання.
2. **Об'єднаний блок `<equipment>`**:
   Як ми і домовлялися, звичайне та експериментальне обладнання тепер лежать в одному списку. ШІ просто бере 3 назви з єдиного масиву для кожної збірки.
3. **Фільтр безпеки виводу (Початок з конкретної фрази)**:
   Вказівка `Start your response immediately with the exact string "Build Generated:"` змушує ШІ одразу перейти до справи. Це тригерує систему безпеки на те, що модель успішно виконує завдання, і запобігає «порожнім відповідям» або технічним збоям через цензуру.
4. **Ізоляція коду (` ```text `)**:
   Загортання результату в блок коду гарантує, що якщо ШІ раптом згенерує якийсь знак пунктуації або спецсимвол, він залишиться всередині текстового блоку, і ваш регулярний вираз у Python легко забере чисті дані.
5. **Динамічний екіпаж та модернізація**:
   Промт не обмежує кількість танкістів чи рівнів польової модернізації. Наприклад, якщо ви
   1. Головний архів із параметрами:
У папці зі встановленою грою тобі потрібен файл:
[Папка з грою]\res\packages\scripts.pkg
(Це звичайний нестиснутий ZIP-архів, його можна відкрити через 7-Zip або WinRAR).

2. Види та характеристики снарядів:
Відкриваєш scripts.pkg і йдеш за шляхом:
scripts\item_defs\vehicles\[нація]\components\
У цій папці лежить файл shells.xml. Саме там зберігається глобальний список усіх снарядів для конкретної нації (наприклад, для СРСР, Німеччини тощо), їхні системні ідентифікатори та класи (ARMOR_PIERCING, HIGH_EXPLOSIVE, ARMOR_PIERCING_CR і т.д.).

3. Місткість боєкомплекту (Ammo Capacity):
Ця цифра прив'язана до конкретного танка і гармати. У тому ж архіві йдеш сюди:
scripts\item_defs\vehicles\[нація]\
Там лежать XML-файли кожного окремого танка (наприклад, R19_IS-3.xml). Якщо відкрити цей файл і знайти блок опису гармати, там буде параметр <maxAmmo> — це і є максимальна кількість снарядів для танка.

4. Текстові назви (Локалізація):
Якщо тобі потрібні не системні змінні типу ARMOR_PIERCING_CR, а нормальні назви, які виводяться в інтерфейсі (англійські чи українські), вони лежать в іншому архіві:
[Папка з грою]\res\packages\text.pkg (або в розпакованому вигляді у res\text\lc_messages\).
Файли там мають розширення .mo (найімовірніше, тобі знадобиться item_types.mo або artifacts.mo).
Команди для Оріон - The following command line options are valid with Python:
--help
--exit
--exec-string=
--run-file=
--import-file=
--compile-file=
--compile-folder=
--minimize-text-file=
--minimize-text-folder=
--obfuscate-text-file=
--obfuscate-text-folder=
--obfuscate-bytecode-file=
--obfuscate-bytecode-folder=
--protect-bytecode-file=
--protect-bytecode-folder=
--decompile-file-uncompyle6=
--decompile-file-decompylepp=
--decompile-file-fupy=
--decompile-file-pyretic=
--decompile-folder-uncompyle6=
--decompile-folder-decompylepp=
--decompile-folder-fupy=
--decompile-folder-pyretic=
--info-file=
--disassemble-file=
--unpack-file=
--unpack-folder=
--run-game