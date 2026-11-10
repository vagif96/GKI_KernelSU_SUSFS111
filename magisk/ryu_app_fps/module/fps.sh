#!/system/bin/sh
# Helper for the WebUI. Commands run with stdin/stdout redirected to files:
# binder calls that receive the caller's fds fail from app sandboxes.
#   list | listsys            installed packages
#   get <key>                 PowerKeeper misc value
#   set <key> <base64 json>   store a value (no restart)
#   clear <key>               empty a value (no restart)
#   restart                   restart PowerKeeper so it re-reads its config
U=content://com.miui.powerkeeper.configure
T=/data/local/tmp/ryu_fps.$$
case "$1" in
  list)    pm list packages -3 </dev/null >"$T" 2>&1; sed -n 's/^package://p' "$T" | sort ;;
  listsys) pm list packages -s </dev/null >"$T" 2>&1; sed -n 's/^package://p' "$T" | sort ;;
  get)     content call --uri $U --method GET_misc --arg "$2" </dev/null >"$T" 2>&1; cat "$T" ;;
  set)     J=$(echo "$3" | base64 -d)
           E=$(printf '%s' "$J" | sed 's/:/\\:/g')
           content call --uri $U --method PUT_misc --arg "$2" --extra "value:s:$E" </dev/null >"$T" 2>&1
           cat "$T" ;;
  clear)   content call --uri $U --method PUT_misc --arg "$2" --extra "value:s:" </dev/null >"$T" 2>&1; cat "$T" ;;
  restart) am force-stop com.miui.powerkeeper </dev/null >/dev/null 2>&1; echo restarted ;;
esac
rm -f "$T"
