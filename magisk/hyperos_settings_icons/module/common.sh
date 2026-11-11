# Shared helpers (customize.sh, post-fs-data.sh)
# touch /data/adb/hyperos_icons_no_wifi to keep MIUI's own "Saved networks" screen
patch_opts() { [ -f /data/adb/hyperos_icons_no_wifi ] && echo "--no-wifi"; }
# system APK of a package; prints UPDATED if an update in /data/app is the active one
pkg_apk() {
  local p
  p=$(pm path "$1" 2>/dev/null </dev/null | head -n1 | sed 's/^package://')
  case "$p" in */data/app/*) echo UPDATED; return 1;; esac
  [ -n "$p" ] && [ -f "$p" ] && { echo "$p"; return 0; }
  return 1
}
# hard links for the mounts live outside /data/adb (see post-fs-data.sh)
LINKDIR=/data/misc/hyperos_settings_icons
file_md5() { md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
ctx_of() { ls -Z "$1" 2>/dev/null | awk '{print $1}'; }
# $1 = "pm" to ask the package manager first (not at post-fs-data: it is not running yet)
settings_apk() {
  local p=""
  [ "$1" = pm ] && p=$(pm path com.android.settings 2>/dev/null </dev/null | head -n1 | sed 's/^package://')
  case "$p" in */data/app/*) p="";; esac   # an installed update is not patched
  for c in "$p" /system_ext/priv-app/Settings/Settings.apk /system/system_ext/priv-app/Settings/Settings.apk \
           /product/priv-app/Settings/Settings.apk /system/priv-app/Settings/Settings.apk; do
    [ -n "$c" ] && [ -f "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
