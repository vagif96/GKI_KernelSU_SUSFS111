#!/system/bin/sh
# Installed by KernelSU / APatch / Magisk manager while Android is running.
SKIPUNZIP=0

ui_print "- HyperOS 4.0 CN: русская локализация"
ui_print "- Оверлеев: $(ls "$MODPATH/system/product/overlay" | wc -l)"

# Remember the current locale so uninstall.sh can restore it.
prev="$(getprop persist.sys.locale)"
[ -z "$prev" ] && prev="$(getprop ro.product.locale)"
echo "$prev" > "$MODPATH/prev_locale"

# Switch the system language to Russian; it applies after the reboot that the
# module install requires anyway.
setprop persist.sys.locale ru-RU
settings put system system_locales ru-RU >/dev/null 2>&1
ui_print "- Язык системы: ru-RU (после перезагрузки)"
ui_print "- Перезагрузите устройство"

set_perm_recursive "$MODPATH/system" 0 0 0755 0644
