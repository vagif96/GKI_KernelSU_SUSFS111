#!/usr/bin/env python3
"""Build "Ryu App FPS": per-app refresh rate (60/90/120 Hz) on HyperOS 3.

PowerKeeper (com.miui.powerkeeper) already supports per-app refresh rate groups
(fps_group: list60/list90/list120, used when "isSmart" is false), but it rewrites
fps_group from the Xiaomi cloud/local config on every start.  The patch adds a few
instructions to DisplayFrameSetting.parseTopDefineAppFromDb(): if PowerKeeper's
misc settings contain "ryu_fps_group", that JSON is used instead.  Nothing else in
the APK changes (only classes.dex is replaced; META-INF and resources stay).

The WebUI (module/webroot) writes ryu_fps_group through
`content call --uri content://com.miui.powerkeeper.configure --method PUT_misc`
and restarts PowerKeeper.

Usage: python3 build.py /path/to/PowerKeeper.apk [--out DIR]
"""
import argparse, hashlib, os, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ryu_settings_icons"))
import apk_patch  # noqa: E402

VERSION, VERSION_CODE = "1.0", 1
APKTOOL_URL = "https://github.com/iBotPeaches/Apktool/releases/download/v2.10.0/apktool_2.10.0.jar"
SMALI = "smali/com/miui/powerkeeper/statemachine/DisplayFrameSetting.smali"
INJECT = '''    :goto_1
    # RYU: user per-app refresh rate config (PowerKeeper misc key "ryu_fps_group") overrides cloud/local
    iget-object v0, v1, Lcom/miui/powerkeeper/statemachine/DisplayFrameSetting;->mContext:Landroid/content/Context;
    const-string v4, "ryu_fps_group"
    const/4 v6, 0x0
    invoke-static {v0, v4, v6}, Lcom/miui/powerkeeper/provider/SimpleSettings$Misc;->getString(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    if-eqz v0, :cond_ryu_skip
    invoke-virtual {v0}, Ljava/lang/String;->isEmpty()Z
    move-result v4
    if-nez v4, :cond_ryu_skip
    move-object v3, v0
    const-string v4, "parseTopDefineAppFromDb ryu override = "
    invoke-virtual {v4, v0}, Ljava/lang/String;->concat(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v4
    invoke-direct {v1, v4}, Lcom/miui/powerkeeper/statemachine/DisplayFrameSetting;->writeLocalLog(Ljava/lang/String;)V
    :cond_ryu_skip
'''


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("powerkeeper_apk")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    a = ap.parse_args()
    work, apk = os.path.abspath(a.work), os.path.abspath(a.powerkeeper_apk)
    os.makedirs(work, exist_ok=True)
    apktool = os.path.join(work, "apktool.jar")
    if not os.path.exists(apktool):
        run(["curl", "-fsSL", "-o", apktool, APKTOOL_URL])
    src = open(apk, "rb").read()
    md5 = hashlib.md5(src).hexdigest()

    dec = os.path.join(work, "dec")
    shutil.rmtree(dec, ignore_errors=True)
    run(["java", "-jar", apktool, "d", "-f", "-r", "-o", dec, apk])
    p = os.path.join(dec, SMALI)
    s = open(p).read()
    a0 = s.index(".method private parseTopDefineAppFromDb(")
    b0 = s.index(".end method", a0)
    m = s[a0:b0]
    if m.count("    :goto_1\n") != 1 or "fps_group" not in m:
        sys.exit("parseTopDefineAppFromDb has an unexpected shape, not patching")
    open(p, "w").write(s[:a0] + m.replace("    :goto_1\n", INJECT, 1) + s[b0:])
    built = os.path.join(work, "built.apk")
    run(["java", "-jar", apktool, "b", "-o", built, dec])
    with zipfile.ZipFile(built) as z:
        dexes = [n for n in z.namelist() if n.startswith("classes") and n.endswith(".dex")]
        if dexes != ["classes.dex"]:
            sys.exit(f"unexpected dex files {dexes}")
        dex = z.read("classes.dex")
    with zipfile.ZipFile(apk) as z:
        if [n for n in z.namelist() if n.endswith(".dex")] != ["classes.dex"]:
            sys.exit("original has more than one dex")
    patched = apk_patch.rebuild_zip(src, replace={"classes.dex": dex}, add=[])
    # sanity: every other entry identical
    zo, zp = zipfile.ZipFile(apk), zipfile.ZipFile(__import__("io").BytesIO(patched))
    for i in zo.infolist():
        j = zp.getinfo(i.filename)
        if i.filename != "classes.dex" and (i.CRC, i.compress_type) != (j.CRC, j.compress_type):
            sys.exit(f"entry {i.filename} changed")
    if zp.testzip() is not None:
        sys.exit("zip test failed")

    mod = os.path.join(work, "module")
    shutil.rmtree(mod, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "module"), mod)
    os.makedirs(os.path.join(mod, "apk"))
    open(os.path.join(mod, "apk", "PowerKeeper.apk"), "wb").write(patched)
    open(os.path.join(mod, "orig_md5"), "w").write(md5 + "\n")
    open(os.path.join(mod, "patched_md5"), "w").write(hashlib.md5(patched).hexdigest() + "\n")
    mp = os.path.join(mod, "module.prop")
    prop = open(mp).read().replace("@VERSION@", VERSION).replace("@VERSION_CODE@", str(VERSION_CODE))
    if not prop.startswith("id="):
        sys.exit("module.prop broken")
    open(mp, "w").write(prop)
    os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(a.out, f"ryu_app_fps-v{VERSION}-{md5[:8]}.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(mod):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, mod))
    print("module:", zpath)


if __name__ == "__main__":
    main()
