# Shared helpers (sourced by customize.sh and post-fs-data.sh)
settings_apk() {
  local p
  p=$(pm path com.android.settings 2>/dev/null | head -n1 | sed 's/^package://')
  case "$p" in */data/app/*) p="";; esac   # ignore an installed update
  for c in "$p" /system_ext/priv-app/Settings/Settings.apk /system/system_ext/priv-app/Settings/Settings.apk \
           /product/priv-app/Settings/Settings.apk /system/priv-app/Settings/Settings.apk; do
    [ -n "$c" ] && [ -f "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
file_md5() { md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
