# Интеграция модификаций в прошивку — Xiaomi 17 Pro Max

**Телефон:** Xiaomi 17 Pro Max (`popsicle`), ProjectRyu / HyperOS 3, Android 16.
**Разделы:** erofs + verity (enforcing) → прямая запись в телефоне невозможна.
**Вывод:** всё интегрируется **на этапе репака прошивки на ПК** — файлы кладём внутрь
образов (`system`/`system_ext`/`product`/`odm`) перед упаковкой, verity пересобирается
репакером.

Это общий чек-лист. Для каждого пункта: **что меняем**, **файл в прошивке (куда класть)**,
**откуда берём / как пересобрать**.

> ⚠️ Патченые APK привязаны к конкретной версии прошивки (их `classes.dex` и ресурсы — из
> той сборки). Если base репака другой версии, чем та, с которой я собирал, — APK надо
> **пересобрать из APK этой base**, иначе будет несовпадение/вылет. XML и props от версии
> почти не зависят.

---

## 1. Settings.apk — иконки + «Сохранённые сети» Wi-Fi

- **Что:** HyperOS-иконки в «Расширенные настройки» (+ разблокирован скрытый пункт
  «Видеоинструменты»); Wi-Fi → «Сохранённые сети» открывает стоковый подробный экран
  (QR, удалить, подключить), а его Compose-пункты скрыты.
- **Файл в прошивке:** `/system_ext/priv-app/Settings/Settings.apk`
  (подпись v1-only, без APK Signing Block — `META-INF` остаётся как есть).
- **Источник:** `magisk/ryu_tweaks/parts/settings/` (патчится нативным `ryu_patch`).
- **Пересобрать:**
  ```sh
  # из Settings.apk взятого ИЗ base репака:
  magisk/hyperos_settings_icons/patcher/ryu_patch  Settings.apk  Settings.patched.apk  icons/
  ```
  (иконки: `magisk/hyperos_settings_icons/build.py` EXTRA + `magisk/ryu_settings_icons/icons.py`)

- **ВАЖНО для порта HyperOS 3.0.332 / A17 (popsicle) — две правки, без которых иконки НЕ видны:**
  1. **НЕ использовать `--no-showicon`.** Экран `xml/other_personal_settings` состоит из
     `com.android.settingslib.miuisettings.preference.Preference`, а этот класс в `PreferenceDelegate`
     вызывает `hideIcon()` (setIcon(null) + обнуление `mIconResId` через рефлексию), ЕСЛИ нет
     `miuisettings:showIcon="true"`. Поэтому нужен И `android:icon`, И `showIcon="true"` на каждой
     записи — то есть поведение `ryu_patch` ПО УМОЛЧАНИЮ (без флага). `ValuePreference` наследует
     miuix `TextPreference` и показал бы `android:icon` и без флага, но лишний `showIcon` ему не мешает.
  2. **Таблица ресурсов в этом порте SPARSE.** Новые drawable не резолвятся, пока тип `drawable`
     не разрежён в плотные u32-смещения. Разрядить ТОЛЬКО тип `drawable` (≈+0.7 МБ; весь arsc = +13 МБ
     и раздел не влезает). Скрипт: `desparse2.py` (де-спарс одного типа в сыром `resources.arsc`),
     затем `ryu_patch` на получившийся apk. Проверка: `aapt2 dump xmltree` экрана должен показывать
     у каждой записи и `android:icon=@…`, и `miuisettings:showIcon=true`.

- **Доставка на этом ROM — ТОЛЬКО запись в раздел (или вшивание в прошивку).** Модуль KernelSU
  НЕ накладывает priv-app (SUSFS + overlayfs `mi_ext` на `/system_ext/priv-app` — проверено:
  `pm path`/`mount` показывают исходный файл раздела, оверлей модуля не виден). Запись вживую:
  `mount -o remount,rw /system_ext` (общий суперблок), затем свежий `mount <dm системного_ext> /mnt/se`
  (видит сырой ext4 без оверлея), `cp` в `/mnt/se/priv-app/Settings/Settings.apk`, `restorecon`,
  `rm -rf …/oat`, `sync`, `umount`. Номер `dm-X` плавает между загрузками — брать из `mount | grep ' /system_ext '`.

## 2. Громкость Bluetooth/наушников (снятие EU-лимита)

- **Что:** кривые громкости music без EU-лимита (`_CE`): 0 dB на максимуме, середина +3–4 dB,
  никогда выше 0 dB. Для HEADSET/A2DP и наушников.
- **Файл в прошивке:** `/odm/etc/audio_policy_engine_stream_volumes_mi.xml`
- **Источник:** `magisk/ryu_tweaks/parts/audio/` (готовый патченый XML).

## 3. AI-обработка изображения (Дисплей → «AI image processing»)

- **Что:** супер-разрешение, AI-улучшение изображения, AI HDR, MEMC.
- **Файл в прошивке:** `/product/etc/device_features/popsicle.xml`
- **Правка:** эти `<bool>` = `true`:
  `support_screen_enhance_engine`, `support_AI_display`, `support_SR_for_image_display`.
- **Источник:** `magisk/ryu_tweaks/parts/display/` (готовый патченый XML).

## 4. Super Resolution / MEMC — пропсы

- **Что:** без этих пропсов пункты SR/MEMC в UI не включаются полноценно.
- **Файл в прошивке:** `build.prop` раздела **product** → `/product/etc/build.prop`
  (можно и `/vendor/build.prop`).
- **Правка:** дописать строки:
  ```
  debug.config.media.video.ais.support=true
  debug.config.media.video.frc.support=true
  ```
- **Источник:** `magisk/ryu_inplace_twrp/payload/patch.sh` (шаг 3).

## 5. Частота обновления по приложениям (адаптивный режим)

Две части, работают в паре.

### 5a. PowerKeeper.apk
- **Что:** в адаптивном («По умолчанию») режиме приложения, **выключенные** в экране
  Xiaomi «Приложения с высокой частотой», идут 60 Гц; **включённые** сторонние —
  не режутся ниже 120 Гц (чинит кейс, когда WhatsApp застревал на 90).
- **Файл в прошивке:** `/system_ext/app/PowerKeeper/PowerKeeper.apk`
- **Источник / пересборка:** `magisk/ryu_hz/build.py` (патч smali: методы
  `ryuMerged`/`ryuRefresh`).

### 5b. MiSettings.apk
- **Что:** показывает пункт «Приложения с высокой частотой» и в адаптивном режиме.
- **Файл в прошивке:** `/product/priv-app/MiSettings/MiSettings.apk`
- **Источник / пересборка:** `magisk/ryu_hz/build.py` (патч `NewRefreshRateFragment`).

### 5c. PowerKeeper `custom_switch` (НЕ файл раздела!)
- **Что:** на моделях, которых PowerKeeper не знает, экран «по приложениям» скрыт, пока
  не выставлен misc-флаг `custom_switch = {"fucSwitch":"true"}` (хранится в данных
  PowerKeeper в `/data`, сам PowerKeeper его не сбрасывает).
- **В прошивку файлом не кладётся.** Варианты при репаке:
  - оставить крошечный модуль/`addon.d`/init-скрипт, который один раз после загрузки
    делает `content call … PUT_misc custom_switch …` (как в `ryu_tweaks/module/service.sh`), **или**
  - пропатчить PowerKeeper, чтобы он считал `custom_switch` всегда включённым.
- **Решаем на шаге интеграции** — напомни, обсудим как удобнее.

---

## 6. Ryu Balanced Tune — сетевой/IO тюнинг (опционально)

- **Что (userspace, governor/частоты/IO-планировщик не трогаются):**
  - `net.ipv4.tcp_congestion_control = bbr`, `net.core.default_qdisc = fq`
  - `net.ipv4.tcp_fastopen = 3`
  - `vm.dirty_background_ratio = 5`, `vm.dirty_ratio = 20`,
    `vm.vfs_cache_pressure = 80`, `vm.stat_interval = 10`
  - per-queue: `iostats = 0`, `add_random = 0`
  - `kernel.sched_schedstats = 0`
- **В прошивку:** это рантайм-sysctl, не файл раздела. При репаке — либо init-`.rc`
  скрипт в `/vendor/etc/init` (или `/system/etc/init`), либо оставить модулем.
- **Источник:** `magisk/ryu_tune/module/service.sh`.

---

## Сводная таблица «что куда»

| # | Модификация | Файл в прошивке | Источник в репо |
|---|---|---|---|
| 1 | Иконки + Wi-Fi | `/system_ext/priv-app/Settings/Settings.apk` | `ryu_tweaks/parts/settings` (ryu_patch) |
| 2 | Громкость BT | `/odm/etc/audio_policy_engine_stream_volumes_mi.xml` | `ryu_tweaks/parts/audio` |
| 3 | AI-дисплей | `/product/etc/device_features/popsicle.xml` | `ryu_tweaks/parts/display` |
| 4 | SR/MEMC пропсы | `/product/etc/build.prop` (строки) | `ryu_inplace_twrp/payload/patch.sh` |
| 5a | Частота/прил. | `/system_ext/app/PowerKeeper/PowerKeeper.apk` | `ryu_hz/build.py` |
| 5b | Частота/UI | `/product/priv-app/MiSettings/MiSettings.apk` | `ryu_hz/build.py` |
| 5c | custom_switch | — (init/модуль, не файл) | `ryu_tweaks/module/service.sh` |
| 6 | Тюнинг | — (init `.rc` или модуль) | `ryu_tune/module/service.sh` |

## Порядок интеграции при репаке
1. Распаковать `super.img` → `system/system_ext/product/odm` (erofs → RW-дерево).
2. Положить файлы 1,2,3,5a,5b; дописать пропсы (4) в product build.prop.
3. Решить, как завести 5c (custom_switch) и 6 (тюнинг): init-скрипт в образе или модуль.
4. Пересобрать образы + verity, собрать `super`, упаковать прошивку.
5. Прошить.

> Замечание по F5: core patch (services.jar, снятие проверки подписи) и мод Mi Browser —
> это **для POCO F5**, не для 17 Pro Max. В greeshan-репаке проверка подписи уже отключена,
> поэтому отдельный core patch для 17 Pro Max обычно не нужен.
