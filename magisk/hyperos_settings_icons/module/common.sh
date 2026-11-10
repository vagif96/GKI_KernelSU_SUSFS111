# Shared helpers (customize.sh, post-fs-data.sh)
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
