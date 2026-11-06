# Ryu Other Settings Icons

KernelSU / KSU Next / Magisk module that adds HyperOS-style icons (colored
squircle + white glyph, like the main Settings list) to
**Settings → Дополнительные настройки** (`xml/other_personal_settings`).

Built for: Xiaomi 17 Pro Max, ProjectRyu 3.0.319.0 (xiaomi.eu HyperOS 3).

## How it works

Version 2 patches **Settings.apk itself** (no RRO overlay, nothing is added to
`/product/overlay`):

* 38 new vector drawables are appended to `resources.arsc` (all existing
  resources keep their ids and values);
* `res/xml/other_personal_settings.xml` gets an `android:icon` on every entry;
* all other files (dex included) are copied byte-for-byte, and the original
  signing block is kept, so the platform signature stays the same.

`post-fs-data.sh` bind-mounts this one file over the original Settings.apk
itself (no dependency on the KernelSU / metamodule mount; result in
`/data/adb/modules/ryu_other_settings_icons/boot.log`). The SELinux label is
copied from the real file.

Glyphs come from [Material Design Icons](https://pictogrammers.com/library/mdi/)
(`@mdi/js`, Apache-2.0).

The module **only works with the exact Settings.apk it was built from**:

* the installer aborts if the Settings.apk md5 does not match;
* after a firmware update, `post-fs-data.sh` disables the module automatically.

If Settings misbehaves: remove the module in the KernelSU Next manager and
reboot. If the phone does not boot, use KernelSU safe mode (press volume down
several times during boot) to disable all modules.

## Rebuild for a new firmware

```sh
# on the phone (Termux):
su -c 'cp $(pm path com.android.settings | sed "s/package://") /sdcard/Settings.apk'
# on a PC with java, node/npm, curl:
python3 build.py /path/to/Settings.apk
# -> out/ryu_other_settings_icons-v3.0-<md5>.zip
```

Icons and colours per entry are in `icons.py`.

## Removing

Remove the module in the KernelSU / Magisk manager and reboot.
