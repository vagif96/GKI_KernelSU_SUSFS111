package main

// Wi-Fi > Advanced > "Saved networks" opens the stock Android screen
// (Settings$SavedAccessPointsSettingsActivity: details, QR sharing, forget/connect
// for every saved network) instead of MIUI's list.
//
//   - xml/wifi_configure_settings: the saved_wifi entry becomes a ValuePreference
//     with an <intent> to that activity (no fragment);
//   - xml/wifi_network_details_fragment2: every ComposePreference is wrapped in its
//     own hidden PreferenceCategory (isPreferenceVisible=false).  In the miuix
//     activity a ComposeView crashes when laid out (ViewTreeLifecycleOwner not
//     found); the controllers still find the preferences, they are never shown.
//
// Same result as ryu_settings_icons/build.py --stock-saved-wifi (tested on the
// Xiaomi 17 Pro Max).

import (
	"errors"
	"fmt"
	"strings"
)

const (
	wifiScreen      = "wifi_configure_settings"
	wifiDetails     = "wifi_network_details_fragment2"
	savedActivity   = "com.android.settings.Settings$SavedAccessPointsSettingsActivity"
	valuePrefClass  = "com.android.settingslib.miuisettings.preference.ValuePreference"
	attrPersistent  = 0x0101000d
	attrTitle       = 0x010101e1
	attrTargetPkg   = 0x01010021
	attrAction      = 0x0101002d
	attrTargetClass = 0x0101002f
	resAuto         = "http://schemas.android.com/apk/res-auto"
	noIndex         = 0xffffffff
)

// ------------------------------------------------------------------ generic binary XML editor

type axNode struct {
	typ            int
	raw            []byte // unchanged chunk (nil when rebuilt)
	line, comment  uint32
	ns, name       uint32 // elements
	attrs          []xattr
	idI, clsI, stI uint16
}

type axDoc struct {
	head   []byte
	sp     *pool
	spRaw  []byte
	resmap []uint32
	add    []string
	nodes  []*axNode
}

func parseAX(x []byte) (*axDoc, error) {
	if len(x) < 8 || le.Uint16(x) != 0x0003 {
		return nil, errors.New("not a binary XML")
	}
	hsize := int(le.Uint16(x[2:]))
	cs, err := chunks(x, hsize, int(le.Uint32(x[4:])))
	if err != nil {
		return nil, err
	}
	d := &axDoc{head: x[:hsize]}
	for _, c := range cs {
		b := x[c.off : c.off+c.size]
		switch {
		case c.typ == 0x0001:
			d.spRaw = b
			if d.sp, err = parsePool(b); err != nil {
				return nil, err
			}
		case c.typ == 0x0180:
			for o := c.hsize; o < c.size; o += 4 {
				d.resmap = append(d.resmap, le.Uint32(b[o:]))
			}
		case c.typ >= 0x0100 && c.typ <= 0x017f:
			n := &axNode{typ: c.typ, raw: b, line: le.Uint32(b[8:]), comment: le.Uint32(b[12:])}
			if c.typ == 0x0102 || c.typ == 0x0103 {
				n.ns, n.name = le.Uint32(b[c.hsize:]), le.Uint32(b[c.hsize+4:])
			}
			if c.typ == 0x0102 {
				_, _, n.attrs = readAttrs(b, c.hsize)
				n.idI, n.clsI, n.stI = le.Uint16(b[c.hsize+14:]), le.Uint16(b[c.hsize+16:]), le.Uint16(b[c.hsize+18:])
			}
			d.nodes = append(d.nodes, n)
		}
	}
	if d.sp == nil {
		return nil, errors.New("XML without string pool")
	}
	return d, nil
}

func (d *axDoc) str(i uint32) string {
	if int(i) < len(d.sp.strs) {
		return d.sp.strs[i]
	}
	if j := int(i) - len(d.sp.strs); j >= 0 && j < len(d.add) {
		return d.add[j]
	}
	return ""
}

func (d *axDoc) resid(i uint32) uint32 {
	if int(i) < len(d.resmap) {
		return d.resmap[i]
	}
	return 0
}

// plain string (values, element names, namespaces): not an attribute name with an id
func (d *axDoc) idx(s string) uint32 {
	n := uint32(len(d.sp.strs) + len(d.add))
	for i := uint32(0); i < n; i++ {
		if d.str(i) == s && d.resid(i) == 0 {
			return i
		}
	}
	d.add = append(d.add, s)
	return n
}

// attribute name with a resource id; the resource map is extended if needed
func (d *axDoc) attrName(id uint32, s string) uint32 {
	for i, r := range d.resmap {
		if r == id {
			return uint32(i)
		}
	}
	i := uint32(len(d.sp.strs) + len(d.add))
	d.add = append(d.add, s)
	for uint32(len(d.resmap)) < i {
		d.resmap = append(d.resmap, 0)
	}
	d.resmap = append(d.resmap, id)
	return i
}

func strAttr(ns, name, v uint32) xattr { return xattr{ns, name, v, 8, 0, typeString, v} }

func (d *axDoc) attr(n *axNode, id uint32) (int, *xattr) {
	for i := range n.attrs {
		if d.resid(n.attrs[i].name) == id {
			return i, &n.attrs[i]
		}
	}
	return -1, nil
}

func (d *axDoc) attrStr(n *axNode, id uint32) string {
	_, a := d.attr(n, id)
	if a == nil {
		return ""
	}
	if a.vtype == typeString {
		return d.str(a.data)
	}
	if a.raw != noIndex {
		return d.str(a.raw)
	}
	return ""
}

// endOf returns the index of the end element matching the start element at i.
func (d *axDoc) endOf(i int) int {
	depth := 0
	for j := i; j < len(d.nodes); j++ {
		switch d.nodes[j].typ {
		case 0x0102:
			depth++
		case 0x0103:
			depth--
			if depth == 0 {
				return j
			}
		}
	}
	return -1
}

func newStart(line, ns, name uint32, attrs []xattr) *axNode {
	return &axNode{typ: 0x0102, line: line, comment: noIndex, ns: ns, name: name, attrs: attrs}
}

func newEnd(line, ns, name uint32) *axNode {
	return &axNode{typ: 0x0103, line: line, comment: noIndex, ns: ns, name: name}
}

func (d *axDoc) insert(at int, ns ...*axNode) {
	d.nodes = append(d.nodes[:at], append(ns, d.nodes[at:]...)...)
}

func (n *axNode) bytes() []byte {
	if n.raw != nil {
		return n.raw
	}
	b := le.AppendUint16(nil, uint16(n.typ))
	b = le.AppendUint16(b, 16)
	b = le.AppendUint32(b, 0) // size, set below
	b = le.AppendUint32(b, n.line)
	b = le.AppendUint32(b, n.comment)
	b = le.AppendUint32(b, n.ns)
	b = le.AppendUint32(b, n.name)
	if n.typ == 0x0102 {
		b = le.AppendUint16(b, 20)
		b = le.AppendUint16(b, 20)
		b = le.AppendUint16(b, uint16(len(n.attrs)))
		b = le.AppendUint16(b, n.idI)
		b = le.AppendUint16(b, n.clsI)
		b = le.AppendUint16(b, n.stI)
		for _, a := range n.attrs {
			b = le.AppendUint32(b, a.ns)
			b = le.AppendUint32(b, a.name)
			b = le.AppendUint32(b, a.raw)
			b = le.AppendUint16(b, a.vsize)
			b = append(b, a.res0, a.vtype)
			b = le.AppendUint32(b, a.data)
		}
	}
	le.PutUint32(b[4:], uint32(len(b)))
	return b
}

func (d *axDoc) bytes() []byte {
	newPool, _ := appendStrings(d.spRaw, d.add)
	out := append([]byte(nil), d.head...)
	out = append(out, newPool...)
	if len(d.resmap) > 0 {
		rm := le.AppendUint16(nil, 0x0180)
		rm = le.AppendUint16(rm, 8)
		rm = le.AppendUint32(rm, uint32(8+4*len(d.resmap)))
		for _, r := range d.resmap {
			rm = le.AppendUint32(rm, r)
		}
		out = append(out, rm...)
	}
	for _, n := range d.nodes {
		out = append(out, n.bytes()...)
	}
	le.PutUint32(out[4:], uint32(len(out)))
	return out
}

func (d *axDoc) androidNS() uint32 { return d.idx(androidNS) }

// ------------------------------------------------------------------ the two edits

func patchSavedWifi(x []byte) ([]byte, error) {
	d, err := parseAX(x)
	if err != nil {
		return nil, err
	}
	for i, n := range d.nodes {
		if n.typ != 0x0102 || d.attrStr(n, attrKey) != "saved_wifi" {
			continue
		}
		e := d.endOf(i)
		if e < 0 {
			return nil, errors.New("saved_wifi: no end element")
		}
		if e != i+1 {
			return nil, errors.New("saved_wifi already has children (already changed?)")
		}
		if frag := d.attrStr(n, 0x010102e3); !strings.Contains(frag, "SavedAccessPoints") {
			return nil, fmt.Errorf("saved_wifi: unexpected fragment %q", frag)
		}
		var keep []xattr
		for _, a := range n.attrs {
			if r := d.resid(a.name); r == attrTitle || r == attrKey {
				keep = append(keep, a)
			}
		}
		if len(keep) != 2 {
			return nil, errors.New("saved_wifi: title/key not found")
		}
		an := d.androidNS()
		cls := d.idx(valuePrefClass)
		start := newStart(n.line, n.ns, cls, keep)
		end := newEnd(n.line, n.ns, cls)
		intent := d.idx("intent")
		ia := []xattr{
			strAttr(an, d.attrName(attrTargetPkg, "targetPackage"), d.idx("com.android.settings")),
			strAttr(an, d.attrName(attrAction, "action"), d.idx("android.intent.action.MAIN")),
			strAttr(an, d.attrName(attrTargetClass, "targetClass"), d.idx(savedActivity)),
		}
		d.nodes[i], d.nodes[e] = start, end
		d.insert(e, newStart(n.line, noIndex, intent, ia), newEnd(n.line, noIndex, intent))
		return d.bytes(), nil
	}
	return nil, errors.New("saved_wifi entry not found")
}

func patchWifiDetails(x []byte, visibleAttr uint32) ([]byte, []string, error) {
	d, err := parseAX(x)
	if err != nil {
		return nil, nil, err
	}
	// namespace of the app's own attributes (res-auto or res/com.android.settings)
	appNS := uint32(noIndex)
	for _, n := range d.nodes {
		for _, a := range n.attrs {
			if d.resid(a.name)>>24 == 0x7f && a.ns != noIndex {
				appNS = a.ns
			}
		}
	}
	if appNS == noIndex {
		appNS = d.idx(resAuto)
	}
	var keys []string
	for i := 0; i < len(d.nodes); i++ {
		n := d.nodes[i]
		if n.typ != 0x0102 || !strings.HasSuffix(d.str(n.name), "ComposePreference") {
			continue
		}
		key := d.attrStr(n, attrKey)
		if key == "" {
			return nil, nil, errors.New("ComposePreference without key")
		}
		if strings.HasPrefix(d.attrStr(d.nodes[max(i-1, 0)], attrKey), "ryu_hidden_") {
			return nil, nil, errors.New("already changed")
		}
		e := d.endOf(i)
		if e < 0 {
			return nil, nil, errors.New("no end element")
		}
		an := d.androidNS()
		cat := d.idx("PreferenceCategory")
		ca := []xattr{
			strAttr(an, d.attrName(attrKey, "key"), d.idx("ryu_hidden_"+key)),
			{appNS, d.attrName(visibleAttr, "isPreferenceVisible"), noIndex, 8, 0, typeBool, 0},
		}
		d.insert(e+1, newEnd(n.line, noIndex, cat))
		d.insert(i, newStart(n.line, noIndex, cat, ca))
		keys = append(keys, key)
		i = e + 2
	}
	if len(keys) == 0 {
		return nil, nil, errors.New("no ComposePreference found")
	}
	return d.bytes(), keys, nil
}

// manifestHas reports whether the binary AndroidManifest mentions the activity.
func manifestHas(m []byte, activity string) bool {
	d, err := parseAX(m)
	if err != nil {
		return false
	}
	short := activity[strings.LastIndex(activity, ".Settings$"):]
	for _, s := range d.sp.strs {
		if s == activity || s == short {
			return true
		}
	}
	return false
}

// stockSavedWifi returns the replaced zip entries, or an error (Wi-Fi part skipped).
func stockSavedWifi(src []byte, zi map[string]zent, t *table) (map[string][]byte, string, error) {
	me, ok := zi["AndroidManifest.xml"]
	if !ok {
		return nil, "", errors.New("no AndroidManifest.xml")
	}
	man, err := content(src, me)
	if err != nil {
		return nil, "", err
	}
	if !manifestHas(man, savedActivity) {
		return nil, "", errors.New(savedActivity + " not in this Settings")
	}
	visible, _, ok := t.lookup("attr", "isPreferenceVisible")
	if !ok {
		return nil, "", errors.New("attr isPreferenceVisible not found")
	}
	out := map[string][]byte{}
	read := func(name string) (string, []byte, error) {
		_, p, ok := t.lookup("xml", name)
		if !ok || p == "" {
			return "", nil, fmt.Errorf("xml/%s not found", name)
		}
		e, ok := zi[p]
		if !ok {
			return "", nil, fmt.Errorf("%s missing", p)
		}
		b, err := content(src, e)
		return p, b, err
	}
	p1, x1, err := read(wifiScreen)
	if err != nil {
		return nil, "", err
	}
	if out[p1], err = patchSavedWifi(x1); err != nil {
		return nil, "", fmt.Errorf("%s: %v", wifiScreen, err)
	}
	p2, x2, err := read(wifiDetails)
	if err != nil {
		return nil, "", err
	}
	var keys []string
	if out[p2], keys, err = patchWifiDetails(x2, visible); err != nil {
		return nil, "", fmt.Errorf("%s: %v", wifiDetails, err)
	}
	return out, "hidden Compose items: " + strings.Join(keys, ", "), nil
}
