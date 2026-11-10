#!/system/bin/sh
# Bind-mount the patched Settings.apk before zygote starts.  After a firmware
# update the new Settings.apk is patched again automatically.
MODDIR=${0%/*}
. "$MODDIR/common.sh"
{
  echo "boot $(date)"
  real=$(cat "$MODDIR/target_path" 2>/dev/null)
  [ -f "$real" ] || real=$(settings_apk)
  [ -f "$real" ] || { echo "Settings.apk not found"; exit 0; }
  have=$(file_md5 "$real")
  if [ "$have" = "$(cat "$MODDIR/patched_md5")" ]; then echo "already mounted"; exit 0; fi
  if [ "$have" != "$(cat "$MODDIR/orig_md5")" ] || [ ! -f "$MODDIR/Settings.apk" ]; then
    echo "Settings.apk changed ($have): patching again"
    if "$MODDIR/bin/ryu_patch" "$real" "$MODDIR/Settings.apk.new" "$MODDIR/icons"; then
      mv -f "$MODDIR/Settings.apk.new" "$MODDIR/Settings.apk"
      echo "$have" > "$MODDIR/orig_md5"
      file_md5 "$MODDIR/Settings.apk" > "$MODDIR/patched_md5"
      echo "$real" > "$MODDIR/target_path"
      chmod 0644 "$MODDIR/Settings.apk"
    else
      rm -f "$MODDIR/Settings.apk.new"; echo "patching failed: original Settings left as is"; exit 0
    fi
  fi
  # Mount from outside /data/adb: Zygisk implementations (ReZygisk ...) remove mounts
  # whose source is under /data/adb/modules from app processes, Settings included.
  # A hard link: same file, no extra space.
  D=/data/misc/hyperos_settings_icons
  mkdir -p "$D" && chmod 0700 "$D"
  ln -f "$MODDIR/Settings.apk" "$D/Settings.apk" 2>/dev/null || cp -f "$MODDIR/Settings.apk" "$D/Settings.apk"
  chcon "$(ctx_of "$real")" "$D/Settings.apk"
  mount -o bind "$D/Settings.apk" "$real" && echo "mounted -> $real (from $D)" || echo "mount failed"
} > "$MODDIR/boot.log" 2>&1
