# Shared helpers (sourced by customize.sh and post-fs-data.sh)
settings_apk() {
  for p in /system_ext/priv-app/Settings/Settings.apk /system/system_ext/priv-app/Settings/Settings.apk \
           /product/priv-app/Settings/Settings.apk /system/priv-app/Settings/Settings.apk; do
    [ -f "$p" ] && { echo "$p"; return 0; }
  done
  return 1
}
settings_md5() {
  local apk
  apk=$(settings_apk) || return 1
  md5sum "$apk" 2>/dev/null | cut -d' ' -f1
}
