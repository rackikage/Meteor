"""Infiltration pipeline — compose footprint + intercept for one engagement view."""

from __future__ import annotations

from typing import Any

from app.infiltration.footprint import FootprintLayer
from app.infiltration.intercept import InterceptLayer


class InfiltrationPipeline:
    """Junior-dev-friendly facade over the two read-mostly layers."""

    def __init__(self) -> None:
        self._footprint = FootprintLayer()
        self._intercept = InterceptLayer()

    def status(self, *, engagement_cidr: str = "") -> dict[str, Any]:
        """Full pipeline snapshot: footprint + latest intercept + graph peek."""
        fp = self._footprint.collect(engagement_cidr=engagement_cidr)
        ic = self._intercept.capture()
        peek = self._intercept.peek_graph()
        return {
            "pipeline": "footprint → grinder (grinder.*) → intercept → graph",
            "authorized_scope": engagement_cidr or fp["local_scope"].get("cidr"),
            "footprint": fp,
            "intercept": ic,
            "graph_peek": peek,
        }

    def footprint(self, engagement_cidr: str = "") -> dict[str, Any]:
        return self._footprint.collect(engagement_cidr=engagement_cidr)

    def intercept(self, max_events: int = 200) -> dict[str, Any]:
        return self._intercept.capture(max_events=int(max_events))

    def peek(self, limit: int = 20) -> dict[str, Any]:
        return self._intercept.peek_graph(limit=limit)
