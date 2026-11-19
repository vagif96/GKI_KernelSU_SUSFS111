#!/system/bin/sh
MODDIR=${0%/*}
prev="$(cat "$MODDIR/prev_locale" 2>/dev/null)"
[ -z "$prev" ] && prev=zh-CN
setprop persist.sys.locale "$prev"
settings put system system_locales "$prev" >/dev/null 2>&1
