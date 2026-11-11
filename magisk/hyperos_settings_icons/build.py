#!/usr/bin/env python3
"""Build "HyperOS Settings Icons": a module that patches the Settings.apk installed
on the phone itself (no Settings.apk of the target firmware is needed here).

Contents of the module:
  bin/ryu_patch   static arm64 patcher (Go, ./patcher)
  icons/*.xml     precompiled vector drawables (binary XML, android: attributes only,
                  so they do not depend on the firmware)
  icons/map.txt   preference key -> drawable [existing drawable of Settings to prefer]

Usage: python3 build.py [--out DIR]
Needs: go, java (aapt2 from apktool), node+npm (@mdi/js).  Uses the helpers of
../ryu_settings_icons/build.py.
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ryu_settings_icons"))
import build as sib  # noqa: E402
from icons import ICONS, BLUE, GRAY, GREEN, ORANGE, PURPLE, RED, TEAL, YELLOW  # noqa: E402

MODULE_ID = "hyperos_settings_icons"
VERSION, VERSION_CODE = "1.6", 7

# Entries that other HyperOS builds / devices may have on this screen
EXTRA = {
    "accessibility_settings": ("mdiHumanHandsup", BLUE),
    "key_settings": ("mdiGestureTapButton", ORANGE),
    "button_settings": ("mdiGestureTapButton", ORANGE),
    "gesture_settings": ("mdiGesture", PURPLE),
    "fullscreen_display": ("mdiGesture", PURPLE),
    "quick_ball": ("mdiCircleDouble", TEAL),
    "touch_assistant": ("mdiCircleDouble", TEAL),
    "one_handed_mode": ("mdiCellphoneArrowDown", GREEN),
    "print_settings": ("mdiPrinter", GRAY),
    "printing_settings": ("mdiPrinter", GRAY),
    "privacy_password": ("mdiLock", BLUE),
    "backup_and_reset": ("mdiBackupRestore", GREEN),
    "headset_settings": ("mdiHeadphones", TEAL),
    "keyboard_settings": ("mdiKeyboard", GRAY),
    "fingerprint_settings": ("mdiFingerprint", RED),
    "power_usage_summary": ("mdiBattery", GREEN),
    "privacy_settings": ("mdiShieldLock", BLUE),
    "manage_apps": ("mdiApplicationCog", ORANGE),
}
USER_FALLBACK = ("mdiAccountMultiple", BLUE)  # if ic_multiple_users is missing
DEFAULT = ("mdiCog", GRAY)                     # any entry without its own icon


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    ap.add_argument("--powerkeeper", help="PowerKeeper.apk of the target phone (per-app refresh rate part)")
    ap.add_argument("--misettings", help="MiSettings.apk of the target phone")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    os.makedirs(work, exist_ok=True)
    _, _, aapt2, mdi = sib.tools(work)
    framework = os.path.expanduser("~/.local/share/apktool/framework/1.apk")
    if not os.path.exists(framework):
        sys.exit("android framework (apktool 1.apk) not found: run apktool once (apktool if framework-res.apk)")

    table = {}   # file base -> (mdi name, colour)
    rows = []    # map.txt lines
    for key, (icon, color) in list(ICONS.items()) + list(EXTRA.items()):
        if icon.startswith("@existing:"):
            table[key] = USER_FALLBACK
            rows.append(f"{key} {key}.xml {icon.split(':', 1)[1]}")
        else:
            table[key] = (icon, color)
            rows.append(f"{key} {key}.xml")
    table["_default"] = DEFAULT
    rows.append("* _default.xml")

    # ---- compile the drawables ----
    proj = os.path.join(work, "drawables")
    shutil.rmtree(proj, ignore_errors=True)
    os.makedirs(os.path.join(proj, "res", "drawable"))
    glyphs = sib.mdi_paths(mdi, {v[0] for v in table.values()})
    for base, (icon, color) in table.items():
        with open(os.path.join(proj, "res", "drawable", f"{base}.xml"), "w") as f:
            f.write(sib.vector(color, glyphs[icon]))
    with open(os.path.join(proj, "AndroidManifest.xml"), "w") as f:
        f.write('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.ryu.icons">'
                '<application android:hasCode="false"/></manifest>')
    flat = os.path.join(work, "drawables.zip")
    apk = os.path.join(work, "drawables.apk")
    sib.run([aapt2, "compile", "--dir", os.path.join(proj, "res"), "-o", flat])
    sib.run([aapt2, "link", "-o", apk, "--manifest", os.path.join(proj, "AndroidManifest.xml"),
             "-I", framework, "--no-auto-version", "--no-resource-deduping", flat])

    # ---- patcher ----
    mod = os.path.join(work, "module")
    shutil.rmtree(mod, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "module"), mod)
    os.makedirs(os.path.join(mod, "bin"))
    os.makedirs(os.path.join(mod, "icons"))
    env = dict(os.environ, GOOS="linux", GOARCH="arm64", CGO_ENABLED="0")
    sib.run(["go", "build", "-trimpath", "-ldflags", "-s -w", "-o", os.path.join(mod, "bin", "ryu_patch"), "."],
            cwd=os.path.join(HERE, "patcher"), env=env)

    with zipfile.ZipFile(apk) as z:
        for base in table:
            data = z.read(f"res/drawable/{base}.xml")
            if data[:2] != b"\x03\x00":
                sys.exit(f"{base}: not binary XML")
            # firmware independence: only framework (0x01......) resource ids
            dump = subprocess.check_output([aapt2, "dump", "xmltree", "--file", f"res/drawable/{base}.xml", apk], text=True)
            if "@0x" in dump or "(0x7" in dump:
                sys.exit(f"{base}: references app resources")
            open(os.path.join(mod, "icons", f"{base}.xml"), "wb").write(data)
    open(os.path.join(mod, "icons", "map.txt"), "w").write(
        "# preference key, drawable, [existing Settings drawable used instead if present]\n" + "\n".join(rows) + "\n")

    if a.powerkeeper and a.misettings:
        h_out = os.path.join(work, "hz_out")
        shutil.rmtree(h_out, ignore_errors=True)
        sib.run([sys.executable, os.path.join(HERE, "..", "ryu_hz", "build.py"), "--powerkeeper", a.powerkeeper,
                 "--misettings", a.misettings, "--out", h_out, "--work", os.path.join(work, "hz")])
        info = {l.split()[0]: dict(kv.split("=") for kv in l.split(" :: ")[0].split()[1:3])
                for l in open(os.path.join(h_out, "info.txt"))}
        for name, apk, pkg in (("powerkeeper", "PowerKeeper", "com.miui.powerkeeper"),
                               ("misettings", "MiSettings", "com.xiaomi.misettings")):
            pp = os.path.join(mod, "parts", name)
            os.makedirs(pp)
            shutil.copy(os.path.join(h_out, apk + ".apk"), os.path.join(pp, "file"))
            open(os.path.join(pp, "orig_md5"), "w").write(info[apk]["orig"] + "\n")
            open(os.path.join(pp, "patched_md5"), "w").write(info[apk]["patched"] + "\n")
            open(os.path.join(pp, "package"), "w").write(pkg + "\n")
    prop = open(os.path.join(mod, "module.prop")).read()
    prop = prop.replace("@VERSION@", VERSION).replace("@VERSION_CODE@", str(VERSION_CODE))
    open(os.path.join(mod, "module.prop"), "w").write(prop)
    os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(os.path.abspath(a.out), f"{MODULE_ID}-v{VERSION}.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, fl in os.walk(mod):
            for f in sorted(fl):
                full = os.path.join(root, f)
                info = zipfile.ZipInfo.from_file(full, os.path.relpath(full, mod))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o755 if f == "ryu_patch" or f.endswith(".sh") else 0o644) << 16
                z.writestr(info, open(full, "rb").read())
    print("icons:", len(table), " module:", zpath)


if __name__ == "__main__":
    main()
