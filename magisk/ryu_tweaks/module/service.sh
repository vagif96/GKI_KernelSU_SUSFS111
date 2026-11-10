#!/system/bin/sh
# After boot:
#  1. PowerKeeper feature switch for Xiaomi's "Apps using high refresh rate" screen
#     (misc custom_switch = {"fucSwitch":"true"}; PowerKeeper never clears it itself);
#     if the patched PowerKeeper is not running, its part is switched off for the next boot;
#  2. once per patched APK: compile it (speed-profile) at low priority, so ART does not
#     recompile it later in the background (that caused lags).
# cmd/content write their output through system_server: use /data/local/tmp, not /data/adb.
MODDIR=${0%/*}
. "$MODDIR/common.sh"
L="$MODDIR/service.log"
T=/data/local/tmp/ryu_tweaks_svc.txt
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 10; done
sleep 60
echo "service $(date)" > "$L"
U=content://com.miui.powerkeeper.configure
content call --uri $U --method GET_misc --arg custom_switch </dev/null > "$T" 2>&1
if grep -q 'fucSwitch":"true' "$T"; then
  echo "custom_switch: ok" >> "$L"
else
  content call --uri $U --method PUT_misc --arg custom_switch --extra 'value:s:{"fucSwitch"\:"true"}' </dev/null > "$T" 2>&1
  echo "custom_switch: set ($(cat "$T"))" >> "$L"
  am force-stop com.miui.powerkeeper </dev/null >/dev/null 2>&1
  sleep 30
fi
d="$MODDIR/parts/powerkeeper"
if [ -d "$d" ] && [ ! -f "$d/off" ] && [ -z "$(pidof com.miui.powerkeeper)" ]; then
  sleep 30
  if [ -z "$(pidof com.miui.powerkeeper)" ]; then
    echo "PowerKeeper is not running: powerkeeper part off from the next boot" >> "$L"
    touch "$d/off"
  fi
fi
sleep 60
for d in "$MODDIR"/parts/*; do
  name=$(basename "$d"); pkg=$(cat "$d/package" 2>/dev/null)
  [ -n "$pkg" ] && [ ! -f "$d/off" ] || continue
  grep -q "^$name: \(mounted\|already mounted\)" "$MODDIR/boot.log" 2>/dev/null || continue
  mark="$d/.dexopt_$(cat "$d/patched_md5")"
  [ -f "$mark" ] && continue
  nice -n 19 cmd package compile -m speed-profile "$pkg" </dev/null > "$T" 2>&1
  rc=$?
  echo "dexopt $pkg: exit $rc $(tr '\n' ' ' < "$T")" >> "$L"
  [ "$rc" = 0 ] && { rm -f "$d"/.dexopt_*; touch "$mark"; }
done
rm -f "$T"
