"""Surgical edits of a (system, platform-signed) APK.

* resources.arsc: append new entries (file resources) to one type of the package,
  leaving every existing resource id / value untouched.
* zip: rebuild the archive copying every untouched entry byte-for-byte (dex keeps
  its CRC, so existing oat/vdex stay valid), replace / add a few entries and put
  the ORIGINAL APK Signing Block back in front of the central directory.

Android does not verify the integrity of APKs on system partitions; it only reads
the certificates from the signing block (unsafeGetCertsWithoutVerification).  With
the original block kept, the patched APK still has the platform certificate, so
android.uid.system / sharedUserId keep working.
"""
import struct
import zlib

# ---------------------------------------------------------------- string pools

UTF8_FLAG = 0x100


def _enc_len8(n):
    return bytes([n]) if n < 0x80 else bytes([0x80 | (n >> 8), n & 0xFF])


def _enc_len16(n):
    return struct.pack("<H", n) if n < 0x8000 else struct.pack("<HH", 0x8000 | (n >> 16), n & 0xFFFF)


def pool_strings(chunk):
    """Decode all strings of a ResStringPool chunk (for lookups / verification)."""
    _, hsize, size, count, styles, flags, sstart, _ = struct.unpack_from("<HHIIIIII", chunk, 0)
    out = []
    for i in range(count):
        off = sstart + struct.unpack_from("<I", chunk, hsize + 4 * i)[0]
        if flags & UTF8_FLAG:
            n = chunk[off]
            off += 2 if n & 0x80 else 1
            b = chunk[off]
            if b & 0x80:
                b = ((b & 0x7F) << 8) | chunk[off + 1]
                off += 2
            else:
                off += 1
            out.append(chunk[off:off + b].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", chunk, off)[0]
            off += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", chunk, off)[0]
                off += 2
            out.append(chunk[off:off + 2 * n].decode("utf-16le", "replace"))
    return out


def pool_append(chunk, new_strings):
    """Return (new_chunk, first_new_index). Strings are appended at the end, so all
    existing indices (and style spans) stay valid."""
    t, hsize, size, count, styles, flags, sstart, stystart = struct.unpack_from("<HHIIIIII", chunk, 0)
    assert len(chunk) == size
    utf8 = bool(flags & UTF8_FLAG)
    offs_end = hsize + 4 * count
    style_offs = chunk[offs_end:offs_end + 4 * styles]
    data_end = stystart if styles else size
    str_data = bytearray(chunk[sstart:data_end])
    style_data = chunk[stystart:size] if styles else b""
    new_offs = b""
    for s in new_strings:
        new_offs += struct.pack("<I", len(str_data))
        if utf8:
            b = s.encode("utf-8")
            str_data += _enc_len8(len(s)) + _enc_len8(len(b)) + b + b"\0"
        else:
            str_data += _enc_len16(len(s)) + s.encode("utf-16le") + b"\0\0"
    while len(str_data) % 4:
        str_data += b"\0"
    n_count = count + len(new_strings)
    n_sstart = hsize + 4 * n_count + 4 * styles
    n_stystart = n_sstart + len(str_data) if styles else 0
    body = (chunk[hsize:offs_end] + new_offs + style_offs + bytes(str_data) + style_data)
    n_size = hsize + len(body)
    header = struct.pack("<HHIIIIII", t, hsize, n_size, n_count, styles, flags, n_sstart, n_stystart)
    header += chunk[28:hsize]
    return header + body, count


# ---------------------------------------------------------------- resources.arsc

RES_STRING_POOL = 0x0001
RES_TABLE = 0x0002
RES_TABLE_PACKAGE = 0x0200
RES_TABLE_TYPE = 0x0201
RES_TABLE_TYPE_SPEC = 0x0202
FLAG_SPARSE = 0x01
FLAG_OFFSET16 = 0x02
NO_ENTRY32 = 0xFFFFFFFF
NO_ENTRY16 = 0xFFFF


def _chunks(buf, start, end):
    off = start
    while off < end:
        t, h, s = struct.unpack_from("<HHI", buf, off)
        yield off, t, h, s
        off += s


def _is_default_config(type_chunk):
    csize = struct.unpack_from("<I", type_chunk, 20)[0]
    return not any(type_chunk[24:20 + csize])


def _grow_type(chunk, new_entries):
    """Append entries (list of (key_index, value_string_index)) to a default-config
    ResTable_type chunk.  Returns new chunk and the first new entry index."""
    t, hsize, size = struct.unpack_from("<HHI", chunk, 0)
    tid, flags = chunk[8], chunk[9]
    count, estart = struct.unpack_from("<II", chunk, 12)
    if flags & FLAG_SPARSE:
        raise ValueError("sparse default type not supported")
    wide = 2 if flags & FLAG_OFFSET16 else 4
    offsets = chunk[hsize:hsize + wide * count]
    entries = bytearray(chunk[estart:size])
    new_offs = b""
    for key, sidx in new_entries:
        pos = len(entries)
        if wide == 2:
            assert pos % 4 == 0 and pos // 4 < NO_ENTRY16
            new_offs += struct.pack("<H", pos // 4)
        else:
            new_offs += struct.pack("<I", pos)
        # ResTable_entry {u16 size=8, u16 flags=0, u32 key} + Res_value {u16 8, u8 0, u8 TYPE_STRING=3, u32}
        entries += struct.pack("<HHI", 8, 0, key) + struct.pack("<HBBI", 8, 0, 0x03, sidx)
    offs = bytearray(offsets + new_offs)
    while (hsize + len(offs)) % 4:
        offs += b"\0"
    n_count = count + len(new_entries)
    n_estart = hsize + len(offs)
    n_size = n_estart + len(entries)
    head = bytearray(chunk[:hsize])
    struct.pack_into("<I", head, 4, n_size)
    struct.pack_into("<II", head, 12, n_count, n_estart)
    return bytes(head) + bytes(offs) + bytes(entries), count


def arsc_add_files(arsc, type_name, files):
    """Add file resources.  files: list of (entry_name, path_in_apk).
    Returns (new_arsc, {entry_name: resource_id})."""
    t, hsize, size, npkg = struct.unpack_from("<HHII", arsc, 0)
    assert t == RES_TABLE and npkg == 1 and size == len(arsc)
    pieces = [arsc[:hsize]]
    gpool_new, gfirst = None, None
    pkg_new, ids = None, {}
    for off, ct, ch, cs in _chunks(arsc, hsize, size):
        chunk = arsc[off:off + cs]
        if ct == RES_STRING_POOL and gpool_new is None:
            gpool_new, gfirst = pool_append(chunk, [p for _, p in files])
            pieces.append(gpool_new)
        elif ct == RES_TABLE_PACKAGE:
            pkg_new, ids = _patch_package(chunk, type_name, files, gfirst)
            pieces.append(pkg_new)
        else:
            pieces.append(chunk)
    out = bytearray(b"".join(pieces))
    struct.pack_into("<I", out, 4, len(out))
    return bytes(out), ids


def _patch_package(pkg, type_name, files, gfirst):
    t, hsize, size, pid = struct.unpack_from("<HHII", pkg, 0)
    type_strings_off, _, key_strings_off = struct.unpack_from("<III", pkg, 268)
    tpool = pkg[type_strings_off:type_strings_off + struct.unpack_from("<I", pkg, type_strings_off + 4)[0]]
    type_id = pool_strings(tpool).index(type_name) + 1
    ksize = struct.unpack_from("<I", pkg, key_strings_off + 4)[0]
    kpool_new, kfirst = pool_append(pkg[key_strings_off:key_strings_off + ksize], [n for n, _ in files])
    out = [pkg[:hsize]]
    spec_done = type_done = False
    first_entry = None
    for off, ct, ch, cs in _chunks(pkg, hsize, size):
        chunk = pkg[off:off + cs]
        if off == key_strings_off:
            chunk = kpool_new
        elif ct == RES_TABLE_TYPE_SPEC and chunk[8] == type_id:
            count = struct.unpack_from("<I", chunk, 12)[0]
            chunk = bytearray(chunk + b"\0\0\0\0" * len(files))
            struct.pack_into("<I", chunk, 4, len(chunk))
            struct.pack_into("<I", chunk, 12, count + len(files))
            chunk = bytes(chunk)
            first_entry = count
            spec_done = True
        elif ct == RES_TABLE_TYPE and chunk[8] == type_id and _is_default_config(chunk) and not type_done:
            entries = [(kfirst + i, gfirst + i) for i in range(len(files))]
            chunk, first = _grow_type(chunk, entries)
            if first != first_entry:
                raise ValueError(f"default type has {first} entries, spec has {first_entry}")
            type_done = True
        out.append(chunk)
    if not (spec_done and type_done):
        raise ValueError("type spec / default type chunk not found")
    out = bytearray(b"".join(out))
    struct.pack_into("<I", out, 4, len(out))
    ids = {n: (pid << 24) | (type_id << 16) | (first_entry + i) for i, (n, _) in enumerate(files)}
    return bytes(out), ids


# ---------------------------------------------------------------- binary XML

def xml_retarget_refs(data, mapping):
    """Replace attribute reference values (TYPE_REFERENCE) using mapping {old_id: new_id}."""
    data = bytearray(data)
    t, hsize, total = struct.unpack_from("<HHI", data, 0)
    assert t == 0x0003
    off, n = hsize, 0
    while off < total:
        ct, ch, cs = struct.unpack_from("<HHI", data, off)
        if ct == 0x0102:
            ext = off + ch
            astart, asize, acount = struct.unpack_from("<HHH", data, ext + 8)
            for i in range(acount):
                a = ext + astart + i * asize
                val = struct.unpack_from("<I", data, a + 16)[0]
                if data[a + 15] in (0x01, 0x07) and val in mapping:
                    data[a + 15] = 0x01
                    struct.pack_into("<I", data, a + 16, mapping[val])
                    n += 1
        off += cs
    return bytes(data), n


# ---------------------------------------------------------------- zip

EOCD_SIG = 0x06054B50
CD_SIG = 0x02014B50
LFH_SIG = 0x04034B50
SIG_BLOCK_MAGIC = b"APK Sig Block 42"


def _eocd(buf):
    i = buf.rfind(struct.pack("<I", EOCD_SIG), max(0, len(buf) - 65557))
    if i < 0:
        raise ValueError("EOCD not found")
    return i


def read_central_dir(buf):
    e = _eocd(buf)
    _, _, _, _, total, cd_size, cd_off, _ = struct.unpack_from("<IHHHHIIH", buf, e)
    entries, p = [], cd_off
    for _ in range(total):
        (sig, vmade, vneed, flag, method, mtime, mdate, crc, csize, usize, nlen, xlen, clen,
         disk, iattr, eattr, lho) = struct.unpack_from("<IHHHHHHIIIHHHHHII", buf, p)
        assert sig == CD_SIG
        name = buf[p + 46:p + 46 + nlen]
        entries.append(dict(vmade=vmade, vneed=vneed, flag=flag, method=method, mtime=mtime,
                            mdate=mdate, crc=crc, csize=csize, usize=usize, name=name,
                            iattr=iattr, eattr=eattr, lho=lho))
        p += 46 + nlen + xlen + clen
    return entries, cd_off, e


def signing_block(buf):
    _, cd_off, _ = read_central_dir(buf)
    if buf[cd_off - 16:cd_off] != SIG_BLOCK_MAGIC:
        return b""
    size = struct.unpack_from("<Q", buf, cd_off - 24)[0]
    start = cd_off - size - 8
    assert struct.unpack_from("<Q", buf, start)[0] == size
    return buf[start:cd_off]


def _raw_data(buf, ent):
    p = ent["lho"]
    sig, _, _, _, _, _, _, _, _, nlen, xlen = struct.unpack_from("<IHHHHHIIIHH", buf, p)
    assert sig == LFH_SIG
    start = p + 30 + nlen + xlen
    return buf[start:start + ent["csize"]]


def rebuild_zip(src, replace, add, align=4, so_align=16384):
    """replace: {name: bytes} (uncompressed content; stored/deflated like the original)
    add: list of (name, bytes) appended (deflated).  Everything else is copied raw.
    The original APK signing block is re-inserted before the central directory."""
    entries, _, _ = read_central_dir(src)
    block = signing_block(src)
    out = bytearray()
    cd = bytearray()

    def emit(ent, data):
        name = ent["name"]
        stored = ent["method"] == 0
        base = len(out) + 30 + len(name)
        a = so_align if name.endswith(b".so") else align
        pad = (-base) % a if stored else 0
        flag = ent["flag"] & ~0x0008  # sizes are written in the local header
        lho = len(out)
        out.extend(struct.pack("<IHHHHHIIIHH", LFH_SIG, ent["vneed"], flag, ent["method"],
                               ent["mtime"], ent["mdate"], ent["crc"], ent["csize"], ent["usize"],
                               len(name), pad))
        out.extend(name + b"\0" * pad + data)
        cd.extend(struct.pack("<IHHHHHHIIIHHHHHII", CD_SIG, ent["vmade"], ent["vneed"], flag,
                              ent["method"], ent["mtime"], ent["mdate"], ent["crc"], ent["csize"],
                              ent["usize"], len(name), 0, 0, 0, ent["iattr"], ent["eattr"], lho))
        cd.extend(name)

    def packed(ent, content):
        ent = dict(ent)
        ent["crc"] = zlib.crc32(content) & 0xFFFFFFFF
        ent["usize"] = len(content)
        if ent["method"] == 0:
            data = content
        else:
            ent["method"] = 8
            co = zlib.compressobj(9, zlib.DEFLATED, -15)
            data = co.compress(content) + co.flush()
        ent["csize"] = len(data)
        return ent, data

    for ent in entries:
        name = ent["name"].decode("utf-8")
        if name in replace:
            emit(*packed(ent, replace[name]))
        else:
            emit(ent, _raw_data(src, ent))
    tmpl = dict(entries[-1])
    for name, content in add:
        ent = dict(tmpl, name=name.encode(), method=8, flag=0, iattr=0, eattr=0)
        emit(*packed(ent, content))

    if block:
        out.extend(block)
    cd_off = len(out)
    n = len(entries) + len(add)
    out.extend(cd)
    out.extend(struct.pack("<IHHHHIIH", EOCD_SIG, 0, 0, n, n, len(cd), cd_off, 0))
    return bytes(out)
