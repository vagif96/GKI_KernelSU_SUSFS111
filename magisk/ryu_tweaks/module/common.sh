# Each part lives in $MODDIR/parts/<name>/ with:
#   file         patched file to bind-mount
#   orig_md5     md5 of the firmware file it was built from
#   patched_md5  md5 of "file"
#   target_path  firmware file it replaces (written at install time)
file_md5() { md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
ctx_of() { ls -Z "$1" 2>/dev/null | awk '{print $1}'; }
settings_apk() {
  local p
  p=$(pm path com.android.settings 2>/dev/null | head -n1 | sed 's/^package://')
  case "$p" in */data/app/*) p="";; esac
  for c in "$p" /system_ext/priv-app/Settings/Settings.apk /system/priv-app/Settings/Settings.apk \
           /product/priv-app/Settings/Settings.apk; do
    [ -n "$c" ] && [ -f "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
