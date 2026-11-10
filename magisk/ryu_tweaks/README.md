# Ryu Tweaks

One KernelSU / Magisk module for Xiaomi 17 Pro Max (ProjectRyu 3.0.319 / HyperOS 3):

| part | file it replaces | what it does |
|---|---|---|
| `parts/settings` | Settings.apk | HyperOS-style icons in "Additional settings" (+ the hidden "Video toolbox" item made visible); Wi-Fi → Saved networks opens the stock detailed screen (QR, delete, connect) with its Compose items hidden |
| `parts/audio` | `/odm/etc/audio_policy_engine_stream_volumes_mi.xml` | Bluetooth/headphone music curves without the EU (`_CE`) limit: 0 dB at max, middle +3–4 dB, never above 0 dB |
| `parts/display` | `/product/etc/device_features/popsicle.xml` | Display → "AI image processing" (super resolution, AI image enhancement, AI HDR, MEMC) |
| `parts/powerkeeper` | PowerKeeper.apk | in the adaptive ("Default") refresh rate mode, apps switched off in Xiaomi's "Apps using high refresh rate" screen run at 60 Hz (see `../ryu_hz`) |
| `parts/misettings` | MiSettings.apk | shows "Apps using high refresh rate" also in the adaptive mode |

Each part is bind-mounted by `post-fs-data.sh` only if its firmware file still has the
md5 it was built from; otherwise only that part turns off (`parts/<name>/off`).
`service.sh` sets PowerKeeper's misc `custom_switch` = `{"fucSwitch":"true"}` (enables
Xiaomi's per-app screen on models PowerKeeper does not list; PowerKeeper never clears it),
switches the powerkeeper part off for the next boot if PowerKeeper is not running, and
compiles every patched APK once per build, at low priority, a few
minutes after boot (avoids a surprise background recompilation later; log: `dexopt.log`).
Log: `/data/adb/modules/ryu_tweaks/boot.log`. Installing marks the older separate
modules (`ryu_other_settings_icons`, `ryu_bt_volume`, `ryu_display_ai`, `ryu_app_fps`)
for removal.

Note: the firmware's Settings.apk is v1-signed only (no APK Signing Block); the
patched APK keeps `META-INF` unchanged.

Mounts are made from hard links in `/data/misc/ryu_tweaks` (ReZygisk & co. remove
mounts whose source is under `/data/adb/modules` from app processes).  APK parts whose
package runs from an update in `/data/app` are skipped.

Build:
```sh
python3 build.py --settings-apk Settings.apk \
  --volume-xml audio_policy_engine_stream_volumes_mi.xml --display-xml popsicle.xml \
  --powerkeeper PowerKeeper.apk --misettings MiSettings.apk
```
