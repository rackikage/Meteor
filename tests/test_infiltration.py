"""Tests for the authorized infiltration pipeline (footprint + intercept layers)."""

from __future__ import annotations

import pytest

from app.infiltration.footprint import FootprintLayer
from app.infiltration.intercept import InterceptLayer
from app.infiltration.pipeline import InfiltrationPipeline
from app.mcp.policy import McpPolicy, is_mutating, is_offensive
from app.runtime.asset_context import get_asset_context, set_asset_context
from app.runtime.tool_executor import ToolExecutor


@pytest.fixture(autouse=True)
def _headless_asset_context():
    """Ensure a graph + event bus exist for pipeline tests."""
    from app.mcp.context import build_headless_context

    ctx = build_headless_context()
    set_asset_context(ctx)
    yield ctx
    set_asset_context(None)


class TestFootprintLayer:
    def test_collect_shape(self):
        fp = FootprintLayer().collect(engagement_cidr="10.0.0.0/24")
        assert fp["engagement_cidr"] == "10.0.0.0/24"
        assert "local_scope" in fp
        assert "gateway" in fp["local_scope"]
        assert "next_steps" in fp
        assert isinstance(fp["next_steps"], list)

    def test_next_steps_suggest_grinder_when_cidr_set(self):
        fp = FootprintLayer().collect(engagement_cidr="192.168.1.0/24")
        assert any("grinder.grind_subnet" in s for s in fp["next_steps"])


class TestInterceptLayer:
    def test_capture_empty_bus(self):
        ctx = get_asset_context()
        result = InterceptLayer().capture()
        assert result["events_captured"] >= 0
        assert "by_topic" in result
        assert "pipeline events only" in result["note"].lower()
        assert result["bus_stats"] == ctx.event_bus.stats()

    def test_peek_graph_returns_lists(self):
        peek = InterceptLayer().peek_graph(limit=5)
        assert "hosts" in peek
        assert "services" in peek
        assert "counts" in peek


class TestInfiltrationPipeline:
    def test_status_composes_layers(self):
        snap = InfiltrationPipeline().status(engagement_cidr="10.0.0.0/8")
        assert snap["authorized_scope"] == "10.0.0.0/8"
        assert "footprint" in snap
        assert "intercept" in snap
        assert "graph_peek" in snap


class TestInfiltrationCapabilities:
    def test_registered_in_executor(self):
        caps = ToolExecutor.CAPABILITIES
        for op in ("footprint", "intercept", "peek", "status"):
            assert f"infiltration.{op}" in caps

    def test_not_offensive_or_mutating(self):
        for op in ("footprint", "intercept", "peek", "status"):
            assert not is_offensive("infiltration", op)
            assert not is_mutating("infiltration", op)

    def test_allowed_under_read_only_mcp(self):
        pol = McpPolicy.from_env(env={"METEOR_MCP_READ_ONLY": "1"})
        for op in ("footprint", "intercept", "peek", "status"):
            assert pol.is_visible("infiltration", op)
            assert pol.gate("infiltration", op, {}) is None
