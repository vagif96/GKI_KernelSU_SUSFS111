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
nice -n 19 cmd package compile -m speed-profile com.android.settings </dev/null >> "$L" 2>&1
echo "exit $?" >> "$L"
rm -f "$MODDIR"/.dexopt_*; touch "$mark"
