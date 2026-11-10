# Ryu Tweaks

One KernelSU / Magisk module for Xiaomi 17 Pro Max (ProjectRyu 3.0.319 / HyperOS 3):

| part | file it replaces | what it does |
|---|---|---|
| `parts/settings` | Settings.apk | HyperOS-style icons in "Additional settings"; Wi-Fi → Saved networks opens the stock detailed screen (QR, delete, connect) with its Compose items hidden |
| `parts/audio` | `/odm/etc/audio_policy_engine_stream_volumes_mi.xml` | Bluetooth/headphone music curves without the EU (`_CE`) limit: 0 dB at max, middle +3–4 dB, never above 0 dB |
| `parts/display` | `/product/etc/device_features/popsicle.xml` | Display → "AI image processing" (super resolution, AI image enhancement, AI HDR, MEMC) |

Each part is bind-mounted by `post-fs-data.sh` only if its firmware file still has the
md5 it was built from; otherwise only that part turns off (`parts/<name>/off`).
`service.sh` compiles the patched Settings once per build, at low priority, a few
minutes after boot (avoids a surprise background recompilation later).
Log: `/data/adb/modules/ryu_tweaks/boot.log`. Installing marks the older separate
modules (`ryu_other_settings_icons`, `ryu_bt_volume`, `ryu_display_ai`, `ryu_app_fps`)
for removal.

Note: the firmware's Settings.apk is v1-signed only (no APK Signing Block); the
patched APK keeps `META-INF` unchanged.

Build:
```sh
python3 build.py --settings-apk Settings.apk \
  --volume-xml audio_policy_engine_stream_volumes_mi.xml --display-xml popsicle.xml
```
