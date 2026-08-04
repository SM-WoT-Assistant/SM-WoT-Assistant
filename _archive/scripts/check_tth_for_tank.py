import json
import re
import sys

with open('tank_db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)
with open('tank_tth.json', 'r', encoding='utf-8') as f:
    tth = json.load(f)

suffixes = ['_storymode', '_7x7', '_fallout', '_fl', '_sh', '_igr', '_bootcamp', '_training', '_test']
alias = {'A14_T30': 'A14_T30_FL', 'R122_T44_100': 'R122_T44_100B'}

def norm(s):
    return str(s).lower().replace('-', '_')

def strip_mode(s):
    b = s
    changed = True
    while changed:
        changed = False
        for suf in suffixes:
            if b.endswith(suf):
                b = b[:-len(suf)]
                changed = True
    return b

def find_tth(tag):
    v = tth.get(tag)
    if isinstance(v, dict) and v:
        return v, f'direct:{tag}'

    if tag in alias:
        a = tth.get(alias[tag])
        if isinstance(a, dict) and a:
            return a, f'alias:{alias[tag]}'

    tag_n = norm(tag)
    for k, v in tth.items():
        if isinstance(v, dict) and v and norm(k) == tag_n:
            return v, f'normalized:{k}'

    base = strip_mode(tag_n)
    if base != tag_n:
        for k, v in tth.items():
            if isinstance(v, dict) and v and norm(k) == base:
                return v, f'strip_mode:{k}'

    m = re.match(r'^([a-z]+)(\d{4})_(.+)$', base)
    if m:
        p, num, rest = m.groups()
        num = int(num)
        if num >= 1000:
            c = f'{p}{num - 1000}_{rest}'
            for k, v in tth.items():
                if isinstance(v, dict) and v and norm(k) == c:
                    return v, f'story_fix:{k}'

    suffix = base.split('_', 1)[1] if '_' in base else base
    for k, v in tth.items():
        if not (isinstance(v, dict) and v):
            continue
        kn = norm(k)
        ks = kn.split('_', 1)[1] if '_' in kn else kn
        if ks == suffix:
            return v, f'suffix:{k}'

    return {}, 'not_found'

def find_tag_by_name(q):
    qn = q.strip().casefold()
    for tag, info in db.items():
        if str(info.get('name', '')).casefold() == qn:
            return tag
    for tag, info in db.items():
        if qn in str(info.get('name', '')).casefold():
            return tag
    return None

if len(sys.argv) < 2:
    print('Usage: python check_tth_for_tank.py <tag_or_name>')
    sys.exit(1)

query = ' '.join(sys.argv[1:]).strip()
tag = query if query in db else find_tag_by_name(query)

if not tag:
    print('Tank not found in tank_db')
    sys.exit(2)

info = db.get(tag, {})
v, via = find_tth(tag)

print('tag=', tag)
print('name=', info.get('name'))
print('nation=', info.get('nation'), 'tier=', info.get('tier'), 'class=', info.get('class'))
print('tth_via=', via)
if not v:
    print('tth=NOT_FOUND')
    sys.exit(3)

print('hp=', v.get('hp'))
print('speed=', v.get('speed_fwd'), '/', v.get('speed_bwd'))
print('hull_armor=', v.get('hull_armor'))
print('turret_armor=', v.get('turret_armor'))
print('reload=', v.get('reload'))
shells = v.get('shells', [])
if isinstance(shells, list) and shells:
    s0 = shells[0] if isinstance(shells[0], dict) else {}
    print('shell0=', s0.get('type'), s0.get('damage'), s0.get('piercing'))
else:
    print('shell0=None')
