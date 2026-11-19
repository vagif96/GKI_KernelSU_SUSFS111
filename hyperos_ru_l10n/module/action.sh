#!/system/bin/sh
# KernelSU/APatch "Action" button: (re)apply Russian as the system language.
setprop persist.sys.locale ru-RU
settings put system system_locales ru-RU >/dev/null 2>&1
echo "Язык системы установлен: ru-RU"
echo "Перезагрузите устройство, чтобы применить."
