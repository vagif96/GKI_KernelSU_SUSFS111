# Ryu Display AI

Xiaomi 17 Pro Max, ProjectRyu 3.0.319 / HyperOS 3 (global).

HyperOS Settings hide **Display → Screen enhancement engine** (MEMC, super
resolution for video/images, SDR→HDR, AI display) unless the FeatureParser flag
`support_screen_enhance_engine` is true. The global
`/product/etc/device_features/popsicle.xml` lacks it (and `support_AI_display`,
`support_SR_for_image_display`), although the drivers are there
(`ro.vendor.media.video.frc.support=true`, `debug.config.media.video.ais.support=true`,
`ro.vendor.video_box.version=2`).

The module bind-mounts a copy of `popsicle.xml` with those three flags added (only
these lines differ), from `post-fs-data.sh`, before zygote starts. The installer
refuses a different original file; after a firmware update the module disables
itself. Log: `/data/adb/modules/ryu_display_ai/boot.log` (also prints
`ro.vendor.display.hyperos.miDualDPU_support`: if it is `true`, Settings show the
Dual DPU page instead of the engine).

Build: `python3 build.py /path/to/popsicle.xml`
