#!/usr/bin/env python3
"""Build "Ryu Display AI": show Settings > Display > "Screen enhancement engine".

HyperOS Settings (ScreenEnhanceEngineStatusCheck) hides the whole engine unless
FeatureParser "support_screen_enhance_engine" is true; AI display and SR for images
need "support_AI_display" / "support_SR_for_image_display".  The global
/product/etc/device_features/popsicle.xml has none of them, while the drivers for
MEMC (ro.vendor.media.video.frc.support), SR for video
(debug.config.media.video.ais.support) and SDR->HDR (ro.vendor.video_box.version=2)
are present.  This module bind-mounts a copy of popsicle.xml with the three flags
added (nothing else changes).

Usage: python3 build.py /path/to/popsicle.xml [--out DIR]
"""
import argparse, hashlib, os, shutil, sys, zipfile
import xml.dom.minidom

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "/product/etc/device_features/popsicle.xml"
VERSION, VERSION_CODE = "1.0", 1
FLAGS = ["support_screen_enhance_engine", "support_AI_display", "support_SR_for_image_display"]
ANCHOR = "<!-- Display END -->"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    a = ap.parse_args()
    raw = open(a.original, "rb").read()
    text = raw.decode("utf-8")
    for f in FLAGS:
        if f'name="{f}"' in text:
            sys.exit(f"{f} already present, nothing to do")
    if text.count(ANCHOR) != 1:
        sys.exit("anchor not found")
    add = "    <!-- Ryu Display AI: screen enhancement engine -->\n" + "".join(
        f'    <bool name="{f}">true</bool>\n' for f in FLAGS)
    new = text.replace(ANCHOR, add + ANCHOR)
    xml.dom.minidom.parseString(new.encode())  # must stay valid XML
    assert new.replace(add, "") == text
    work = os.path.join(HERE, "work")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "module"), work)
    os.makedirs(os.path.join(work, "files"))
    nb = new.encode()
    open(os.path.join(work, "files", os.path.basename(TARGET)), "wb").write(nb)
    open(os.path.join(work, "orig_md5"), "w").write(hashlib.md5(raw).hexdigest() + "\n")
    open(os.path.join(work, "patched_md5"), "w").write(hashlib.md5(nb).hexdigest() + "\n")
    open(os.path.join(work, "target_path"), "w").write(TARGET + "\n")
    p = os.path.join(work, "module.prop")
    open(p, "w").write(open(p).read().replace("@VERSION@", VERSION).replace("@VERSION_CODE@", str(VERSION_CODE)))
    os.makedirs(a.out, exist_ok=True)
    z = os.path.join(a.out, f"ryu_display_ai-v{VERSION}-{hashlib.md5(raw).hexdigest()[:8]}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(work):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, work))
    print("added:", ", ".join(FLAGS))
    print("module:", z)


if __name__ == "__main__":
    main()
