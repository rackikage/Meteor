"""Footprint layer — passive recon before active infiltration.

Collects what we already know about the local environment and the asset graph
without firing scans at a target. Safe for MCP read-only profiles.
"""

from __future__ import annotations

from typing import Any, Optional


class FootprintLayer:
    """Build an engagement footprint: local network scope + graph stats + arsenal."""

    def collect(self, *, engagement_cidr: str = "") -> dict[str, Any]:
        """Return a structured footprint snapshot.

        ``engagement_cidr`` is recorded as the declared authorized scope for this
        run (does not trigger scanning — use ``grinder.grind_subnet`` for that).
        """
        from app.tools.pentest.network_scope import discover_network_scope
        from app.runtime.asset_context import get_asset_context

        scope = discover_network_scope()
        footprint: dict[str, Any] = {
            "engagement_cidr": engagement_cidr or None,
            "local_scope": {
                "gateway": scope.gateway,
                "cidr": scope.cidr,
                "priority_targets": list(scope.priority_targets),
                "summary": scope.summary_lines(),
            },
        }

        try:
            ctx = get_asset_context()
            footprint["graph"] = ctx.graph_tool.stats()
            footprint["grinder_stats"] = {
                "tasks_completed": ctx.grinder.stats.tasks_completed,
                "hosts_discovered": ctx.grinder.stats.hosts_discovered,
                "services_discovered": ctx.grinder.stats.services_discovered,
            }
            footprint["event_bus"] = ctx.event_bus.stats()
        except Exception as exc:  # noqa: BLE001 — headless partial boot
            footprint["graph_error"] = str(exc)

        try:
            from app.tools.system.registry import get_registry
            from app.arsenal.weapons import ArsenalTool
            arsenal = get_registry().get("arsenal")
            if isinstance(arsenal, ArsenalTool):
                footprint["arsenal"] = arsenal.detect()
        except Exception as exc:  # noqa: BLE001
            footprint["arsenal_error"] = str(exc)

        footprint["next_steps"] = self._next_steps(footprint, engagement_cidr)
        return footprint

    @staticmethod
    def _next_steps(footprint: dict, cidr: str) -> list[str]:
        steps = ["graph.query recent hosts", "network.scope already captured"]
        if cidr:
            steps.insert(0, f"grinder.grind_subnet cidr={cidr} (requires METEOR_MCP_ALLOWED_CIDR on MCP)")
        g = footprint.get("graph") or {}
        if not g.get("hosts", 0):
            steps.append("grinder.grind_host or nmap.discover on authorized targets")
        steps.append("infiltration.intercept after grinding to pull bus discoveries")
        return steps
