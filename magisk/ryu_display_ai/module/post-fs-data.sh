#!/system/bin/sh
# Bind-mount the patched device_features before zygote starts.
MODDIR=${0%/*}
real=$(cat "$MODDIR/target_path")
f="$MODDIR/files/$(basename "$real")"
{
  echo "boot $(date)"
  echo "dualDPU: $(getprop ro.vendor.display.hyperos.miDualDPU_support)"
  [ -f "$real" ] && [ -f "$f" ] || { echo "missing files"; exit 0; }
  have=$(md5sum "$real" | cut -d' ' -f1)
  if [ "$have" = "$(cat "$MODDIR/patched_md5")" ]; then echo "already mounted"; exit 0; fi
  if [ "$have" != "$(cat "$MODDIR/orig_md5")" ]; then
    echo "firmware changed ($have) -> disabling"
    touch "$MODDIR/disable"
    sed -i 's/^description=.*/description=DISABLED: firmware changed, rebuild the module/' "$MODDIR/module.prop"
    exit 0
  fi
  chcon "$(ls -Z "$real" | awk '{print $1}')" "$f"
  mount -o bind "$f" "$real" && echo "mounted" || echo "mount failed"
  echo "now: $(md5sum "$real" | cut -d' ' -f1)"
} > "$MODDIR/boot.log" 2>&1
