# In-place patcher body (sourced by update-binary; ui_print/abort already defined).
# Patches whatever Settings.apk / device_features xml / build.prop are on the device.
# $PD = payload dir, $OUTFD set.
PATCHTMP=/tmp/ryu_work; rm -rf "$PATCHTMP"; mkdir -p "$PATCHTMP"
BACKUP_PART=""   # mountpoints we remounted, to put back ro
md5of(){ md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
ctxof(){ ls -Zd "$1" 2>/dev/null | awk '{print $1}'; }

# ---- mount the system dynamic partitions rw, collect their mountpoints in $ROOTS ----
ROOTS=""
mount_named(){   # <name> -> echoes mountpoint
  local n="$1" blk mp
  for blk in /dev/block/mapper/$n /dev/block/mapper/${n}_a /dev/block/by-name/$n /dev/block/by-name/${n}_a; do
    [ -e "$blk" ] || continue
    mp="/ryu_$n"; mkdir -p "$mp"
    umount "$mp" 2>/dev/null
    mount -o rw "$blk" "$mp" 2>/dev/null && { echo "$mp"; return 0; }
  done
  # already mounted by TWRP?
  for mp in "/$n" "/mnt/$n" "/system_root"; do
    [ -d "$mp" ] && mount -o remount,rw "$mp" 2>/dev/null && [ -w "$mp" ] && { echo "$mp"; return 0; }
  done
  echo ""
}
for n in system system_ext product; do
  mp=$(mount_named "$n"); [ -n "$mp" ] && ROOTS="$ROOTS $mp"
done
[ -n "$ROOTS" ] || abort "could not mount any system partition rw"
ui_print "- mounted:$ROOTS"

find_one(){ # <relative glob> : first match across all roots
  local g="$1" r f
  for r in $ROOTS; do
    f=$(find "$r" -path "*$g" 2>/dev/null | head -n1)
    [ -n "$f" ] && { echo "$f"; return 0; }
  done
  echo ""
}

BK=/data/ryu_inplace_backup; mkdir -p "$BK" 2>/dev/null

# ---- 1) Settings.apk : icons + stock Wi-Fi (native patcher) ----
SET=$(find_one "/priv-app/Settings/Settings.apk")
if [ -n "$SET" ]; then
  ui_print "- Settings.apk: $SET"
  [ -f "$BK/Settings.apk" ] || cp "$SET" "$BK/Settings.apk"
  rc=0
  "$PD/bin/ryu_patch" "$SET" "$PATCHTMP/Settings.apk" "$PD/icons" >/tmp/ryu_patch.log 2>&1 || rc=$?
  if [ "$rc" = 3 ]; then
    ui_print "  (already patched, skipped)"
  elif [ "$rc" = 0 ] && [ -f "$PATCHTMP/Settings.apk" ]; then
    c=$(ctxof "$SET")
    cp "$PATCHTMP/Settings.apk" "$SET.ryunew" && chmod 0644 "$SET.ryunew" && chown 0:0 "$SET.ryunew" 2>/dev/null
    [ -n "$c" ] && [ "$c" != "?" ] && chcon "$c" "$SET.ryunew" 2>/dev/null
    mv -f "$SET.ryunew" "$SET" && ui_print "  icons + Wi-Fi: done"
    # drop stale compiled copy
    rm -f "$(dirname "$SET")"/oat/*/Settings.odex "$(dirname "$SET")"/oat/*/Settings.vdex 2>/dev/null
  else
    ui_print "  !! Settings patch failed (see /tmp/ryu_patch.log) – skipped"
  fi
else
  ui_print "- Settings.apk not found – skipped"
fi

# ---- 2) device_features/<device>.xml : AI image processing ----
DEV=$(getprop ro.product.device 2>/dev/null)
DF=""
[ -n "$DEV" ] && DF=$(find_one "/etc/device_features/$DEV.xml")
[ -n "$DF" ] || DF=$(find_one "/etc/device_features/popsicle.xml")
[ -n "$DF" ] || DF=$(for r in $ROOTS; do ls -S "$r"/*/etc/device_features/*.xml "$r"/etc/device_features/*.xml 2>/dev/null | head -1; done | head -1)
if [ -n "$DF" ] && [ -f "$DF" ]; then
  ui_print "- AI display flags: $DF"
  [ -f "$BK/$(basename "$DF")" ] || cp "$DF" "$BK/$(basename "$DF")"
  changed=0
  for fl in support_screen_enhance_engine support_AI_display support_SR_for_image_display; do
    if grep -q "name=\"$fl\"" "$DF"; then
      grep -q "<bool name=\"$fl\">true</bool>" "$DF" || { sed -i "s#<bool name=\"$fl\">false</bool>#<bool name=\"$fl\">true</bool>#" "$DF"; changed=1; }
    elif grep -q "<!-- Display END -->" "$DF"; then
      sed -i "s#<!-- Display END -->#<bool name=\"$fl\">true</bool><!-- Display END -->#" "$DF"; changed=1
    else
      sed -i "s#</features>#<bool name=\"$fl\">true</bool></features>#" "$DF"; changed=1
    fi
  done
  ui_print "  AI image processing: $( [ "$changed" = 1 ] && echo enabled || echo "already on" )"
else
  ui_print "- device_features xml not found – AI display skipped"
fi

# ---- 3) build.prop : super resolution + MEMC ----
BP=$(find_one "/etc/build.prop" )
# prefer product build.prop if several
for r in $ROOTS; do [ -f "$r/product/etc/build.prop" ] && BP="$r/product/etc/build.prop" && break; [ -f "$r/etc/build.prop" ] && { case "$r" in *product*) BP="$r/etc/build.prop";; esac; }; done
if [ -n "$BP" ] && [ -f "$BP" ]; then
  ui_print "- props: $BP"
  [ -f "$BK/build.prop" ] || cp "$BP" "$BK/build.prop"
  for kv in "debug.config.media.video.ais.support=true" "debug.config.media.video.frc.support=true"; do
    grep -q "^${kv%%=*}=" "$BP" || echo "$kv" >> "$BP"
  done
  ui_print "  SR / MEMC props added"
else
  ui_print "- build.prop not found – props skipped"
fi

sync
for r in $ROOTS; do case "$r" in /ryu_*) umount "$r" 2>/dev/null;; *) mount -o remount,ro "$r" 2>/dev/null;; esac; done
rm -rf "$PATCHTMP"
ui_print " "
ui_print "Done. Reboot. First boot recompiles Settings (slower once)."
ui_print "Refresh-rate per app (PowerKeeper/MiSettings) is NOT in this zip –"
ui_print "send those two APKs after you boot the new ROM and I build it."
ui_print "Originals backed up to /data/ryu_inplace_backup"
exit 0
