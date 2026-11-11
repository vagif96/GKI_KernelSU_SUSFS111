# Shared helpers (customize.sh, post-fs-data.sh)
# touch /data/adb/hyperos_icons_no_wifi to keep MIUI's own "Saved networks" screen
patch_opts() { [ -f /data/adb/hyperos_icons_no_wifi ] && echo "--no-wifi"; }
# system APK of a package; prints UPDATED if an update in /data/app is the active one
pkg_apk() {
  local p
  p=$(pm path "$1" 2>/dev/null </dev/null | head -n1 | sed 's/^package://')
  case "$p" in */data/app/*) echo UPDATED; return 1;; esac
  [ -n "$p" ] && [ -f "$p" ] && { echo "$p"; return 0; }
  return 1
}
# hard links for the mounts live outside /data/adb (see post-fs-data.sh)
LINKDIR=/data/misc/hyperos_settings_icons
file_md5() { md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
ctx_of() { ls -Z "$1" 2>/dev/null | awk '{print $1}'; }
# $1 = "pm" to ask the package manager first (not at post-fs-data: it is not running yet)
settings_apk() {
  local p=""
  [ "$1" = pm ] && p=$(pm path com.android.settings 2>/dev/null </dev/null | head -n1 | sed 's/^package://')
  case "$p" in */data/app/*) p="";; esac   # an installed update is not patched
  for c in "$p" /system_ext/priv-app/Settings/Settings.apk /system/system_ext/priv-app/Settings/Settings.apk \
           /product/priv-app/Settings/Settings.apk /system/priv-app/Settings/Settings.apk; do
    [ -n "$c" ] && [ -f "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
# Our bind mounts can survive a "soft"/userspace reboot; remove them before the
# md5 checks, otherwise the still-mounted patched file looks like a firmware change.
unmount_stale() {
  local i=0
  while [ $i -lt 4 ] && grep -q " $1 " /proc/self/mountinfo; do
    umount -l "$1" 2>/dev/null || break
    i=$((i + 1))
  done
  [ $i -gt 0 ] && echo "$(basename "$1"): removed $i earlier mount(s)"
  return 0
}
# Display > "AI image processing": FeatureParser flags of the screen enhancement engine.
# <in> <out>; each flag is set to true (or added); returns 1 if nothing changed.
# touch /data/adb/hyperos_icons_no_ai to leave device_features alone.
AI_FLAGS="support_screen_enhance_engine support_AI_display support_SR_for_image_display"
ai_features() {
  cp -f "$1" "$2" || return 1
  for f in $AI_FLAGS; do
    if grep -q "name=\"$f\"" "$2"; then
      sed -i "s#<bool name=\"$f\">false</bool>#<bool name=\"$f\">true</bool>#" "$2"
    elif grep -q "<!-- Display END -->" "$2"; then
      sed -i "s#<!-- Display END -->#<bool name=\"$f\">true</bool><!-- Display END -->#" "$2"
    else
      sed -i "s#</features>#<bool name=\"$f\">true</bool></features>#" "$2"
    fi
  done
  chmod 0644 "$2"
  ! cmp -s "$1" "$2"
}
# Super resolution (video) and MEMC entries are shown only if these properties are
# "true" (ScreenEnhanceEngineStatusCheck); they are debug.* props, set at every boot.
# touch /data/adb/hyperos_icons_no_memc to leave MEMC out.
ai_props() {
  local p
  for p in debug.config.media.video.ais.support debug.config.media.video.frc.support; do
    case "$p" in *frc*) [ -f /data/adb/hyperos_icons_no_memc ] && continue;; esac
    [ "$(getprop "$p")" = true ] && continue
    if command -v resetprop >/dev/null 2>&1; then resetprop -n "$p" true; else setprop "$p" true; fi
    echo "features: $p=$(getprop "$p")"
  done
}
features_xml() { echo "/product/etc/device_features/$(getprop ro.product.device).xml"; }
