# Bluetooth / headphone volume limits (run as root)
curves() {  # music curves of one stream_volumes file: max and 50% level in dB
  awk '
  function at(v,  i) { if (n == 0) return "";
    if (v <= X[0]) return Y[0]; for (i = 1; i < n; i++) if (v <= X[i])
      return Y[i-1] + (Y[i]-Y[i-1]) * (v-X[i-1]) / (X[i]-X[i-1]); return Y[n-1] }
  /<volumeGroup>/ { g = "" }
  /<name>/ && g == "" { s = $0; sub(/.*<name>/, "", s); sub(/<\/name>.*/, "", s); g = s }
  g == "music" && /<volume / { s = $0; sub(/.*deviceCategory="/, "", s); sub(/".*/, "", s); c = s; n = 0
    if ($0 ~ /ref="/) { r = $0; sub(/.*ref="/, "", r); sub(/".*/, "", r); printf "  %-40s -> %s\n", c, r; c = "" } }
  g == "music" && c != "" && /<point>/ { s = $0; sub(/.*<point>/, "", s); sub(/<\/point>.*/, "", s)
    split(s, p, ","); X[n] = p[1] + 0; Y[n] = p[2] + 0; n++ }
  g == "music" && c != "" && /<\/volume>/ { printf "  %-40s max %6.1f dB   50%%: %6.1f dB\n", c, at(100)/100, at(50)/100; c = "" }
  ' "$1"
}
echo "== device"
getprop ro.product.model; getprop ro.product.mod_device; getprop ro.mi.os.version.incremental
echo "region: $(getprop ro.miui.region)  hwc: $(getprop ro.boot.hwc)  odm engine: $(getprop ro.miui.audio.policy.engine.odm)"
echo "== volume files"
for f in $(ls /odm/etc/audio_policy_engine*stream_volumes*.xml /vendor/etc/audio_policy_engine*stream_volumes*.xml \
           /vendor/etc/audio/*/audio_policy_engine*stream_volumes*.xml 2>/dev/null); do
  echo "$f  $(md5sum "$f" | cut -c1-8)"
  curves "$f"
done
echo "== props (bt / safe volume / region)"
getprop | grep -iE "safe|csd|dose|absvol|absolute|disableabsvol|a2dp_offload\.(cap|disabled)|region|\.ce\]|audio.*limit|vol.*limit|eu\]" | head -40
echo "== dumpsys audio"
dumpsys audio </dev/null > /data/local/tmp/btvol_audio.txt 2>&1
grep -iE "safe media|safemedia|mSafeMediaVolume|csd|sound dose|absolute volume|AbsoluteVolume|PrescaleAbsolute" /data/local/tmp/btvol_audio.txt | head -25
grep -A6 "^- STREAM_MUSIC:" /data/local/tmp/btvol_audio.txt
rm -f /data/local/tmp/btvol_audio.txt
