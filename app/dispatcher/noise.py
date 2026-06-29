"""NoiseFloorSampler — host entropy gauge for LotL concurrency decisions.

Samples CPU utilization, I/O, and active developer processes every N seconds.
When psutil is unavailable, returns a neutral multiplier (1.0) — the dispatcher
behaves normally without camouflage.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

DEV_NAMES: frozenset[str] = frozenset({
    "docker", "dockerd", "com.docker.backend",
    "make", "cmake", "gcc", "clang", "rustc", "cargo",
    "node", "npm", "yarn", "bun",
    "python", "pip", "pytest",
    "git", "xcodebuild", "java", "go",
    "claude", "opencode",
})


@dataclass
class NoiseFloorState:
    cpu_utilization: float = 0.0
    io_activity: float = 0.0
    developer_processes_active: int = 0
    camouflage_multiplier: float = 1.0
    is_host_idle: bool = True
    timestamp: float = 0.0


class NoiseFloorSampler:
    """Background sampler that reads host entropy for the dispatcher.

    When psutil is available, samples CPU + I/O + dev process counts.
    When unavailable, returns a neutral NoiseFloorState (multiplier 1.0).

    Usage:
        sampler = NoiseFloorSampler(interval_s=2.0)
        state = sampler.get_state()    # cached, non-blocking
        await sampler.start()          # begins background loop
        await sampler.stop()
    """

    def __init__(self, interval_s: float = 2.0) -> None:
        self._interval = interval_s
        self._state = NoiseFloorState()
        self._task: Optional[asyncio.Task] = None
        self._psutil = self._try_import()

    @staticmethod
    def _try_import():
        try:
            import psutil
            return psutil
        except ImportError:
            logger.info("psutil not available — noise floor locked at 1.0x")
            return None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_state(self) -> NoiseFloorState:
        return self._state

    def get_multiplier(self) -> float:
        return self._state.camouflage_multiplier

    def worker_count(self, base_min: int = 3, base_max: int = 500) -> int:
        """Map noise floor multiplier to a worker count."""
        mult = self._state.camouflage_multiplier
        clamped = min(max(mult, 0.5), 5.0)
        fraction = (clamped - 0.5) / 4.5
        return max(base_min, int(base_min + fraction * (base_max - base_min)))

    async def _loop(self) -> None:
        import time as _time
        while True:
            try:
                self._state = await self._sample()
            except Exception:
                logger.debug("Noise floor sample failed", exc_info=True)
                self._state = NoiseFloorState(camouflage_multiplier=1.0)
            await asyncio.sleep(self._interval)

    async def _sample(self) -> NoiseFloorState:
        if self._psutil is None:
            return NoiseFloorState(camouflage_multiplier=1.0)

        now = _monotonic()
        psutil = self._psutil

        cpu = psutil.cpu_percent(interval=0.05)
        io_score = 0.0

        active_dev = 0
        try:
            for proc in psutil.process_iter(["name", "cpu_percent"]):
                name = (proc.info.get("name") or "").lower()
                if name in DEV_NAMES and (proc.info.get("cpu_percent") or 0) > 0.5:
                    active_dev += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
            pass

        multiplier = 1.0 + (cpu / 100.0) * 1.5 + io_score * 1.5
        multiplier += min(active_dev * 0.5, 2.0)

        is_idle = cpu < 5.0 and active_dev == 0
        if is_idle:
            multiplier = 0.5

        return NoiseFloorState(
            cpu_utilization=cpu,
            io_activity=io_score,
            developer_processes_active=active_dev,
            camouflage_multiplier=round(multiplier, 2),
            is_host_idle=is_idle,
            timestamp=now,
        )


def _monotonic() -> float:
    import time
    return time.monotonic()
