// ryu_patch: adds icons to Settings -> "Additional settings" (xml/other_personal_settings)
// of the Settings.apk installed on the phone.
//
//	ryu_patch <Settings.apk> <out.apk> <icons dir>
//
// <icons dir> holds precompiled vector drawables (binary XML, firmware independent)
// and map.txt: "<preference key> <drawable file> [existing drawable name]"; key "*"
// is the fallback icon for entries without their own one.
//
// What is changed (everything else is copied byte-for-byte, dex included):
//   - resources.arsc: new drawable entries appended (no existing id or value changes);
//   - the screen XML: android:icon + miuisettings:showIcon="true" on every entry;
//   - the new drawables are added as zip entries.
//
// The original APK signing block is kept in front of the central directory.
//
// Exit codes: 0 ok, 1 error, 3 the APK is already patched.
package main

import (
	"bufio"
	"bytes"
	"compress/flate"
	"encoding/binary"
	"errors"
	"fmt"
	"hash/crc32"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

var le = binary.LittleEndian

const (
	screenName   = "other_personal_settings"
	entryPrefix  = "ryu_icon_"
	androidNS    = "http://schemas.android.com/apk/res/android"
	miuiNS       = "http://schemas.android.com/apk/miuisettings"
	attrIcon     = 0x01010002
	attrKey      = 0x010101e8
	typeRef      = 0x01
	typeString   = 0x03
	typeBool     = 0x12
	errAlready   = 3
	utf8Flag     = 0x100
	sortedFlag   = 0x1
	flagSparse   = 0x01
	flagOffset16 = 0x02
	flagComplex  = 0x0001
	flagCompact  = 0x0008
)

func fail(f string, a ...any) {
	fmt.Fprintf(os.Stderr, "ERROR: "+f+"\n", a...)
	os.Exit(1)
}

// ------------------------------------------------------------------ string pool

type pool struct {
	raw   []byte
	utf8  bool
	count int
	strs  []string
}

func parsePool(c []byte) (*pool, error) {
	if len(c) < 28 || le.Uint16(c) != 0x0001 {
		return nil, errors.New("not a string pool")
	}
	hsize := int(le.Uint16(c[2:]))
	size := int(le.Uint32(c[4:]))
	if size > len(c) {
		return nil, errors.New("string pool truncated")
	}
	c = c[:size]
	count := int(le.Uint32(c[8:]))
	flags := le.Uint32(c[16:])
	sstart := int(le.Uint32(c[20:]))
	p := &pool{raw: c, utf8: flags&utf8Flag != 0, count: count}
	for i := 0; i < count; i++ {
		off := sstart + int(le.Uint32(c[hsize+4*i:]))
		if off >= len(c) {
			return nil, errors.New("bad string offset")
		}
		if p.utf8 {
			if c[off]&0x80 != 0 {
				off += 2
			} else {
				off++
			}
			n := int(c[off])
			if n&0x80 != 0 {
				n = (n&0x7f)<<8 | int(c[off+1])
				off += 2
			} else {
				off++
			}
			p.strs = append(p.strs, string(c[off:off+n]))
		} else {
			n := int(le.Uint16(c[off:]))
			off += 2
			if n&0x8000 != 0 {
				n = (n&0x7fff)<<16 | int(le.Uint16(c[off:]))
				off += 2
			}
			u := make([]rune, n)
			for j := 0; j < n; j++ {
				u[j] = rune(le.Uint16(c[off+2*j:]))
			}
			p.strs = append(p.strs, decodeUTF16(u))
		}
	}
	return p, nil
}

func decodeUTF16(u []rune) string {
	var b strings.Builder
	for i := 0; i < len(u); i++ {
		r := u[i]
		if r >= 0xd800 && r < 0xdc00 && i+1 < len(u) && u[i+1] >= 0xdc00 && u[i+1] < 0xe000 {
			r = (r-0xd800)<<10 + (u[i+1] - 0xdc00) + 0x10000
			i++
		}
		b.WriteRune(r)
	}
	return b.String()
}

func (p *pool) index(s string) int {
	for i, v := range p.strs {
		if v == s {
			return i
		}
	}
	return -1
}

func encLen8(n int) []byte {
	if n < 0x80 {
		return []byte{byte(n)}
	}
	return []byte{byte(0x80 | n>>8), byte(n)}
}

func encLen16(n int) []byte {
	if n < 0x8000 {
		return le.AppendUint16(nil, uint16(n))
	}
	b := le.AppendUint16(nil, uint16(0x8000|n>>16))
	return le.AppendUint16(b, uint16(n))
}

// appendStrings returns a new pool chunk with ss appended (existing indices and
// style spans stay valid) and the index of the first new string.
func appendStrings(c []byte, ss []string) ([]byte, int) {
	hsize := int(le.Uint16(c[2:]))
	size := int(le.Uint32(c[4:]))
	count := int(le.Uint32(c[8:]))
	styles := int(le.Uint32(c[12:]))
	flags := le.Uint32(c[16:])
	sstart := int(le.Uint32(c[20:]))
	stystart := int(le.Uint32(c[24:]))
	offsEnd := hsize + 4*count
	styleOffs := c[offsEnd : offsEnd+4*styles]
	dataEnd := size
	if styles > 0 {
		dataEnd = stystart
	}
	data := append([]byte(nil), c[sstart:dataEnd]...)
	var styleData []byte
	if styles > 0 {
		styleData = c[stystart:size]
	}
	var newOffs []byte
	for _, s := range ss {
		newOffs = le.AppendUint32(newOffs, uint32(len(data)))
		if flags&utf8Flag != 0 {
			u16 := len(utf16Units(s))
			data = append(data, encLen8(u16)...)
			data = append(data, encLen8(len(s))...)
			data = append(data, s...)
			data = append(data, 0)
		} else {
			u := utf16Units(s)
			data = append(data, encLen16(len(u))...)
			for _, x := range u {
				data = le.AppendUint16(data, x)
			}
			data = append(data, 0, 0)
		}
	}
	for len(data)%4 != 0 {
		data = append(data, 0)
	}
	nCount := count + len(ss)
	nSstart := hsize + 4*nCount + 4*styles
	nStystart := 0
	if styles > 0 {
		nStystart = nSstart + len(data)
	}
	var body []byte
	body = append(body, c[hsize:offsEnd]...)
	body = append(body, newOffs...)
	body = append(body, styleOffs...)
	body = append(body, data...)
	body = append(body, styleData...)
	head := append([]byte(nil), c[:hsize]...)
	le.PutUint32(head[4:], uint32(hsize+len(body)))
	le.PutUint32(head[8:], uint32(nCount))
	le.PutUint32(head[16:], flags&^sortedFlag)
	le.PutUint32(head[20:], uint32(nSstart))
	le.PutUint32(head[24:], uint32(nStystart))
	return append(head, body...), count
}

func utf16Units(s string) []uint16 {
	var u []uint16
	for _, r := range s {
		if r >= 0x10000 {
			r -= 0x10000
			u = append(u, uint16(0xd800+(r>>10)), uint16(0xdc00+(r&0x3ff)))
		} else {
			u = append(u, uint16(r))
		}
	}
	return u
}

// ------------------------------------------------------------------ resources.arsc

type chunk struct {
	off, typ, hsize, size int
}

func chunks(b []byte, start, end int) ([]chunk, error) {
	var out []chunk
	for off := start; off < end; {
		if off+8 > end {
			return nil, errors.New("truncated chunk header")
		}
		c := chunk{off, int(le.Uint16(b[off:])), int(le.Uint16(b[off+2:])), int(le.Uint32(b[off+4:]))}
		if c.size < 8 || off+c.size > end {
			return nil, fmt.Errorf("bad chunk size at 0x%x", off)
		}
		out = append(out, c)
		off += c.size
	}
	return out, nil
}

type table struct {
	arsc      []byte
	gpool     *pool
	pkgOff    int
	pkgID     uint32
	types     *pool
	keys      *pool
	keysOff   int // relative to the package
	typeIdOff int
}

func parseTable(arsc []byte) (*table, error) {
	if len(arsc) < 12 || le.Uint16(arsc) != 0x0002 {
		return nil, errors.New("resources.arsc: bad header")
	}
	hsize := int(le.Uint16(arsc[2:]))
	if le.Uint32(arsc[8:]) != 1 {
		return nil, errors.New("resources.arsc: expected one package")
	}
	cs, err := chunks(arsc, hsize, len(arsc))
	if err != nil {
		return nil, err
	}
	t := &table{arsc: arsc, pkgOff: -1}
	for _, c := range cs {
		switch {
		case c.typ == 0x0001 && t.gpool == nil:
			if t.gpool, err = parsePool(arsc[c.off : c.off+c.size]); err != nil {
				return nil, err
			}
		case c.typ == 0x0200:
			t.pkgOff = c.off
		}
	}
	if t.gpool == nil || t.pkgOff < 0 {
		return nil, errors.New("resources.arsc: no string pool / package")
	}
	pkg := t.pkg()
	t.pkgID = le.Uint32(pkg[8:])
	tso := int(le.Uint32(pkg[268:]))
	t.keysOff = int(le.Uint32(pkg[276:]))
	if t.types, err = parsePool(pkg[tso:]); err != nil {
		return nil, err
	}
	if t.keys, err = parsePool(pkg[t.keysOff:]); err != nil {
		return nil, err
	}
	return t, nil
}

func (t *table) pkg() []byte {
	return t.arsc[t.pkgOff : t.pkgOff+int(le.Uint32(t.arsc[t.pkgOff+4:]))]
}

func (t *table) typeID(name string) int {
	i := t.types.index(name)
	if i < 0 {
		return -1
	}
	return i + 1
}

func isDefaultConfig(c []byte) bool {
	csize := int(le.Uint32(c[20:]))
	for _, x := range c[24 : 20+csize] {
		if x != 0 {
			return false
		}
	}
	return true
}

// entryOffsets returns entry index -> offset (relative to entriesStart) of a type chunk.
func entryOffsets(c []byte) map[int]int {
	hsize := int(le.Uint16(c[2:]))
	flags := c[9]
	count := int(le.Uint32(c[12:]))
	m := map[int]int{}
	for i := 0; i < count; i++ {
		switch {
		case flags&flagSparse != 0:
			m[int(le.Uint16(c[hsize+4*i:]))] = 4 * int(le.Uint16(c[hsize+4*i+2:]))
		case flags&flagOffset16 != 0:
			if o := le.Uint16(c[hsize+2*i:]); o != 0xffff {
				m[i] = 4 * int(o)
			}
		default:
			if o := le.Uint32(c[hsize+4*i:]); o != 0xffffffff {
				m[i] = int(o)
			}
		}
	}
	return m
}

// lookup finds type/name in the default configuration: resource id and, for a
// string value, the string.
func (t *table) lookup(typ, name string) (uint32, string, bool) {
	tid := t.typeID(typ)
	key := t.keys.index(name)
	if tid < 0 || key < 0 {
		return 0, "", false
	}
	pkg := t.pkg()
	hsize := int(le.Uint16(pkg[2:]))
	cs, err := chunks(pkg, hsize, len(pkg))
	if err != nil {
		return 0, "", false
	}
	for _, c := range cs {
		if c.typ != 0x0201 || int(pkg[c.off+8]) != tid {
			continue
		}
		b := pkg[c.off : c.off+c.size]
		if !isDefaultConfig(b) {
			continue
		}
		estart := int(le.Uint32(b[16:]))
		for idx, o := range entryOffsets(b) {
			e := b[estart+o:]
			esize, eflags := int(le.Uint16(e)), le.Uint16(e[2:])
			var k int
			var vtype byte
			var vdata uint32
			if eflags&flagCompact != 0 {
				k, vtype, vdata = esize, byte(eflags>>8), le.Uint32(e[4:])
			} else {
				k = int(le.Uint32(e[4:]))
				if eflags&flagComplex == 0 {
					vtype, vdata = e[esize+3], le.Uint32(e[esize+4:])
				}
			}
			if k != key {
				continue
			}
			id := t.pkgID<<24 | uint32(tid)<<16 | uint32(idx)
			if vtype == typeString && int(vdata) < len(t.gpool.strs) {
				return id, t.gpool.strs[vdata], true
			}
			return id, "", true
		}
	}
	return 0, "", false
}

// addFiles appends file resources (entry name -> path in apk) to a type.
func (t *table) addFiles(typ string, names, paths []string) ([]byte, []uint32, error) {
	tid := t.typeID(typ)
	if tid < 0 {
		return nil, nil, fmt.Errorf("type %s not found", typ)
	}
	arsc := t.arsc
	hsize := int(le.Uint16(arsc[2:]))
	cs, _ := chunks(arsc, hsize, len(arsc))
	var out []byte
	out = append(out, arsc[:hsize]...)
	gfirst := -1
	var pkgNew []byte
	var ids []uint32
	var err error
	for _, c := range cs {
		b := arsc[c.off : c.off+c.size]
		switch {
		case c.typ == 0x0001 && gfirst < 0:
			var nb []byte
			nb, gfirst = appendStrings(b, paths)
			out = append(out, nb...)
		case c.typ == 0x0200:
			if gfirst < 0 {
				return nil, nil, errors.New("package before global string pool")
			}
			if pkgNew, ids, err = t.patchPackage(b, tid, names, gfirst); err != nil {
				return nil, nil, err
			}
			out = append(out, pkgNew...)
		default:
			out = append(out, b...)
		}
	}
	le.PutUint32(out[4:], uint32(len(out)))
	return out, ids, nil
}

func (t *table) patchPackage(pkg []byte, tid int, names []string, gfirst int) ([]byte, []uint32, error) {
	hsize := int(le.Uint16(pkg[2:]))
	ksize := int(le.Uint32(pkg[t.keysOff+4:]))
	kNew, kfirst := appendStrings(pkg[t.keysOff:t.keysOff+ksize], names)
	cs, err := chunks(pkg, hsize, len(pkg))
	if err != nil {
		return nil, nil, err
	}
	var out []byte
	out = append(out, pkg[:hsize]...)
	n := len(names)
	first := -1
	typeDone := false
	delta := len(kNew) - ksize
	for _, c := range cs {
		b := pkg[c.off : c.off+c.size]
		switch {
		case c.off == t.keysOff:
			b = kNew
		case c.typ == 0x0202 && int(b[8]) == tid:
			count := int(le.Uint32(b[12:]))
			nb := append(append([]byte(nil), b...), make([]byte, 4*n)...)
			le.PutUint32(nb[4:], uint32(len(nb)))
			le.PutUint32(nb[12:], uint32(count+n))
			b, first = nb, count
		case c.typ == 0x0201 && int(b[8]) == tid && !typeDone && isDefaultConfig(b):
			if first < 0 {
				return nil, nil, errors.New("type chunk before its spec")
			}
			entries := make([][2]int, n)
			for i := range entries {
				entries[i] = [2]int{kfirst + i, gfirst + i}
			}
			if b, err = growType(b, first, entries); err != nil {
				return nil, nil, err
			}
			typeDone = true
		}
		out = append(out, b...)
	}
	if first < 0 || !typeDone {
		return nil, nil, errors.New("drawable spec / default type not found")
	}
	le.PutUint32(out[4:], uint32(len(out)))
	// the key pool moved nothing before it; offsets of later pools (none normally) shift
	if ts := int(le.Uint32(pkg[268:])); ts > t.keysOff {
		le.PutUint32(out[268:], uint32(ts+delta))
	}
	ids := make([]uint32, n)
	for i := range ids {
		ids[i] = t.pkgID<<24 | uint32(tid)<<16 | uint32(first+i)
	}
	return out, ids, nil
}

// growType appends entries (key index, global string index) as entry indices
// first, first+1, ... to a default-config ResTable_type chunk.
func growType(c []byte, first int, entries [][2]int) ([]byte, error) {
	hsize := int(le.Uint16(c[2:]))
	size := int(le.Uint32(c[4:]))
	flags := c[9]
	count := int(le.Uint32(c[12:]))
	estart := int(le.Uint32(c[16:]))
	var width int
	switch {
	case flags&flagSparse != 0:
		width = 4
	case flags&flagOffset16 != 0:
		width = 2
		if count != first {
			return nil, fmt.Errorf("default type has %d entries, spec %d", count, first)
		}
	default:
		width = 4
		if count != first {
			return nil, fmt.Errorf("default type has %d entries, spec %d", count, first)
		}
	}
	offs := append([]byte(nil), c[hsize:hsize+width*count]...)
	data := append([]byte(nil), c[estart:size]...)
	for len(data)%4 != 0 {
		data = append(data, 0)
	}
	for i, e := range entries {
		pos := len(data)
		switch {
		case flags&flagSparse != 0:
			if pos/4 >= 0xffff {
				return nil, errors.New("sparse type too large")
			}
			offs = le.AppendUint16(offs, uint16(first+i))
			offs = le.AppendUint16(offs, uint16(pos/4))
		case width == 2:
			if pos/4 >= 0xffff {
				return nil, errors.New("offset16 type too large")
			}
			offs = le.AppendUint16(offs, uint16(pos/4))
		default:
			offs = le.AppendUint32(offs, uint32(pos))
		}
		// ResTable_entry{size 8, flags 0, key} + Res_value{8, 0, TYPE_STRING, string}
		data = le.AppendUint16(data, 8)
		data = le.AppendUint16(data, 0)
		data = le.AppendUint32(data, uint32(e[0]))
		data = le.AppendUint16(data, 8)
		data = append(data, 0, typeString)
		data = le.AppendUint32(data, uint32(e[1]))
	}
	for (hsize+len(offs))%4 != 0 {
		offs = append(offs, 0)
	}
	head := append([]byte(nil), c[:hsize]...)
	nEstart := hsize + len(offs)
	le.PutUint32(head[4:], uint32(nEstart+len(data)))
	le.PutUint32(head[12:], uint32(count+len(entries)))
	le.PutUint32(head[16:], uint32(nEstart))
	out := append(head, offs...)
	return append(out, data...), nil
}

// ------------------------------------------------------------------ binary XML

type xattr struct {
	ns, name, raw uint32
	vsize         uint16
	res0, vtype   byte
	data          uint32
}

func readAttrs(b []byte, ext int) (attrStart, attrSize int, attrs []xattr) {
	attrStart = int(le.Uint16(b[ext+8:]))
	attrSize = int(le.Uint16(b[ext+10:]))
	n := int(le.Uint16(b[ext+12:]))
	for i := 0; i < n; i++ {
		a := b[ext+attrStart+i*attrSize:]
		attrs = append(attrs, xattr{le.Uint32(a), le.Uint32(a[4:]), le.Uint32(a[8:]),
			le.Uint16(a[12:]), a[14], a[15], le.Uint32(a[16:])})
	}
	return
}

type iconRef struct {
	key string
	id  uint32
}

// patchXML adds android:icon=@id and miuisettings:showIcon=true to every entry
// whose android:key is in icons.  Returns the new XML and the keys it changed.
func patchXML(x []byte, icons map[string]uint32, skip func(elem, key string) bool) ([]byte, []iconRef, []string, error) {
	if len(x) < 8 || le.Uint16(x) != 0x0003 {
		return nil, nil, nil, errors.New("not a binary XML")
	}
	hsize := int(le.Uint16(x[2:]))
	cs, err := chunks(x, hsize, int(le.Uint32(x[4:])))
	if err != nil {
		return nil, nil, nil, err
	}
	var sp *pool
	var spRaw []byte
	var resmap []uint32
	var nodes []chunk
	for _, c := range cs {
		switch {
		case c.typ == 0x0001:
			spRaw = x[c.off : c.off+c.size]
			if sp, err = parsePool(spRaw); err != nil {
				return nil, nil, nil, err
			}
		case c.typ == 0x0180:
			for o := c.off + c.hsize; o < c.off+c.size; o += 4 {
				resmap = append(resmap, le.Uint32(x[o:]))
			}
		case c.typ >= 0x0100 && c.typ <= 0x017f:
			nodes = append(nodes, c)
		}
	}
	if sp == nil || len(nodes) == 0 {
		return nil, nil, nil, errors.New("XML without string pool / nodes")
	}
	resid := func(i uint32) uint32 {
		if int(i) < len(resmap) {
			return resmap[i]
		}
		return 0
	}
	str := func(i uint32) string {
		if int(i) < len(sp.strs) {
			return sp.strs[i]
		}
		return ""
	}
	// strings we need
	var add []string
	next := len(sp.strs)
	need := func(s string, ok func(i int) bool) uint32 {
		for i, v := range sp.strs {
			if v == s && ok(i) {
				return uint32(i)
			}
		}
		for i, v := range add {
			if v == s {
				return uint32(len(sp.strs) + i)
			}
		}
		add = append(add, s)
		next++
		return uint32(next - 1)
	}
	iconIdx := -1
	for i, r := range resmap {
		if r == attrIcon {
			iconIdx = i
			break
		}
	}
	if iconIdx < 0 { // appended; the resource map is extended up to it
		iconIdx = int(need("icon", func(int) bool { return false }))
		for len(resmap) < iconIdx {
			resmap = append(resmap, 0)
		}
		resmap = append(resmap, attrIcon)
	}
	noID := func(i int) bool { return i >= len(resmap) || resmap[i] == 0 }
	androidIdx := need(androidNS, func(int) bool { return true })
	miuiIdx := need(miuiNS, func(int) bool { return true })
	showIdx := need("showIcon", noID)
	prefixIdx := need("miuisettings", func(int) bool { return true })

	// is the miuisettings namespace declared?
	declared := false
	for _, c := range nodes {
		if c.typ == 0x0100 && le.Uint32(x[c.off+c.hsize+4:]) == miuiIdx && int(miuiIdx) < len(sp.strs) {
			declared = true
		}
	}

	var body []byte
	var done []iconRef
	var seen []string
	for _, c := range nodes {
		b := x[c.off : c.off+c.size]
		if c.typ != 0x0102 {
			body = append(body, b...)
			continue
		}
		ext := c.hsize
		attrStart, attrSize, attrs := readAttrs(b, ext)
		elem := str(le.Uint32(b[ext+4:]))
		key := ""
		hasIcon, showAt := false, -1
		for i, a := range attrs {
			switch {
			case resid(a.name) == attrKey:
				if a.vtype == typeString {
					key = str(a.data)
				} else if a.raw != 0xffffffff {
					key = str(a.raw)
				}
			case resid(a.name) == attrIcon:
				hasIcon = true
			case str(a.ns) == miuiNS && str(a.name) == "showIcon":
				showAt = i
			}
		}
		if key == "" || skip(elem, key) {
			body = append(body, b...)
			continue
		}
		if !hasIcon {
			seen = append(seen, key) // entries that need a new icon
		}
		id, ok := icons[key]
		if !ok {
			id, ok = icons["*"]
		}
		if hasIcon { // icon already there (hidden by MIUI): only make it visible
			if showAt >= 0 {
				nb := append([]byte(nil), b...)
				a := nb[ext+attrStart+showAt*attrSize:]
				le.PutUint32(a[8:], 0xffffffff)
				a[15] = typeBool
				le.PutUint32(a[16:], 0xffffffff)
				body = append(body, nb...)
				done = append(done, iconRef{key, 0})
				continue
			}
			ok, id = true, 0
		}
		if !ok {
			body = append(body, b...)
			continue
		}
		idIdx, clsIdx, styIdx := le.Uint16(b[ext+14:]), le.Uint16(b[ext+16:]), le.Uint16(b[ext+18:])
		// android:icon goes in front of the first attribute with a larger (or no) resource id
		pos := len(attrs)
		for i, a := range attrs {
			if r := resid(a.name); r == 0 || r > attrIcon {
				pos = i
				break
			}
		}
		nattrs := append([]xattr(nil), attrs...)
		if hasIcon {
			pos = len(attrs) + 1 // nothing inserted
		} else {
			icon := xattr{androidIdx, uint32(iconIdx), 0xffffffff, 8, 0, typeRef, id}
			nattrs = append(append(append([]xattr(nil), attrs[:pos]...), icon), attrs[pos:]...)
		}
		if showAt >= 0 {
			if showAt >= pos {
				showAt++
			}
			nattrs[showAt].vtype, nattrs[showAt].data, nattrs[showAt].raw = typeBool, 0xffffffff, 0xffffffff
		} else {
			nattrs = append(nattrs, xattr{miuiIdx, showIdx, 0xffffffff, 8, 0, typeBool, 0xffffffff})
		}
		fix := func(v uint16) uint16 {
			if v > 0 && int(v)-1 >= pos {
				return v + 1
			}
			return v
		}
		nb := append([]byte(nil), b[:ext+attrStart]...)
		le.PutUint16(nb[ext+10:], 20)
		le.PutUint16(nb[ext+12:], uint16(len(nattrs)))
		le.PutUint16(nb[ext+14:], fix(idIdx))
		le.PutUint16(nb[ext+16:], fix(clsIdx))
		le.PutUint16(nb[ext+18:], fix(styIdx))
		for _, a := range nattrs {
			nb = le.AppendUint32(nb, a.ns)
			nb = le.AppendUint32(nb, a.name)
			nb = le.AppendUint32(nb, a.raw)
			nb = le.AppendUint16(nb, a.vsize)
			nb = append(nb, a.res0, a.vtype)
			nb = le.AppendUint32(nb, a.data)
		}
		le.PutUint32(nb[4:], uint32(len(nb)))
		body = append(body, nb...)
		done = append(done, iconRef{key, id})
	}
	if !declared {
		line := le.Uint32(x[nodes[0].off+8:])
		ns := func(typ uint16) []byte {
			n := le.AppendUint16(nil, typ)
			n = le.AppendUint16(n, 16)
			n = le.AppendUint32(n, 24)
			n = le.AppendUint32(n, line)
			n = le.AppendUint32(n, 0xffffffff)
			n = le.AppendUint32(n, prefixIdx)
			return le.AppendUint32(n, miuiIdx)
		}
		body = append(append(ns(0x0100), body...), ns(0x0101)...)
	}
	newPool, _ := appendStrings(spRaw, add)
	var rm []byte
	rm = le.AppendUint16(rm, 0x0180)
	rm = le.AppendUint16(rm, 8)
	rm = le.AppendUint32(rm, uint32(8+4*len(resmap)))
	for _, r := range resmap {
		rm = le.AppendUint32(rm, r)
	}
	out := append([]byte(nil), x[:hsize]...)
	out = append(out, newPool...)
	if len(resmap) > 0 {
		out = append(out, rm...)
	}
	out = append(out, body...)
	le.PutUint32(out[4:], uint32(len(out)))
	return out, done, seen, nil
}

// ------------------------------------------------------------------ zip

type zent struct {
	vmade, vneed, flag, method, mtime, mdate uint16
	crc, csize, usize                        uint32
	name                                     string
	iattr                                    uint16
	eattr, lho                               uint32
}

func readCD(b []byte) ([]zent, int, error) {
	e := -1
	for i := len(b) - 22; i >= 0 && i >= len(b)-65557; i-- {
		if le.Uint32(b[i:]) == 0x06054b50 {
			e = i
			break
		}
	}
	if e < 0 {
		return nil, 0, errors.New("zip: end of central directory not found")
	}
	total := int(le.Uint16(b[e+10:]))
	cdOff := int(le.Uint32(b[e+16:]))
	if total == 0xffff || cdOff == -1 || uint32(cdOff) == 0xffffffff {
		return nil, 0, errors.New("zip64 not supported")
	}
	var ents []zent
	p := cdOff
	for i := 0; i < total; i++ {
		if p+46 > len(b) || le.Uint32(b[p:]) != 0x02014b50 {
			return nil, 0, errors.New("zip: bad central directory")
		}
		nl, xl, cl := int(le.Uint16(b[p+28:])), int(le.Uint16(b[p+30:])), int(le.Uint16(b[p+32:]))
		ents = append(ents, zent{le.Uint16(b[p+4:]), le.Uint16(b[p+6:]), le.Uint16(b[p+8:]), le.Uint16(b[p+10:]),
			le.Uint16(b[p+12:]), le.Uint16(b[p+14:]), le.Uint32(b[p+16:]), le.Uint32(b[p+20:]), le.Uint32(b[p+24:]),
			string(b[p+46 : p+46+nl]), le.Uint16(b[p+36:]), le.Uint32(b[p+38:]), le.Uint32(b[p+42:])})
		p += 46 + nl + xl + cl
	}
	return ents, cdOff, nil
}

func signingBlock(b []byte, cdOff int) []byte {
	if cdOff < 32 || string(b[cdOff-16:cdOff]) != "APK Sig Block 42" {
		return nil
	}
	size := int(le.Uint64(b[cdOff-24:]))
	start := cdOff - size - 8
	if start < 0 || int(le.Uint64(b[start:])) != size {
		return nil
	}
	return b[start:cdOff]
}

func rawData(b []byte, e zent) ([]byte, error) {
	p := int(e.lho)
	if p+30 > len(b) || le.Uint32(b[p:]) != 0x04034b50 {
		return nil, fmt.Errorf("zip: bad local header for %s", e.name)
	}
	start := p + 30 + int(le.Uint16(b[p+26:])) + int(le.Uint16(b[p+28:]))
	return b[start : start+int(e.csize)], nil
}

func content(b []byte, e zent) ([]byte, error) {
	d, err := rawData(b, e)
	if err != nil {
		return nil, err
	}
	var out []byte
	switch e.method {
	case 0:
		out = d
	case 8:
		r := flate.NewReader(bytes.NewReader(d))
		var buf bytes.Buffer
		if _, err := buf.ReadFrom(r); err != nil {
			return nil, fmt.Errorf("inflate %s: %v", e.name, err)
		}
		out = buf.Bytes()
	default:
		return nil, fmt.Errorf("%s: unsupported compression %d", e.name, e.method)
	}
	if crc32.ChecksumIEEE(out) != e.crc {
		return nil, fmt.Errorf("%s: CRC mismatch", e.name)
	}
	return out, nil
}

func deflate(d []byte) []byte {
	var buf bytes.Buffer
	w, _ := flate.NewWriter(&buf, 9)
	w.Write(d)
	w.Close()
	return buf.Bytes()
}

type newFile struct {
	name string
	data []byte
}

func rebuildZip(src []byte, replace map[string][]byte, add []newFile) ([]byte, error) {
	ents, cdOff, err := readCD(src)
	if err != nil {
		return nil, err
	}
	block := signingBlock(src, cdOff)
	var out, cd bytes.Buffer
	emit := func(e zent, data []byte) {
		stored := e.method == 0
		base := out.Len() + 30 + len(e.name)
		align := 4
		if strings.HasSuffix(e.name, ".so") {
			align = 16384
		}
		pad := 0
		if stored {
			pad = (align - base%align) % align
		}
		flag := e.flag &^ 0x0008
		lho := uint32(out.Len())
		h := le.AppendUint32(nil, 0x04034b50)
		for _, v := range []uint16{e.vneed, flag, e.method, e.mtime, e.mdate} {
			h = le.AppendUint16(h, v)
		}
		h = le.AppendUint32(h, e.crc)
		h = le.AppendUint32(h, e.csize)
		h = le.AppendUint32(h, e.usize)
		h = le.AppendUint16(h, uint16(len(e.name)))
		h = le.AppendUint16(h, uint16(pad))
		out.Write(h)
		out.WriteString(e.name)
		out.Write(make([]byte, pad))
		out.Write(data)
		c := le.AppendUint32(nil, 0x02014b50)
		for _, v := range []uint16{e.vmade, e.vneed, flag, e.method, e.mtime, e.mdate} {
			c = le.AppendUint16(c, v)
		}
		c = le.AppendUint32(c, e.crc)
		c = le.AppendUint32(c, e.csize)
		c = le.AppendUint32(c, e.usize)
		c = le.AppendUint16(c, uint16(len(e.name)))
		c = append(c, 0, 0, 0, 0, 0, 0) // extra, comment, disk
		c = le.AppendUint16(c, e.iattr)
		c = le.AppendUint32(c, e.eattr)
		c = le.AppendUint32(c, lho)
		cd.Write(c)
		cd.WriteString(e.name)
	}
	pack := func(e zent, d []byte) (zent, []byte) {
		e.crc = crc32.ChecksumIEEE(d)
		e.usize = uint32(len(d))
		if e.method != 0 {
			e.method = 8
			d = deflate(d)
		}
		e.csize = uint32(len(d))
		return e, d
	}
	names := map[string]bool{}
	for _, e := range ents {
		names[e.name] = true
		if r, ok := replace[e.name]; ok {
			emit(pack(e, r))
			continue
		}
		d, err := rawData(src, e)
		if err != nil {
			return nil, err
		}
		emit(e, d)
	}
	tmpl := ents[len(ents)-1]
	for _, f := range add {
		if names[f.name] {
			return nil, fmt.Errorf("%s already exists in the APK", f.name)
		}
		e := tmpl
		e.name, e.method, e.flag, e.iattr, e.eattr = f.name, 8, 0, 0, 0
		emit(pack(e, f.data))
	}
	out.Write(block)
	off := out.Len()
	n := len(ents) + len(add)
	out.Write(cd.Bytes())
	end := le.AppendUint32(nil, 0x06054b50)
	end = append(end, 0, 0, 0, 0)
	end = le.AppendUint16(end, uint16(n))
	end = le.AppendUint16(end, uint16(n))
	end = le.AppendUint32(end, uint32(cd.Len()))
	end = le.AppendUint32(end, uint32(off))
	end = append(end, 0, 0)
	out.Write(end)
	return out.Bytes(), nil
}

// ------------------------------------------------------------------ main

type mapping struct {
	key, file, existing string
}

func readMap(dir string) ([]mapping, error) {
	f, err := os.Open(filepath.Join(dir, "map.txt"))
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var m []mapping
	s := bufio.NewScanner(f)
	for s.Scan() {
		l := strings.Fields(s.Text())
		if len(l) == 0 || strings.HasPrefix(l[0], "#") {
			continue
		}
		e := mapping{key: l[0], file: l[1]}
		if len(l) > 2 {
			e.existing = l[2]
		}
		m = append(m, e)
	}
	return m, s.Err()
}

func zipIndex(b []byte) (map[string]zent, []zent, int, error) {
	ents, cdOff, err := readCD(b)
	if err != nil {
		return nil, nil, 0, err
	}
	m := map[string]zent{}
	for _, e := range ents {
		m[e.name] = e
	}
	return m, ents, cdOff, nil
}

func skipEntry(elem, key string) bool {
	return strings.HasSuffix(elem, "PreferenceCategory") || strings.HasSuffix(elem, "PreferenceScreen") ||
		strings.HasSuffix(key, "_section") || strings.HasSuffix(key, "_category")
}

func main() {
	wifi := true
	var args []string
	for _, a := range os.Args[1:] {
		if a == "--no-wifi" {
			wifi = false
		} else {
			args = append(args, a)
		}
	}
	if len(args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: ryu_patch [--no-wifi] <Settings.apk> <out.apk> <icons dir>")
		os.Exit(1)
	}
	os.Args = append([]string{os.Args[0]}, args...)
	src, err := os.ReadFile(os.Args[1])
	if err != nil {
		fail("%v", err)
	}
	maps, err := readMap(os.Args[3])
	if err != nil {
		fail("map.txt: %v", err)
	}
	zi, _, _, err := zipIndex(src)
	if err != nil {
		fail("%v", err)
	}
	ae, ok := zi["resources.arsc"]
	if !ok {
		fail("resources.arsc not found")
	}
	arsc, err := content(src, ae)
	if err != nil {
		fail("%v", err)
	}
	t, err := parseTable(arsc)
	if err != nil {
		fail("%v", err)
	}
	for _, k := range t.keys.strs {
		if strings.HasPrefix(k, entryPrefix) {
			fmt.Println("already patched (", k, ")")
			os.Exit(errAlready)
		}
	}
	_, xmlPath, ok := t.lookup("xml", screenName)
	if !ok || xmlPath == "" {
		fail("xml/%s not found in this Settings.apk", screenName)
	}
	xe, ok := zi[xmlPath]
	if !ok {
		fail("%s missing in the APK", xmlPath)
	}
	xml, err := content(src, xe)
	if err != nil {
		fail("%v", err)
	}
	// first pass: which keys does the screen have?
	_, _, keys, err := patchXML(xml, map[string]uint32{}, skipEntry)
	if err != nil {
		fail("%v", err)
	}
	byKey := map[string]mapping{}
	for _, m := range maps {
		byKey[m.key] = m
	}
	icons := map[string]uint32{}
	var names, paths []string
	var files []newFile
	fileOf := map[string]int{} // drawable file -> index in names
	var report []string
	for _, k := range keys {
		m, ok := byKey[k]
		if !ok {
			m, ok = byKey["*"]
			if !ok {
				continue
			}
			report = append(report, k+": standard icon")
		}
		if m.existing != "" {
			if id, _, ok := t.lookup("drawable", m.existing); ok {
				icons[k] = id
				continue
			}
		}
		if _, ok := fileOf[m.file]; !ok {
			d, err := os.ReadFile(filepath.Join(os.Args[3], m.file))
			if err != nil {
				fail("%v", err)
			}
			if len(d) < 8 || le.Uint16(d) != 0x0003 {
				fail("%s is not a compiled drawable", m.file)
			}
			fileOf[m.file] = len(names)
			base := strings.TrimSuffix(m.file, ".xml")
			names = append(names, entryPrefix+base)
			p := "res/drawable/" + entryPrefix + base + ".xml"
			paths = append(paths, p)
			files = append(files, newFile{p, d})
		}
	}
	if len(names) == 0 {
		fail("no entries found on the screen")
	}
	newArsc, ids, err := t.addFiles("drawable", names, paths)
	if err != nil {
		fail("%v", err)
	}
	for _, k := range keys {
		m, ok := byKey[k]
		if !ok {
			m = byKey["*"]
		}
		if _, set := icons[k]; set {
			continue
		}
		if i, ok := fileOf[m.file]; ok {
			icons[k] = ids[i]
		}
	}
	newXML, done, _, err := patchXML(xml, icons, skipEntry)
	if err != nil {
		fail("%v", err)
	}
	replace := map[string][]byte{"resources.arsc": newArsc, xmlPath: newXML}
	if wifi {
		w, info, err := stockSavedWifi(src, zi, t)
		if err != nil {
			fmt.Println("  Wi-Fi saved networks: skipped (" + err.Error() + ")")
		} else {
			for k, v := range w {
				replace[k] = v
			}
			fmt.Println("  Wi-Fi saved networks: stock screen (" + info + ")")
		}
	}
	out, err := rebuildZip(src, replace, files)
	if err != nil {
		fail("%v", err)
	}
	if err := verify(src, out, xmlPath, replace, paths, done); err != nil {
		fail("verify: %v", err)
	}
	tmp := os.Args[2] + ".tmp"
	if err := os.WriteFile(tmp, out, 0644); err != nil {
		fail("%v", err)
	}
	if err := os.Rename(tmp, os.Args[2]); err != nil {
		fail("%v", err)
	}
	sort.Strings(report)
	for _, r := range report {
		fmt.Println("  " + r)
	}
	fmt.Printf("OK: %d icons on %s (%d new drawables)\n", len(done), xmlPath, len(names))
}

// verify re-reads the output: every original entry is unchanged except the two
// replaced ones, the new drawables resolve, and the icons point at them.
func verify(src, out []byte, xmlPath string, replace map[string][]byte, paths []string, done []iconRef) error {
	_, eo, _, err := zipIndex(src)
	if err != nil {
		return err
	}
	zn, en, cdn, err := zipIndex(out)
	if err != nil {
		return err
	}
	if len(en) != len(eo)+len(paths) {
		return errors.New("entry count")
	}
	for _, e := range eo {
		n, ok := zn[e.name]
		if !ok {
			return fmt.Errorf("%s lost", e.name)
		}
		if _, ok := replace[e.name]; ok {
			b, err := content(out, n)
			if err != nil || !bytes.Equal(b, replace[e.name]) {
				return fmt.Errorf("%s not written correctly", e.name)
			}
			continue
		}
		a, err1 := rawData(src, e)
		b, err2 := rawData(out, n)
		if err1 != nil || err2 != nil || !bytes.Equal(a, b) || e.crc != n.crc || e.method != n.method {
			return fmt.Errorf("%s changed", e.name)
		}
	}
	for _, e := range en {
		if _, err := content(out, e); err != nil && (e.name == "resources.arsc" || e.name == xmlPath || strings.HasPrefix(e.name, "res/drawable/"+entryPrefix)) {
			return err
		}
		if e.method == 0 && e.name == "resources.arsc" {
			p := int(e.lho)
			if (p+30+int(le.Uint16(out[p+26:]))+int(le.Uint16(out[p+28:])))%4 != 0 {
				return errors.New("resources.arsc not aligned")
			}
		}
	}
	_, _, cdo, _ := zipIndex(src)
	if !bytes.Equal(signingBlock(src, cdo), signingBlock(out, cdn)) {
		return errors.New("signing block differs")
	}
	arsc, err := content(out, zn["resources.arsc"])
	if err != nil {
		return err
	}
	t, err := parseTable(arsc)
	if err != nil {
		return err
	}
	if _, p, ok := t.lookup("xml", screenName); !ok || p != xmlPath {
		return errors.New("screen xml lookup changed")
	}
	for _, p := range paths {
		name := strings.TrimSuffix(filepath.Base(p), ".xml")
		id, v, ok := t.lookup("drawable", name)
		if !ok || v != p {
			return fmt.Errorf("drawable %s does not resolve", name)
		}
		found := false
		for _, d := range done {
			if d.id == id {
				found = true
			}
		}
		if !found {
			return fmt.Errorf("drawable %s unused", name)
		}
	}
	return nil
}
