"""InfiltrationGrinder — autonomous network exploration engine.

The Grinder closes the loop between the AssetGraph (state) and the StealthScanner
(probes). It reads the graph for unscanned hosts/subnets, fans out concurrent
workers at a rate governed by host noise floor, and publishes discoveries to the
EventBus — which auto-persists them to the graph via pre-wired subscribers.

Architecture:
    AssetGraph ──(targets)──► Grinder ──(scan tasks)──► StealthScanner
         ▲                        │                           │
         │                        ▼                           ▼
         └────(auto-persist)── AssetEventBus ◄──(publish)─────┘

Meteor Doctrine #4: Runtime is the product. The Grinder is the runtime.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.dispatcher.noise import NoiseFloorSampler
from app.graph.event_bus import AssetEventBus
from app.graph.sqlite_graph import SQLiteAssetGraph
from app.tools.pentest.scanner import StealthScanner, ScanConfig
from app.tools.pentest.raw_scanner import HybridScanner

logger = logging.getLogger(__name__)

DEFAULT_COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443,
                        445, 993, 995, 1723, 3306, 3389, 5432, 5900, 6379,
                        8080, 8443, 27017]
DEFAULT_SUBSET_PORTS = [22, 80, 443, 445, 3389, 8080]
DEFAULT_SWEEP_PORTS = [22, 80, 443, 445]


@dataclass
class GrinderTask:
    ip: str
    ports: list[int]
    source: str = "grinder"


@dataclass
class GrinderStats:
    tasks_queued: int = 0
    tasks_completed: int = 0
    services_discovered: int = 0
    hosts_discovered: int = 0
    errors: int = 0
    wall_time_ms: float = 0.0


class InfiltrationGrinder:
    """Autonomous network exploration loop.

    Reads targets from the AssetGraph, fans out concurrent StealthScanner
    workers at a rate determined by the host noise floor (LotL), and publishes
    all discoveries to the EventBus.

    Usage:
        grinder = InfiltrationGrinder(graph, bus, scanner, noise)
        await grinder.grind_subnet("10.0.0.0/24")
    """

    def __init__(
        self,
        graph: SQLiteAssetGraph,
        event_bus: AssetEventBus,
        scanner: Optional[StealthScanner] = None,
        noise: Optional[NoiseFloorSampler] = None,
        min_workers: int = 3,
        max_workers: int = 500,
    ) -> None:
        self._graph = graph
        self._bus = event_bus
        # Prefer raw SYN scanner (root) — falls back to connect-scan automatically
        self._scanner = HybridScanner(pps=2000, connect_concurrent=200, event_bus=event_bus)
        self._noise = noise or NoiseFloorSampler()
        self._min_workers = min_workers
        self._max_workers = max_workers
        self._stats = GrinderStats()
        self._running = False

    @property
    def stats(self) -> GrinderStats:
        return self._stats

    # ── Public API ────────────────────────────────────────────────────

    async def grind_subnet(
        self,
        cidr: str,
        ports: Optional[list[int]] = None,
        scan: str = "common",
    ) -> GrinderStats:
        """Scan an entire subnet, writing results to the graph via events.

        scan mode:
            "common" → DEFAULT_COMMON_PORTS (23 ports)
            "subset" → DEFAULT_SUBSET_PORTS (6 ports)
            "sweep"  → DEFAULT_SWEEP_PORTS (4 ports)
            custom list → passed directly
        """
        ports = ports or _resolve_ports(scan)
        await self._bus.publish("scan.started", {"cidr": cidr, "ports": ports})

        import time
        t0 = time.monotonic()
        self._stats = GrinderStats()
        self._running = True

        # Discover hosts in the subnet, then fan out
        tasks = [
            self._grind_single_host(ip, ports)
            for ip in self._expand_cidr(cidr)
        ]

        self._stats.tasks_queued = len(tasks)

        try:
            await self._fan_out(tasks)
        finally:
            self._running = False

        self._stats.wall_time_ms = (time.monotonic() - t0) * 1000
        await self._bus.publish("scan.completed", {
            "cidr": cidr,
            "hosts_queued": self._stats.tasks_queued,
            "services_discovered": self._stats.services_discovered,
            "wall_time_ms": self._stats.wall_time_ms,
        })
        return self._stats

    async def grind_host(self, ip: str, ports: Optional[list[int]] = None) -> GrinderStats:
        """Deep scan a single host."""
        ports = ports or DEFAULT_COMMON_PORTS
        await self._bus.publish("scan.started", {"ip": ip, "ports": ports})

        import time
        t0 = time.monotonic()
        self._stats = GrinderStats()
        self._running = True

        try:
            await self._grind_single_host(ip, ports)
        finally:
            self._running = False

        self._stats.wall_time_ms = (time.monotonic() - t0) * 1000
        await self._bus.publish("scan.completed", {
            "ip": ip,
            "services_discovered": self._stats.services_discovered,
            "wall_time_ms": self._stats.wall_time_ms,
        })
        return self._stats

    async def grind_sector(self, cidr: Optional[str] = None,
                           ports: Optional[list[int]] = None) -> GrinderStats:
        """Query the graph for unscanned hosts and scan them all.

        Without a cidr, scans every host in the graph with state='up'.
        """
        ports = ports or DEFAULT_SUBSET_PORTS

        if cidr:
            subnets = self._graph.query(
                "SELECT id, cidr FROM subnets WHERE cidr = ?", (cidr,))
            if not subnets:
                self._graph.upsert_subnet(cidr)
                subnets = self._graph.query(
                    "SELECT id, cidr FROM subnets WHERE cidr = ?", (cidr,))
        else:
            subnets = self._graph.query(
                "SELECT id, cidr FROM subnets WHERE scope_session IS NOT NULL")

        all_tasks: list[GrinderTask] = []
        for sub in subnets:
            c = sub["cidr"]
            for ip in self._expand_cidr(c):
                all_tasks.append(GrinderTask(ip=ip, ports=list(ports)))

        if not all_tasks:
            return self._stats

        import time
        t0 = time.monotonic()
        self._stats = GrinderStats()
        self._stats.tasks_queued = len(all_tasks)
        self._running = True

        try:
            worker_tasks = [self._grind_single_host(t.ip, t.ports) for t in all_tasks]
            await self._fan_out(worker_tasks)
        finally:
            self._running = False

        self._stats.wall_time_ms = (time.monotonic() - t0) * 1000
        await self._bus.publish("scan.completed", {
            "cidr": cidr or "global",
            "hosts_queued": self._stats.tasks_queued,
            "services_discovered": self._stats.services_discovered,
            "wall_time_ms": self._stats.wall_time_ms,
        })
        return self._stats

    # ── Internal ───────────────────────────────────────────────────────

    async def _grind_single_host(self, ip: str, ports: list[int]) -> None:
        """Scan a single host and count discoveries."""
        try:
            results = await self._scanner.scan_host(ip, ports)
            open_count = sum(1 for r in results if isinstance(r, object) and getattr(r, "open", False))
            self._stats.tasks_completed += 1
            self._stats.services_discovered += open_count

            if open_count > 0:
                self._stats.hosts_discovered += 1
                self._graph.upsert_host(ip=ip, source="grinder")
                await self._bus.publish("host.discovered", {
                    "ip": ip, "source": "grinder",
                    "open_ports": open_count,
                })
        except Exception:
            self._stats.errors += 1
            logger.debug("Grinder: scan error for %s", ip, exc_info=True)

    async def _fan_out(self, tasks: list) -> None:
        """Execute all tasks with concurrency bounded by noise floor.

        Re-samples noise floor every 2s and adjusts semaphore dynamically.
        """
        count = self._noise.worker_count(self._min_workers, self._max_workers)
        sem = asyncio.Semaphore(count)
        logger.info("Grinder: starting %d tasks with %d workers", len(tasks), count)

        async def _bounded(coro):
            async with sem:
                await coro

        noise_task = asyncio.create_task(self._noise.start()) if not self._noise._task else None

        try:
            async with asyncio.TaskGroup() as tg:
                for t in tasks:
                    tg.create_task(_bounded(t))
        except* Exception:
            pass
        finally:
            if noise_task:
                await self._noise.stop()

    @staticmethod
    def _expand_cidr(cidr: str) -> list[str]:
        """Expand a CIDR block to a list of IPs. Handles /24 and /32."""
        import ipaddress
        net = ipaddress.ip_network(cidr, strict=False)
        if net.prefixlen >= 28:
            return [str(ip) for ip in net.hosts()]
        return [str(net.network_address + i) for i in range(1, min(net.num_addresses - 1, 256))]


def _resolve_ports(scan: str) -> list[int]:
    """Return port list for a scan mode string."""
    mapping = {
        "common": DEFAULT_COMMON_PORTS,
        "subset": DEFAULT_SUBSET_PORTS,
        "sweep": DEFAULT_SWEEP_PORTS,
    }
    return mapping.get(scan, DEFAULT_SWEEP_PORTS)
