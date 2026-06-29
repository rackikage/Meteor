"""Tests for NoiseFloorSampler and InfiltrationGrinder.

Verifies: noise sampler with/without psutil, grinder fan-out pipeline,
graph → dispatcher → event bus → graph roundtrip, scan.completed events,
LotL concurrency bounds.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.config import MeteorConfig
from app.dispatcher.noise import NoiseFloorSampler, NoiseFloorState
from app.dispatcher.grinder import InfiltrationGrinder, GrinderStats, _resolve_ports
from app.graph.event_bus import AssetEventBus
from app.graph.sqlite_graph import SQLiteAssetGraph
from app.storage.sqlite_adapter import build_sqlite_adapter

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
def mock_noise():
    """Noise sampler locked at 1.0x (neutral)."""
    sampler = MagicMock(spec=NoiseFloorSampler)
    sampler.get_state.return_value = NoiseFloorState(camouflage_multiplier=1.0)
    sampler.get_multiplier.return_value = 1.0
    sampler.worker_count.return_value = 5
    sampler._task = True
    sampler.start = AsyncMock()
    sampler.stop = AsyncMock()
    return sampler


def _build_grinder(graph, event_bus, mock_noise, min_w=3, max_w=10):
    """Build a grinder with a mock scanner that returns fake open ports."""
    @dataclass
    class FakeResult:
        ip: str
        port: int
        open: bool = True
        service: str = "http"
        banner: str = ""

    scanner = MagicMock()

    async def _fake_scan(ip, ports):
        results = [FakeResult(ip=ip, port=p) for p in ports[:3]]
        for r in results:
            await event_bus.publish("service.discovered", {
                "ip": r.ip, "port": r.port,
                "name": r.service, "banner": r.banner,
            })
        return results

    scanner.scan_host = _fake_scan
    scanner._grinder_bus = event_bus

    # Wire event bus → graph auto-persist
    def _on_host(payload):
        graph.upsert_host(ip=payload["ip"], source="grinder")

    def _on_service(payload):
        hid = graph.upsert_host(ip=payload["ip"])
        graph.upsert_service(host_id=hid, port=payload["port"],
                             name=payload.get("name", "unknown"))

    event_bus.subscribe("host.discovered", _on_host)
    event_bus.subscribe("service.discovered", _on_service)

    return InfiltrationGrinder(
        graph=graph, event_bus=event_bus,
        scanner=scanner, noise=mock_noise,
        min_workers=min_w, max_workers=max_w,
    )


# ── NoiseFloorSampler ──────────────────────────────────────────────────

def test_noise_sampler_defaults():
    sampler = NoiseFloorSampler()
    state = sampler.get_state()
    assert state.camouflage_multiplier == 1.0
    assert state.is_host_idle is True


def test_noise_sampler_worker_count_clamps():
    sampler = NoiseFloorSampler()
    sampler._state = NoiseFloorState(camouflage_multiplier=5.0)
    assert sampler.worker_count(base_min=3, base_max=500) == 500

    sampler._state = NoiseFloorState(camouflage_multiplier=0.5)
    assert sampler.worker_count(base_min=3, base_max=500) == 3

    sampler._state = NoiseFloorState(camouflage_multiplier=3.0)
    w = sampler.worker_count(base_min=3, base_max=100)
    assert 3 < w < 100


def test_noise_sampler_worker_count_formula():
    sampler = NoiseFloorSampler()
    sampler._state = NoiseFloorState(camouflage_multiplier=1.0)
    w = sampler.worker_count(base_min=3, base_max=500)
    assert 50 <= w <= 65


# ── Grind host ─────────────────────────────────────────────────────────

def test_grind_host_dispatches(graph, event_bus, mock_noise):
    grinder = _build_grinder(graph, event_bus, mock_noise)
    stats = asyncio.run(grinder.grind_host("10.0.0.1", ports=[80, 443, 8080]))

    assert stats.tasks_completed == 1
    assert stats.services_discovered == 3
    assert stats.errors == 0
    assert stats.wall_time_ms > 0

    hosts = graph.query("SELECT * FROM hosts WHERE ip = '10.0.0.1'")
    assert len(hosts) == 1

    services = graph.query("SELECT * FROM services WHERE host_id = ?", (hosts[0]["id"],))
    assert len(services) == 3


def test_grind_host_emits_scan_completed(graph, event_bus, mock_noise):
    captured = []

    def _capture(payload):
        captured.append(payload)

    event_bus.subscribe("scan.completed", _capture)
    grinder = _build_grinder(graph, event_bus, mock_noise)
    asyncio.run(grinder.grind_host("10.0.0.1", ports=[80]))

    completed = [e for e in captured if "services_discovered" in e]
    assert len(completed) >= 1


# ── Grind subnet ───────────────────────────────────────────────────────

def test_grind_subnet_fans_out(graph, event_bus, mock_noise):
    grinder = _build_grinder(graph, event_bus, mock_noise)
    stats = asyncio.run(grinder.grind_subnet("10.0.0.0/30", ports=[80], scan="sweep"))

    assert stats.tasks_completed == 2
    assert stats.services_discovered >= 1
    assert stats.wall_time_ms > 0


def test_grind_subnet_queues_correct_count(graph, event_bus, mock_noise):
    grinder = _build_grinder(graph, event_bus, mock_noise)
    stats = asyncio.run(grinder.grind_subnet("10.0.0.0/30", ports=[22]))
    assert stats.tasks_queued == 2


# ── Grind sector ───────────────────────────────────────────────────────

def test_grind_sector_reads_from_graph(graph, event_bus, mock_noise):
    graph.upsert_subnet("10.0.0.0/30", scope_session="test-session")

    def _on_service(payload):
        hid = graph.upsert_host(ip=payload["ip"], source="grinder")
        graph.upsert_service(host_id=hid, port=payload["port"],
                             name=payload.get("name", "unknown"))

    event_bus.subscribe("service.discovered", _on_service)

    grinder = _build_grinder(graph, event_bus, mock_noise)
    stats = asyncio.run(grinder.grind_sector(cidr="10.0.0.0/30"))

    assert stats.tasks_completed >= 2
    hosts = graph.query("SELECT * FROM hosts WHERE source = 'grinder'")
    assert len(hosts) >= 2


def test_grind_sector_no_targets(graph, event_bus, mock_noise):
    grinder = _build_grinder(graph, event_bus, mock_noise)
    stats = asyncio.run(grinder.grind_sector())
    assert stats.tasks_queued == 0


# ── GrinderStats ───────────────────────────────────────────────────────

def test_grinder_stats_defaults():
    stats = GrinderStats()
    assert stats.tasks_queued == 0
    assert stats.services_discovered == 0


# ── LotL concurrency bounds ────────────────────────────────────────────

def test_grinder_respects_worker_count(graph, event_bus, mock_noise):
    mock_noise.worker_count.return_value = 2
    grinder = _build_grinder(graph, event_bus, mock_noise)
    stats = asyncio.run(grinder.grind_subnet("10.0.0.0/30", ports=[80, 443]))
    assert stats.tasks_completed == 2


# ── Port resolution ────────────────────────────────────────────────────

def test_port_scan_modes():
    assert len(_resolve_ports("common")) == 24
    assert len(_resolve_ports("subset")) == 6
    assert len(_resolve_ports("sweep")) == 4
    assert _resolve_ports("unknown") == [22, 80, 443, 445]


# ── CIDR expansion ─────────────────────────────────────────────────────

def test_expand_cidr():
    ips = InfiltrationGrinder._expand_cidr("10.0.0.0/30")
    assert len(ips) == 2
    assert "10.0.0.1" in ips
    assert "10.0.0.2" in ips

    ips24 = InfiltrationGrinder._expand_cidr("192.168.1.0/24")
    assert len(ips24) == 254
