#!/system/bin/sh
# Once per installed Settings.apk: let ART compile the patched Settings now, at low
# priority, instead of a surprise background recompilation later (that caused lags).
MODDIR=${0%/*}
d="$MODDIR/parts/settings"
L="$MODDIR/dexopt.log"
[ -f "$d/off" ] && exit 0
mark="$MODDIR/.dexopt_$(cat "$d/patched_md5" 2>/dev/null)"
[ -f "$mark" ] && exit 0
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 10; done
sleep 180
echo "dexopt settings $(date)" > "$L"
# system_server must be able to write the output file: /data/adb is not allowed
# (that gave "Failed transaction"), /data/local/tmp is
T=/data/local/tmp/ryu_dexopt.txt
nice -n 19 cmd package compile -m speed-profile com.android.settings </dev/null > "$T" 2>&1
rc=$?
cat "$T" >> "$L"; rm -f "$T"
echo "exit $rc" >> "$L"
[ "$rc" = 0 ] || exit 0   # try again next boot
touch "$mark"
