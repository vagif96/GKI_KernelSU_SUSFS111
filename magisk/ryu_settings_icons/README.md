# Ryu Other Settings Icons

KernelSU / KSU Next / Magisk module that adds HyperOS-style icons (colored
squircle + white glyph, like the main Settings list) to
**Settings → Дополнительные настройки** (`xml/other_personal_settings`).

Built for: Xiaomi 17 Pro Max, ProjectRyu 3.0.319.0 (xiaomi.eu HyperOS 3).

## How it works

A static RRO overlay (`/product/overlay/RyuOtherSettingsIcons.apk`) replaces the
screen XML with a copy that adds `android:icon` to every entry. Glyphs come
from [Material Design Icons](https://pictogrammers.com/library/mdi/) (`@mdi/js`, Apache-2.0).
Details are in the `build.py` docstring.

The overlay references Settings resources by ID, so **it only works with the
exact Settings.apk it was built from**:

* the installer aborts if the Settings.apk md5 does not match;
* after a firmware update, `post-fs-data.sh` disables the module automatically.

## Rebuild for a new firmware

```sh
# on the phone (Termux):
su -c 'cp $(pm path com.android.settings | sed "s/package://") /sdcard/Settings.apk'
# on a PC with java, node/npm, curl:
python3 build.py /path/to/Settings.apk
# -> out/ryu_other_settings_icons-v1.0-<md5>.zip
```

Icons and colours per entry are in `icons.py`.

## Removing

Remove the module in the KernelSU / Magisk manager and reboot.
