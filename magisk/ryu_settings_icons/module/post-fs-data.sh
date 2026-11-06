#!/system/bin/sh
# Bind-mount the patched Settings.apk over the original one (before zygote and
# PackageManager start).  Skips itself if the firmware changed.
MODDIR=${0%/*}
. "$MODDIR/common.sh"
LOG="$MODDIR/boot.log"
real=$(cat "$MODDIR/target_path" 2>/dev/null)
apk="$MODDIR/apk/Settings.apk"
{
  echo "boot $(date)"
  [ -f "$real" ] && [ -f "$apk" ] || { echo "missing files"; exit 0; }
  have=$(file_md5 "$real")
  if [ "$have" = "$(cat "$MODDIR/patched_md5")" ]; then echo "already mounted"; exit 0; fi
  if [ "$have" != "$(cat "$MODDIR/settings_md5")" ]; then
    echo "firmware changed ($have) -> disabling"
    touch "$MODDIR/disable"
    sed -i 's/^description=.*/description=DISABLED: firmware changed, rebuild the module for the new Settings.apk/' "$MODDIR/module.prop"
    exit 0
  fi
  ctx=$(ls -Z "$real" | awk '{print $1}')
  chcon "$ctx" "$apk"
  mount -o bind "$apk" "$real" && echo "mounted $apk -> $real" || echo "mount failed"
  echo "now: $(file_md5 "$real")"
} > "$LOG" 2>&1
