import struct, sys
def u16(d,o): return struct.unpack_from("<H",d,o)[0]
def u32(d,o): return struct.unpack_from("<I",d,o)[0]

def read_strpool(b, off):
    # ResStringPool at b[off:], вернуть список строк (UTF-8)
    scount=u32(b,off+8); flags=u32(b,off+16); strStart=u32(b,off+20)
    utf8 = bool(flags & 0x100)
    strs=[]
    base=off+strStart
    for i in range(scount):
        so=base+u32(b,off+28+i*4)
        if utf8:
            # две длины (u8/u16) для n16 и n8
            p=so
            def declen(p):
                n=b[p]
                if n&0x80: n=((n&0x7f)<<8)|b[p+1]; p2=p+2
                else: p2=p+1
                return n,p2
            n16,p=declen(so)
            n8,p=declen(p)
            strs.append(b[p:p+n8].decode("utf-8","replace"))
        else:
            n=u16(b,so)
            if n&0x8000: n=((n&0x7fff)<<16)|u16(b,so+2); p=so+4
            else: p=so+2
            strs.append(b[p:p+n*2].decode("utf-16-le","replace"))
    return strs

def desparse_type(b):
    hsize=u16(b,2); size=u32(b,4); flags=b[9]
    if not (flags & 0x03): return b
    entryCount=u32(b,12); entriesStart=u32(b,16)
    entrydata=b[entriesStart:size]
    if flags&0x01:
        pairs=[(u16(b,hsize+i*4), u16(b,hsize+i*4+2)*4) for i in range(entryCount)]
        newCount=(max(k for k,_ in pairs)+1) if pairs else 0
        off=[0xffffffff]*newCount
        for k,v in pairs: off[k]=v
    else:
        newCount=entryCount
        off=[(0xffffffff if u16(b,hsize+i*2)==0xffff else u16(b,hsize+i*2)*4) for i in range(entryCount)]
    new_es=hsize+newCount*4
    nb=bytearray(b[:hsize]); nb[9]=flags & ~0x03
    struct.pack_into("<I",nb,12,newCount); struct.pack_into("<I",nb,16,new_es)
    for o in off: nb+=struct.pack("<I",o)
    nb+=entrydata; struct.pack_into("<I",nb,4,len(nb))
    return bytes(nb)

TARGET=None  # type id to desparse
def rewrite(b):
    typ=u16(b,0); hsize=u16(b,2); size=u32(b,4)
    if typ==0x0201:
        return desparse_type(b) if b[8]==TARGET else b
    if typ in (0x0002,0x0200):
        out=bytearray(b[:hsize]); o=hsize
        while o<size:
            cs=u32(b,o+4); out+=rewrite(b[o:o+cs]); o+=cs
        struct.pack_into("<I",out,4,len(out)); return bytes(out)
    return b

src=open(sys.argv[1],"rb").read()
# найти package -> type string pool -> индекс 'drawable'
# table(0x0002): header hsize, затем global strpool, затем package(0x0200)
to=u16(src,2)  # table hsize
o=to
pkg=None
while o<len(src):
    t=u16(src,o); sz=u32(src,o+4)
    if t==0x0200: pkg=o; break
    o+=sz
tstr_off=pkg+u32(src,pkg+8+4+256)   # package: header(8)+id(4)+name(256)+typeStrings(4)
types=read_strpool(src, tstr_off)
did=types.index("drawable")+1
print("drawable type id =", did, "(индекс", did-1, ")")
TARGET=did
out=rewrite(src)
open(sys.argv[2],"wb").write(out)
print(f"desparsed только drawable; size {len(src)} -> {len(out)} (+{len(out)-len(src)} байт)")
