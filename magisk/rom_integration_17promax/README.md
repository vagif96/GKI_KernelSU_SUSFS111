# Вшивание модификаций в ROM (Xiaomi 17 Pro Max, без модулей)

Цель: всё зашито прямо в разделы прошивки — поставил один раз, нечему «удаляться».
Подходит под **любую HyperOS 3 прошивку для 17 Pro Max** (`popsicle`).

## Инструмент: MIO-KITCHEN (Windows 11)
Умеет распаковывать `payload.bin`/`super.img` и recovery-ZIP, разбирать erofs-разделы
в папки, собирать обратно и чинить verity/AVB. GUI.

## Что от базы зависит, а что нет
- **Зависит (патчу я из файлов твоего ROM):** `Settings.apk`, `PowerKeeper.apk`, `MiSettings.apk`.
- **НЕ зависит (готово в этой папке):** тюнинг `system/etc/init/ryu_tune.rc`,
  две строки в product `build.prop` (`product_build.prop.add`).
  XML (`popsicle.xml`, аудио) — патчатся по твоему файлу, но правка типовая.

## Шаги
1. **Ты:** скачал прошивку → открыл в MIO-KITCHEN → распаковал `super`/`payload` →
   распаковал erofs-разделы `system_ext`, `product`, `odm` в папки.
2. **Ты → мне** пришли файлы из распакованного дерева:
   - `system_ext/priv-app/Settings/Settings.apk`
   - `system_ext/app/PowerKeeper/PowerKeeper.apk`
   - `product/priv-app/MiSettings/MiSettings.apk`
   - `product/etc/device_features/popsicle.xml`
   - `odm/etc/audio_policy_engine_stream_volumes_mi.xml`
   - `product/etc/build.prop`
   (пути у разных ROM могут чуть отличаться — если не найдёшь, скажи, подскажу поиск.)
3. **Я → тебе** верну папку с готовыми патчеными файлами и точными путями:
   куда какой класть (включая PowerKeeper с зашитым флагом — экран «по приложениям»
   работает без модуля).
4. **Ты:** копируешь мои файлы по путям поверх распакованного дерева; дописываешь 2
   строки из `product_build.prop.add` в `product/etc/build.prop`; кладёшь
   `ryu_tune.rc` в `system/etc/init/`.
5. **Ты:** в MIO-KITCHEN собираешь разделы обратно (erofs), собираешь `super`,
   упаковываешь прошивку с отключённой проверкой (verity/AVB), шьёшь.

## Карта «файл → путь в прошивке»
| файл | путь |
|---|---|
| Settings.apk (патч) | `system_ext/priv-app/Settings/Settings.apk` |
| PowerKeeper.apk (патч, флаг зашит) | `system_ext/app/PowerKeeper/PowerKeeper.apk` |
| MiSettings.apk (патч) | `product/priv-app/MiSettings/MiSettings.apk` |
| popsicle.xml (патч) | `product/etc/device_features/popsicle.xml` |
| audio ...stream_volumes_mi.xml (патч) | `odm/etc/audio_policy_engine_stream_volumes_mi.xml` |
| build.prop (+2 строки) | `product/etc/build.prop` |
| ryu_tune.rc (новый) | `system/etc/init/ryu_tune.rc` |

Подробный разбор каждой модификации — в `../INTEGRATION_17PROMAX.md`.
