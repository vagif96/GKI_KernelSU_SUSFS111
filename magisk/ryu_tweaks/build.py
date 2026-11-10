#!/usr/bin/env python3
"""Build "Ryu Tweaks" = ryu_settings_icons + ryu_bt_volume + ryu_display_ai in one module.

Usage: python3 build.py --settings-apk Settings.apk --volume-xml audio_policy_engine_stream_volumes_mi.xml \
           --display-xml popsicle.xml
Each part is independent: on install / boot a part whose firmware file changed is
switched off, the other part keeps working.
"""
import argparse, os, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION, VERSION_CODE = "1.3", 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings-apk", required=True)
    ap.add_argument("--volume-xml", required=True)
    ap.add_argument("--display-xml", required=True, help="/product/etc/device_features/popsicle.xml")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--no-stock-saved-wifi", action="store_true",
                    help="keep MIUI's own Saved networks screen")
    ap.add_argument("--settings-work", default=os.path.join(HERE, "..", "ryu_settings_icons", "work"))
    a = ap.parse_args()
    s_dir = os.path.join(HERE, "..", "ryu_settings_icons")
    v_dir = os.path.join(HERE, "..", "ryu_bt_volume")
    d_dir = os.path.join(HERE, "..", "ryu_display_ai")
    tmp_out = os.path.join(HERE, "work_parts")
    subprocess.run([sys.executable, os.path.join(s_dir, "build.py"), a.settings_apk,
                    "--work", a.settings_work, "--out", tmp_out]
                   + ([] if a.no_stock_saved_wifi else ["--stock-saved-wifi"]), check=True)
    subprocess.run([sys.executable, os.path.join(v_dir, "build.py"), a.volume_xml, "--out", tmp_out], check=True)
    subprocess.run([sys.executable, os.path.join(d_dir, "build.py"), a.display_xml, "--out", tmp_out], check=True)
    dmod = os.path.join(d_dir, "work")
    smod = os.path.join(a.settings_work, "module")
    vmod = os.path.join(v_dir, "work")

    work = os.path.join(HERE, "work")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "module"), work)
    ps, pv = os.path.join(work, "parts", "settings"), os.path.join(work, "parts", "audio")
    pd = os.path.join(work, "parts", "display")
    os.makedirs(ps); os.makedirs(pv); os.makedirs(pd)
    shutil.copy(os.path.join(smod, "apk", "Settings.apk"), os.path.join(ps, "file"))
    shutil.copy(os.path.join(smod, "settings_md5"), os.path.join(ps, "orig_md5"))
    shutil.copy(os.path.join(smod, "patched_md5"), os.path.join(ps, "patched_md5"))
    vfile = os.listdir(os.path.join(vmod, "files"))[0]
    shutil.copy(os.path.join(vmod, "files", vfile), os.path.join(pv, "file"))
    for f in ("orig_md5", "patched_md5", "target_path"):
        shutil.copy(os.path.join(vmod, f), os.path.join(pv, f))
    dfile = os.listdir(os.path.join(dmod, "files"))[0]
    shutil.copy(os.path.join(dmod, "files", dfile), os.path.join(pd, "file"))
    for f in ("orig_md5", "patched_md5", "target_path"):
        shutil.copy(os.path.join(dmod, f), os.path.join(pd, f))
    prop = open(os.path.join(work, "module.prop")).read()
    prop = prop.replace("@VERSION@", VERSION).replace("@VERSION_CODE@", str(VERSION_CODE))
    if not prop.startswith("id=ryu_tweaks"):
        sys.exit("module.prop broken")
    open(os.path.join(work, "module.prop"), "w").write(prop)
    os.makedirs(a.out, exist_ok=True)
    z = os.path.join(a.out, f"ryu_tweaks-v{VERSION}.zip")
    if os.path.exists(z):
        os.remove(z)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(work):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, work))
    shutil.rmtree(tmp_out, ignore_errors=True)
    print("module:", z)


if __name__ == "__main__":
    main()
