"""Process Manager Hook — list, monitor, and control system processes."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_rss_mb: float
    memory_vms_mb: float
    threads: int
    user: str
    cmdline: str
    created: str
    parent_pid: Optional[int] = None


class ProcessManager:
    def __init__(self) -> None:
        self._has_psutil = self._check_psutil()
        self._monitored: dict[int, dict] = {}

    def _check_psutil(self) -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    def list_processes(self, sort_by: str = "cpu", limit: int = 50, filter_name: Optional[str] = None) -> list[ProcessInfo]:
        if self._has_psutil:
            return self._list_psutil(sort_by, limit, filter_name)
        return self._list_ps(sort_by, limit, filter_name)

    def _list_psutil(self, sort_by: str, limit: int, filter_name: Optional[str]) -> list[ProcessInfo]:
        import psutil
        procs = []
        for proc in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_percent", "memory_info", "num_threads", "username", "cmdline", "create_time", "ppid"]):
            try:
                info = proc.info
                if filter_name and filter_name.lower() not in (info["name"] or "").lower():
                    continue
                mem = info["memory_info"]
                procs.append(ProcessInfo(pid=info["pid"], name=info["name"] or "", status=info["status"] or "unknown", cpu_percent=info["cpu_percent"] or 0.0, memory_percent=info["memory_percent"] or 0.0, memory_rss_mb=mem.rss / 1024 / 1024 if mem else 0.0, memory_vms_mb=mem.vms / 1024 / 1024 if mem else 0.0, threads=info["num_threads"] or 0, user=info["username"] or "unknown", cmdline=" ".join(info["cmdline"] or [])[:500], created=datetime.fromtimestamp(info["create_time"], tz=timezone.utc).isoformat(), parent_pid=info["ppid"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda p: getattr(p, sort_by, 0), reverse=True)
        return procs[:limit]

    def _list_ps(self, sort_by: str, limit: int, filter_name: Optional[str]) -> list[ProcessInfo]:
        sort_map = {"cpu": "pcpu", "memory_percent": "pmem", "memory_rss_mb": "rss", "pid": "pid", "name": "comm"}
        sort_key = sort_map.get(sort_by, "pcpu")
        cmd = ["ps", "-ax", "-o", "pid=,ppid=,pcpu=,pmem=,rss=,vsz=,state=,user=,comm="]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except FileNotFoundError:
            return []

        procs = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
                cpu = float(parts[2])
                mem = float(parts[3])
                rss_kb = int(parts[4])
                vsz_kb = int(parts[5])
                state = parts[6]
                user = parts[7]
                cmdline = parts[8][:500]
                name = cmdline.split("/")[-1] if "/" in cmdline else cmdline
                name = name[:64]
                if filter_name and filter_name.lower() not in name.lower():
                    continue
                procs.append(ProcessInfo(
                    pid=pid, name=name, status=state,
                    cpu_percent=cpu, memory_percent=mem,
                    memory_rss_mb=rss_kb / 1024.0, memory_vms_mb=vsz_kb / 1024.0,
                    threads=0, user=user, cmdline=cmdline, created="",
                    parent_pid=ppid,
                ))
            except (ValueError, IndexError):
                continue

        reverse = sort_by in ("cpu", "memory_percent", "memory_rss_mb", "pid")
        procs.sort(key=lambda p: getattr(p, sort_by, 0), reverse=reverse)
        return procs[:limit]

    def get_process(self, pid: int) -> Optional[ProcessInfo]:
        for p in self.list_processes(limit=9999):
            if p.pid == pid:
                return p
        return None

    def find_pids(self, name: str) -> list[int]:
        return [p.pid for p in self.list_processes(limit=9999) if name.lower() in p.name.lower()]

    def kill(self, pid: int, sig: int = signal.SIGTERM) -> bool:
        try:
            os.kill(pid, sig)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def kill_by_name(self, name: str, sig: int = signal.SIGTERM) -> int:
        return sum(1 for pid in self.find_pids(name) if self.kill(pid, sig))

    def is_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def system_stats(self) -> dict:
        if self._has_psutil:
            import psutil
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return {"cpu_percent": psutil.cpu_percent(interval=0.1), "cpu_count": psutil.cpu_count(), "memory_total_gb": mem.total / (1024**3), "memory_used_gb": mem.used / (1024**3), "memory_percent": mem.percent, "disk_total_gb": disk.total / (1024**3), "disk_used_gb": disk.used / (1024**3), "disk_percent": disk.percent, "boot_time": datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc).isoformat(), "process_count": len(psutil.pids())}
        try:
            mem_info = {}
            if os.path.exists("/proc/meminfo"):
                for line in open("/proc/meminfo"):
                    parts = line.split()
                    mem_info[parts[0].rstrip(":")] = int(parts[1]) // 1024
            load = open("/proc/loadavg").read().split()[:3] if os.path.exists("/proc/loadavg") else ["N/A"]
            return {"load_1m": load[0], "load_5m": load[1] if len(load) > 1 else "N/A", "memory_total_mb": mem_info.get("MemTotal", 0)}
        except Exception as e:
            return {"error": str(e)}
