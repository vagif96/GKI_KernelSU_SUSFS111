#!/system/bin/sh
# remove the override so stock PowerKeeper behaviour is restored
content call --uri content://com.miui.powerkeeper.configure --method PUT_misc --arg ryu_fps_group --extra "value:s:" </dev/null >/dev/null 2>&1
