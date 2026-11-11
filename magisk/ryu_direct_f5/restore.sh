#!/system/bin/sh
# Put the original system files back from /sdcard/ryu_backup.
#   su -c 'sh restore.sh'
set -u
BACKUP=/sdcard/ryu_backup
[ "$(id -u)" = 0 ] || { echo "run as root: su -c 'sh $0'"; exit 1; }
ctx(){ ls -Zd "$1" 2>/dev/null | awk '{print $1}'; }
apk(){ pm path "$1" </dev/null 2>/dev/null | sed -n 's/^package://p' | head -1; }

REMOUNTED=""
rw(){ case " $REMOUNTED " in *" $1 "*) ;; *) mount -o remount,rw "$1" && REMOUNTED="$REMOUNTED $1";; esac; }
restore(){ # <dst> <part>
  d=$1; part=$2
  b="$BACKUP/$(echo "$d" | sed 's#/#_#g')"
  [ -f "$b" ] || { echo "no backup for $d"; return; }
  c=$(ctx "$d"); rw "$part" || { echo "remount failed $part"; return; }
  cp "$b" "$d.ryur" && chown 0:0 "$d.ryur" && chmod 0644 "$d.ryur" || { echo "write failed $d"; return; }
  [ -n "$c" ] && [ "$c" != "?" ] && chcon "$c" "$d.ryur"
  mv -f "$d.ryur" "$d" && echo "restored $d"
}

SET=$(apk com.android.settings)
PK=$(apk com.miui.powerkeeper)
MS=$(apk com.xiaomi.misettings)
MARBLE=/product/etc/device_features/$(getprop ro.product.device).xml
BP=/product/etc/build.prop
case "$SET" in /product/*) PS=/product;; *) PS=/system_ext;; esac
case "$PK"  in /product/*) PP=/product;; *) PP=/system_ext;; esac
case "$MS"  in /system_ext/*) PM=/system_ext;; *) PM=/product;; esac

[ -n "$SET" ] && restore "$SET" "$PS"
[ -n "$PK" ]  && restore "$PK"  "$PP"
[ -n "$MS" ]  && restore "$MS"  "$PM"
restore "$MARBLE" /product
restore "$BP" /product

for p in $REMOUNTED; do mount -o remount,ro "$p" 2>/dev/null; done

echo ""
echo "Reverted. Reboot, then recompile once:"
echo "  su -c 'for p in com.android.settings com.miui.powerkeeper com.xiaomi.misettings; do cmd package compile -f -m speed-profile \$p; done'"
