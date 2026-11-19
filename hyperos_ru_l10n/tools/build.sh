#!/bin/bash
# Rebuild the Russian overlay module from a HyperOS fastboot/recovery ROM zip.
#
# usage: tools/build.sh ROM.zip WORKDIR
# needs: python3 (+ pip androguard loguru for coverage only), zstd, e2fsprogs (debugfs),
#        aapt (v1), zipalign, apksigner, keytool, android-sdk-platform-23, git, zip
set -euo pipefail
ROM=$(realpath "$1"); W=$(realpath -m "$2"); HERE=$(cd "$(dirname "$0")" && pwd); MOD="$HERE/../module"
mkdir -p "$W/super" "$W/ex" "$W/work"

# 1. translations (xiaomi.eu, CC BY-NC-SA 3.0)
[ -d "$W/tr" ] || git clone --depth 1 https://github.com/ingbrzy/hyperos-xml-1.0-russian "$W/tr"

# 2. super.img -> system/product/system_ext/mi_ext trees
if [ ! -d "$W/ex/system" ]; then
  unzip -p "$ROM" images/super.img.zst | zstd -dq -o "$W/super/super.img"
  while read -r n s o _; do
    case $n in mi_ext_a|product_a|system_a|system_ext_a)
      dd if="$W/super/super.img" of="$W/super/${n%_a}.img" bs=1M iflag=skip_bytes,count_bytes skip="$o" count="$s" status=none
      mkdir -p "$W/ex/${n%_a}"; debugfs -R "rdump / $W/ex/${n%_a}" "$W/super/${n%_a}.img" >/dev/null 2>&1 ;;
    esac
  done < <(python3 -I "$HERE/lpparse.py" "$W/super/super.img")
  rm -f "$W/super/super.img"
fi

# 3. package name of every APK in the ROM
( cd "$W/ex" && find . -name '*.apk' -print0 | xargs -0 python3 -I "$HERE/pkgs.py" | sort > "$W/rom_pkgs.txt" )

# 4. overlays
rm -rf "$W/out"
( cd "$W/ex" && python3 -I "$HERE/build_overlays.py" . "$W/tr/Russian/main" "$HERE/map.txt" "$W/rom_pkgs.txt" "$W/out" "$W/work" )
rm -f "$W/out"/*.idsig
rm -f "$MOD"/system/product/overlay/*.apk
cp "$W/out"/*.apk "$MOD/system/product/overlay/"

# 5. module zip
VER=$(sed -n 's/^version=//p' "$MOD/module.prop")
( cd "$MOD" && rm -f "$HERE/../HyperOS4_CN_RU_l10n_$VER.zip" && zip -qr9 "$HERE/../HyperOS4_CN_RU_l10n_$VER.zip" . -x prev_locale )
echo "done: $HERE/../HyperOS4_CN_RU_l10n_$VER.zip"
