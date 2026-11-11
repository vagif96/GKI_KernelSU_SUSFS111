# Ryu Tweaks — direct install for POCO F5 (no module)

Writes the patched files straight into the ext4 RW system partitions, so the
`hyperos_settings_icons` module is no longer needed. Only for an **ext4 RW** ROM
(marble / POCO F5) where a write test to `/product` succeeds; on erofs / verity
this does not work.

What it changes (built from this F5's own APKs):
* `/system_ext/priv-app/Settings/Settings.apk` — HyperOS icons in Additional
  settings + stock Wi-Fi "Saved networks" (patched on-device at install);
* `/system_ext/app/PowerKeeper/PowerKeeper.apk`, `/product/priv-app/MiSettings/MiSettings.apk`
  — per-app refresh rate in the adaptive mode;
* `/product/etc/device_features/marble.xml` — Display > AI image processing flags;
* `/product/etc/build.prop` — `debug.config.media.video.ais.support` /
  `.frc.support` = true (Super resolution / MEMC entries).

Originals are copied to `/sdcard/ryu_backup` first; `restore.sh` puts them back.

## Use

1. Remove the `hyperos_settings_icons` module in your manager and **reboot**
   (so the real, unpatched files are exposed).
2. Unzip somewhere and run:
   ```
   su -c 'sh /sdcard/ryu_direct_f5/install.sh'
   ```
3. Reboot.

## Revert

```
su -c 'sh /sdcard/ryu_direct_f5/restore.sh'
```
then reboot.

## Notes
* A firmware (ROM) update rewrites the partitions and removes these changes — run
  `install.sh` again afterwards (rebuild the package if the APKs changed).
* Harder to undo than a module: if the phone does not boot, restore from
  `/sdcard/ryu_backup` in recovery. Back up your partitions first if you can.
