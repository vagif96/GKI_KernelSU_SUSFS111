#!/system/bin/sh
# Bind-mount the patched PowerKeeper.apk before zygote starts.
MODDIR=${0%/*}
real=$(cat "$MODDIR/target_path" 2>/dev/null)
apk="$MODDIR/apk/PowerKeeper.apk"
{
  echo "boot $(date)"
  [ -f "$real" ] && [ -f "$apk" ] || { echo "missing files"; exit 0; }
  have=$(md5sum "$real" | cut -d' ' -f1)
  [ "$have" = "$(cat "$MODDIR/patched_md5")" ] && { echo "already mounted"; exit 0; }
  if [ "$have" != "$(cat "$MODDIR/orig_md5")" ]; then
    echo "firmware changed ($have) -> disabling"; touch "$MODDIR/disable"
    sed -i 's/^description=.*/description=DISABLED: firmware changed, rebuild the module/' "$MODDIR/module.prop"
    exit 0
  fi
  chcon "$(ls -Z "$real" | awk '{print $1}')" "$apk"
  mount -o bind "$apk" "$real" && echo "mounted -> $real" || echo "mount failed"
} > "$MODDIR/boot.log" 2>&1
