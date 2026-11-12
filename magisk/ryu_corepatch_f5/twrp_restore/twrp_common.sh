# shared body for the TWRP update-binary (sourced after ui_print/abort are defined)
# expects: $JAR (services.jar to write), $MODE ("restore" or "apply"),
#          $ORIG_MD5, $PATCHED_MD5 (from the payload)
md5of(){ md5sum "$1" 2>/dev/null | cut -d' ' -f1; }

MNT=/ryu_sys; mkdir -p "$MNT"; MOUNTED=""
# 1) try to mount the system dynamic partition rw at our own mountpoint
for blk in /dev/block/mapper/system /dev/block/mapper/system_a /dev/block/mapper/system-verity \
           /dev/block/by-name/system /dev/block/by-name/system_a; do
  [ -e "$blk" ] || continue
  umount "$MNT" 2>/dev/null
  mount -o rw "$blk" "$MNT" 2>/dev/null && { MOUNTED="$MNT"; break; }
done
# 2) otherwise use whatever TWRP already mounted
if [ -z "$MOUNTED" ]; then
  for mp in /system_root /mnt/system /system; do
    [ -d "$mp" ] || continue
    mount -o remount,rw "$mp" 2>/dev/null
    [ -w "$mp" ] && { MOUNTED="$mp"; break; }
  done
fi
[ -n "$MOUNTED" ] || abort "cannot mount the system partition rw"
ui_print "- system mounted at $MOUNTED"

# find services.jar
TGT=""
for p in "$MOUNTED/system/framework/services.jar" "$MOUNTED/framework/services.jar"; do
  [ -f "$p" ] && { TGT="$p"; break; }
done
[ -n "$TGT" ] || abort "services.jar not found under $MOUNTED"
cur=$(md5of "$TGT")
ui_print "- target: $TGT"

if [ "$MODE" = apply ]; then
  [ "$cur" = "$PATCHED_MD5" ] && { ui_print "- already patched, nothing to do"; umount "$MNT" 2>/dev/null; exit 0; }
  [ "$cur" = "$ORIG_MD5" ] || abort "services.jar is not the firmware this patch was built for (md5 $cur)"
fi
# (restore just overwrites whatever is there with the bundled original)

c=$(ls -Zd "$TGT" 2>/dev/null | awk '{print $1}')
[ -n "$c" ] && [ "$c" != "?" ] || c=u:object_r:system_file:s0
cp "$JAR" "$TGT.ryunew" || abort "write failed (no space / read-only?)"
chown 0:0 "$TGT.ryunew" 2>/dev/null; chmod 0644 "$TGT.ryunew"
chcon "$c" "$TGT.ryunew" 2>/dev/null
mv -f "$TGT.ryunew" "$TGT" || abort "rename failed"
new=$(md5of "$TGT")
[ "$new" = "$(md5of "$JAR")" ] || abort "verify failed"
ui_print "- services.jar written ($MODE)"

# drop any stale compiled copies in the partition so the new dex is used
for d in "$MOUNTED/system/framework/oat" "$MOUNTED/framework/oat"; do
  rm -f "$d"/*/services.odex "$d"/*/services.vdex "$d"/*/services.art 2>/dev/null
done
sync
umount "$MNT" 2>/dev/null
ui_print " "
ui_print "Done. Reboot. First boot is slower (services recompiles)."
exit 0
