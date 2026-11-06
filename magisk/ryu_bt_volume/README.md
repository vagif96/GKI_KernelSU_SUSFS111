# Ryu BT Volume

KernelSU / Magisk module for Xiaomi 17 Pro Max (ProjectRyu 3.0.319 / HyperOS 3).

HyperOS loads volume curves from `/odm/etc/audio_policy_engine_stream_volumes_mi.xml`.
The `music` group has EU (`_CE`) curves that attenuate Bluetooth / headphones at
maximum volume (A2DP_CE −6.5 dB, A2DP_SPATIALIZER_CE −11.9 dB, HEADSET_CE −10.8 dB,
HEADSET_SPATIALIZER_CE −16.3 dB) and a HEADSET curve ending at −2.9 dB.

The module replaces these music curves with Xiaomi's own non-EU Bluetooth curve
(`DEVICE_CATEGORY_A2DP`, max −0.5 dB), and USB_CE with USB. No curve goes above 0 dB,
so there is no digital gain and no clipping. Nothing outside the music group changes.

`post-fs-data.sh` bind-mounts the patched file before audioserver starts (log:
`/data/adb/modules/ryu_bt_volume/boot.log`). The installer refuses a different
original file, and the module disables itself if the firmware file changes.

Rebuild: `python3 build.py /path/to/audio_policy_engine_stream_volumes_mi.xml`
