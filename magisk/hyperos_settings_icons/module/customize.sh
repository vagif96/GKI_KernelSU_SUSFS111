SKIPUNZIP=0
. "$MODPATH/common.sh"
ui_print "- HyperOS Settings Icons + stock Wi-Fi saved networks"
[ "$ARCH" = "arm64" ] || abort "! Only arm64 phones are supported"
for m in ryu_tweaks ryu_other_settings_icons; do
  d=/data/adb/modules/$m
  if [ -d "$d" ] && [ ! -f "$d/remove" ] && [ ! -f "$d/disable" ]; then
    abort "! Module $m already patches Settings.apk. Remove it first."
  fi
done
BIN="$MODPATH/bin/ryu_patch"
set_perm "$BIN" 0 0 0755
real=$(settings_apk pm) || abort "! Settings.apk not found"
ui_print "- Settings.apk: $real"
OUT="$MODPATH/Settings.apk"
log=$("$BIN" $(patch_opts) "$real" "$OUT" "$MODPATH/icons" 2>&1); rc=$?
if [ "$rc" = 3 ]; then
  # still bind-mounted by the installed version of this module: read the original below it
  ui_print "- Settings.apk is patched by the installed version, reading the original"
  umount -l "$real" 2>/dev/null
  log=$("$BIN" $(patch_opts) "$real" "$OUT" "$MODPATH/icons" 2>&1); rc=$?
  [ "$rc" = 3 ] && abort "! Cannot reach the original Settings.apk: disable the module, reboot, install again"
fi
echo "$log" | while IFS= read -r l; do ui_print "  $l"; done
[ "$rc" = 0 ] && [ -f "$OUT" ] || abort "! Patching failed, nothing was changed"
file_md5 "$real" > "$MODPATH/orig_md5"
file_md5 "$OUT" > "$MODPATH/patched_md5"
echo "$real" > "$MODPATH/target_path"
set_perm "$OUT" 0 0 0644
c=$(ctx_of "$real"); [ -n "$c" ] && [ "$c" != "?" ] && chcon "$c" "$OUT"
ui_print "- Done. Reboot to apply."
