"""Intercept layer — capture discovery intel from the asset event bus.

This intercepts **your pipeline's own events** (hosts/services/vulns the grinder
published) — not third-party network traffic. Think structured SIGINT on your
authorized scan output, not illegal wiretapping.
"""

from __future__ import annotations

import asyncio
from typing import Any


class InterceptLayer:
    """Drain the asset event bus and summarize discoveries."""

    def capture(self, *, max_events: int = 200) -> dict[str, Any]:
        """Pull queued bus events and bucket them by topic."""
        from app.runtime.asset_context import get_asset_context

        ctx = get_asset_context()
        events = asyncio.run(ctx.event_bus.drain())
        if len(events) > max_events:
            events = events[-max_events:]

        buckets: dict[str, list[dict]] = {}
        for topic, payload in events:
            buckets.setdefault(topic, []).append(payload)

        summary = {
            topic: len(items) for topic, items in buckets.items()
        }
        highlights: list[dict[str, Any]] = []
        for topic in ("host.discovered", "service.discovered", "vulnerability.matched"):
            for payload in buckets.get(topic, [])[:10]:
                highlights.append({"topic": topic, **payload})

        return {
            "events_captured": len(events),
            "by_topic": summary,
            "highlights": highlights,
            "bus_stats": ctx.event_bus.stats(),
            "graph_counts": ctx.graph_tool.stats(),
            "note": "Intercepted pipeline events only — not raw network packets.",
        }

    def peek_graph(self, limit: int = 20) -> dict[str, Any]:
        """Latest hosts/services in the graph (read-only intercept of persisted state)."""
        from app.runtime.asset_context import get_asset_context

        ctx = get_asset_context()
        hosts = ctx.graph.query(
            "SELECT ip, source, last_seen FROM hosts ORDER BY last_seen DESC LIMIT ?",
            (limit,),
        )
        services = ctx.graph.query(
            "SELECT h.ip, s.port, s.name, s.banner FROM services s "
            "JOIN hosts h ON h.id = s.host_id ORDER BY s.last_seen DESC LIMIT ?",
            (limit,),
        )
        return {
            "hosts": hosts,
            "services": services,
            "counts": ctx.graph_tool.stats(),
        }
