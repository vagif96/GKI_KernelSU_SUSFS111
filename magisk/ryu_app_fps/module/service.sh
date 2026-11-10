#!/system/bin/sh
# Safety net: if the patched PowerKeeper does not come up, disable the module.
MODDIR=${0%/*}
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 5; done
sleep 90
if pidof com.miui.powerkeeper >/dev/null 2>&1 || pidof com.miui.powerkeeper:service >/dev/null 2>&1 \
   || ps -A 2>/dev/null | grep -q com.miui.powerkeeper; then
  echo "powerkeeper running" >> "$MODDIR/boot.log"
else
  echo "powerkeeper NOT running -> disabling module (reboot to restore stock)" >> "$MODDIR/boot.log"
  touch "$MODDIR/disable"
  sed -i 's/^description=.*/description=DISABLED: PowerKeeper did not start with the patch. Reboot to restore stock./' "$MODDIR/module.prop"
fi
