import os
root = '.'
old = 'WoT_Assistant_5.1'
new = 'SETUP & MAPS WOT ASSISTANT 1.00'
found = []
for r, d, f in os.walk(root):
    d[:] = [x for x in d if not x.startswith('.')]
    for fn in f:
        if fn.endswith(('.py','.md','.txt','.json','.js','.html')):
            fp = os.path.join(r, fn)
            try:
                with open(fp,'r',encoding='utf-8',errors='ignore') as fobj:
                    if old in fobj.read():
                        found.append(fp)
            except: pass
print('Found:')
for p in found:
    print(p)
print('Count:', len(found))