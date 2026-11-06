#!/usr/bin/env python3
"""Build the "Ryu Other Settings Icons" KernelSU/Magisk module.

Adds HyperOS-style icons to Settings -> "Additional settings"
(xml/other_personal_settings) through a static RRO overlay.

How it works
------------
The overlay replaces xml/other_personal_settings with a copy that has an
android:icon on every entry.  The replaced XML is parsed with the overlay's
dynamic reference table, so:
  * the overlay is compiled as package 0x7e (not 0x7f) -> every reference to
    com.android.settings (0x7f: strings, attrs, existing drawables) stays an
    absolute, valid id;
  * references to the overlay's own icon drawables are rewritten in the binary
    XML to TYPE_DYNAMIC_REFERENCE, which the runtime translates to the package
    id the overlay is actually loaded with.

Because the result depends on resource ids, the module must be rebuilt for
every firmware.  The module refuses to install / disables itself when the
Settings.apk on the device differs from the one it was built for.

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

TARGET_PKG = "com.android.settings"
OVERLAY_PKG = "com.ryu.settings.othericons.overlay"
OVERLAY_APK = "RyuOtherSettingsIcons.apk"
SCREEN = "xml/other_personal_settings"
MODULE_ID = "ryu_other_settings_icons"
VERSION = "1.0"
VERSION_CODE = 1

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("settings_apk")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
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
    sid = res[SCREEN][0]
    src = None
    for cand in (f"{SCREEN.split('/')[1]}.xml", f"APKTOOL_DUMMYVAL_0x{sid:08x}.xml"):
        p = os.path.join(dec, "res", "xml", cand)
        if os.path.exists(p):
            src = p
    if not src:
        sys.exit("decoded screen xml not found")
    xml = open(src, encoding="utf-8").read()

    def fix_ref(m):
        typ, name = m.group(1), m.group(2)
        if name.startswith("APKTOOL_DUMMYVAL_"):
            name = id2name[int(name[len("APKTOOL_DUMMYVAL_"):], 16)].split("/", 1)[1]
        if f"{typ}/{name}" not in res:
            sys.exit(f"unresolved reference @{typ}/{name}")
        return f"@{TARGET_PKG}:{typ}/{name}"

    xml = re.sub(r"@(?!android:)(\w+)/([\w.]+)", fix_ref, xml)
    xml = xml.replace('xmlns:settings="http://schemas.android.com/apk/res-auto"',
                      f'xmlns:settings="http://schemas.android.com/apk/res/{TARGET_PKG}"')

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
        return tag.replace(f'android:key="{key}"', f'android:icon="{ref}" android:key="{key}"', 1)

    xml = re.sub(r'<com\.android\.settingslib[^>]*?android:key="([\w.]+)"[^>]*>', add_icon, xml)

    # ---- overlay sources ----
    ov = os.path.join(work, "overlay")
    shutil.rmtree(ov, ignore_errors=True)
    os.makedirs(os.path.join(ov, "res", "xml"))
    os.makedirs(os.path.join(ov, "res", "drawable"))
    open(os.path.join(ov, "res", "xml", SCREEN.split("/")[1] + ".xml"), "w", encoding="utf-8").write(xml)
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
    xml_entry = f"res/xml/{SCREEN.split('/')[1]}.xml"
    patched_apk = unsigned.replace(".apk", "-patched.apk")
    with zipfile.ZipFile(unsigned) as zin, zipfile.ZipFile(patched_apk, "w") as zout:
        for item in zin.infolist():
            blob = zin.read(item.filename)
            if item.filename == xml_entry:
                blob, n = patch_dynamic_refs(blob, 0x7e)
                print(f"patched {n} own references to dynamic references")
                if n != len(new_icons):
                    sys.exit(f"expected {len(new_icons)} patched references, got {n}")
            zout.writestr(item, blob)
    unsigned = patched_apk
    sdir = os.path.join(work, "signed")
    shutil.rmtree(sdir, ignore_errors=True)
    run(["java", "-jar", signer, "-a", unsigned, "-o", sdir, "--allowResign"])
    signed = glob.glob(os.path.join(sdir, "*.apk"))[0]

    # ---- module ----
    mod = os.path.join(work, "module")
    shutil.rmtree(mod, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "module"), mod)
    odir = os.path.join(mod, "system", "product", "overlay")
    os.makedirs(odir)
    shutil.copy(signed, os.path.join(odir, OVERLAY_APK))
    open(os.path.join(mod, "settings_md5"), "w").write(md5 + "\n")
    prop = open(os.path.join(mod, "module.prop")).read()
    prop = prop.replace("@VERSION@", VERSION).replace("@VERSION_CODE@", str(VERSION_CODE))
    open(os.path.join(mod, "module.prop"), "w").write(prop)
    zpath = os.path.join(out, f"{MODULE_ID}-v{VERSION}-{md5[:8]}.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(mod):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, mod))
    print("\nicons:", len(wanted), "(new:", len(new_icons), ")")
    print("module:", zpath)


if __name__ == "__main__":
    main()
