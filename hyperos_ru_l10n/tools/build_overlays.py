#!/usr/bin/env python3
"""Build static RRO overlays with Russian (values-ru*) strings for HyperOS CN apps.

usage: build_overlays.py EXTRACTED_ROM TRANSLATION_MAIN MAP ROM_PKGS OUT_DIR WORK_DIR
"""
import sys, os, re, glob, shutil, struct, subprocess, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arsc

EX, TR, MAP, PKGS, OUT, WORK = sys.argv[1:7]
ANDROID_JAR = '/usr/lib/android-sdk/platforms/android-23/android.jar'
ATTR_PLACEHOLDER, ATTR_ISSTATIC = 0x0101016b, 0x0101055a  # android:editable -> android:isStatic
PRIORITY = 950

SPEC = re.compile(r'%(\d+\$)?([-#+ 0,(<]*)(\d+)?(\.\d+)?([tT]?[a-zA-Z%])')
CLS = {'s': 's', 'S': 's', 'b': 'b', 'B': 'b', 'h': 's', 'H': 's',
       'd': 'i', 'o': 'i', 'x': 'i', 'X': 'i', 'c': 'c', 'C': 'c',
       'e': 'f', 'E': 'f', 'f': 'f', 'g': 'f', 'G': 'f', 'a': 'f', 'A': 'f'}


def plain(raw):
    """Approximate the runtime text of an XML resource body."""
    t = re.sub(r'<[^>]+>', '', raw)
    t = t.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"').replace('&apos;', "'")
    return t


def specs(text):
    """Return set of (arg index, class) or None if the text contains a malformed '%'."""
    if text is None:
        return set()
    out, seq, bad = set(), 0, False
    stripped = SPEC.sub('', text)
    if '%' in stripped:
        bad = True
    for m in SPEC.finditer(text):
        conv = m.group(5)
        if conv in ('%', 'n'):
            continue
        if conv[0] in 'tT':
            cls = 't'
        else:
            cls = CLS.get(conv)
            if cls is None:
                bad = True
                continue
        if m.group(1):
            idx = int(m.group(1)[:-1])
        elif m.group(2) and '<' in m.group(2):
            idx = seq
        else:
            seq += 1
            idx = seq
        out.add((idx, cls))
    return None if bad else out


def compatible(ru_text, default_texts):
    """True if formatting the translation with the default's arguments can't throw."""
    d = set()
    dbad = False
    for t in default_texts:
        s = specs(t)
        if s is None:
            dbad = True
        else:
            d |= s
    r = specs(ru_text)
    if r is None:
        # stray '%' in translation: only safe when the original is never formatted
        return not d and not dbad
    for idx, cls in r:
        ok = any(i == idx and (c == cls or cls in ('s', 'b')) for i, c in d)
        if not ok:
            return False
    return True


ELEM = re.compile(r'<(string|plurals|string-array|array|integer-array)\b([^>]*?)(/>|>(.*?)</\1\s*>)', re.S)
ITEM = re.compile(r'<item\b([^>]*?)(?:/>|>(.*?)</item\s*>)', re.S)
QTY = {'zero': 0x01000005, 'one': 0x01000006, 'two': 0x01000007, 'few': 0x01000008, 'many': 0x01000009, 'other': 0x01000004}


def is_ref(body):
    b = plain(body).strip()
    return (b.startswith('@') or b.startswith('?')) and not b.startswith('@android:') and not b.startswith('?android:')


def fix_apostrophes(body):
    """aapt v1 rejects bare apostrophes; quote tag attributes with " and escape the rest."""
    if body.lstrip().startswith('"') and body.rstrip().endswith('"'):
        return body
    parts = re.split(r'(<[^>]+>)', body)
    out = []
    for p in parts:
        if p.startswith('<'):
            out.append(re.sub(r"=\s*'([^']*)'", lambda m: '="%s"' % m.group(1).replace('"', '&quot;'), p))
        else:
            out.append(re.sub(r"(?<!\\)'", r"\\'", p))
    return ''.join(out)


def filter_file(path, kind, defaults, vals, stats, seen):
    txt = open(path, encoding='utf-8').read()
    kept = []
    for m in ELEM.finditer(txt):
        tag, attrs, body = m.group(1), m.group(2), m.group(4)
        nm = re.search(r'\bname\s*=\s*"([^"]+)"', attrs)
        if not nm or body is None or 'translatable="false"' in attrs:
            continue
        name = nm.group(1)
        typ = {'string': 'string', 'plurals': 'plurals', 'string-array': 'array', 'array': 'array'}.get(tag)
        if typ is None:
            continue
        if name not in defaults.get(typ, ()):
            stats['unknown'] += 1
            continue
        dv = vals.get(typ, {}).get(name)
        ok = True
        if typ == 'string':
            if is_ref(body):
                ok = False
            elif dv and dv[0][1] is not None and not compatible(plain(body), [dv[0][1]]):
                ok = False
        else:
            items = ITEM.findall(body)
            if not items or any(b is None or is_ref(b) for _, b in items):
                ok = False
            elif typ == 'array':
                if dv is None or len(dv) != len(items):
                    ok = False
                else:
                    for (a, b), (_, dt) in zip(items, dv):
                        if dt is not None and not compatible(plain(b), [dt]):
                            ok = False
                            break
            else:  # plurals
                dts = [t for _, t in (dv or []) if t is not None]
                for a, b in items:
                    q = re.search(r'quantity\s*=\s*"(\w+)"', a)
                    if not q or q.group(1) not in QTY or not compatible(plain(b), dts):
                        ok = False
                        break
        if ok and (typ, name) in seen:
            stats['dup'] = stats.get('dup', 0) + 1
            continue
        if ok:
            seen.add((typ, name))
            whole = m.group(0)
            start = whole.find('>') + 1 if not whole.startswith('<string') else whole.find('>') + 1
            if typ == 'string':
                kept.append(whole[:start] + fix_apostrophes(body) + whole[start + len(body):])
            else:
                kept.append(ITEM.sub(lambda im: im.group(0) if im.group(2) is None else
                                     im.group(0).replace(im.group(2), fix_apostrophes(im.group(2)), 1), whole))
            stats['kept'] += 1
        else:
            stats['unsafe'] += 1
    return kept


def patch_manifest(apk):
    """Rename the placeholder android:exported attribute to android:isStatic in the binary manifest."""
    import zipfile
    zin = zipfile.ZipFile(apk)
    items = [(i, zin.read(i.filename)) for i in zin.infolist()]
    zin.close()
    out = []
    for info, data in items:
        if info.filename == 'AndroidManifest.xml':
            data = bytearray(data)
            u16 = 'editable'.encode('utf-16le')
            n = data.count(u16)
            assert n == 1, n
            data[data.find(u16):data.find(u16) + len(u16)] = 'isStatic'.encode('utf-16le')
            # resource map chunk (type 0x0180)
            off = 8
            done = False
            while off < len(data):
                t, h, sz = struct.unpack_from('<HHI', data, off)
                if t == 0x0180:
                    for i in range((sz - h) // 4):
                        if struct.unpack_from('<I', data, off + h + 4 * i)[0] == ATTR_PLACEHOLDER:
                            struct.pack_into('<I', data, off + h + 4 * i, ATTR_ISSTATIC)
                            done = True
                off += sz
            assert done
            data = bytes(data)
        out.append((info, data))
    zout = zipfile.ZipFile(apk, 'w')
    for info, data in out:
        zout.writestr(info, data)
    zout.close()


MANIFEST = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{opkg}" android:versionCode="{ver}" android:versionName="{vername}">
  <uses-sdk android:minSdkVersion="28" android:targetSdkVersion="28"/>
  <overlay android:targetPackage="{target}" android:editable="true" android:priority="{prio}"/>
  <application android:hasCode="false" android:label="{label}"/>
</manifest>
'''


def main():
    ver = int(os.environ.get('OVL_VERSION', '1'))
    vername = os.environ.get('OVL_VERSION_NAME', '1.0')
    keystore = os.path.join(WORK, 'l10n.jks')
    if not os.path.exists(keystore):
        subprocess.run(['keytool', '-genkeypair', '-keystore', keystore, '-storepass', 'android', '-keypass', 'android',
                        '-alias', 'l10n', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000',
                        '-dname', 'CN=HyperOS RU l10n'], check=True, capture_output=True)
    rom = {}
    for l in open(PKGS):
        p = l.split()
        if len(p) == 2 and p[0] != 'ERR':
            rom.setdefault(p[0], []).append(os.path.join(EX, p[1]))
    os.makedirs(OUT, exist_ok=True)
    report = []
    for l in open(MAP):
        if not l.strip() or l.startswith('#'):
            continue
        folder, target = l.split()
        if target not in rom:
            report.append((folder, target, 'not in ROM'))
            continue
        apk = [a for a in rom[target] if not re.search(r'-(x+h|h|m|l|tv)dpi\.apk$|arm64|xxhdpi', a)][0]
        names, vals = arsc.apk(apk, values=True)
        if len(names) != 1:
            report.append((folder, target, 'unexpected arsc packages %s' % list(names)))
            continue
        rpkg = list(names)[0]
        defaults = {t: names[rpkg].get(t, {}).get('default', set()) for t in ('string', 'array', 'plurals')}
        v = vals.get(rpkg, {})
        stats = {'kept': 0, 'unsafe': 0, 'unknown': 0}
        work = os.path.join(WORK, folder)
        shutil.rmtree(work, ignore_errors=True)
        for d in sorted(glob.glob(os.path.join(TR, folder, 'res', 'values-ru*'))):
            q = os.path.basename(d)
            seen = set()
            for f in sorted(glob.glob(os.path.join(d, '*.xml'))):
                kept = filter_file(f, None, defaults, v, stats, seen)
                if kept:
                    os.makedirs(os.path.join(work, 'res', q), exist_ok=True)
                    with open(os.path.join(work, 'res', q, os.path.basename(f)), 'w', encoding='utf-8') as fo:
                        fo.write('<?xml version="1.0" encoding="utf-8"?>\n'
                                 '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\n')
                        fo.write('\n'.join(kept))
                        fo.write('\n</resources>\n')
        if not stats['kept']:
            report.append((folder, target, 'nothing to add', stats))
            continue
        opkg = 'ru.hyperos.l10n.' + re.sub(r'[^A-Za-z0-9_.]', '_', target)
        with open(os.path.join(work, 'AndroidManifest.xml'), 'w') as fo:
            fo.write(MANIFEST.format(opkg=opkg, target=target, prio=PRIORITY, ver=ver, vername=vername,
                                     label='Russian l10n: ' + folder))
        unsigned = os.path.join(work, 'unsigned.apk')
        r = subprocess.run(['aapt', 'package', '-f', '-M', os.path.join(work, 'AndroidManifest.xml'),
                            '-S', os.path.join(work, 'res'), '-I', ANDROID_JAR, '-F', unsigned],
                           capture_output=True, text=True)
        if r.returncode:
            report.append((folder, target, 'aapt failed', r.stderr[-2000:]))
            continue
        patch_manifest(unsigned)
        aligned = os.path.join(work, 'aligned.apk')
        subprocess.run(['zipalign', '-f', '-p', '4', unsigned, aligned], check=True)
        final = os.path.join(OUT, 'RuL10n_%s.apk' % folder.replace('.apk', ''))
        subprocess.run(['apksigner', 'sign', '--ks', keystore, '--ks-pass', 'pass:android', '--key-pass', 'pass:android',
                        '--ks-key-alias', 'l10n', '--min-sdk-version', '28', '--out', final, aligned], check=True)
        report.append((folder, target, 'ok', stats))
    json.dump(report, open(os.path.join(WORK, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    for r in report:
        print(*r)


main()
