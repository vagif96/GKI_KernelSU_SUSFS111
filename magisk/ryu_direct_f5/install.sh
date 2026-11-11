#!/system/bin/sh
# Ryu Tweaks – direct install for POCO F5 (ext4 RW ROM). Writes the patched files
# straight into the system partitions, so no module is needed afterwards.
# Originals are backed up to /sdcard/ryu_backup; restore.sh puts them back.
#
# BEFORE running this: remove the hyperos_settings_icons module in your manager and
# reboot, so the real (unpatched) system files are exposed.
#
#   su -c 'sh install.sh'
set -u
DIR=${0%/*}; [ "$DIR" = "$0" ] && DIR=.
DIR=$(cd "$DIR" && pwd)
BACKUP=/sdcard/ryu_backup
LOG="$BACKUP/install.log"

say(){ echo "$@"; }
die(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root: su -c 'sh $0'"
[ "$(getprop ro.product.device)" = marble ] || say "! device is '$(getprop ro.product.device)', expected marble – continuing anyway"

ctx(){ ls -Zd "$1" 2>/dev/null | awk '{print $1}'; }
md5(){ md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
apk(){ pm path "$1" </dev/null 2>/dev/null | sed -n 's/^package://p' | head -1; }

SET=$(apk com.android.settings);  case "$SET" in */data/*|"") die "Settings.apk not found in system";; esac
PK=$(apk com.miui.powerkeeper);   case "$PK"  in */data/*|"") die "PowerKeeper.apk not found";; esac
MS=$(apk com.xiaomi.misettings);  case "$MS"  in */data/*|"") die "MiSettings.apk not found";; esac
MARBLE=/product/etc/device_features/$(getprop ro.product.device).xml
BP=/product/etc/build.prop
[ -f "$MARBLE" ] || die "$MARBLE not found"
[ -f "$BP" ] || die "$BP not found"

# the module must be gone, otherwise we read its mounted (already patched) files
if [ "$(md5 "$PK")" = "$(cat "$DIR/pk_patched_md5")" ]; then
  die "the module is still active (PowerKeeper is the patched one). Remove the hyperos_settings_icons module, reboot, then run this again."
fi
[ "$(md5 "$PK")" = "$(cat "$DIR/pk_orig_md5")" ] || die "PowerKeeper.apk is not the firmware this installer was built for ($(md5 "$PK"))"
[ "$(md5 "$MS")" = "$(cat "$DIR/ms_orig_md5")" ] || die "MiSettings.apk is not the firmware this installer was built for ($(md5 "$MS"))"

PART_SET=/system_ext; case "$SET" in /product/*) PART_SET=/product;; esac
PART_PK=/system_ext;  case "$PK"  in /product/*) PART_PK=/product;;  esac
PART_MS=/product;     case "$MS"  in /system_ext/*) PART_MS=/system_ext;; esac

mkdir -p "$BACKUP" || die "cannot create $BACKUP"
echo "install $(date)" > "$LOG"
say "- targets:"; say "    $SET"; say "    $PK"; say "    $MS"; say "    $MARBLE"

# ---- backup ----
for f in "$SET" "$PK" "$MS" "$MARBLE" "$BP"; do
  b="$BACKUP/$(echo "$f" | sed 's#/#_#g')"
  if [ ! -f "$b" ]; then cp "$f" "$b" || die "backup failed: $f"; fi
done
say "- originals backed up to $BACKUP"

# ---- build patched files in /data (plenty of room) ----
TMP=/data/local/tmp/ryu_direct.$$; rm -rf "$TMP"; mkdir -p "$TMP" || die tmp
chmod 0755 "$DIR/bin/ryu_patch"
"$DIR/bin/ryu_patch" "$SET" "$TMP/Settings.apk" "$DIR/icons" >>"$LOG" 2>&1; rc=$?
[ "$rc" = 3 ] && die "Settings.apk is already patched. Run restore.sh first."
{ [ "$rc" = 0 ] && [ -f "$TMP/Settings.apk" ]; } || die "patching Settings.apk failed (see $LOG)"
say "- Settings.apk patched"
cp "$DIR/PowerKeeper.apk" "$TMP/PowerKeeper.apk" || die cp
cp "$DIR/MiSettings.apk"  "$TMP/MiSettings.apk"  || die cp

cp "$MARBLE" "$TMP/marble.xml"
for fl in support_screen_enhance_engine support_AI_display support_SR_for_image_display; do
  if grep -q "name=\"$fl\"" "$TMP/marble.xml"; then
    sed -i "s#<bool name=\"$fl\">false</bool>#<bool name=\"$fl\">true</bool>#" "$TMP/marble.xml"
  elif grep -q "<!-- Display END -->" "$TMP/marble.xml"; then
    sed -i "s#<!-- Display END -->#<bool name=\"$fl\">true</bool><!-- Display END -->#" "$TMP/marble.xml"
  else
    sed -i "s#</features>#<bool name=\"$fl\">true</bool></features>#" "$TMP/marble.xml"
  fi
done

# ---- atomic replace keeping owner/mode/SELinux context ----
REMOUNTED=""
rw(){ case " $REMOUNTED " in *" $1 "*) ;; *) mount -o remount,rw "$1" || die "remount rw $1"; REMOUNTED="$REMOUNTED $1";; esac; }
writefile(){ # <src> <dst> <part>
  c=$(ctx "$2"); rw "$3"
  cp "$1" "$2.ryunew" || die "write $2"
  chown 0:0 "$2.ryunew"; chmod 0644 "$2.ryunew"
  [ -n "$c" ] && [ "$c" != "?" ] && chcon "$c" "$2.ryunew"
  mv -f "$2.ryunew" "$2" || die "rename $2"
  [ "$(md5 "$2")" = "$(md5 "$1")" ] || die "verify failed: $2"
  say "- wrote $2"
}
writefile "$TMP/Settings.apk"    "$SET"    "$PART_SET"
writefile "$TMP/PowerKeeper.apk" "$PK"     "$PART_PK"
writefile "$TMP/MiSettings.apk"  "$MS"     "$PART_MS"
writefile "$TMP/marble.xml"      "$MARBLE" /product

# ---- props for Super resolution + MEMC (persist in build.prop) ----
rw /product
for kv in "debug.config.media.video.ais.support=true" "debug.config.media.video.frc.support=true"; do
  grep -q "^${kv%%=*}=" "$BP" || echo "$kv" >> "$BP"
done
say "- build.prop updated"

for p in $REMOUNTED; do mount -o remount,ro "$p" 2>/dev/null; done

# set them live for this session too
for k in debug.config.media.video.ais.support debug.config.media.video.frc.support; do
  if command -v resetprop >/dev/null 2>&1; then resetprop -n "$k" true; else setprop "$k" true 2>/dev/null; fi
done

# enable PowerKeeper's per-app refresh-rate screen (stored in /data, persists)
content call --uri content://com.miui.powerkeeper.configure --method PUT_misc \
  --arg custom_switch --extra 'value:s:{"fucSwitch"\:"true"}' </dev/null >>"$LOG" 2>&1

rm -rf "$TMP"

# ---- recompile the replaced apps once (avoid a background recompile / lag) ----
say "- recompiling (this takes a minute)…"
for p in com.android.settings com.miui.powerkeeper com.xiaomi.misettings; do
  nice -n 19 cmd package compile -f -m speed-profile "$p" </dev/null >>"$LOG" 2>&1
  say "    $p: $?"
done

say ""
say "Done. Reboot to apply."
say "Revert everything:  su -c 'sh $DIR/restore.sh'"
