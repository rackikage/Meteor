"""GraphQueryTool — LLM-facing interface to the asset graph.

Exposes schema introspection, row counts, and raw SQL SELECT queries
against the infiltration grinder's asset graph. The LLM discovers the
network topology by writing its own SQL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.graph.sqlite_graph import SQLiteAssetGraph

logger = logging.getLogger(__name__)

SCHEMA_HELP = """Tables available:
  hosts        — (id, ip, hostname, os, subnet_id, state, source, first_seen, last_seen, confidence, attrs_json)
  subnets      — (id, cidr, parent_id, scope_session, first_seen, last_seen, attrs_json)
  services     — (id, host_id, port, proto, name, banner, state, first_seen, last_seen, attrs_json)
  credentials  — (id, host_id, username, secret_type, secret_value, source, verified, discovered_at, last_used, attrs_json)
  users        — (id, name, domain, source, first_seen, last_seen, attrs_json)
  shares       — (id, host_id, name, share_type, permissions, first_seen, last_seen)
  vulnerabilities — (id, service_id, cve_id, severity, description, exploit_available, discovered_at, attrs_json)
  asset_edges  — (id, source_type, source_id, target_type, target_id, edge_type, weight, confidence, first_seen, last_seen, attrs_json)
  asset_observations — (id, asset_type, asset_id, source, observed_at, attrs_json)

Join pattern: hosts.id = services.host_id, services.id = vulnerabilities.service_id
Edge pattern: asset_edges connects any source_type:source_id to target_type:target_id
"""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    error: str = ""


class GraphQueryTool:
    """LLM-callable tool for graph introspection and SQL queries.

    Called by the orchestrator tool loop when the model emits:
        {tool: "graph", operation: "query", arguments: {sql: "SELECT ..."}}
    """

    def __init__(self, graph: SQLiteAssetGraph) -> None:
        self._graph = graph

    def schema(self) -> str:
        """Return the full schema reference for the LLM."""
        return SCHEMA_HELP

    def tables(self) -> list[str]:
        """Return list of table names in the graph."""
        rows = self._graph.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_migrations' ORDER BY name"
        )
        return [r["name"] for r in rows]

    def stats(self) -> dict[str, int]:
        """Return row counts for every table in the graph."""
        counts: dict[str, int] = {}
        for table in self.tables():
            rows = self._graph.query(f"SELECT COUNT(*) as cnt FROM \"{table}\"")
            counts[table] = rows[0]["cnt"] if rows else 0
        return counts

    def query(self, sql: str) -> QueryResult:
        """Execute a SELECT/WITH query against the graph."""
        if not sql.strip().upper().startswith(("SELECT", "WITH", "EXPLAIN", "PRAGMA")):
            return QueryResult(columns=[], rows=[], row_count=0,
                               error="Only SELECT/WITH queries are allowed")

        try:
            rows = self._graph.query(sql)

            columns: list[str] = []
            if rows:
                columns = list(rows[0].keys())

            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
            )
        except Exception as exc:
            logger.warning("Graph query failed: %s", exc, exc_info=True)
            return QueryResult(columns=[], rows=[], row_count=0, error=str(exc))

    def ping(self) -> str:
        """Health check."""
        rows = self._graph.query("SELECT 1 AS ok")
        return "ok" if rows and rows[0].get("ok") == 1 else "unhealthy"
