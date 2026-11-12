#!/system/bin/sh
# Restore the original services.jar (and its oat artifacts) from /sdcard/ryu_backup/corepatch.
#   su -c 'sh restore.sh'
set -u
BACKUP=/sdcard/ryu_backup/corepatch
[ "$(id -u)" = 0 ] || { echo "run as root: su -c 'sh $0'"; exit 1; }
ctx(){ ls -Zd "$1" 2>/dev/null | awk '{print $1}'; }
[ -f "$BACKUP/services.jar" ] || { echo "no backup at $BACKUP"; exit 1; }

SJ=""
for c in /system/framework/services.jar /system_ext/framework/services.jar /system/system_ext/framework/services.jar; do
  [ -f "$c" ] && { SJ="$c"; break; }
done
[ -n "$SJ" ] || { echo "services.jar not found"; exit 1; }
case "$SJ" in /system_ext/*) PART=/system_ext;; /system/system_ext/*) PART=/system;; *) PART=/system;; esac

c=$(ctx "$SJ")
mount -o remount,rw "$PART" || { echo "remount rw failed"; exit 1; }
cp "$BACKUP/services.jar" "$SJ.ryur" && chown 0:0 "$SJ.ryur" && chmod 0644 "$SJ.ryur" && { [ -n "$c" ] && chcon "$c" "$SJ.ryur"; mv -f "$SJ.ryur" "$SJ"; echo "restored $SJ"; }
# restore oat artifacts
for b in "$BACKUP"/oat_*; do
  [ -f "$b" ] || continue
  dst=$(basename "$b"); dst=$(echo "${dst#oat_}" | tr '@' '/')
  [ -d "$(dirname "$dst")" ] && cp "$b" "$dst" && chmod 0644 "$dst" && echo "restored $dst"
done
mount -o remount,ro "$PART" 2>/dev/null
echo ""
echo "Reverted. Reboot."
