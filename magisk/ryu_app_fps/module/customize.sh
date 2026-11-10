SKIPUNZIP=0
ui_print "- Ryu App FPS"
real=$(pm path com.miui.powerkeeper 2>/dev/null | head -n1 | sed 's/^package://')
case "$real" in */data/app/*) real="";; esac
if [ -z "$real" ] || [ ! -f "$real" ]; then
  real=$(find /system/app /system/priv-app /system_ext/app /system_ext/priv-app /product/app /product/priv-app -name PowerKeeper.apk 2>/dev/null | head -n1)
fi
[ -f "$real" ] || abort "! PowerKeeper.apk not found"
ui_print "- PowerKeeper: $real"
have=$(md5sum "$real" | cut -d' ' -f1)
prev=$(cat /data/adb/modules/ryu_app_fps/patched_md5 2>/dev/null)
if [ "$have" != "$(cat "$MODPATH/orig_md5")" ] && [ "$have" != "$prev" ]; then
  ui_print "! PowerKeeper.apk differs from the one this module was built for"
  abort "! Installation aborted (nothing was changed)"
fi
[ "$(md5sum "$MODPATH/apk/PowerKeeper.apk" | cut -d' ' -f1)" = "$(cat "$MODPATH/patched_md5")" ] || abort "! Damaged module zip"
echo "$real" > "$MODPATH/target_path"
set_perm_recursive "$MODPATH/apk" 0 0 0755 0644
set_perm "$MODPATH/fps.sh" 0 0 0755
ctx=$(ls -Z "$real" | awk '{print $1}')
[ -n "$ctx" ] && [ "$ctx" != "?" ] && chcon "$ctx" "$MODPATH/apk/PowerKeeper.apk"
ui_print "- OK. Reboot, then open this module's WebUI (KernelSU Next > Modules)."
