SKIPUNZIP=0
. "$MODPATH/common.sh"

ui_print "- Ryu Other Settings Icons (patched Settings.apk)"
real=$(settings_apk) || abort "! Settings.apk not found"
ui_print "- Settings: $real"
want=$(cat "$MODPATH/settings_md5")
have=$(file_md5 "$real")
if [ "$have" != "$want" ]; then
  ui_print "! This module was built for another Settings.apk"
  ui_print "! expected $want, found $have"
  abort "! Installation aborted (nothing was changed)"
fi
[ "$(file_md5 "$MODPATH/apk/Settings.apk")" = "$(cat "$MODPATH/patched_md5")" ] || abort "! Damaged module zip"

# The module bind-mounts the APK itself in post-fs-data.sh (does not depend on
# the KernelSU / metamodule mount), so there is no system/ folder here.
echo "$real" > "$MODPATH/target_path"
set_perm_recursive "$MODPATH/apk" 0 0 0755 0644
ctx=$(ls -Z "$real" | awk '{print $1}')
[ -n "$ctx" ] && [ "$ctx" != "?" ] && chcon "$ctx" "$MODPATH/apk/Settings.apk"
ui_print "- Label: $(ls -Z "$MODPATH/apk/Settings.apk" | awk '{print $1}')"
ui_print "- OK. Reboot to apply."
ui_print "- If Settings misbehaves: remove the module in KernelSU and reboot."
