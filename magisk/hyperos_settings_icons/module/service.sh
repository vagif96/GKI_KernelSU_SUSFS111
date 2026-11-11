#!/system/bin/sh
# After boot:
#  1. PowerKeeper feature switch for Xiaomi's "Apps using high refresh rate" screen
#     (misc custom_switch = {"fucSwitch":"true"}; PowerKeeper never clears it itself);
#     if the patched PowerKeeper is not running, its part is switched off for the next boot;
#  2. once per patched APK: compile it (speed-profile) at low priority, so ART does not
#     recompile it later in the background (that caused lags).
# cmd/content write their output through system_server: use /data/local/tmp, not /data/adb.
MODDIR=${0%/*}
L="$MODDIR/service.log"
T=/data/local/tmp/hyperos_icons_svc.txt
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 10; done
sleep 60
echo "service $(date)" > "$L"
if [ -d "$MODDIR/parts/powerkeeper" ]; then
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
  if [ ! -f "$d/off" ] && [ -z "$(pidof com.miui.powerkeeper)" ]; then
    sleep 30
    if [ -z "$(pidof com.miui.powerkeeper)" ]; then
      echo "PowerKeeper is not running: powerkeeper part off from the next boot" >> "$L"
      touch "$d/off"
    fi
  fi
fi
sleep 60
compile() {  # <name> <package> <patched md5 file> <mark dir>
  grep -q "^$1: \(mounted\|already mounted\)" "$MODDIR/boot.log" 2>/dev/null || return
  mark="$4/.dexopt_$(cat "$3")"
  [ -f "$mark" ] && return
  nice -n 19 cmd package compile -m speed-profile "$2" </dev/null > "$T" 2>&1
  rc=$?
  echo "dexopt $2: exit $rc $(tr '\n' ' ' < "$T")" >> "$L"
  [ "$rc" = 0 ] && { rm -f "$4"/.dexopt_*; touch "$mark"; }
}
compile settings com.android.settings "$MODDIR/patched_md5" "$MODDIR"
for d in "$MODDIR"/parts/*; do
  [ -d "$d" ] && [ ! -f "$d/off" ] || continue
  compile "$(basename "$d")" "$(cat "$d/package")" "$d/patched_md5" "$d"
done
rm -f "$T"
