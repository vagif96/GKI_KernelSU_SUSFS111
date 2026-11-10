# HyperOS Settings Icons

KernelSU / KSU Next / Magisk module: HyperOS-style icons (coloured squircle + white
glyph) in **Settings → Additional settings** (`xml/other_personal_settings`).

Unlike `ryu_settings_icons` it is **not built for one firmware**: the Settings.apk
of the phone is patched on the phone, at install time, by a small static arm64
program (`bin/ryu_patch`, Go source in `patcher/`).  Tested against the Xiaomi 17
Pro Max (ProjectRyu 3.0) Settings.apk: the result is identical to the verified
`ryu_settings_icons` build.  Meant for other HyperOS 3 phones (e.g. POCO F5).

## What the patcher changes

* `resources.arsc`: new drawable entries appended (existing resource ids and values
  untouched; plain, offset16 and sparse type chunks, UTF-8 / UTF-16 pools);
* the screen XML: `android:icon` + `miuisettings:showIcon="true"` on every entry
  (entries that already have a hidden icon only get `showIcon`);
* the drawables are added; every other zip entry (dex included) is copied
  byte-for-byte; the original APK signing block is kept.

Entries without their own icon in `icons/map.txt` get a grey gear icon; the
installer lists them.  The output is checked before it is used (original entries
unchanged, new drawables resolve, icons reference them); on any error nothing is
changed.

## On the phone

* install: `customize.sh` patches `pm path com.android.settings` into
  `/data/adb/modules/hyperos_settings_icons/Settings.apk`;
* boot: `post-fs-data.sh` bind-mounts it over the original (log: `boot.log`) from a
  hard link in `/data/misc/hyperos_settings_icons/`: Zygisk implementations
  (ReZygisk) remove mounts whose source is in `/data/adb/modules` from app
  processes, Settings included;
  after a firmware update the new Settings.apk is patched again automatically;
* `service.sh` compiles Settings once (speed-profile) 3 minutes after boot.

Refuses to install next to `ryu_tweaks` / `ryu_other_settings_icons` (they patch
the same file).  Remove the module and reboot to undo.  If something goes wrong
during boot, KernelSU safe mode (volume down several times) disables modules.

## Build

```sh
python3 build.py        # needs go, java, node/npm; -> out/hyperos_settings_icons-v1.0.zip
```

Icons per key: `../ryu_settings_icons/icons.py` + `EXTRA` in `build.py`.
