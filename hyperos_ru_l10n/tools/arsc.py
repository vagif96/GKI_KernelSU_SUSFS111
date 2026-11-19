"""Minimal resources.arsc parser: returns {pkg: {type: {config_str: set(names)}}}"""
import struct, zipfile, sys, json

def read_pool(b, off):
    typ, hsz, size = struct.unpack_from('<HHI', b, off)
    count, scount, flags, sstart, stylestart = struct.unpack_from('<IIIII', b, off+8)
    utf8 = flags & 0x100
    offs = struct.unpack_from('<%dI' % count, b, off+hsz)
    res = []
    base = off + sstart
    for o in offs:
        p = base + o
        if utf8:
            n = b[p]; p += 1
            if n & 0x80: p += 1
            n = b[p]; p += 1
            if n & 0x80: n = ((n & 0x7f) << 8) | b[p]; p += 1
            res.append(b[p:p+n].decode('utf-8', 'replace'))
        else:
            n = struct.unpack_from('<H', b, p)[0]; p += 2
            if n & 0x8000: n = ((n & 0x7fff) << 16) | struct.unpack_from('<H', b, p)[0]; p += 2
            res.append(b[p:p+2*n].decode('utf-16le', 'replace'))
    return res

def cfg_str(b, off):
    size = struct.unpack_from('<I', b, off)[0]
    lang = b[off+8:off+10]; country = b[off+10:off+12]
    s = []
    def dec(x):
        if x == b'\0\0': return ''
        if x[0] & 0x80:
            v = (x[1] << 8) | x[0]
            return ''.join(chr(0x61 + ((v >> sh) & 0x1f)) for sh in (0, 5, 10))
        return x.decode('latin1')
    l = dec(lang); c = dec(country)
    if l: s.append(l)
    if c: s.append('r' + c)
    rest = b[off+4:off+size]
    other = any(rest[8:]) or any(rest[:4])  # anything besides lang/country
    return '-'.join(s) if s else 'default', other

def parse(data, values=False):
    out = {}
    vals = {}
    typ, hsz, size, pcount = struct.unpack_from('<HHII', data, 0)
    off = hsz
    gpool = None
    while off < len(data):
        t, h, sz = struct.unpack_from('<HHI', data, off)
        if t == 0x0001 and gpool is None and values:
            gpool = read_pool(data, off)
        if t == 0x0200:
            pid = struct.unpack_from('<I', data, off+8)[0]
            name = data[off+12:off+12+256].decode('utf-16le').split('\0')[0]
            typeStrings, lastPublicType, keyStrings = struct.unpack_from('<III', data, off+268)
            types = read_pool(data, off+typeStrings)
            keys = read_pool(data, off+keyStrings)
            pk = out.setdefault(name, {})
            p = off + h
            while p < off + sz:
                ct, chs, csz = struct.unpack_from('<HHI', data, p)
                if ct == 0x0201:
                    tid, flags, _, count, estart = struct.unpack_from('<BBHII', data, p+8)
                    tname = types[tid-1]
                    cfg, other = cfg_str(data, p+20)
                    if not other:
                        names = pk.setdefault(tname, {}).setdefault(cfg, set())
                        ib = p + chs
                        sparse = flags & 1; off16 = flags & 2
                        entries = []
                        for i in range(count):
                            if sparse:
                                idx, o16 = struct.unpack_from('<HH', data, ib + 4*i); eo = o16*4
                            elif off16:
                                o16 = struct.unpack_from('<H', data, ib + 2*i)[0]
                                if o16 == 0xffff: continue
                                eo = o16*4
                            else:
                                eo = struct.unpack_from('<I', data, ib + 4*i)[0]
                                if eo == 0xffffffff: continue
                            e = p + estart + eo
                            esz, eflags = struct.unpack_from('<HH', data, e)
                            if eflags & 0x8:  # compact
                                key = esz
                                vt = eflags >> 8; vd = struct.unpack_from('<I', data, e+4)[0]
                                items = [(None, vt, vd)]
                            else:
                                key = struct.unpack_from('<I', data, e+4)[0]
                                if eflags & 0x1:  # complex/bag
                                    cnt = struct.unpack_from('<I', data, e+12)[0]
                                    items = []
                                    for j in range(cnt):
                                        nm, vs, _, vt, vd = struct.unpack_from('<IHBBI', data, e+16+12*j)
                                        items.append((nm, vt, vd))
                                else:
                                    vs, _, vt, vd = struct.unpack_from('<HBBI', data, e+esz)
                                    items = [(None, vt, vd)]
                            names.add(keys[key])
                            if values and cfg == 'default' and tname in ('string', 'array', 'plurals'):
                                vals.setdefault(name, {}).setdefault(tname, {})[keys[key]] = [
                                    (nm, gpool[vd] if vt == 3 and gpool and vd < len(gpool) else None) for nm, vt, vd in items]
                p += csz
        off += sz
    return (out, vals) if values else out

def apk(path, values=False):
    return parse(zipfile.ZipFile(path).read('resources.arsc'), values)

if __name__ == '__main__':
    r = apk(sys.argv[1])
    for pkg, ts in r.items():
        for t in ('string', 'array', 'plurals'):
            cf = ts.get(t, {})
            print(pkg, t, 'default=%d' % len(cf.get('default', ())), 'locales=' + ','.join(sorted(k for k in cf if k != 'default')))
