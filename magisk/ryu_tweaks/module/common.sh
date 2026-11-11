# Each part lives in $MODDIR/parts/<name>/ with:
#   file         patched file to bind-mount
#   orig_md5     md5 of the firmware file it was built from
#   patched_md5  md5 of "file"
#   target_path  firmware file it replaces (written at install time for APK parts)
#   package      (APK parts) package whose system APK is replaced
file_md5() { md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
ctx_of() { ls -Z "$1" 2>/dev/null | awk '{print $1}'; }
# system APK of a package; prints UPDATED if an update in /data/app is the active one
pkg_apk() {
  local p
  p=$(pm path "$1" 2>/dev/null </dev/null | head -n1 | sed 's/^package://')
  case "$p" in */data/app/*) echo UPDATED; return 1;; esac
  [ -n "$p" ] && [ -f "$p" ] && { echo "$p"; return 0; }
  return 1
}
settings_apk() {
  local p
  p=$(pkg_apk com.android.settings) || p=""
  [ "$p" = UPDATED ] && p=""
  for c in "$p" /system_ext/priv-app/Settings/Settings.apk /system/priv-app/Settings/Settings.apk \
           /product/priv-app/Settings/Settings.apk; do
    [ -n "$c" ] && [ -f "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
# mounts come from hard links outside /data/adb: Zygisk implementations (ReZygisk ...)
# remove mounts whose source is under /data/adb/modules from app processes
LINKDIR=/data/misc/ryu_tweaks
# Our bind mounts can survive a "soft"/userspace reboot; remove them before the
# md5 checks, otherwise the still-mounted patched file looks like a firmware change.
unmount_stale() {
  local i=0
  while [ $i -lt 4 ] && grep -q " $1 " /proc/self/mountinfo; do
    umount -l "$1" 2>/dev/null || break
    i=$((i + 1))
  done
  [ $i -gt 0 ] && echo "$(basename "$1"): removed $i earlier mount(s)"
  return 0
}
