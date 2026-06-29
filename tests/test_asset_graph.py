"""Tests for the Asset Graph and Event Bus — infiltration grinder substrate.

Verifies: 8 node tables, polymorphic edges, observations, event bus pub/sub,
graph → event bus roundtrip, recursive path-finding CTE, subscriber wiring.
"""

from __future__ import annotations

import asyncio
import pytest
from pathlib import Path

from app.config import MeteorConfig
from app.storage.sqlite_adapter import SQLiteAdapter, build_sqlite_adapter
from app.graph.contract import AssetGraphContract
from app.graph.sqlite_graph import SQLiteAssetGraph
from app.graph.event_bus import AssetEventBus, Event

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


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


# ── Contract enforcement ────────────────────────────────────────────────

def test_contract_is_abstract():
    with pytest.raises(TypeError):
        AssetGraphContract()


def test_graph_implements_contract(graph):
    assert isinstance(graph, AssetGraphContract)


# ── Host CRUD ───────────────────────────────────────────────────────────

def test_upsert_host_creates_and_returns_id(graph):
    hid = graph.upsert_host("10.0.0.5")
    assert hid > 0

    rows = graph.query("SELECT * FROM hosts WHERE ip = ?", ("10.0.0.5",))
    assert len(rows) == 1
    assert rows[0]["ip"] == "10.0.0.5"
    assert rows[0]["state"] == "up"


def test_upsert_host_is_idempotent(graph):
    hid1 = graph.upsert_host("10.0.0.5", hostname="web-01")
    hid2 = graph.upsert_host("10.0.0.5", hostname="web-01-updated")
    assert hid1 == hid2

    rows = graph.query("SELECT * FROM hosts WHERE ip = ?", ("10.0.0.5",))
    assert len(rows) == 1


def test_upsert_host_with_all_fields(graph):
    hid = graph.upsert_host(
        ip="192.168.1.1", hostname="dc01", os="Windows Server 2022",
        subnet_id=1, source="nmap",
    )
    rows = graph.query("SELECT * FROM hosts WHERE ip = ?", ("192.168.1.1",))
    assert rows[0]["hostname"] == "dc01"
    assert rows[0]["os"] == "Windows Server 2022"
    assert rows[0]["source"] == "nmap"


# ── Subnet CRUD ─────────────────────────────────────────────────────────

def test_upsert_subnet(graph):
    sid = graph.upsert_subnet("10.0.0.0/24")
    assert sid > 0

    rows = graph.query("SELECT * FROM subnets WHERE cidr = ?", ("10.0.0.0/24",))
    assert len(rows) == 1


def test_upsert_subnet_with_parent(graph):
    parent_id = graph.upsert_subnet("10.0.0.0/16")
    child_id = graph.upsert_subnet("10.0.1.0/24", parent_id=parent_id)
    rows = graph.query("SELECT * FROM subnets WHERE id = ?", (child_id,))
    assert rows[0]["parent_id"] == parent_id


# ── Service CRUD ────────────────────────────────────────────────────────

def test_upsert_service(graph):
    hid = graph.upsert_host("10.0.0.5")
    sid = graph.upsert_service(hid, 443, "https", banner="nginx/1.24")
    assert sid > 0

    rows = graph.query("SELECT * FROM services WHERE host_id = ?", (hid,))
    assert len(rows) == 1
    assert rows[0]["name"] == "https"
    assert rows[0]["banner"] == "nginx/1.24"


def test_service_unique_per_host_port_proto(graph):
    hid = graph.upsert_host("10.0.0.5")
    graph.upsert_service(hid, 80, "http", proto="tcp")
    graph.upsert_service(hid, 80, "http-alt", proto="tcp")

    rows = graph.query("SELECT * FROM services WHERE host_id = ? AND port = 80", (hid,))
    assert len(rows) == 1  # upsert, not insert


def test_upsert_service_multiple_hosts(graph):
    a = graph.upsert_host("10.0.0.1")
    b = graph.upsert_host("10.0.0.2")
    graph.upsert_service(a, 22, "ssh")
    graph.upsert_service(b, 22, "ssh")

    rows = graph.query("SELECT * FROM services WHERE port = 22")
    assert len(rows) == 2


# ── Credential CRUD ─────────────────────────────────────────────────────

def test_upsert_credential(graph):
    hid = graph.upsert_host("10.0.0.5")
    cid = graph.upsert_credential(hid, "admin", "password", "secret123",
                                  source="lsass_dump")
    assert cid > 0

    rows = graph.query("SELECT * FROM credentials WHERE host_id = ?", (hid,))
    assert len(rows) == 1
    assert rows[0]["username"] == "admin"


# ── User CRUD ───────────────────────────────────────────────────────────

def test_upsert_user(graph):
    uid = graph.upsert_user("Administrator", domain="CORP.local")
    rows = graph.query("SELECT * FROM users WHERE name = ?", ("Administrator",))
    assert len(rows) == 1
    assert rows[0]["domain"] == "CORP.local"


# ── Share CRUD ──────────────────────────────────────────────────────────

def test_upsert_share(graph):
    hid = graph.upsert_host("10.0.0.5")
    sid = graph.upsert_share(hid, "C$", share_type="smb",
                             permissions="rw")
    rows = graph.query("SELECT * FROM shares WHERE host_id = ?", (hid,))
    assert len(rows) == 1
    assert rows[0]["name"] == "C$"


# ── Vulnerability CRUD ──────────────────────────────────────────────────

def test_upsert_vulnerability(graph):
    hid = graph.upsert_host("10.0.0.5")
    svc_id = graph.upsert_service(hid, 445, "smb")
    vid = graph.upsert_vulnerability(svc_id, "CVE-2020-0796",
                                     severity="critical",
                                     exploit_available=True)
    rows = graph.query("SELECT * FROM vulnerabilities WHERE cve_id = ?",
                       ("CVE-2020-0796",))
    assert len(rows) == 1
    assert rows[0]["severity"] == "critical"
    assert rows[0]["exploit_available"] == 1


# ── Edges ───────────────────────────────────────────────────────────────

def test_add_edge_and_query(graph):
    hid = graph.upsert_host("10.0.0.5")
    svc_id = graph.upsert_service(hid, 22, "ssh")
    graph.add_edge("host", hid, "service", svc_id, "RUNS_SERVICE", weight=0.8)

    edges = graph.query("SELECT * FROM asset_edges")
    assert len(edges) == 1
    assert edges[0]["edge_type"] == "RUNS_SERVICE"
    assert edges[0]["source_type"] == "host"
    assert edges[0]["target_type"] == "service"


def test_add_edge_idempotent(graph):
    hid = graph.upsert_host("10.0.0.5")
    svc_id = graph.upsert_service(hid, 22, "ssh")
    graph.add_edge("host", hid, "service", svc_id, "RUNS_SERVICE")
    graph.add_edge("host", hid, "service", svc_id, "RUNS_SERVICE")

    edges = graph.query("SELECT * FROM asset_edges")
    assert len(edges) == 1  # deduped by UNIQUE constraint


def test_open_edge_types(graph):
    hid = graph.upsert_host("10.0.0.1")
    hid2 = graph.upsert_host("10.0.0.2")
    graph.add_edge("host", hid, "host", hid2, "ROUTES_THROUGH")
    graph.add_edge("host", hid, "host", hid2, "AUTHENTICATES_TO")
    graph.add_edge("host", hid, "host", hid2, "TRUSTS_CHILD_DOMAIN")

    edges = graph.query("SELECT edge_type FROM asset_edges")
    types = {e["edge_type"] for e in edges}
    assert "ROUTES_THROUGH" in types
    assert "AUTHENTICATES_TO" in types
    assert "TRUSTS_CHILD_DOMAIN" in types  # open TEXT — no enum constraint


# ── Observations ────────────────────────────────────────────────────────

def test_add_observation(graph):
    hid = graph.upsert_host("10.0.0.5")
    graph.add_observation("host", hid, "nmap_syn_scan",
                          {"latency_ms": 2.3, "ttl": 64})

    rows = graph.query(
        "SELECT * FROM asset_observations WHERE asset_type = 'host' AND asset_id = ?",
        (hid,),
    )
    assert len(rows) == 1


# ── Query safety ────────────────────────────────────────────────────────

def test_query_rejects_non_select(graph):
    with pytest.raises(ValueError, match="Only read queries"):
        graph.query("DROP TABLE hosts")


def test_query_allows_with_cte(graph):
    graph.upsert_host("10.0.0.1")
    graph.upsert_host("10.0.0.2")
    rows = graph.query("WITH cte AS (SELECT ip FROM hosts) SELECT * FROM cte")
    assert len(rows) == 2


# ── Neighbors / path-finding ────────────────────────────────────────────

def test_find_neighbors_all(graph):
    hid = graph.upsert_host("10.0.0.5")
    svc_id = graph.upsert_service(hid, 22, "ssh")
    graph.add_edge("host", hid, "service", svc_id, "RUNS_SERVICE")
    graph.add_edge("host", hid, "service", svc_id, "EXPOSES_PORT")

    neighbors = graph.find_neighbors("host", hid)
    assert len(neighbors) >= 1


def test_find_neighbors_filtered(graph):
    hid = graph.upsert_host("10.0.0.5")
    svc_id = graph.upsert_service(hid, 22, "ssh")
    graph.add_edge("host", hid, "service", svc_id, "RUNS_SERVICE")
    graph.add_edge("host", hid, "service", svc_id, "EXPOSES_PORT")

    neighbors = graph.find_neighbors("host", hid, edge_type="RUNS_SERVICE")
    for n in neighbors:
        assert n["edge_type"] == "RUNS_SERVICE"


def test_find_paths_single_hop(graph):
    a = graph.upsert_host("10.0.0.1")
    b = graph.upsert_host("10.0.0.2")
    graph.add_edge("host", a, "host", b, "AUTHENTICATES_TO")

    paths = graph.find_paths("host", a, "host", b, max_hops=1)
    assert len(paths) >= 1


def test_find_paths_no_path(graph):
    a = graph.upsert_host("10.0.0.1")
    b = graph.upsert_host("10.0.0.99")
    paths = graph.find_paths("host", a, "host", b)
    assert len(paths) == 0


def test_find_paths_multi_hop(graph):
    a = graph.upsert_host("10.0.0.1")
    b = graph.upsert_host("10.0.0.2")
    c = graph.upsert_host("10.0.0.3")
    graph.add_edge("host", a, "host", b, "AUTHENTICATES_TO")
    graph.add_edge("host", b, "host", c, "ROUTES_THROUGH")

    paths = graph.find_paths("host", a, "host", c, max_hops=3)
    assert len(paths) >= 1


# ── EventBus ────────────────────────────────────────────────────────────

def test_event_bus_publish_drain(event_bus):
    async def _run():
        await event_bus.publish("host.discovered", {"ip": "10.0.0.1"})
        await event_bus.publish("service.discovered", {"port": 443})
        return await event_bus.drain()

    events = asyncio.run(_run())
    assert len(events) == 2
    topics = {t for t, _ in events}
    assert "host.discovered" in topics
    assert "service.discovered" in topics


def test_event_bus_subscribe(event_bus):
    captured = []

    def handler(payload):
        captured.append(payload)

    async def _run():
        event_bus.subscribe("host.discovered", handler)
        await event_bus.publish("host.discovered", {"ip": "10.0.0.5"})

    asyncio.run(_run())
    assert len(captured) == 1
    assert captured[0]["ip"] == "10.0.0.5"


def test_event_bus_wildcard_subscribe(event_bus):
    captured = []

    def handler(payload):
        captured.append(payload)

    async def _run():
        event_bus.subscribe("*", handler)
        await event_bus.publish("host.discovered", {"ip": "10.0.0.1"})
        await event_bus.publish("service.discovered", {"port": 80})

    asyncio.run(_run())
    assert len(captured) == 2


def test_event_bus_unsubscribe(event_bus):
    captured = []

    def handler(payload):
        captured.append(payload)

    async def _run():
        token = event_bus.subscribe("host.discovered", handler)
        await event_bus.publish("host.discovered", {"ip": "1"})
        event_bus.unsubscribe(token)
        await event_bus.publish("host.discovered", {"ip": "2"})

    asyncio.run(_run())
    assert len(captured) == 1  # still 1, unsubscribed


def test_event_bus_async_subscriber(event_bus):
    captured = []

    async def async_handler(payload):
        await asyncio.sleep(0)
        captured.append(payload)

    async def _run():
        event_bus.subscribe("service.discovered", async_handler)
        await event_bus.publish("service.discovered", {"port": 22})

    asyncio.run(_run())
    assert len(captured) == 1


def test_event_bus_stats(event_bus):
    async def _run():
        await event_bus.publish("host.discovered", {"ip": "1"})
        await event_bus.publish("host.discovered", {"ip": "2"})

    asyncio.run(_run())
    stats = event_bus.stats()
    assert stats["events_published"] == 2
    assert stats["events_dropped"] == 0


def test_event_bus_drain_clears_queue(event_bus):
    async def _run():
        await event_bus.publish("host.discovered", {"ip": "1"})
        await event_bus.publish("host.discovered", {"ip": "2"})
        events = await event_bus.drain()
        assert len(events) == 2
        events = await event_bus.drain()
        assert len(events) == 0  # queue is now empty

    asyncio.run(_run())


def test_scanner_publishes_to_graph(graph, event_bus):
    def _on_discover(payload):
        hid = graph.upsert_host(ip=payload["ip"], source="scanner_e2e_test")
        svc_id = graph.upsert_service(
            host_id=hid, port=payload["port"],
            name=payload.get("name", "unknown"),
            banner=payload.get("banner", ""),
        )
        graph.add_edge("host", hid, "service", svc_id, "RUNS_SERVICE")

    async def _run():
        event_bus.subscribe("service.discovered", _on_discover)
        await event_bus.publish("service.discovered", {
            "ip": "10.0.0.99", "port": 443, "name": "https", "banner": "Apache/2.4"
        })

    asyncio.run(_run())

    hosts = graph.query("SELECT * FROM hosts WHERE ip = '10.0.0.99'")
    assert len(hosts) == 1
    assert hosts[0]["source"] == "scanner_e2e_test"

    services = graph.query(
        "SELECT * FROM services WHERE host_id = ?", (hosts[0]["id"],))
    assert len(services) == 1
    assert services[0]["name"] == "https"
    assert services[0]["banner"] == "Apache/2.4"

    edges = graph.query(
        "SELECT * FROM asset_edges WHERE source_type = 'host' AND source_id = ?",
        (hosts[0]["id"],),
    )
    assert len(edges) == 1
    assert edges[0]["edge_type"] == "RUNS_SERVICE"
