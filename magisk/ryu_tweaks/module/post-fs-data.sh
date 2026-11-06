#!/system/bin/sh
# Bind-mount every enabled part before zygote/audioserver start.
MODDIR=${0%/*}
. "$MODDIR/common.sh"
{
  echo "boot $(date)"
  for d in "$MODDIR"/parts/*; do
    name=$(basename "$d"); real=$(cat "$d/target_path" 2>/dev/null)
    [ -f "$d/off" ] && { echo "$name: off"; continue; }
    [ -f "$real" ] && [ -f "$d/file" ] || { echo "$name: missing files"; continue; }
    have=$(file_md5 "$real")
    [ "$have" = "$(cat "$d/patched_md5")" ] && { echo "$name: already mounted"; continue; }
    if [ "$have" != "$(cat "$d/orig_md5")" ]; then
      echo "$name: firmware changed ($have) -> off"; touch "$d/off"; continue
    fi
    chcon "$(ctx_of "$real")" "$d/file"
    mount -o bind "$d/file" "$real" && echo "$name: mounted -> $real" || echo "$name: mount failed"
  done
} > "$MODDIR/boot.log" 2>&1
