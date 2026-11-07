# OpenWrt для TP-Link Archer AX55 v4

Порт OpenWrt (snapshot, target `qualcommax/ipq50xx`) для Archer AX55 **v4**.
За основу взята уже поддерживаемая в OpenWrt Archer AX55 v1.

> ⚠️ **Образ на железе ещё не проверялся.** Первый запуск — только из RAM
> (initramfs по TFTP), флеш при этом не трогается.

## Что проверено по стоковой прошивке v4

Файл: `ax55v4-up-all-ver1-1-3-P1.20251030-rel63052` (1.1.3 Build 20251030),
support-list `Archer AX55 4.0.0` (US/CA/TW).

| | v4 (сток) | v1 (OpenWrt) |
|---|---|---|
| SoC | IPQ5018, референс MP03.3, CDT `AP-MP03.3_512M16_DDR3` | то же |
| Разметка NAND 128 МБ | SBL1…TRAINING, rootfs `0x640000`, rootfs_1 `0x3040000`, tp_data `0x5a40000` | совпадает байт в байт |
| Кнопки (GPIO) | reset 25, wifi 31 | то же |
| Светодиоды (GPIO) | power 18, wan-orange 22, wan-green 11, lan 10, 2g 13, 5g 39, usb 38 | то же |
| USB VBUS | GPIO 27 | то же |
| Свитч | Realtek по MDIO (сброс GPIO 33), линк 2.5G HSGMII | то же |
| Wi-Fi | IPQ5018 2.4 ГГц + QCN6122 5 ГГц, board-id 0x24 / 0x60 | то же |
| Калибровка (ART) | `0x1000` / `0x26800` | то же |
| MAC | `tp_data/default-mac` | то же |

**Единственное отличие** — board data файлы Wi-Fi (BDF): у v4 они
перенастроены (1–3 КБ отличий). Поэтому у v4 отдельный
`calibration-variant` и пакет `ipq-wifi-tplink_archer-ax55-v4`, а его
`board-2.bin` собран из стоковых `bdwlan.b24` и `qcn6122/bdwlan.b60`
(`tools/make-board-2.py`; на файлах v1 он воспроизводит upstream
байт в байт).

## Известный риск: чип свитча

Сток v4 содержит драйвер Realtek, который поддерживает и RTL8367S, и
RTL8367D. На части плат AX55 стоит **RTL8367D** (chip id `0x6642`), а
драйвер OpenWrt `rtl8365mb` его пока не поддерживает. Тогда проводные
порты работать не будут.

Поэтому в тестовом образе Wi-Fi включается сам при первой загрузке
(файл `files/etc/rc.local`):

- SSID: `OpenWrt-AX55v4-test`
- пароль: `ax55v4test`
- адрес: http://192.168.1.1, пользователь `root`, без пароля

## Сборка

GitHub Actions (`.github/workflows/openwrt-ax55-v4.yml`) собирает образ
при каждом изменении в этой папке. Готовые файлы публикуются в
**Releases** как pre-release `openwrt-ax55-v4-N`. Сборка занимает 1,5–3 часа.

Главные файлы:

- `…-tplink_archer-ax55-v4-initramfs-uImage.itb` — для теста из RAM;
- `…-tplink_archer-ax55-v4-squashfs-sysupgrade.bin` — для установки
  во флеш (только после проверки).

## Тест из RAM (по данным для v1, нужен UART)

1. UART на разъёме JP1, 115200 8N1, **логика 1,8 В** (адаптер на 3,3 В
   может повредить SoC). По данным для v1, дорожка RX разорвана, её
   нужно перемкнуть.
2. ПК: IP `192.168.1.2`, TFTP-сервер с файлом `initramfs-uImage.itb`.
   Кабель в любой LAN-порт.
3. Прервать U-Boot (любая клавиша) и ввести:

   ```
   setenv ipaddr 192.168.1.1
   setenv serverip 192.168.1.2
   tftpboot 0x44000000 openwrt-qualcommax-ipq50xx-tplink_archer-ax55-v4-initramfs-uImage.itb
   bootm
   ```

4. После загрузки прислать вывод:

   ```
   dmesg | grep -iE "rtl8365|realtek|switch|ath11k|ubi"
   cat /proc/mtd
   ip link
   iw dev
   ls /tmp/tp_data
   ```

Перезагрузка возвращает сток: флеш не изменялся.

## Установка во флеш (только после успешного теста)

Из initramfs: `sysupgrade -n <squashfs-sysupgrade.bin>`. Образ ставится
в неактивный слот (`rootfs`/`rootfs_1`), второй слот со стоком остаётся.

## Возврат на сток

Зажать Reset, включить питание. На ПК поставить IP `192.168.0.10` и
загрузить официальный образ TP-Link для v4 на http://192.168.0.1.
