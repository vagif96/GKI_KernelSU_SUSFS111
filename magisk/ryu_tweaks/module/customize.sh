SKIPUNZIP=0
. "$MODPATH/common.sh"
ui_print "- Ryu Tweaks"
# targets of the APK parts are found on the device
real=$(settings_apk) && echo "$real" > "$MODPATH/parts/settings/target_path"
for d in "$MODPATH"/parts/*; do
  [ -f "$d/package" ] && [ "$(basename "$d")" != settings ] || continue
  real=$(pkg_apk "$(cat "$d/package")")
  if [ "$real" = UPDATED ]; then
    ui_print "! $(basename "$d"): $(cat "$d/package") runs from an update in /data/app, skipped"
    touch "$d/off"; continue
  fi
  [ -n "$real" ] && echo "$real" > "$d/target_path"
done
ok=0
for d in "$MODPATH"/parts/*; do
  name=$(basename "$d")
  [ -f "$d/off" ] && continue
  real=$(cat "$d/target_path" 2>/dev/null)
  if [ ! -f "$real" ]; then ui_print "! $name: target not found, skipped"; touch "$d/off"; continue; fi
  unmount_stale "$real" >/dev/null   # read the firmware file, not an earlier version's mount
  have=$(file_md5 "$real")
  # the file may still be bind-mounted by an installed (older) version of this module
  prev=""
  for pm in /data/adb/modules/ryu_tweaks/parts/$name/patched_md5 \
            /data/adb/modules/ryu_bt_volume/patched_md5 /data/adb/modules/ryu_other_settings_icons/patched_md5 \
            /data/adb/modules/ryu_display_ai/patched_md5 /data/adb/modules/ryu_app_fps/patched_md5; do
    [ -f "$pm" ] && prev="$prev $(cat "$pm")"
  done
  case " $prev " in *" $have "*) ui_print "- $name: currently patched by the installed version";; esac
  if [ "$have" != "$(cat "$d/orig_md5")" ] && ! echo " $prev " | grep -q " $have "; then
    ui_print "! $name: built for another firmware, skipped"; touch "$d/off"; continue
  fi
  [ "$(file_md5 "$d/file")" = "$(cat "$d/patched_md5")" ] || abort "! $name: damaged module zip"
  set_perm "$d/file" 0 0 0644
  c=$(ctx_of "$real"); [ -n "$c" ] && [ "$c" != "?" ] && chcon "$c" "$d/file"
  ui_print "- $name: OK ($real)"
  ok=1
done
[ "$ok" = 1 ] || abort "! Nothing matches this firmware (nothing was changed)"
# the separate modules are replaced by this one
for old in ryu_other_settings_icons ryu_bt_volume ryu_display_ai ryu_app_fps; do
  if [ -d "/data/adb/modules/$old" ]; then
    touch "/data/adb/modules/$old/remove"; ui_print "- old module $old will be removed"
  fi
done
[ -d "$MODPATH/parts/powerkeeper" ] && ui_print "- Refresh rate: Settings > Display > Refresh rate > Apps using high refresh rate (also in Default mode)"
ui_print "- Reboot to apply."
