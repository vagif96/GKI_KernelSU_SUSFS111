#!/system/bin/sh
# Balanced tuning, applied once ~1 min after boot. Only safe userspace knobs:
# nothing here touches the cpu governor (walt), cpu frequencies or the I/O scheduler.
# Everything is a runtime value, so removing the module + reboot restores stock.
MODDIR=${0%/*}
L="$MODDIR/tune.log"
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 5; done
sleep 60
echo "ryu_tune $(date)" > "$L"

w(){ # <path> <value>
  [ -e "$1" ] && [ -w "$1" ] || { echo "skip  $1" >> "$L"; return; }
  echo "$2" > "$1" 2>/dev/null && echo "set   $1 = $2" >> "$L" || echo "fail  $1" >> "$L"
}
sc(){ w "/proc/sys/$(echo "$1" | tr . /)" "$2"; }

# --- network: BBR + fair queueing (the one change with a real, noticeable effect) ---
if grep -qw bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null; then
  sc net.ipv4.tcp_congestion_control bbr
  w /proc/sys/net/core/default_qdisc fq
fi
sc net.ipv4.tcp_fastopen 3

# --- vm: slightly smoother writes, keep file caches a little longer (balanced) ---
sc vm.dirty_background_ratio 5
sc vm.dirty_ratio 20
sc vm.vfs_cache_pressure 80
sc vm.stat_interval 10

# --- storage queues: drop per-I/O stats / entropy accounting (tiny efficiency) ---
#     the scheduler itself (cpq / mq-deadline) is left exactly as the firmware set it.
for q in /sys/block/sd*/queue; do
  w "$q/iostats" 0
  w "$q/add_random" 0
done

# --- scheduler statistics accounting off (micro-efficiency); governor untouched ---
sc kernel.sched_schedstats 0

echo "done" >> "$L"
