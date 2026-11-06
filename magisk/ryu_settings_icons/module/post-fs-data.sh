#!/system/bin/sh
# Safety net: if the firmware (Settings.apk) changed, the overlay's resource ids
# are no longer valid -> disable the module so Settings does not crash.
MODDIR=${0%/*}
. "$MODDIR/common.sh"
want=$(cat "$MODDIR/settings_md5")
have=$(settings_md5)
if [ -n "$have" ] && [ "$have" != "$want" ]; then
  touch "$MODDIR/disable"
  rm -f "$MODDIR"/system/product/overlay/*.apk
  sed -i 's/^description=.*/description=DISABLED: firmware changed, rebuild the module for the new Settings.apk/' "$MODDIR/module.prop"
fi
