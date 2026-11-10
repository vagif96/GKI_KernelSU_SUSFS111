#!/system/bin/sh
# Helper for the WebUI. Commands are run with stdin/stdout redirected to files:
# binder calls that receive the caller's fds fail from app sandboxes.
U=content://com.miui.powerkeeper.configure
T=/data/local/tmp/ryu_fps.$$
case "$1" in
  list)  pm list packages -3 </dev/null >"$T" 2>&1; sed -n 's/^package://p' "$T" | sort ;;
  listsys) pm list packages -s </dev/null >"$T" 2>&1; sed -n 's/^package://p' "$T" | sort ;;
  get)   content call --uri $U --method GET_misc --arg ryu_fps_group </dev/null >"$T" 2>&1; cat "$T" ;;
  set)   J=$(echo "$2" | base64 -d)
         E=$(printf '%s' "$J" | sed 's/:/\\:/g')
         content call --uri $U --method PUT_misc --arg ryu_fps_group --extra "value:s:$E" </dev/null >"$T" 2>&1
         cat "$T"
         am force-stop com.miui.powerkeeper </dev/null >/dev/null 2>&1 ;;
  clear) content call --uri $U --method PUT_misc --arg ryu_fps_group --extra "value:s:" </dev/null >"$T" 2>&1
         cat "$T"
         am force-stop com.miui.powerkeeper </dev/null >/dev/null 2>&1 ;;
  rate)  dumpsys SurfaceFlinger </dev/null >"$T" 2>&1; grep -m1 renderRate "$T" ;;
esac
rm -f "$T"
