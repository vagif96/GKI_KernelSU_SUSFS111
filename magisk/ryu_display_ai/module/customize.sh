SKIPUNZIP=0
ui_print "- Ryu Display AI"
real=$(cat "$MODPATH/target_path")
[ -f "$real" ] || abort "! $real not found"
have=$(md5sum "$real" | cut -d' ' -f1)
if [ "$have" != "$(cat "$MODPATH/orig_md5")" ]; then
  ui_print "! $real differs from the file this module was built for"
  abort "! Installation aborted (nothing was changed)"
fi
f="$MODPATH/files/$(basename "$real")"
[ "$(md5sum "$f" | cut -d' ' -f1)" = "$(cat "$MODPATH/patched_md5")" ] || abort "! Damaged module zip"
set_perm_recursive "$MODPATH/files" 0 0 0755 0644
ctx=$(ls -Z "$real" | awk '{print $1}')
[ -n "$ctx" ] && [ "$ctx" != "?" ] && chcon "$ctx" "$f"
ui_print "- Label: $(ls -Z "$f" | awk '{print $1}')"
ui_print "- OK. Reboot to apply."
