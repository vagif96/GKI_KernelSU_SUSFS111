#!/system/bin/sh
# Safety net: after a firmware update the patched Settings.apk no longer matches
# the system -> disable the module instead of replacing the new Settings.
MODDIR=${0%/*}
. "$MODDIR/common.sh"
for c in /system_ext/priv-app/Settings/Settings.apk /system/priv-app/Settings/Settings.apk \
         /product/priv-app/Settings/Settings.apk; do
  [ -f "$c" ] && { real=$c; break; }
done
[ -n "$real" ] || exit 0
have=$(file_md5 "$real")
if [ "$have" != "$(cat "$MODDIR/settings_md5")" ] && [ "$have" != "$(cat "$MODDIR/patched_md5")" ]; then
  touch "$MODDIR/disable"
  sed -i 's/^description=.*/description=DISABLED: firmware changed, rebuild the module for the new Settings.apk/' "$MODDIR/module.prop"
fi
