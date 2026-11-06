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

# module path that mirrors the real one
case "$real" in
  /system/*) dst="$MODPATH$real" ;;
  *)         dst="$MODPATH/system$real" ;;
esac
mkdir -p "$(dirname "$dst")"
mv "$MODPATH/Settings.apk" "$dst"
set_perm_recursive "$MODPATH/system" 0 0 0755 0644

# copy SELinux labels from the real files/dirs (wrong labels make whole dirs unreadable)
ctx_of() { ls -Zd "$1" 2>/dev/null | awk '{print $1}'; }
r="$real"; m="$dst"
while :; do
  c=$(ctx_of "$r")
  [ -n "$c" ] && [ "$c" != "?" ] && chcon "$c" "$m"
  r=$(dirname "$r"); m=$(dirname "$m")
  [ "$m" = "$MODPATH" ] || [ "$r" = "/" ] && break
done
ui_print "- Label: $(ls -Z "$dst" | awk '{print $1}')"
ui_print "- OK. Reboot to apply."
ui_print "- If Settings misbehaves: remove the module in KernelSU and reboot."
