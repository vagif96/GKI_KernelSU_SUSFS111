#!/usr/bin/env python3
"""Build the "Ryu BT Volume" module.

HyperOS loads volume curves from /odm/etc/audio_policy_engine_stream_volumes_mi.xml.
For music it has EU ("_CE") curves that attenuate Bluetooth/headphone audio by up to
-6.5 dB (A2DP_CE) / -11.9 dB (A2DP_SPATIALIZER_CE) at max volume, and a HEADSET curve
ending at -2.9 dB.  This replaces those music curves with Xiaomi's own non-EU
Bluetooth curve (DEVICE_CATEGORY_A2DP, max -0.5 dB) and USB_CE with USB.

Only attenuation is reduced (no curve goes above 0 dB), so there is no digital
gain / clipping.  Everything else in the file is unchanged.

Usage: python3 build.py /path/to/audio_policy_engine_stream_volumes_mi.xml [--out DIR]
"""
import argparse, hashlib, os, re, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "/odm/etc/audio_policy_engine_stream_volumes_mi.xml"
VERSION, VERSION_CODE = "1.0", 1
# music category -> category whose curve it gets
REPLACE = {
    "DEVICE_CATEGORY_HEADSET": "DEVICE_CATEGORY_A2DP",
    "DEVICE_CATEGORY_A2DP_CE": "DEVICE_CATEGORY_A2DP",
    "DEVICE_CATEGORY_A2DP_SPATIALIZER_CE": "DEVICE_CATEGORY_A2DP",
    "DEVICE_CATEGORY_HEADSET_CE": "DEVICE_CATEGORY_A2DP",
    "DEVICE_CATEGORY_HEADSET_SPATIALIZER_CE": "DEVICE_CATEGORY_A2DP",
    "DEVICE_CATEGORY_USB_CE": "DEVICE_CATEGORY_USB",
    "DEVICE_CATEGORY_USB_SPATIALIZER_CE": "DEVICE_CATEGORY_USB",
}
VOL_RE = re.compile(r'(<volume deviceCategory="(\w+)">)(.*?)(</volume>)', re.S)


def points(body):
    return [tuple(map(int, p.split(","))) for p in re.findall(r"<point>\s*([-\d]+\s*,\s*[-\d]+)\s*</point>", body)]


def patch(text):
    m = re.search(r"<volumeGroup>\s*<name>music</name>.*?</volumeGroup>", text, re.S)
    if not m:
        sys.exit("music volumeGroup not found")
    group = m.group(0)
    curves = {c: body for _, c, body, _ in VOL_RE.findall(group)}
    for src, dst in REPLACE.items():
        if src not in curves or dst not in curves:
            sys.exit(f"curve {src} or {dst} missing in music group")
    changed = []

    def repl(mm):
        cat = mm.group(2)
        if cat in REPLACE:
            changed.append(cat)
            return mm.group(1) + curves[REPLACE[cat]] + mm.group(4)
        return mm.group(0)

    new_group = VOL_RE.sub(repl, group)
    assert sorted(changed) == sorted(REPLACE)
    out = text[:m.start()] + new_group + text[m.end():]
    # safety: no music point above 0 dB, other groups untouched
    for _, cat, body, _ in VOL_RE.findall(new_group):
        if any(att > 0 for _, att in points(body)):
            sys.exit(f"{cat}: positive gain")
    if text[:m.start()] != out[:m.start()] or text[m.end():] != out[m.start() + len(new_group):]:
        sys.exit("unexpected change outside music group")
    return out, curves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    a = ap.parse_args()
    raw = open(a.original, "rb").read()
    text = raw.decode("utf-8")
    new, curves = patch(text)
    for src, dst in REPLACE.items():
        o, n = points(curves[src]), points(curves[dst])
        print(f"{src:40s} max {o[-1][1]/100:+.1f} dB -> {n[-1][1]/100:+.1f} dB")
    work = os.path.join(HERE, "work")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "module"), work)
    os.makedirs(os.path.join(work, "files"))
    newb = new.encode("utf-8")
    open(os.path.join(work, "files", os.path.basename(TARGET)), "wb").write(newb)
    open(os.path.join(work, "orig_md5"), "w").write(hashlib.md5(raw).hexdigest() + "\n")
    open(os.path.join(work, "patched_md5"), "w").write(hashlib.md5(newb).hexdigest() + "\n")
    open(os.path.join(work, "target_path"), "w").write(TARGET + "\n")
    prop = open(os.path.join(work, "module.prop")).read()
    open(os.path.join(work, "module.prop"), "w").write(
        prop.replace("@VERSION@", VERSION).replace("@VERSION_CODE@", str(VERSION_CODE)))
    os.makedirs(a.out, exist_ok=True)
    z = os.path.join(a.out, f"ryu_bt_volume-v{VERSION}-{hashlib.md5(raw).hexdigest()[:8]}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(work):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, work))
    print("module:", z)


if __name__ == "__main__":
    main()
