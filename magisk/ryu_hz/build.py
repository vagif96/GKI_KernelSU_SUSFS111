#!/usr/bin/env python3
"""HyperOS "Apps using high refresh rate" also in the adaptive refresh rate mode.

Xiaomi's own per-app screen (Settings > Display > Refresh rate > "Apps using high
refresh rate": a switch per app, stored in PowerKeeper's highRefreshRateTable) only
exists in the "Custom" (fixed 120/144 Hz) mode.  Two small dex patches make it work
in "Default (recommended)" (adaptive / smart) mode too:

MiSettings  (com.xiaomi.misettings, NewRefreshRateFragment)
    the method that shows/hides the "high_refresh_options" entry is told "show"
    also when smart mode is on (same remaining conditions as Xiaomi's: the feature
    switch custom_mode_switch is set and Performance mode is off).

PowerKeeper (com.miui.powerkeeper, DisplayFrameSetting)
    in smart mode the per-app map used for the foreground app (mTopApps) becomes
    Xiaomi's smart map (mTopSmartApps) + the user's switched-off apps (mCustomApps,
    60 Hz).  Apps left on keep Xiaomi's adaptive behaviour.  updateCustomDataBase
    (called when a switch is flipped) no longer replaces the smart map with the
    custom one in smart mode.

The feature itself is enabled by PowerKeeper misc "custom_switch" =
{"fucSwitch":"true"} (done by the module, no patch needed for that).

Obfuscated names in MiSettings are found by content (is_smart_fps, speed_mode,
custom_mode_switch), so the same script works for other HyperOS 3 builds.

Usage: python3 build.py --powerkeeper PowerKeeper.apk --misettings MiSettings.apk --out DIR
Writes DIR/PowerKeeper.apk, DIR/MiSettings.apk and DIR/info.txt (md5s).
"""
import argparse
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ryu_settings_icons"))
import apk_patch  # noqa: E402

APKTOOL_URL = "https://github.com/iBotPeaches/Apktool/releases/download/v2.10.0/apktool_2.10.0.jar"
DFS = "Lcom/miui/powerkeeper/statemachine/DisplayFrameSetting;"
NRF = "Lcom/xiaomi/misettings/display/RefreshRate/NewRefreshRateFragment;"


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def smali_file(dec, cls):
    rel = cls[1:-1] + ".smali"
    hits = [os.path.join(dec, d, rel) for d in sorted(os.listdir(dec))
            if d.startswith("smali") and os.path.exists(os.path.join(dec, d, rel))]
    if len(hits) != 1:
        sys.exit(f"{cls}: found {len(hits)} times")
    return hits[0]


def methods(text):
    """[(start, end, header)] of every method (end = index after '.end method')."""
    out = []
    for m in re.finditer(r"^\.method [^\n]*$", text, re.M):
        e = text.index(".end method", m.end()) + len(".end method")
        out.append((m.start(), e, m.group(0)))
    return out


def method(text, pattern, must=None):
    found = [(a, b, h) for a, b, h in methods(text) if re.search(pattern, h) and (must is None or must in text[a:b])]
    if len(found) != 1:
        sys.exit(f"method {pattern!r} ({must!r}): found {len(found)}")
    return found[0]


def p0_is_this(body):
    """True if p0 is never written in the method body."""
    return not re.search(r"^\s+(move-result(-object)?|move(-object)?(/from16|/16)?|const[\w/-]*|"
                         r"[ais]get[\w-]*|new-instance|new-array|check-cast|instance-of|"
                         r"array-length|[\w-]+-(int|long|float|double)[\w/]*) p0,", body, re.M)


def first_insn(body):
    """Index (in body) of the first instruction after the .locals line."""
    i = body.index("\n", body.index(".locals")) + 1
    for m in re.finditer(r"^    (\S[^\n]*)$", body[i:], re.M):
        if not m.group(1).startswith((".", "#", ":")):
            return i + m.start()
    sys.exit("no instruction")


# ------------------------------------------------------------------ PowerKeeper

HELPERS = f"""
.method private ryuMerged()Landroid/util/ArrayMap;
    .locals 3

    # RYU: Xiaomi's smart per-app map + the user's switched-off apps (60 Hz)
    new-instance v0, Landroid/util/ArrayMap;

    iget-object v1, p0, {DFS}->mTopSmartApps:Landroid/util/ArrayMap;

    invoke-direct {{v0, v1}}, Landroid/util/ArrayMap;-><init>(Landroid/util/ArrayMap;)V

    const-string v1, "true"

    sget-object v2, {DFS}->mIsCustomFpsSwitch:Ljava/lang/String;

    invoke-virtual {{v1, v2}}, Ljava/lang/Object;->equals(Ljava/lang/Object;)Z

    move-result v1

    if-eqz v1, :ryu_m_done

    iget-object v1, p0, {DFS}->mCustomApps:Landroid/util/ArrayMap;

    if-eqz v1, :ryu_m_done

    invoke-virtual {{v0, v1}}, Landroid/util/ArrayMap;->putAll(Landroid/util/ArrayMap;)V

    :ryu_m_done
    return-object v0
.end method

.method private ryuRefresh()V
    .locals 1

    # RYU: in smart mode keep mTopApps = smart map + user's choices
    sget-boolean v0, {DFS}->mIsSmart:Z

    if-eqz v0, :ryu_r_done

    invoke-direct {{p0}}, {DFS}->ryuMerged()Landroid/util/ArrayMap;

    move-result-object v0

    iput-object v0, p0, {DFS}->mTopApps:Landroid/util/ArrayMap;

    :ryu_r_done
    return-void
.end method
"""

REFRESH = f"    invoke-direct/range {{p0 .. p0}}, {DFS}->ryuRefresh()V\n\n    return-void"


def refresh_before_returns(text, pattern):
    a, b, h = method(text, pattern)
    body = text[a:b]
    if not p0_is_this(body):
        sys.exit(f"{h}: p0 is reassigned, cannot call ryuRefresh")
    n = body.count("\n    return-void")
    if n == 0:
        sys.exit(f"{h}: no return-void")
    body = body.replace("\n    return-void", "\n" + REFRESH)
    return text[:a] + body + text[b:], n


def patch_powerkeeper_smali(text):
    if "ryuMerged" in text:
        sys.exit("PowerKeeper already patched")
    for f in ("mTopSmartApps:Landroid/util/ArrayMap;", "mTopApps:Landroid/util/ArrayMap;",
              "mCustomApps:Landroid/util/ArrayMap;", "mIsCustomFpsSwitch:Ljava/lang/String;", "mIsSmart:Z"):
        if f".field " not in text or not re.search(r"^\.field [^\n]*" + re.escape(f), text, re.M):
            sys.exit(f"field {f} missing")
    log = []
    # 1. parseInit: smart mode starts with the merged map
    a, b, h = method(text, r" parseInit\(\)V$")
    body = text[a:b]
    pat = re.compile(r"(    )iget-object (v\d+), p0, " + re.escape(DFS) + r"->mTopSmartApps:Landroid/util/ArrayMap;\n\n"
                     r"    iput-object \2, p0, " + re.escape(DFS) + r"->mTopApps:Landroid/util/ArrayMap;")
    body, n = pat.subn(lambda m: f"    invoke-direct/range {{p0 .. p0}}, {DFS}->ryuMerged()Landroid/util/ArrayMap;\n\n"
                       f"    move-result-object {m.group(2)}\n\n"
                       f"    iput-object {m.group(2)}, p0, {DFS}->mTopApps:Landroid/util/ArrayMap;", body)
    if n != 1 or not p0_is_this(body):
        sys.exit(f"parseInit: {n} smart assignments")
    text = text[:a] + body + text[b:]
    log.append("parseInit")
    # 2. synthetic setter of mTopApps (used when the mode changes)
    setters = [(a, b, h) for a, b, h in methods(text)
               if re.search(r"static (bridge )?synthetic \w+\(" + re.escape(DFS) + r"Landroid/util/ArrayMap;\)V$", h)
               and re.search(r"iput-object p1, p0, " + re.escape(DFS) + r"->mTopApps:", text[a:b])]
    if len(setters) != 1:
        sys.exit(f"mTopApps setter: found {len(setters)}")
    a, b, h = setters[0]
    text = text[:a] + f"""{h}
    .locals 1

    # RYU: switching to smart mode -> merged map
    iget-object v0, p0, {DFS}->mTopSmartApps:Landroid/util/ArrayMap;

    if-ne p1, v0, :ryu_q

    invoke-direct {{p0}}, {DFS}->ryuMerged()Landroid/util/ArrayMap;

    move-result-object p1

    :ryu_q
    iput-object p1, p0, {DFS}->mTopApps:Landroid/util/ArrayMap;

    return-void
.end method""" + text[b:]
    log.append("setter " + h.split()[-1])
    # 3. updateCustomDataBase: in smart mode refresh instead of replacing the smart map
    a, b, h = method(text, r" updateCustomDataBase\(Ljava/lang/String;\)V$")
    body = text[a:b]
    pat = re.compile(r"    iget-object (p1|v\d+), p0, " + re.escape(DFS) + r"->mCustomApps:Landroid/util/ArrayMap;\n\n"
                     r"    iput-object \1, p0, " + re.escape(DFS) + r"->mTopApps:Landroid/util/ArrayMap;")
    body, n = pat.subn(lambda m: f"    sget-boolean v0, {DFS}->mIsSmart:Z\n\n    if-eqz v0, :ryu_ucd\n\n"
                       f"    invoke-direct {{p0}}, {DFS}->ryuRefresh()V\n\n    return-void\n\n    :ryu_ucd\n" + m.group(0), body)
    if n != 1 or not p0_is_this(body):
        sys.exit(f"updateCustomDataBase: {n} assignments")
    text = text[:a] + body + text[b:]
    log.append("updateCustomDataBase")
    # 4. after the lists are (re)built: refresh
    for pat in (r" parseTopSmartAppFromDb\(Ljava/lang/String;Landroid/util/ArraySet;\)V$",
                r" parseTopDefineAppFromDb\(Ljava/lang/String;Landroid/util/ArraySet;\)V$"):
        text, n = refresh_before_returns(text, pat)
        log.append(f"{pat.split('(')[0].strip()} ({n} returns)")
    text = text.rstrip("\n") + "\n" + HELPERS
    return text, log


# ------------------------------------------------------------------ MiSettings

def find_helper(dec, needle, extra):
    """public static X(Landroid/content/Context;)Z containing const-string needle."""
    found = []
    for root, _, files in os.walk(dec):
        if "/smali" not in root:
            continue
        for f in files:
            p = os.path.join(root, f)
            t = open(p, encoding="utf-8").read()
            if f'"{needle}"' not in t:
                continue
            cls = re.search(r"^\.class [^\n]*?(L[^;\s]+;)", t, re.M).group(1)
            for a, b, h in methods(t):
                if re.search(r"static \w+\(Landroid/content/Context;\)Z$", h) and f'"{needle}"' in t[a:b] and extra in t[a:b]:
                    found.append(cls + "->" + h.split()[-1])
    if len(found) != 1:
        sys.exit(f"helper for {needle}: {found}")
    return found[0]


def patch_misettings(dec):
    p = smali_file(dec, NRF)
    text = open(p, encoding="utf-8").read()
    if "RYU" in text:
        sys.exit("MiSettings already patched")
    smart = find_helper(dec, "is_smart_fps", "Settings$System;->getInt")
    speed = find_helper(dec, "speed_mode", "Settings$System;->getInt")
    m = re.search(r'const-string (v\d+), "custom_mode_switch"\n\n    invoke-static \{\w+, \1\}, '
                  r'Landroid/provider/Settings\$System;->getString\(Landroid/content/ContentResolver;Ljava/lang/String;\)Ljava/lang/String;\n\n'
                  r"    move-result-object (\w+)\n\n    sput-object \2, " + re.escape(NRF) + r"->(\w+):Ljava/lang/String;", text)
    if not m:
        sys.exit("custom_mode_switch field not found")
    sw_field = m.group(3)
    ctx = re.findall(r"^\.field public static (\w+):Landroid/content/Context;$", text, re.M)
    if len(ctx) != 1:
        sys.exit(f"static Context field: {ctx}")
    a, b, h = method(text, r" \w+\(Z\)V$", must='"high_refresh_options"')
    body = text[a:b]
    if "setKey" not in body or int(re.search(r"\.locals (\d+)", body).group(1)) < 2:
        sys.exit("show/hide method has an unexpected shape")
    inj = f"""    # RYU: also show "Apps using high refresh rate" in smart (adaptive) mode
    sget-object v0, {NRF}->{ctx[0]}:Landroid/content/Context;

    invoke-static {{v0}}, {smart}

    move-result v1

    if-eqz v1, :ryu_show_end

    sget-object v1, {NRF}->{sw_field}:Ljava/lang/String;

    invoke-static {{v1}}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z

    move-result v1

    if-nez v1, :ryu_show_end

    invoke-static {{v0}}, {speed}

    move-result v1

    if-nez v1, :ryu_show_end

    const/16 p1, 0x1

    :ryu_show_end
"""
    i = first_insn(body)
    body = body[:i] + inj + "\n" + body[i:]
    text = text[:a] + body + text[b:]
    open(p, "w", encoding="utf-8").write(text)
    return os.path.relpath(p, dec).split(os.sep)[0], [f"show method {h.split()[-1]}", f"smart={smart}",
                                                      f"speed={speed}", f"switch field={sw_field}"]


# ------------------------------------------------------------------ apk plumbing

def dex_name(smali_dir):
    return "classes.dex" if smali_dir == "smali" else smali_dir.replace("smali_", "") + ".dex"


def rebuild(apktool, work, apk, name, patcher):
    dec = os.path.join(work, "dec_" + name)
    shutil.rmtree(dec, ignore_errors=True)
    run(["java", "-jar", apktool, "d", "-f", "-r", "-o", dec, apk])
    changed_dir, log = patcher(dec)
    built = os.path.join(work, name + "_built.apk")
    run(["java", "-jar", apktool, "b", "-o", built, dec])
    dex = dex_name(changed_dir)
    with zipfile.ZipFile(built) as z:
        new_dex = z.read(dex)
    src = open(apk, "rb").read()
    patched = apk_patch.rebuild_zip(src, replace={dex: new_dex}, add=[])
    zo, zp = zipfile.ZipFile(apk), zipfile.ZipFile(io.BytesIO(patched))
    for i in zo.infolist():
        j = zp.getinfo(i.filename)
        if i.filename != dex and (i.CRC, i.compress_type) != (j.CRC, j.compress_type):
            sys.exit(f"{name}: entry {i.filename} changed")
    if zp.testzip() is not None or len(zo.infolist()) != len(zp.infolist()):
        sys.exit(f"{name}: zip check failed")
    # the injected code must survive a round trip through baksmali
    chk = os.path.join(work, "chk_" + name)
    shutil.rmtree(chk, ignore_errors=True)
    tmp = os.path.join(work, name + "_chk.apk")
    open(tmp, "wb").write(patched)
    run(["java", "-jar", apktool, "d", "-f", "-r", "-o", chk, tmp])
    found = subprocess.run(["grep", "-rl", "RYU\\|ryuMerged", chk], capture_output=True, text=True).stdout.split()
    if not found:
        sys.exit(f"{name}: patch not found after round trip")
    return patched, dex, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--powerkeeper", required=True)
    ap.add_argument("--misettings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    os.makedirs(work, exist_ok=True)
    apktool = os.path.join(work, "apktool.jar")
    if not os.path.exists(apktool):
        run(["curl", "-fsSL", "-o", apktool, APKTOOL_URL])

    def pk(dec):
        p = smali_file(dec, DFS)
        t, log = patch_powerkeeper_smali(open(p, encoding="utf-8").read())
        open(p, "w", encoding="utf-8").write(t)
        return os.path.relpath(p, dec).split(os.sep)[0], log

    os.makedirs(a.out, exist_ok=True)
    info = []
    for name, apk, fn in (("PowerKeeper", a.powerkeeper, pk), ("MiSettings", a.misettings, patch_misettings)):
        apk = os.path.abspath(apk)
        patched, dex, log = rebuild(apktool, work, apk, name, fn)
        open(os.path.join(a.out, name + ".apk"), "wb").write(patched)
        o, p = hashlib.md5(open(apk, "rb").read()).hexdigest(), hashlib.md5(patched).hexdigest()
        info.append(f"{name} orig={o} patched={p} dex={dex} :: " + "; ".join(log))
        print(info[-1])
    open(os.path.join(a.out, "info.txt"), "w").write("\n".join(info) + "\n")


if __name__ == "__main__":
    main()
