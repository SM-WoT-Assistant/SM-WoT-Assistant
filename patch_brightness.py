with open('stats_ai.py', 'r', encoding='utf-8') as f:
    src = f.read()

target = '''        if icon_path:
            img = Image.open(icon_path).convert("RGBA")
            if disabled:
                from PIL import ImageEnhance
                img = ImageEnhance.Brightness(img).enhance(0.3)'''

replacement = '''        if icon_path:
            img = Image.open(icon_path).convert("RGBA")
            if disabled:
                from PIL import ImageEnhance
                img = ImageEnhance.Brightness(img).enhance(0.3)
            elif category == "artefacts" and name in ["repair", "camouflage", "fireFighting"]:
                # These are dark directive icons in the artefacts folder, so artificially brighten them
                from PIL import ImageEnhance
                img = ImageEnhance.Brightness(img).enhance(2.5)'''

if target in src:
    src = src.replace(target, replacement)
    with open('stats_ai.py', 'w', encoding='utf-8') as f:
        f.write(src)
    print("Patched brightness")
else:
    print("Target not found!")
