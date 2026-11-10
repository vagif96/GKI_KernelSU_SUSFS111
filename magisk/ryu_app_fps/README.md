# Ryu App FPS

Per-app refresh rate (60 / 90 / 120 Hz) for Xiaomi 17 Pro Max, ProjectRyu 3.0.319 /
HyperOS 3, with a KernelSU Next WebUI (Modules → Ryu App FPS → WebUI).

PowerKeeper already applies per-app groups from `fps_group`
(`{"isSmart":false,"list60":"…","list90":"…","list120":"…"}`), but it rewrites that
value from the Xiaomi cloud/local config on every start. The module bind-mounts a
PowerKeeper.apk whose `classes.dex` has one small change in
`DisplayFrameSetting.parseTopDefineAppFromDb()`: if PowerKeeper's misc settings
contain `ryu_fps_group`, that JSON is used instead (logged as
`parseTopDefineAppFromDb ryu override = …`). Everything else in the APK is unchanged.

The WebUI stores the user's choice with
`content call --uri content://com.miui.powerkeeper.configure --method PUT_misc --arg ryu_fps_group`
and restarts PowerKeeper. "Остальные приложения" puts every third-party app without an
explicit choice into the selected list.

Requirements: Settings → Display → Refresh rate → **High** + **Custom (Выбор) 120 Hz**
(the "default/recommended" mode is PowerKeeper's smart mode, which ignores the lists).

Safety: the installer refuses a different PowerKeeper.apk; after a firmware update the
module disables itself; if PowerKeeper is not running 90 s after boot, `service.sh`
disables the module. Uninstalling clears `ryu_fps_group`.

Build: `python3 build.py /path/to/PowerKeeper.apk`
