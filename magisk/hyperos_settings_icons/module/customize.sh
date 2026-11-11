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
# prebuilt APK parts (refresh rate per app in the adaptive mode); each one is
# used only if the phone has exactly the APK it was built from
for d in "$MODPATH"/parts/*; do
  [ -d "$d" ] || continue
  name=$(basename "$d"); pkg=$(cat "$d/package")
  real=$(pkg_apk "$pkg")
  if [ "$real" = UPDATED ]; then ui_print "! $name: $pkg runs from an update in /data/app, skipped"; touch "$d/off"; continue; fi
  [ -f "$real" ] || { ui_print "! $name: $pkg not found, skipped"; touch "$d/off"; continue; }
  unmount_stale "$real" >/dev/null   # read the firmware file, not an earlier version's mount
  have=$(file_md5 "$real")
  prev=$(cat "/data/adb/modules/hyperos_settings_icons/parts/$name/patched_md5" 2>/dev/null)
  if [ "$have" != "$(cat "$d/orig_md5")" ] && [ "$have" != "$prev" ]; then
    ui_print "! $name: built for another firmware, skipped"; touch "$d/off"; continue
  fi
  [ "$(file_md5 "$d/file")" = "$(cat "$d/patched_md5")" ] || abort "! $name: damaged module zip"
  echo "$real" > "$d/target_path"
  set_perm "$d/file" 0 0 0644
  c=$(ctx_of "$real"); [ -n "$c" ] && [ "$c" != "?" ] && chcon "$c" "$d/file"
  ui_print "- $name: OK ($real)"
done
[ -f "$MODPATH/parts/powerkeeper/off" ] || [ ! -d "$MODPATH/parts/powerkeeper" ] || \
  ui_print "- Refresh rate: Display > Refresh rate > Apps using high refresh rate (also in Default mode)"
ui_print "- Done. Reboot to apply."
