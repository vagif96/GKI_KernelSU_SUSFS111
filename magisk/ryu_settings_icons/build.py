#!/usr/bin/env python3
"""Build the "Ryu Other Settings Icons" KernelSU/Magisk module.

Adds HyperOS-style icons to Settings -> "Additional settings"
(xml/other_personal_settings) by patching Settings.apk itself.

How it works
------------
* A small "donor" APK is compiled with aapt2: the screen XML with an
  android:icon on every entry, plus one vector drawable per icon.
* resources.arsc of Settings.apk gets 38 new drawable entries appended to the
  drawable type (no existing id or value changes, see apk_patch.py).
* The screen XML is replaced (icon references point to the new ids), the
  drawables are added, every other zip entry is copied byte-for-byte (dex
  unchanged -> existing oat/vdex stay valid).
* The original APK Signing Block is put back.  Android does not verify the
  integrity of APKs on system partitions (ProjectRyu's own Settings.apk already
  fails verification), it only reads the certificates, so the platform
  signature / android.uid.system stays intact.
* post-fs-data.sh bind-mounts the patched APK over the original file itself
  (KernelSU Next 3.x does not mount module system/ folders without a
  metamodule); the SELinux label is copied from the real file.

The module must be rebuilt for every firmware: the installer refuses a
different Settings.apk and the module disables itself after an update.

Usage:  python3 build.py /path/to/Settings.apk [--out DIR]
Needs:  java, node+npm (for @mdi/js), curl, zip; downloads apktool and
        uber-apk-signer from GitHub on first run.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from icons import ICONS  # noqa: E402
import apk_patch  # noqa: E402

TARGET_PKG = "com.android.settings"
OVERLAY_PKG = "com.ryu.settings.othericons.overlay"
OVERLAY_APK = "RyuOtherSettingsIcons.apk"
SCREEN = "xml/other_personal_settings"
WIFI_SCREEN = "xml/wifi_configure_settings"
WIFI_DETAILS = "xml/wifi_network_details_fragment2"
SAVED_WIFI_ACTIVITY = "com.android.settings.Settings$SavedAccessPointsSettingsActivity"
MODULE_ID = "ryu_other_settings_icons"
VERSION = "3.4"
VERSION_CODE = 34

APKTOOL_URL = "https://github.com/iBotPeaches/Apktool/releases/download/v2.10.0/apktool_2.10.0.jar"
SIGNER_URL = "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"
MDI_VERSION = "7.4.47"


def run(cmd, **kw):
    print("+", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, check=True, **kw)


def fetch(url, dst):
    if not os.path.exists(dst):
        run(["curl", "-fsSL", "-o", dst, url])
    return dst


def tools(work):
    tdir = os.path.join(work, "tools")
    os.makedirs(tdir, exist_ok=True)
    apktool = fetch(APKTOOL_URL, os.path.join(tdir, "apktool.jar"))
    signer = fetch(SIGNER_URL, os.path.join(tdir, "uber-apk-signer.jar"))
    aapt2 = os.path.join(tdir, "aapt2")
    if not os.path.exists(aapt2):
        with zipfile.ZipFile(apktool) as z, open(aapt2, "wb") as f:
            f.write(z.read("prebuilt/linux/aapt2_64"))
        os.chmod(aapt2, 0o755)
    mdi = os.path.join(tdir, "mdi")
    if not os.path.exists(os.path.join(mdi, "node_modules", "@mdi", "js")):
        os.makedirs(mdi, exist_ok=True)
        run(["npm", "install", "--prefix", mdi, f"@mdi/js@{MDI_VERSION}"], stdout=subprocess.DEVNULL)
    return apktool, signer, aapt2, mdi


def mdi_paths(mdi, names):
    js = ("const m=require(%s);const o={};for(const n of %s){if(!m[n])throw new Error('no '+n);o[n]=m[n]}"
          "console.log(JSON.stringify(o))") % (
        json.dumps(os.path.join(mdi, "node_modules", "@mdi", "js")), json.dumps(sorted(names)))
    return json.loads(subprocess.check_output(["node", "-e", js]))


def parse_dump(text):
    """aapt2 dump resources -> {name: (id, [(config, value)])}"""
    res, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"\s+resource (0x[0-9a-f]+) (\S+)", line)
        if m:
            cur = m.group(2)
            res[cur] = (int(m.group(1), 16), [])
            continue
        m = re.match(r"\s+\((.*?)\) (.*)", line)
        if m and cur:
            res[cur][1].append((m.group(1), m.group(2)))
    return res


def squircle(size=28.0):
    # Continuous-corner rounded square, same proportions as HyperOS settings icons.
    s, a, b, c = size, 11.95, 7.77, 5.68
    k1, k2 = 0.81, 4.08
    return (f"M0,{a}C0,{b} 0,{c} {k1},{k2}C1.53,2.67 2.67,1.53 {k2},{k1}C{c},0 {b},0 {a},0"
            f"H{s - a}C{s - b},0 {s - c},0 {s - k2},{k1}C{s - 2.67},1.53 {s - 1.53},2.67 {s - k1},{k2}"
            f"C{s},{c} {s},{b} {s},{a}V{s - a}C{s},{s - b} {s},{s - c} {s - k1},{s - k2}"
            f"C{s - 1.53},{s - 2.67} {s - 2.67},{s - 1.53} {s - k2},{s - k1}C{s - c},{s} {s - b},{s} {s - a},{s}"
            f"H{a}C{b},{s} {c},{s} {k2},{s - k1}C2.67,{s - 1.53} 1.53,{s - 2.67} {k1},{s - k2}"
            f"C0,{s - c} 0,{s - b} 0,{s - a}Z")


def vector(color, glyph):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="28dp" android:height="28dp"
    android:viewportWidth="28" android:viewportHeight="28">
    <path android:fillColor="{color}" android:pathData="{squircle()}" />
    <group android:translateX="6" android:translateY="6" android:scaleX="0.6667" android:scaleY="0.6667">
        <path android:fillColor="#ffffffff" android:pathData="{glyph}" />
    </group>
</vector>
"""


def patch_dynamic_refs(data, pkg_id):
    """Turn TYPE_REFERENCE (0x01) attribute values that point into the overlay's own
    package (pkg_id) into TYPE_DYNAMIC_REFERENCE (0x07) in a compiled binary XML.

    The replaced XML is parsed with the overlay's dynamic reference table: a plain
    reference to 0x7e... would be used as an absolute id (and fail), a dynamic one is
    translated to the package id the overlay gets at runtime.  References to
    com.android.settings (0x7f) and android (0x01) stay absolute."""
    data = bytearray(data)
    typ, hsize, total = struct.unpack_from("<HHI", data, 0)
    assert typ == 0x0003, "not a binary xml"
    off, patched = hsize, 0
    while off < total:
        ctype, chsize, csize = struct.unpack_from("<HHI", data, off)
        if ctype == 0x0102:  # RES_XML_START_ELEMENT_TYPE
            ext = off + chsize
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", data, ext + 8)
            for i in range(attr_count):
                a = ext + attr_start + i * attr_size
                # ns, name, rawValue (3*u32), then Res_value {u16 size, u8 res0, u8 type, u32 data}
                vt = a + 12 + 3
                val = struct.unpack_from("<I", data, a + 16)[0]
                if data[vt] == 0x01 and (val >> 24) == pkg_id:
                    data[vt] = 0x07
                    patched += 1
        off += csize
    return bytes(data), patched


def verify(aapt2, orig, patched, new_ids, xml_entry, wifi_entry, details_entry=None):
    """Sanity checks of the patched APK against the original."""
    dump_o = subprocess.check_output([aapt2, "dump", "resources", orig], text=True)
    dump_p = subprocess.check_output([aapt2, "dump", "resources", patched], text=True)
    ro, rp = parse_dump(dump_o), parse_dump(dump_p)
    for name, val in ro.items():
        if rp.get(name) != val:
            sys.exit(f"VERIFY: resource {name} changed")
    added = set(rp) - set(ro)
    if added != {"drawable/" + n for n in new_ids}:
        sys.exit(f"VERIFY: unexpected added resources {sorted(added)[:5]}")
    for n, rid in new_ids.items():
        if rp["drawable/" + n][0] != rid:
            sys.exit(f"VERIFY: id mismatch for {n}")
    tree = subprocess.check_output([aapt2, "dump", "xmltree", "--file", xml_entry, patched], text=True)
    if tree.count("apk/miuisettings:showIcon=true") < len(new_ids):
        sys.exit("VERIFY: miuisettings:showIcon=true (boolean) missing")
    for rid in new_ids.values():
        if f"@0x{rid:08x}" not in tree:
            sys.exit(f"VERIFY: icon 0x{rid:08x} not referenced")
    # Wi-Fi screen: identical to the original except the saved_wifi item
    if wifi_entry is None:
        wifi_entry = "-"
    def tree_of(apkp):
        return subprocess.check_output([aapt2, "dump", "xmltree", "--file", wifi_entry, apkp], text=True)
    wo = wp = ""
    if wifi_entry != "-":
        wo, wp = tree_of(orig), tree_of(patched)
    if wifi_entry != "-" and ("SavedAccessPointsSettingsActivity" not in wp or "MiuiSavedAccessPointsWifiSettings" in wp):
        sys.exit("VERIFY: saved_wifi not replaced")
    strip = lambda t: [l.strip().split("(line=")[0] for l in t.splitlines() if "saved_wifi" not in l and "xmlns" not in l and "N: " not in l]
    so, sp = strip(wo), strip(wp)
    extra = [l for l in sp if l not in so]
    print("wifi screen: lines not in original:", len(extra))
    for l in extra:
        print("   ", l[:150])
    if details_entry:
        dump = lambda a: subprocess.check_output([aapt2, "dump", "xmltree", "--file", details_entry, a], text=True)
        do, dp = dump(orig), dump(patched)
        norm = lambda t: [re.sub(r"\(line=\d+\)", "", l).strip().replace("apk/res-auto:", "apk/res/com.android.settings:")
                          for l in t.splitlines() if "N: " not in l]
        no, np_ = norm(do), norm(dp)
        extra = [l for l in np_ if l not in no]
        missing = [l for l in no if l not in np_]
        print("wifi details: added lines:", len(extra), "missing:", len(missing))
        for l in extra:
            print("   +", l[:140])
        if missing or len(extra) != 3 or dp.count('key(0x010101e8)="ryu_hidden_') != 3:
            sys.exit("VERIFY: wifi details changed unexpectedly")
    zo, zp = zipfile.ZipFile(orig), zipfile.ZipFile(patched)
    po = {i.filename: (i.CRC, i.compress_type) for i in zo.infolist()}
    for i in zp.infolist():
        if i.filename in po and i.filename not in ("resources.arsc", xml_entry, wifi_entry, details_entry) and po[i.filename] != (i.CRC, i.compress_type):
            sys.exit(f"VERIFY: entry {i.filename} changed")
    if zp.testzip() is not None:
        sys.exit("VERIFY: zip test failed")
    for i in zp.infolist():
        if i.compress_type == 0 and i.filename == "resources.arsc":
            with open(patched, "rb") as f:
                f.seek(i.header_offset + 26)
                nl, xl = struct.unpack("<HH", f.read(4))
            if (i.header_offset + 30 + nl + xl) % 4:
                sys.exit("VERIFY: resources.arsc not 4-byte aligned")
    if apk_patch.signing_block(open(patched, "rb").read()) != apk_patch.signing_block(open(orig, "rb").read()):
        sys.exit("VERIFY: signing block differs")
    print("VERIFY OK: all original resources unchanged,", len(new_ids), "drawables added")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("settings_apk")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    ap.add_argument("--stock-saved-wifi", action="store_true",
                    help="Wi-Fi > Saved networks opens the stock Android screen. Off by default: on "
                         "HyperOS 3 its network details crash (Compose: ViewTreeLifecycleOwner not found) "
                         "for every network except the connected one")
    args = ap.parse_args()
    work, out = os.path.abspath(args.work), os.path.abspath(args.out)
    os.makedirs(work, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    apk = os.path.abspath(args.settings_apk)
    apktool, signer, aapt2, mdi = tools(work)

    md5 = hashlib.md5(open(apk, "rb").read()).hexdigest()
    dec = os.path.join(work, "dec_" + md5[:8])
    if not os.path.exists(os.path.join(dec, "apktool.yml")):
        run(["java", "-jar", apktool, "d", "-s", "-f", "-o", dec, apk])
    res = parse_dump(subprocess.check_output([aapt2, "dump", "resources", apk], text=True))
    id2name = {v[0]: k for k, v in res.items()}
    framework = os.path.expanduser("~/.local/share/apktool/framework/1.apk")

    # ---- screen XML ----
    def load_xml(resname):
        rid = res[resname][0]
        src = None
        for cand in (f"{resname.split('/')[1]}.xml", f"APKTOOL_DUMMYVAL_0x{rid:08x}.xml"):
            p = os.path.join(dec, "res", "xml", cand)
            if os.path.exists(p):
                src = p
        if not src:
            sys.exit(f"decoded {resname} not found")
        text = open(src, encoding="utf-8").read()
        text = re.sub(r"@(?!android:)(\w+)/([\w.]+)", fix_ref, text)
        return text.replace('xmlns:settings="http://schemas.android.com/apk/res-auto"',
                            f'xmlns:settings="http://schemas.android.com/apk/res/{TARGET_PKG}"')

    def fix_ref(m):
        typ, name = m.group(1), m.group(2)
        if name.startswith("APKTOOL_DUMMYVAL_"):
            name = id2name[int(name[len("APKTOOL_DUMMYVAL_"):], 16)].split("/", 1)[1]
        if f"{typ}/{name}" not in res:
            sys.exit(f"unresolved reference @{typ}/{name}")
        return f"@*{TARGET_PKG}:{typ}/{name}"  # "*": allow private resources

    xml = load_xml(SCREEN)

    # ---- Wi-Fi > Advanced: "Saved networks" opens the stock Android activity (optional) ----
    wifi = details = None
    if args.stock_saved_wifi:
        wifi = load_xml(WIFI_SCREEN)
        pat = re.compile(r'<com\.android\.settingslib\.miuisettings\.preference\.Preference ([^>]*?)android:key="saved_wifi"([^>]*?)/>')
        m = pat.search(wifi)
        if not m:
            sys.exit("saved_wifi preference not found in " + WIFI_SCREEN)
        title = re.search(r'android:title="([^"]+)"', m.group(0)).group(1)
        wifi = wifi[:m.start()] + (
            f'<com.android.settingslib.miuisettings.preference.ValuePreference android:title="{title}" android:key="saved_wifi">'
            f'<intent android:targetPackage="{TARGET_PKG}" android:action="android.intent.action.MAIN" '
            f'android:targetClass="{SAVED_WIFI_ACTIVITY}" />'
            '</com.android.settingslib.miuisettings.preference.ValuePreference>') + wifi[m.end():]
        manifest = subprocess.check_output([aapt2, "dump", "xmltree", "--file", "AndroidManifest.xml", apk], text=True)
        if f'"{SAVED_WIFI_ACTIVITY}"' not in manifest:
            sys.exit(SAVED_WIFI_ACTIVITY + " missing in AndroidManifest")
        # The stock network details page has three Compose items (privacy_settings,
        # certificate_details, server_name).  In the miuix activity a ComposeView crashes
        # (ViewTreeLifecycleOwner not found) as soon as it is laid out.  Their controllers
        # need the preferences to exist, so each one is put into its own hidden category:
        # found by the controller, never shown, never laid out.
        details = load_xml(WIFI_DETAILS)
        cpat = re.compile(r'<com\.android\.settings\.spa\.preference\.ComposePreference [^>]*?android:key="(\w+)"[^>]*?/>')
        wrapped = []

        def hide(mm):
            wrapped.append(mm.group(1))
            return (f'<PreferenceCategory android:key="ryu_hidden_{mm.group(1)}" settings:isPreferenceVisible="false">'
                    + mm.group(0) + '</PreferenceCategory>')
        details = cpat.sub(hide, details)
        if sorted(wrapped) != ["certificate_details", "privacy_settings", "server_name"]:
            sys.exit(f"unexpected Compose items in {WIFI_DETAILS}: {wrapped}")

    keys = re.findall(r'android:key="([\w.]+)"', xml)
    wanted = [k for k in keys if k in ICONS]
    missing = [k for k in keys if k not in ICONS and not k.endswith(("_section", "_category")) and k != "usersAndAccounts"]
    if missing:
        print("WARNING: no icon defined for keys:", missing)
    new_icons = [k for k in wanted if not ICONS[k][0].startswith("@existing:")]
    slot_of = {k: "ryu_icon_" + k for k in new_icons}

    def add_icon(m):
        tag, key = m.group(0), m.group(1)
        if key not in ICONS or "android:icon=" in tag:
            return tag
        icon = ICONS[key][0]
        if icon.startswith("@existing:"):
            dname = icon.split(":", 1)[1]
            if f"drawable/{dname}" not in res:
                sys.exit(f"drawable {dname} missing in target")
            ref = f"@{TARGET_PKG}:drawable/{dname}"
        else:
            ref = f"@drawable/{slot_of[key]}"  # own resource, patched to a dynamic ref below
        # miuisettings Preference hides the icon unless miuisettings:showIcon="true"
        return tag.replace(f'android:key="{key}"',
                           f'android:icon="{ref}" miuisettings:showIcon="true" android:key="{key}"', 1)

    xml = re.sub(r'<com\.android\.settingslib[^>]*?android:key="([\w.]+)"[^>]*>', add_icon, xml)
    if "xmlns:miuisettings=" not in xml:
        xml = xml.replace("<PreferenceScreen", '<PreferenceScreen xmlns:miuisettings="http://schemas.android.com/apk/miuisettings"', 1)

    # ---- overlay sources ----
    ov = os.path.join(work, "overlay")
    shutil.rmtree(ov, ignore_errors=True)
    os.makedirs(os.path.join(ov, "res", "xml"))
    os.makedirs(os.path.join(ov, "res", "drawable"))
    open(os.path.join(ov, "res", "xml", SCREEN.split("/")[1] + ".xml"), "w", encoding="utf-8").write(xml)
    if wifi:
        open(os.path.join(ov, "res", "xml", WIFI_SCREEN.split("/")[1] + ".xml"), "w", encoding="utf-8").write(wifi)
        open(os.path.join(ov, "res", "xml", WIFI_DETAILS.split("/")[1] + ".xml"), "w", encoding="utf-8").write(details)
    glyphs = mdi_paths(mdi, {ICONS[k][0] for k in new_icons})
    for k in new_icons:
        name, color = ICONS[k]
        open(os.path.join(ov, "res", "drawable", slot_of[k] + ".xml"), "w").write(vector(color, glyphs[name]))
    open(os.path.join(ov, "AndroidManifest.xml"), "w").write(f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{OVERLAY_PKG}"
    android:versionCode="{VERSION_CODE}" android:versionName="{VERSION}">
    <uses-sdk android:minSdkVersion="34" android:targetSdkVersion="34" />
    <overlay android:targetPackage="{TARGET_PKG}" android:isStatic="true" android:priority="777" />
    <application android:hasCode="false" />
</manifest>
""")

    # ---- compile / link / sign ----
    flat = os.path.join(work, "compiled.zip")
    unsigned = os.path.join(work, "overlay-unsigned.apk")
    run([aapt2, "compile", "--dir", os.path.join(ov, "res"), "-o", flat])
    run([aapt2, "link", "-o", unsigned, "--manifest", os.path.join(ov, "AndroidManifest.xml"),
         "-I", framework, "-I", apk, "--package-id", "0x7e", "--allow-reserved-package-id",
         "--no-auto-version", "--no-resource-deduping", "--no-resource-removal", flat])
    # ---- patch Settings.apk itself ----
    xml_entry = f"res/xml/{SCREEN.split('/')[1]}.xml"
    wifi_entry = f"res/xml/{WIFI_SCREEN.split('/')[1]}.xml"
    details_entry = f"res/xml/{WIFI_DETAILS.split('/')[1]}.xml"
    donor = zipfile.ZipFile(unsigned)
    ddump = parse_dump(subprocess.check_output([aapt2, "dump", "resources", unsigned], text=True))
    files = [(slot_of[k], f"res/drawable/{slot_of[k]}.xml") for k in new_icons]
    src = open(apk, "rb").read()
    with zipfile.ZipFile(apk) as zapk:
        arsc = zapk.read("resources.arsc")
        names_in_apk = set(zapk.namelist())
    for _, path in files:
        if path in names_in_apk:
            sys.exit(f"{path} already exists in Settings.apk")
    new_arsc, new_ids = apk_patch.arsc_add_files(arsc, "drawable", files)
    mapping = {ddump["drawable/" + n][0]: new_ids[n] for n, _ in files}
    new_xml, n = apk_patch.xml_retarget_refs(donor.read(xml_entry), mapping)
    if n != len(new_icons):
        sys.exit(f"expected {len(new_icons)} retargeted icon references, got {n}")
    patched = apk_patch.rebuild_zip(
        src,
        replace=dict({"resources.arsc": new_arsc, xml_entry: new_xml},
                     **({wifi_entry: donor.read(wifi_entry), details_entry: donor.read(details_entry)} if wifi else {})),
        add=[(path, donor.read(path)) for _, path in files])
    patched_path = os.path.join(work, "Settings.apk")
    open(patched_path, "wb").write(patched)
    verify(aapt2, apk, patched_path, new_ids, xml_entry, wifi_entry if wifi else None,
           details_entry if wifi else None)
    patched_md5 = hashlib.md5(patched).hexdigest()

    # ---- module ----
    mod = os.path.join(work, "module")
    shutil.rmtree(mod, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "module"), mod)
    os.makedirs(os.path.join(mod, "apk"))
    shutil.copy(patched_path, os.path.join(mod, "apk", "Settings.apk"))
    open(os.path.join(mod, "settings_md5"), "w").write(md5 + "\n")
    open(os.path.join(mod, "patched_md5"), "w").write(patched_md5 + "\n")
    prop = open(os.path.join(mod, "module.prop")).read()
    prop = prop.replace("@VERSION@", VERSION).replace("@VERSION_CODE@", str(VERSION_CODE))
    open(os.path.join(mod, "module.prop"), "w").write(prop)
    zpath = os.path.join(out, f"{MODULE_ID}-v{VERSION}-{md5[:8]}.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, fl in os.walk(mod):
            for f in fl:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, mod))
    print("\nicons:", len(wanted), "(new:", len(new_icons), ")")
    print("module:", zpath)


if __name__ == "__main__":
    main()
