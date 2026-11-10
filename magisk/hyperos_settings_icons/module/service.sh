#!/system/bin/sh
# Once per patched Settings.apk: compile Settings now, at low priority, instead of
# a background recompilation later (avoids lags in Settings).
MODDIR=${0%/*}
L="$MODDIR/dexopt.log"
mark="$MODDIR/.dexopt_$(cat "$MODDIR/patched_md5" 2>/dev/null)"
[ -f "$mark" ] && exit 0
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 10; done
sleep 180
grep -q "^mounted" "$MODDIR/boot.log" 2>/dev/null || grep -q "^already" "$MODDIR/boot.log" 2>/dev/null || exit 0
echo "dexopt settings $(date)" > "$L"
# system_server must be able to write the output file: /data/adb is not allowed
# (that gave "Failed transaction"), /data/local/tmp is
T=/data/local/tmp/ryu_dexopt.txt
nice -n 19 cmd package compile -m speed-profile com.android.settings </dev/null > "$T" 2>&1
rc=$?
cat "$T" >> "$L"; rm -f "$T"
echo "exit $rc" >> "$L"
[ "$rc" = 0 ] || exit 0   # try again next boot
rm -f "$MODDIR"/.dexopt_*; touch "$mark"
