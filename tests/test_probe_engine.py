"""Tests for async probe engine and network probe toolkit."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.tools.pentest.probe_engine import (
    AsyncProbeEngine,
    PortState,
    ProbeEngineConfig,
    ProbeResult,
    ReachabilityChecker,
    WorkerPoolManager,
    WorkerPoolStats,
    format_probe_batch_markdown,
    parse_probe_state,
    probe_to_scan_result,
)
from app.tools.pentest.probe_toolkit import NetworkProbeToolkit
from app.tools.pentest.tool_executor import get_pentest_executor


class TestAsyncProbeEngine:

    def test_closed_port_localhost(self):
        engine = AsyncProbeEngine(ProbeEngineConfig(timeout=0.5, concurrency_limit=5))

        async def _run():
            return await engine.probe_socket_state("127.0.0.1", 59999)

        result = asyncio.run(_run())
        assert result.state in (PortState.CLOSED, PortState.FILTERED_OR_TIMEOUT)
        assert result.ip == "127.0.0.1"
        assert result.port == 59999

    def test_execute_batch(self):
        engine = AsyncProbeEngine(ProbeEngineConfig(timeout=0.5, concurrency_limit=10))

        async def _run():
            return await engine.execute_batch([("127.0.0.1", 59998), ("127.0.0.1", 59997)])

        results = asyncio.run(_run())
        assert len(results) == 2

    def test_parse_probe_state_open(self):
        r = ProbeResult(ip="1.1.1.1", port=80, state=PortState.OPEN)
        assert parse_probe_state(r) == "OPEN"

    def test_probe_to_scan_result(self):
        from app.tools.pentest.scanner import ScanResult

        pr = ProbeResult(ip="10.0.0.1", port=22, state=PortState.OPEN, banner="SSH-2.0")
        sr = probe_to_scan_result(pr)
        assert isinstance(sr, ScanResult)
        assert sr.open is True
        assert sr.service == "ssh"

    def test_format_markdown_includes_stats(self):
        results = [
            ProbeResult(ip="10.0.0.1", port=22, state=PortState.OPEN, latency_ms=12.0),
        ]
        stats = WorkerPoolStats(targets_queued=1, targets_probed=1, open_ports=1)
        md = format_probe_batch_markdown(results, stats)
        assert "Open ports" in md
        assert "10.0.0.1:22" in md


class TestReachabilityChecker:

    def test_filter_reachable(self):
        checker = ReachabilityChecker()

        async def _mock_ping(_ip: str) -> bool:
            return True

        with patch.object(ReachabilityChecker, "_icmp_ping", side_effect=_mock_ping):
            out = asyncio.run(checker.filter_reachable(["192.168.1.1", "192.168.1.2"]))
        assert out == ["192.168.1.1", "192.168.1.2"]


class TestWorkerPoolManager:

    def test_run_matrix(self):
        async def _run():
            mock_filter = AsyncMock(return_value=["10.0.0.1"])
            mock_batch = AsyncMock(
                return_value=[ProbeResult(ip="10.0.0.1", port=80, state=PortState.CLOSED)]
            )
            with patch.object(ReachabilityChecker, "filter_reachable", mock_filter):
                with patch.object(AsyncProbeEngine, "execute_batch", mock_batch):
                    pool = WorkerPoolManager(require_reachable=True)
                    return await pool.run_matrix(["10.0.0.1", "10.0.0.2"], [80])

        results, stats = asyncio.run(_run())
        assert len(results) == 1
        assert stats.targets_queued == 1


class TestNetworkProbeToolkit:

    def test_capabilities_structure(self):
        toolkit = NetworkProbeToolkit()
        caps = toolkit.capabilities
        assert "async_connect" in caps
        assert "raw_syn" in caps
        assert caps["async_connect"]["available"] is True

    def test_probe_host_localhost(self):
        toolkit = NetworkProbeToolkit()

        async def _run():
            return await toolkit.probe_host("127.0.0.1", [59996])

        report = asyncio.run(_run())
        assert report.technique in ("async_connect", "raw_syn")
        assert len(report.results) == 1


class TestProbeToolExecutor:

    def test_probe_capabilities_op(self):
        result = get_pentest_executor().execute("probe_capabilities")
        assert result.status == "ok"
        assert "async_connect" in result.markdown

    def test_intent_probe_route(self):
        from app.gui.intent_router import route_intent

        intent = route_intent("run async probe engine on gateway")
        assert intent is not None
        assert intent.command == "probe"
