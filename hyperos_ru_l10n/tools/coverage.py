import sys, re, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arsc
EX, TR, MAP, PKGS = sys.argv[1:5]
rom = {}
for l in open(PKGS):
    p = l.split()
    if len(p) == 2 and p[0] != 'ERR': rom.setdefault(p[0], []).append(os.path.join(EX, p[1]))
tot = [0, 0]
for l in open(MAP):
    folder, pkg = l.split()
    if pkg not in rom: print('%-28s %-34s NOT IN ROM' % (folder, pkg)); continue
    apk = [a for a in rom[pkg] if not re.search(r'-(x+h|h|m|l|tv)dpi\.apk$|arm64|xxhdpi', a)][0]
    try: r = arsc.apk(apk).get(pkg, {})
    except KeyError: print('%-28s no arsc' % folder); continue
    d = set(r.get('string', {}).get('default', ()))
    has_ru = any(k.startswith('ru') for k in r.get('string', {}))
    ru = set()
    for f in glob.glob(os.path.join(TR, folder, 'res', 'values-ru*', 'strings.xml')):
        ru |= set(re.findall(r'<string\s+name="([^"]+)"', open(f, encoding='utf-8').read()))
    rr = set().union(*[v for k, v in r.get('string', {}).items() if k.startswith('ru')]) if has_ru else set()
    c = len(d & ru); u = len(d & (ru | rr)); tot[0] += len(d); tot[1] += u
    print('%-28s %-30s rom=%5d romru=%5d +tr=%5d  before=%3d%% after=%3d%%' % (folder, pkg, len(d), len(d & rr), len(d & ru - rr), 100*len(d&rr)//max(1,len(d)), 100*u//max(1,len(d))))
print('TOTAL', tot, 100*tot[1]//tot[0])
