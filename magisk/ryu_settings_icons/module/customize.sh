SKIPUNZIP=0
. "$MODPATH/common.sh"

ui_print "- Ryu Other Settings Icons"
want=$(cat "$MODPATH/settings_md5")
have=$(settings_md5)
ui_print "- Settings.apk md5: $have"
if [ "$have" != "$want" ]; then
  ui_print "! This module was built for another Settings.apk"
  ui_print "! (expected $want)"
  ui_print "! Rebuild it for your firmware, otherwise Settings may crash."
  abort "! Installation aborted"
fi
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
ui_print "- OK. Reboot to apply."
