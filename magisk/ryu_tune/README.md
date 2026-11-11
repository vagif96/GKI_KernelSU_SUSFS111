# Ryu Balanced Tune

A tiny KernelSU/Magisk module with safe, balanced userspace tuning for the stock
Xiaomi 17 Pro Max kernel (GKI 6.12, Snapdragon 8 Elite, walt governor).

It deliberately does **not** touch the CPU governor, CPU frequencies or the I/O
scheduler — those are already well tuned on this chip. It only sets a few runtime
knobs ~1 min after boot (`service.sh`):

* TCP **BBR** + `fq` qdisc (the one change with a clearly noticeable effect:
  steadier throughput on mobile/Wi-Fi), TCP Fast Open;
* small vm tweaks (dirty ratios, `vfs_cache_pressure`) for slightly smoother
  writes and file access;
* storage queues: `iostats`/`add_random` off (tiny efficiency), scheduler stats off.

Everything is a runtime value, so **removing the module and rebooting restores
stock**. Log: `/data/adb/modules/ryu_tune/tune.log`.
