#!/system/bin/sh
# Core Patch for POCO F5 (ext4 RW): disables APK signature verification in
# services.jar (verifySignatures -> true, compareSignatures -> SIGNATURE_MATCH),
# so any-signature apps/updates install, including over system apps.
# Writes directly into the framework partition. Originals -> /sdcard/ryu_backup/corepatch.
#
# !! Framework patch. A wrong services.jar = bootloop. Make a TWRP backup of
#    System and System_ext FIRST. Recover with restore.sh or that backup.
#
#   su -c 'sh install.sh'
set -u
DIR=${0%/*}; [ "$DIR" = "$0" ] && DIR=.
DIR=$(cd "$DIR" && pwd)
BACKUP=/sdcard/ryu_backup/corepatch
LOG=/sdcard/ryu_backup/corepatch.log

say(){ echo "$@"; }
die(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root: su -c 'sh $0'"
ctx(){ ls -Zd "$1" 2>/dev/null | awk '{print $1}'; }
md5(){ md5sum "$1" 2>/dev/null | cut -d' ' -f1; }

SJ=""
for c in /system/framework/services.jar /system_ext/framework/services.jar /system/system_ext/framework/services.jar; do
  [ -f "$c" ] && { SJ="$c"; break; }
done
[ -n "$SJ" ] || die "services.jar not found"
case "$SJ" in /system_ext/*) PART=/system_ext;; /system/system_ext/*) PART=/system;; *) PART=/system;; esac
OATDIR="$(dirname "$SJ")/oat"
say "- services.jar: $SJ"

cur=$(md5 "$SJ")
[ "$cur" = "$(cat "$DIR/services_patched_md5")" ] && die "already patched (services.jar is the patched one)."
[ "$cur" = "$(cat "$DIR/services_orig_md5")" ] || die "services.jar is NOT the firmware this patch was built for (md5 $cur). A firmware update changed it: re-send services.jar so I can rebuild."
[ "$(md5 "$DIR/services.jar")" = "$(cat "$DIR/services_patched_md5")" ] || die "damaged package (services.jar checksum)"

mkdir -p "$BACKUP" || die "cannot create $BACKUP"
echo "corepatch $(date)" > "$LOG"
# backup original jar + its compiled artifacts
[ -f "$BACKUP/services.jar" ] || cp "$SJ" "$BACKUP/services.jar" || die "backup failed"
OATS=""
for a in "$OATDIR"/*/services.odex "$OATDIR"/*/services.vdex "$OATDIR"/*/services.art; do
  [ -f "$a" ] || continue
  OATS="$OATS $a"
  b="$BACKUP/oat_$(echo "$a" | tr '/' '@')"
  [ -f "$b" ] || cp "$a" "$b"
done
say "- backed up services.jar$( [ -n "$OATS" ] && echo " + oat artifacts" ) to $BACKUP"

c=$(ctx "$SJ")
mount -o remount,rw "$PART" || die "remount rw $PART"
cp "$DIR/services.jar" "$SJ.ryunew" || { mount -o remount,ro "$PART"; die "write failed"; }
chown 0:0 "$SJ.ryunew"; chmod 0644 "$SJ.ryunew"
[ -n "$c" ] && [ "$c" != "?" ] && chcon "$c" "$SJ.ryunew"
mv -f "$SJ.ryunew" "$SJ" || { mount -o remount,ro "$PART"; die "rename failed"; }
[ "$(md5 "$SJ")" = "$(cat "$DIR/services_patched_md5")" ] || { mount -o remount,ro "$PART"; die "verify failed"; }
say "- patched services.jar written"
# remove stale compiled artifacts so the patched dex is used (clean recompile on boot)
for a in $OATS; do rm -f "$a" && say "- removed stale $(basename "$a")"; done
mount -o remount,ro "$PART" 2>/dev/null

say ""
say "Done. Reboot. The FIRST boot is slower (services is recompiled) – wait a few minutes."
say "Revert:  su -c 'sh $DIR/restore.sh'"
