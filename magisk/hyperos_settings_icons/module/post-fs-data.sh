#!/system/bin/sh
# Bind-mount the patched files before zygote starts.  After a firmware update the
# new Settings.apk is patched again automatically; a prebuilt APK part whose
# firmware file changed is switched off.
# Mounts come from hard links in $LINKDIR (outside /data/adb): Zygisk implementations
# (ReZygisk ...) remove mounts whose source is under /data/adb/modules from app processes.
MODDIR=${0%/*}
. "$MODDIR/common.sh"

link_mount() {  # <file> <name> <target>
  mkdir -p "$LINKDIR" && chmod 0700 "$LINKDIR"
  ln -f "$1" "$LINKDIR/$2" 2>/dev/null || cp -f "$1" "$LINKDIR/$2"
  chcon "$(ctx_of "$3")" "$LINKDIR/$2"
  mount -o bind "$LINKDIR/$2" "$3" && echo "$2: mounted -> $3" || echo "$2: mount failed"
}

settings() {
  real=$(cat "$MODDIR/target_path" 2>/dev/null)
  [ -f "$real" ] || real=$(settings_apk)
  [ -f "$real" ] || { echo "settings: Settings.apk not found"; return; }
  unmount_stale "$real"
  have=$(file_md5 "$real")
  if [ "$have" = "$(cat "$MODDIR/patched_md5")" ]; then echo "settings: already mounted"; return; fi
  if [ "$have" != "$(cat "$MODDIR/orig_md5")" ] || [ ! -f "$MODDIR/Settings.apk" ]; then
    echo "settings: Settings.apk changed ($have), patching again"
    if "$MODDIR/bin/ryu_patch" $(patch_opts) "$real" "$MODDIR/Settings.apk.new" "$MODDIR/icons"; then
      mv -f "$MODDIR/Settings.apk.new" "$MODDIR/Settings.apk"
      echo "$have" > "$MODDIR/orig_md5"
      file_md5 "$MODDIR/Settings.apk" > "$MODDIR/patched_md5"
      echo "$real" > "$MODDIR/target_path"
      chmod 0644 "$MODDIR/Settings.apk"
    else
      rm -f "$MODDIR/Settings.apk.new"; echo "settings: patching failed, original left as is"; return
    fi
  fi
  link_mount "$MODDIR/Settings.apk" settings "$real"
}

{
  echo "boot $(date)"
  rm -f "$LINKDIR/Settings.apk"   # link name used by v1.1-1.2
  settings
  for d in "$MODDIR"/parts/*; do
    [ -d "$d" ] || continue
    name=$(basename "$d"); real=$(cat "$d/target_path" 2>/dev/null)
    [ -f "$d/off" ] && { echo "$name: off"; continue; }
    [ -f "$real" ] && [ -f "$d/file" ] || { echo "$name: missing files"; continue; }
    unmount_stale "$real"
    have=$(file_md5 "$real")
    [ "$have" = "$(cat "$d/patched_md5")" ] && { echo "$name: already mounted"; continue; }
    if [ "$have" != "$(cat "$d/orig_md5")" ]; then
      echo "$name: firmware changed ($have) -> off"; touch "$d/off"; continue
    fi
    link_mount "$d/file" "$name" "$real"
  done
} > "$MODDIR/boot.log" 2>&1
