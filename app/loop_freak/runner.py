"""Loop Freak runner — headless multi-round recon pulse."""

from __future__ import annotations

from typing import Any


class LoopFreakRunner:
    """Repeat read-mostly pipeline passes until graph growth plateaus."""

    def __init__(self) -> None:
        from app.infiltration.pipeline import InfiltrationPipeline
        from app.exploit.layer import ExploitLayer

        self._infiltration = InfiltrationPipeline()
        self._exploit = ExploitLayer()

    def _graph_counts(self) -> dict[str, Any]:
        from app.runtime.asset_context import get_asset_context

        ctx = get_asset_context()
        return ctx.graph_tool.stats()

    def pulse(self, *, engagement_cidr: str = "") -> dict[str, Any]:
        """One freak round: footprint → intercept → prioritize → counts."""
        before = self._graph_counts()
        footprint = self._infiltration.footprint(engagement_cidr=engagement_cidr)
        intercept = self._infiltration.intercept()
        prioritize = self._exploit.prioritize(limit=10, cidr=engagement_cidr)
        after = self._graph_counts()
        delta = {
            k: (after.get(k, 0) or 0) - (before.get(k, 0) or 0)
            for k in set(before) | set(after)
        }
        return {
            "round": 1,
            "footprint_summary": {
                "gateway": footprint.get("local_scope", {}).get("gateway"),
                "cidr": footprint.get("local_scope", {}).get("cidr"),
            },
            "events_captured": intercept.get("events_captured", 0),
            "top_targets": (prioritize.get("targets") or [])[:5],
            "graph_before": before,
            "graph_after": after,
            "graph_delta": delta,
        }

    def cycle(
        self,
        *,
        max_rounds: int = 5,
        engagement_cidr: str = "",
        stop_on_plateau: bool = True,
    ) -> dict[str, Any]:
        """Spin ``max_rounds`` pulses; stop early if host count stops growing."""
        rounds: list[dict[str, Any]] = []
        prev_hosts = -1
        plateau_at: int | None = None

        for i in range(max(1, int(max_rounds))):
            before = self._graph_counts()
            footprint = self._infiltration.footprint(engagement_cidr=engagement_cidr)
            intercept = self._infiltration.intercept()
            prioritize = self._exploit.prioritize(limit=10, cidr=engagement_cidr)
            after = self._graph_counts()
            host_count = after.get("hosts", 0) or 0
            delta = {
                k: (after.get(k, 0) or 0) - (before.get(k, 0) or 0)
                for k in set(before) | set(after)
            }
            rounds.append({
                "round": i + 1,
                "events_captured": intercept.get("events_captured", 0),
                "top_targets": (prioritize.get("targets") or [])[:5],
                "graph_delta": delta,
                "hosts_total": host_count,
            })
            if stop_on_plateau and i > 0 and host_count == prev_hosts:
                plateau_at = i + 1
                break
            prev_hosts = host_count

        return {
            "rounds_completed": len(rounds),
            "plateau_at_round": plateau_at,
            "engagement_cidr": engagement_cidr or None,
            "rounds": rounds,
            "final_counts": self._graph_counts(),
            "next": (
                "grinder.grind_subnet with METEOR_MCP_ALLOWED_CIDR if hosts still flat"
                if plateau_at
                else "exploit.chain on top prioritize target"
            ),
            "note": "Headless read loop — active scans are separate and scope-gated.",
        }

    def status(self) -> dict[str, Any]:
        counts = self._graph_counts()
        return {
            "persona": "loop_freak",
            "graph": counts,
            "default_chain": [
                "loopfreak.pulse",
                "infiltration.intercept",
                "exploit.prioritize",
                "exploit.chain",
            ],
        }
