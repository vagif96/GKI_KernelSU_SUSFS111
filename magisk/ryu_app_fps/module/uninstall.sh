#!/system/bin/sh
# remove the overrides so stock PowerKeeper behaviour is restored
for k in ryu_fps_group ryu_fps_smart_group ryu_fps_choices; do
  content call --uri content://com.miui.powerkeeper.configure --method PUT_misc --arg $k --extra "value:s:" </dev/null >/dev/null 2>&1
done
