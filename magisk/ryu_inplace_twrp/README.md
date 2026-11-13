# Ryu in-place TWRP patch

A TWRP-flashable zip that MODIFIES the APK/files already on the device instead of
replacing them — so it works on any HyperOS ROM (e.g. a 17 Pro Max port on the F5),
without bundling the firmware's own 100 MB+ Settings.apk.

Applies in recovery:
* **Settings.apk** — HyperOS icons in "Additional settings" + stock detailed Wi-Fi
  "Saved networks", patched in place by the bundled native `ryu_patch` (arm64);
* **device_features/<device>.xml** — Display > "AI image processing" flags;
* **build.prop** — Super resolution / MEMC props.

Everything else in each file is kept byte-for-byte. Originals are backed up to
`/data/ryu_inplace_backup`. Mounts the system partitions rw, finds the files by
searching, and skips cleanly anything it does not find (nothing is forced).

## NOT included
Per-app refresh rate in the adaptive mode needs new code added to PowerKeeper /
MiSettings — that can only be built with apktool for a specific ROM, not applied by an
on-device script. After booting the new ROM, send me its `PowerKeeper.apk` and
`MiSettings.apk` and I build that part separately.

## Use
TWRP → Install → this zip (or `adb sideload`). Reboot; first boot recompiles Settings.

## Revert
Flash with the originals from `/data/ryu_inplace_backup`, or restore a TWRP backup of
System / System_ext / Product.
