# Ryu Tweaks

One KernelSU / Magisk module = `ryu_settings_icons` + `ryu_bt_volume`
(Xiaomi 17 Pro Max, ProjectRyu 3.0.319 / HyperOS 3).

* `parts/settings` — patched Settings.apk (icons in "Additional settings").
* `parts/audio` — `/odm/etc/audio_policy_engine_stream_volumes_mi.xml` without the
  EU music volume curves.

Parts are independent: each one is bind-mounted by `post-fs-data.sh` only if its
firmware file still has the md5 it was built from; otherwise only that part turns
off (`parts/<name>/off`). Log: `/data/adb/modules/ryu_tweaks/boot.log`.
Installing it marks the separate `ryu_other_settings_icons` / `ryu_bt_volume`
modules for removal.

Build:
```sh
python3 build.py --settings-apk Settings.apk --volume-xml audio_policy_engine_stream_volumes_mi.xml
```
