"""Tests for the GraphQueryTool — LLM-facing graph introspection interface.

Verifies: schema(), tables(), stats(), query(), safety (only SELECT allowed),
ping(), empty graph defaults.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from app.config import MeteorConfig
from app.storage.sqlite_adapter import build_sqlite_adapter
from app.graph.sqlite_graph import SQLiteAssetGraph
from app.graph.tools import GraphQueryTool, QueryResult, SCHEMA_HELP

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


@pytest.fixture
def graph_tool(tmp_path):
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    storage = build_sqlite_adapter(config.storage, tmp_path)
    graph = SQLiteAssetGraph(storage)
    return GraphQueryTool(graph)


def test_schema_returns_reference(graph_tool):
    result = graph_tool.schema()
    assert "hosts" in result
    assert "services" in result
    assert "asset_edges" in result
    assert "asset_observations" in result


def test_tables_list_all(graph_tool):
    tables = graph_tool.tables()
    assert "hosts" in tables
    assert "subnets" in tables
    assert "services" in tables
    assert "credentials" in tables
    assert "users" in tables
    assert "shares" in tables
    assert "vulnerabilities" in tables
    assert "asset_edges" in tables
    assert "asset_observations" in tables


def test_stats_counts_zero_on_empty(graph_tool):
    stats = graph_tool.stats()
    # Graph tables start empty on fresh DB
    assert stats["hosts"] == 0
    assert stats["services"] == 0
    assert stats["asset_edges"] == 0
    assert stats["asset_observations"] == 0


def test_ping_returns_ok(graph_tool):
    assert graph_tool.ping() == "ok"


def test_query_select(graph_tool):
    result = graph_tool.query("SELECT 1 AS x")
    assert result.error == ""
    assert result.row_count == 1
    assert result.rows[0]["x"] == 1
    assert result.columns == ["x"]


def test_query_with_cte(graph_tool):
    result = graph_tool.query("WITH cte AS (SELECT 2 AS n) SELECT * FROM cte")
    assert result.error == ""
    assert result.row_count == 1
    assert result.rows[0]["n"] == 2


def test_query_rejects_non_select(graph_tool):
    result = graph_tool.query("DROP TABLE hosts")
    assert result.error != ""
    assert "SELECT" in result.error
    assert result.row_count == 0


def test_query_on_invalid_sql(graph_tool):
    result = graph_tool.query("SELECT * FROM nonexistent_table")
    assert result.error != ""
    assert result.row_count == 0


def test_query_columns_match_rows(graph_tool):
    graph_tool._graph.upsert_host("10.0.0.1", hostname="test")
    result = graph_tool.query("SELECT ip, hostname FROM hosts WHERE ip = '10.0.0.1'")
    assert result.columns == ["ip", "hostname"]
    assert result.rows[0]["ip"] == "10.0.0.1"
    assert result.rows[0]["hostname"] == "test"


def test_query_empty_result(graph_tool):
    result = graph_tool.query("SELECT * FROM hosts WHERE ip = '9.9.9.9'")
    assert result.error == ""
    assert result.row_count == 0


def test_stats_reflects_inserts(graph_tool):
    graph_tool._graph.upsert_host("10.0.0.1")
    graph_tool._graph.upsert_host("10.0.0.2")
    stats = graph_tool.stats()
    assert stats["hosts"] == 2
    assert stats["services"] == 0


def test_realistic_llm_workflow(graph_tool):
    """Simulate the LLM exploring the graph after a grinder run."""
    g = graph_tool._graph

    # Setup: grinder discovered these
    g.upsert_subnet("10.0.0.0/24")
    hid = g.upsert_host("10.0.0.5", hostname="dc01", os="Windows Server 2022")
    svc = g.upsert_service(hid, 445, "smb", banner="SMB 3.1")
    g.add_edge("host", hid, "service", svc, "RUNS_SERVICE")
    g.upsert_vulnerability(svc, "CVE-2020-0796", severity="critical", exploit_available=True)

    # LLM step 1: check schema
    schema = graph_tool.schema()
    assert "vulnerabilities" in schema

    # LLM step 2: count tables
    stats = graph_tool.stats()
    assert stats["hosts"] == 1
    assert stats["services"] == 1
    assert stats["vulnerabilities"] == 1

    # LLM step 3: find critical vulns
    result = graph_tool.query(
        "SELECT h.ip, s.port, s.name, v.cve_id, v.severity "
        "FROM hosts h "
        "JOIN services s ON s.host_id = h.id "
        "JOIN vulnerabilities v ON v.service_id = s.id "
        "WHERE v.severity = 'critical'"
    )
    assert result.row_count == 1
    assert result.rows[0]["ip"] == "10.0.0.5"
    assert result.rows[0]["port"] == 445
    assert result.rows[0]["cve_id"] == "CVE-2020-0796"

    # LLM step 4: find all hosts on subnet
    result2 = graph_tool.query(
        "SELECT h.ip, h.hostname FROM hosts h WHERE h.ip LIKE '10.0.0.%'"
    )
    assert result2.row_count == 1
    assert result2.rows[0]["hostname"] == "dc01"

    # LLM step 5: find edges
    result3 = graph_tool.query(
        "SELECT source_type, source_id, target_type, target_id, edge_type FROM asset_edges"
    )
    assert result3.row_count == 1
    assert result3.rows[0]["edge_type"] == "RUNS_SERVICE"
