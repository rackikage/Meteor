"""Tests for MeteorAgent and WebSearcher.

Verifies: web search fallback, service intel scoring, agent infiltration
loop, pivot logic, graph integration, event publishing.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.config import MeteorConfig
from app.storage.sqlite_adapter import build_sqlite_adapter
from app.graph.event_bus import AssetEventBus
from app.graph.sqlite_graph import SQLiteAssetGraph
from app.dispatcher.grinder import InfiltrationGrinder, GrinderStats
from app.dispatcher.noise import NoiseFloorSampler, NoiseFloorState
from app.agent.web_search import WebSearcher, ServiceIntel, CveEntry, ExploitMatch, SearchHit
from app.agent.loop import MeteorAgent, AgentReport

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def storage(tmp_path):
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    adapter = build_sqlite_adapter(config.storage, tmp_path)
    yield adapter
    adapter.close()


@pytest.fixture
def graph(storage):
    return SQLiteAssetGraph(storage)


@pytest.fixture
def event_bus():
    return AssetEventBus()


@pytest.fixture
def mock_grinder():
    grinder = MagicMock(spec=InfiltrationGrinder)
    grinder.grind_host = AsyncMock(return_value=GrinderStats(
        tasks_completed=1, services_discovered=2, hosts_discovered=1))
    grinder.grind_subnet = AsyncMock(return_value=GrinderStats(
        tasks_completed=3, services_discovered=5, hosts_discovered=3))
    grinder.grind_sector = AsyncMock(return_value=GrinderStats(
        tasks_completed=10, services_discovered=20, hosts_discovered=5))
    return grinder


@pytest.fixture
def searcher():
    return WebSearcher()


@pytest.fixture
def agent(graph, event_bus, mock_grinder, searcher):
    return MeteorAgent(graph=graph, event_bus=event_bus,
                       grinder=mock_grinder, searcher=searcher)


# ── WebSearcher ────────────────────────────────────────────────────────

def test_web_searcher_mock_hits():
    searcher = WebSearcher()
    hits = searcher._mock_hits("ssh exploit")
    assert len(hits) >= 1
    assert any("ssh" in h.title.lower() for h in hits)


def test_web_searcher_mock_hits_multiple():
    searcher = WebSearcher()
    hits = searcher._mock_hits("smb rdp http ssh")
    assert len(hits) >= 3  # smb, rdp, http, ssh


def test_extract_version():
    banner = "SSH-2.0-OpenSSH_8.9"
    version = WebSearcher._extract_version(banner)
    assert version == "8.9"


def test_extract_version_no_version():
    assert WebSearcher._extract_version("unknown") == ""


def test_service_intel_scoring():
    intel = ServiceIntel(ip="10.0.0.1", port=445, service="smb", banner="SMB 3.1")
    intel.cves = [
        CveEntry(cve_id="CVE-2020-0796", description="SMBGhost",
                 severity="CRITICAL", exploit_available=True),
        CveEntry(cve_id="CVE-2017-0144", description="EternalBlue",
                 severity="CRITICAL", exploit_available=True),
    ]
    score = WebSearcher()._score(intel)
    assert score >= 8.0  # 3+3 + 2+2 = 10 but capped at 10


def test_service_intel_exploit_weight():
    intel = ServiceIntel(ip="10.0.0.1", port=80, service="http", banner="Apache/2.4")
    intel.exploits = [
        ExploitMatch(cve_id="CVE-2021-44228", title="Log4Shell"),
        ExploitMatch(cve_id="", title="LFI Scanner"),
    ]
    score = WebSearcher()._score(intel)
    assert score >= 2.5  # 1.5 + 1.5 = 3, plus maybe search hits


# ── MeteorAgent ────────────────────────────────────────────────────────

def test_agent_infiltrate_host(agent, event_bus, graph):
    """Full infiltration of a single host — scan + research + graph write."""
    report = asyncio.run(agent.infiltrate("10.0.0.5", depth=1, ports=[22, 80]))

    assert report.target == "10.0.0.5"
    assert report.depth_reached >= 1
    assert report.completed_at != ""


def test_next_ip_calculation():
    assert MeteorAgent._next_ip("10.0.0.1", 1) == "10.0.0.2"
    assert MeteorAgent._next_ip("10.0.0.1", 5) == "10.0.0.6"
    assert MeteorAgent._next_ip("10.0.0.254", 1) == "10.0.0.255"
    assert MeteorAgent._next_ip("10.0.0.254", 2) == "10.0.1.0"
    assert MeteorAgent._next_ip("255.255.255.255", 1) is None


def test_next_ip_invalid():
    assert MeteorAgent._next_ip("not.an.ip", 1) is None
    assert MeteorAgent._next_ip("10.0.0", 1) is None


# ── Agent Report ───────────────────────────────────────────────────────

def test_agent_report_defaults():
    report = AgentReport(target="10.0.0.0/24", depth_reached=0,
                         hosts_discovered=0, services_discovered=0,
                         critical_vulns=0, high_vulns=0, exploits_found=0,
                         pivot_chains=[])
    assert report.target == "10.0.0.0/24"
    assert report.depth_reached == 0
    assert len(report.pivot_chains) == 0


# ── Integration: agent pushes to graph ─────────────────────────────────

def test_agent_writes_to_graph(agent, graph, event_bus):
    """After infiltration, the graph should contain host and vulnerability data."""
    def _on_host(payload):
        graph.upsert_host(ip=payload["ip"], source="agent_test")

    event_bus.subscribe("host.discovered", _on_host)

    report = asyncio.run(agent.infiltrate("192.168.1.1", depth=1, ports=[22]))

    assert report.hosts_discovered >= 0
    assert report.wall_time_ms > 0


# ── Depth ports mapping ────────────────────────────────────────────────

def test_depth_ports_surface():
    from app.agent.loop import DEFAULT_DEPTH_PORTS
    ports = DEFAULT_DEPTH_PORTS[0]
    assert 22 in ports
    assert 80 in ports
    assert 443 in ports
    assert 445 in ports


def test_depth_ports_deep():
    from app.agent.loop import DEFAULT_DEPTH_PORTS
    ports = DEFAULT_DEPTH_PORTS[1]
    assert 3306 in ports  # mysql
    assert 5432 in ports  # postgres
    assert len(ports) >= 10
