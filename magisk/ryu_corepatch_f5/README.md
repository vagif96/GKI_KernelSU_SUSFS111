# Ryu Core Patch (POCO F5)

Disables APK signature verification in the framework (`services.jar`), so apps and
updates install regardless of signature — including differently-signed apps over
system apps (e.g. the modded Mi Browser), and downgrades.

Built from THIS phone's exact `services.jar` (md5 `bda245f7…`). Two methods patched
in `com.android.server.pm.PackageManagerServiceUtils`:

* `verifySignatures(...)` -> always `true` (the check `ReconcilePackageUtils` uses on
  install/update);
* `compareSignatures(...)` -> always `SIGNATURE_MATCH` (0).

(`checkDowngrade` is already empty in this firmware.)

Writes the patched `services.jar` straight into the framework partition (ext4 RW),
backs up the original + its oat/vdex to `/sdcard/ryu_backup/corepatch`, and removes
the stale compiled artifacts so the patch takes effect.

## Use

1. **Make a TWRP backup of System and System_ext first** — this patches the framework;
   a wrong file = bootloop.
2. ```
   su -c 'sh install.sh'
   ```
3. Reboot. The **first boot is slower** (services is recompiled) — wait a few minutes.

## Revert

```
su -c 'sh restore.sh'
```
then reboot.

## Notes
* Security: this turns off signature checking system-wide — any app can be replaced
  or updated with any signature. That is the whole point of a core patch, but be aware.
* Only matches this firmware's `services.jar`. After a ROM update it won't match
  (the installer refuses) — send the new `services.jar` and I rebuild.
* Play Integrity: STRONG may drop with the framework modified; check if your wallet
  still works.
