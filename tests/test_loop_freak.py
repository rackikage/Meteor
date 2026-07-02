"""Tests for Loop Freak runner and persona."""

from __future__ import annotations

import pytest

from app.agent.loop_freak import LoopFreakConfig, build_loop_freak_prompt, continue_nudge
from app.loop_freak.runner import LoopFreakRunner
from app.mcp.policy import is_mutating, is_offensive
from app.runtime.tool_executor import ToolExecutor


class FakeGraphResult:
    def __init__(self, rows):
        self.rows = rows
        self.row_count = len(rows)


class FakeGraphTool:
    def __init__(self, stats=None):
        self._stats = stats or {"hosts": 2, "services": 5, "vulnerabilities": 1}
        self._hosts = self._stats.get("hosts", 0)

    def query(self, sql, params=None):
        return FakeGraphResult([])

    def stats(self):
        return dict(self._stats)


@pytest.fixture
def asset_ctx(monkeypatch):
    from app.mcp.context import HeadlessAssetContext
    from app.graph.event_bus import AssetEventBus

    gt = FakeGraphTool()
    ctx = HeadlessAssetContext(
        graph=None,
        event_bus=AssetEventBus(),
        noise=None,
        grinder=None,
        graph_tool=gt,
    )
    monkeypatch.setattr("app.runtime.asset_context.get_asset_context", lambda: ctx)

    def fake_footprint(**kw):
        return {"local_scope": {"gateway": "10.0.0.1", "cidr": "10.0.0.0/24"}, "next_steps": []}

    def fake_intercept():
        return {"events_captured": 0, "by_topic": {}, "highlights": [], "note": "test"}

    def fake_prioritize(**kw):
        return {"targets": [{"ip": "10.0.0.5", "priority_score": 9.0}], "hosts_ranked": 1}

    monkeypatch.setattr(
        "app.infiltration.pipeline.InfiltrationPipeline.footprint", lambda self, **kw: fake_footprint(**kw),
    )
    monkeypatch.setattr(
        "app.infiltration.pipeline.InfiltrationPipeline.intercept", lambda self: fake_intercept(),
    )
    monkeypatch.setattr(
        "app.exploit.layer.ExploitLayer.prioritize", lambda self, **kw: fake_prioritize(**kw),
    )
    return ctx


class TestLoopFreakRunner:
    def test_pulse_one_round(self, asset_ctx):
        out = LoopFreakRunner().pulse()
        assert "top_targets" in out
        assert out["graph_after"]["hosts"] == 2

    def test_cycle_stops_on_plateau(self, asset_ctx):
        out = LoopFreakRunner().cycle(max_rounds=5, stop_on_plateau=True)
        assert out["rounds_completed"] >= 1
        assert out["plateau_at_round"] == 2


class TestLoopFreakPersona:
    def test_prompt_mentions_loop(self):
        class FakeExec:
            CAPABILITIES = {"shell.run": ("run", ["command"], "run shell")}

        p = build_loop_freak_prompt(FakeExec())
        assert "Loop Freak" in p
        assert "loopfreak.cycle" in p

    def test_continue_nudge(self):
        assert "Continue" in continue_nudge(LoopFreakConfig())


class TestLoopFreakCapabilities:
    def test_registered(self):
        for op in ("pulse", "cycle", "status"):
            assert f"loopfreak.{op}" in ToolExecutor.CAPABILITIES

    def test_read_only(self):
        for op in ("pulse", "cycle", "status"):
            assert not is_offensive("loopfreak", op)
            assert not is_mutating("loopfreak", op)
