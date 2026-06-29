"""AssetEventBus — async pub/sub event bus for asset discoveries.

Decouples producers (scanners, protocol bridges, dispatcher workers) from
consumers (graph persist, LLM orchestrator, GUI dashboard, audit trail).
Supports both push (fire callbacks) and pull (drain accumulated events) modes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class Event:
    topic: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.monotonic)


class AssetEventBus:
    """Async pub/sub for infiltration grinder discoveries.

    Usage:
        bus = AssetEventBus()
        bus.subscribe("service.discovered", my_callback)
        await bus.publish("service.discovered", {"ip": "10.0.0.1", "port": 443})

        # LLM pulls accumulated events between turns:
        events = await bus.drain()
    """

    TOPICS = frozenset({
        "host.discovered",
        "service.discovered",
        "credential.found",
        "vulnerability.matched",
        "share.discovered",
        "user.discovered",
        "edge.added",
        "scan.started",
        "scan.completed",
        "scan.error",
    })

    def __init__(self, max_queue_size: int = 2000) -> None:
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], None | Awaitable[None]]]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._event_count: int = 0
        self._dropped_count: int = 0

    def subscribe(self, topic: str, callback: Callable[[dict[str, Any]], None | Awaitable[None]]) -> str:
        """Register a callback for a topic. Returns a subscription token.

        Callback can be sync or async — dispatch handles both.
        Use '*' to subscribe to all topics.
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)
        return f"{topic}:{id(callback)}"

    def unsubscribe(self, token: str) -> bool:
        """Remove a subscription by token. Returns True if removed."""
        topic_part = token.rsplit(":", 1)[0]
        if topic_part not in self._subscribers:
            return False
        cb_id = int(token.rsplit(":", 1)[1])
        self._subscribers[topic_part] = [
            cb for cb in self._subscribers[topic_part] if id(cb) != cb_id
        ]
        if not self._subscribers[topic_part]:
            del self._subscribers[topic_part]
        return True

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish an event to all subscribers and the drain queue."""
        event = Event(topic=topic, payload=payload)
        self._event_count += 1

        # Push to pull-mode queue
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            self._dropped_count += 1
            logger.warning("Event bus queue full, dropped event: %s", topic)

        # Push to topic subscribers
        for pattern, callbacks in self._subscribers.items():
            if pattern == "*" or pattern == topic:
                for cb in callbacks:
                    try:
                        result = cb(payload)
                        if hasattr(result, "__await__"):
                            await result
                    except Exception:
                        logger.exception("Subscriber callback failed for topic %s", topic)

    async def drain(self) -> list[tuple[str, dict[str, Any]]]:
        """Pull all accumulated events (non-blocking). Returns list of (topic, payload)."""
        events: list[tuple[str, dict[str, Any]]] = []
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                events.append((event.topic, event.payload))
            except asyncio.QueueEmpty:
                break
        return events

    def stats(self) -> dict[str, int]:
        """Return bus statistics."""
        return {
            "events_published": self._event_count,
            "events_dropped": self._dropped_count,
            "queue_size": self._queue.qsize(),
            "subscriber_count": sum(len(v) for v in self._subscribers.values()),
        }
