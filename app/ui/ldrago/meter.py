"""System meter backend — CPU, RAM, disk, network. Replaceable."""
import time
import subprocess


def read_cpu() -> float:
    def line():
        with open("/proc/stat") as f:
            return list(map(int, f.readline().split()[1:]))

    a = line()
    time.sleep(0.05)
    b = line()
    da = sum(a) - a[3] - a[4]
    db = sum(b) - b[3] - b[4]
    return max(0.0, min(100.0, (1 - (db - da) / max(1, db)) * 100))


def read_mem() -> float:
    d = {}
    with open("/proc/meminfo") as f:
        for l in f:
            k, v = l.split(":", 1)
            d[k.strip()] = int(v.strip().split()[0])
    return (d["MemTotal"] - d["MemAvailable"]) / d["MemTotal"] * 100


def read_disk(path: str = "/") -> float:
    try:
        out = subprocess.check_output(
            ["df", "-P", path], text=True
        ).splitlines()[1].split()
        used, total = int(out[2]), int(out[1])
        return used / total * 100
    except Exception:
        return 0.0


class _Net:
    def __init__(self):
        self.prev = self._sample()

    def _sample(self):
        rx = tx = 0
        with open("/proc/net/dev") as f:
            for l in f.readlines()[2:]:
                p = l.split()
                if p[0].endswith(":"):
                    p[0] = p[0][:-1]
                if p[0] in ("lo",):
                    continue
                rx += int(p[1])
                tx += int(p[9])
        return (rx, tx)

    def read(self):
        rx, tx = self._sample()
        dr = max(0, rx - self.prev[0])
        dt = max(0, tx - self.prev[1])
        self.prev = (rx, tx)
        return dr / 1024.0, dt / 1024.0


_NET = _Net()


def read_net():
    return _NET.read()


def fmt_bytes(kbs: float) -> str:
    for u in ("KB/s", "MB/s", "GB/s"):
        if kbs < 1024:
            return f"{kbs:6.1f} {u}"
        kbs /= 1024
    return f"{kbs:6.1f} TB/s"


def collect() -> dict:
    return {
        "cpu": read_cpu(),
        "mem": read_mem(),
        "disk": read_disk(),
        "net_rx_kbs": read_net()[0],
        "net_tx_kbs": read_net()[1],
    }
