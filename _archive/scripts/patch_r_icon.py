with open('stats_ai.py', 'r', encoding='utf-8') as f:
    src = f.read()

target = 'if "commander" in r_icon: r_icon = "commander"'
replacement = 'if "commander" in r_icon: r_icon = "commander"\n            r_icon += "_plus"'

src = src.replace(target, replacement)

with open('stats_ai.py', 'w', encoding='utf-8') as f:
    f.write(src)
    
print("Patched stats_ai.py")
