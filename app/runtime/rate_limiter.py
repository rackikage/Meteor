"""Per-session rate limiting for orchestrator and GUI ops."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum


class OpClass(str, Enum):
    DEEP = "deep"
    QUICK = "quick"


@dataclass
class RateLimitConfig:
    max_concurrent_deep: int = 1
    max_quick_per_minute: int = 5


@dataclass
class RateLimitResult:
    allowed: bool
    reason: str = ""


class SessionRateLimiter:
    """Limit deep ops to one active per session; cap quick ops per minute."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self._config = config or RateLimitConfig()
        self._lock = threading.Lock()
        self._active_deep: set[str] = set()
        self._quick_timestamps: dict[str, deque[float]] = defaultdict(deque)

    def check(self, session_id: str, op_class: OpClass) -> RateLimitResult:
        with self._lock:
            if op_class == OpClass.DEEP:
                if session_id in self._active_deep:
                    return RateLimitResult(
                        False,
                        "A deep operation is already running for this session.",
                    )
                return RateLimitResult(True)

            now = time.monotonic()
            window = 60.0
            stamps = self._quick_timestamps[session_id]
            while stamps and now - stamps[0] > window:
                stamps.popleft()
            if len(stamps) >= self._config.max_quick_per_minute:
                return RateLimitResult(
                    False,
                    f"Rate limit: max {self._config.max_quick_per_minute} quick ops per minute.",
                )
            return RateLimitResult(True)

    def acquire(self, session_id: str, op_class: OpClass) -> RateLimitResult:
        result = self.check(session_id, op_class)
        if not result.allowed:
            return result
        with self._lock:
            if op_class == OpClass.DEEP:
                self._active_deep.add(session_id)
            else:
                self._quick_timestamps[session_id].append(time.monotonic())
        return RateLimitResult(True)

    def release(self, session_id: str, op_class: OpClass) -> None:
        with self._lock:
            if op_class == OpClass.DEEP:
                self._active_deep.discard(session_id)


_limiter: SessionRateLimiter | None = None


def get_rate_limiter() -> SessionRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SessionRateLimiter()
    return _limiter
