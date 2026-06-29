"""SQLiteAssetGraph — SQLite-backed implementation of the AssetGraph contract.

Stores network nodes (hosts, services, subnets, credentials, users, shares,
vulnerabilities) and typed edges between them. Backed by the audit store.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.graph.contract import AssetGraphContract
from app.storage.sqlite_adapter import SQLiteAdapter

logger = logging.getLogger(__name__)


class SQLiteAssetGraph(AssetGraphContract):
    """SQLite persistence for the infiltration grinder asset graph."""

    def __init__(self, storage: SQLiteAdapter) -> None:
        self._storage = storage

    # ── Node upserts ──────────────────────────────────────────────────

    def upsert_host(self, ip: str, hostname: Optional[str] = None,
                    os: Optional[str] = None, subnet_id: Optional[int] = None,
                    source: Optional[str] = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO hosts (ip, hostname, os, subnet_id, source, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ip) DO UPDATE SET
                   hostname = COALESCE(excluded.hostname, hosts.hostname),
                   os = COALESCE(excluded.os, hosts.os),
                   subnet_id = COALESCE(excluded.subnet_id, hosts.subnet_id),
                   source = COALESCE(excluded.source, hosts.source),
                   last_seen = excluded.last_seen""",
            (ip, hostname, os, subnet_id, source, now, now),
            store="audit",
        )
        rows = self._storage.execute("SELECT id FROM hosts WHERE ip = ?", (ip,), store="audit")
        return rows[0]["id"]

    def upsert_subnet(self, cidr: str, parent_id: Optional[int] = None,
                      scope_session: Optional[str] = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO subnets (cidr, parent_id, scope_session, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(cidr) DO UPDATE SET
                   parent_id = COALESCE(excluded.parent_id, subnets.parent_id),
                   last_seen = excluded.last_seen""",
            (cidr, parent_id, scope_session, now, now),
            store="audit",
        )
        rows = self._storage.execute("SELECT id FROM subnets WHERE cidr = ?", (cidr,), store="audit")
        return rows[0]["id"]

    def upsert_service(self, host_id: int, port: int, name: str,
                       proto: str = "tcp", banner: str = "",
                       state: str = "open") -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO services (host_id, port, proto, name, banner, state, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(host_id, port, proto) DO UPDATE SET
                   name = COALESCE(excluded.name, services.name),
                   banner = COALESCE(excluded.banner, services.banner),
                   state = COALESCE(excluded.state, services.state),
                   last_seen = excluded.last_seen""",
            (host_id, port, proto, name, banner, state, now, now),
            store="audit",
        )
        rows = self._storage.execute(
            "SELECT id FROM services WHERE host_id = ? AND port = ? AND proto = ?",
            (host_id, port, proto), store="audit",
        )
        return rows[0]["id"]

    def upsert_credential(self, host_id: Optional[int], username: str,
                          secret_type: str, secret_value: str,
                          source: Optional[str] = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO credentials (host_id, username, secret_type, secret_value, source, discovered_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(host_id, username, secret_type) DO UPDATE SET
                   secret_value = COALESCE(excluded.secret_value, credentials.secret_value),
                   last_used = excluded.discovered_at""",
            (host_id, username, secret_type, secret_value, source, now),
            store="audit",
        )
        rows = self._storage.execute(
            "SELECT id FROM credentials WHERE host_id IS ? AND username = ? AND secret_type = ?",
            (host_id, username, secret_type), store="audit",
        )
        return rows[0]["id"]

    def upsert_user(self, name: str, domain: Optional[str] = None,
                    source: Optional[str] = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO users (name, domain, source, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(name, domain) DO UPDATE SET
                   last_seen = excluded.last_seen""",
            (name, domain, source, now, now),
            store="audit",
        )
        rows = self._storage.execute(
            "SELECT id FROM users WHERE name = ? AND domain IS ?", (name, domain), store="audit",
        )
        return rows[0]["id"]

    def upsert_share(self, host_id: int, name: str, share_type: Optional[str] = None,
                     permissions: Optional[str] = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO shares (host_id, name, share_type, permissions, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(host_id, name, share_type) DO UPDATE SET
                   permissions = COALESCE(excluded.permissions, shares.permissions),
                   last_seen = excluded.last_seen""",
            (host_id, name, share_type, permissions, now, now),
            store="audit",
        )
        rows = self._storage.execute(
            "SELECT id FROM shares WHERE host_id = ? AND name = ? AND share_type IS ?",
            (host_id, name, share_type), store="audit",
        )
        return rows[0]["id"]

    def upsert_vulnerability(self, service_id: int, cve_id: str,
                             severity: Optional[str] = None,
                             description: Optional[str] = None,
                             exploit_available: bool = False) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO vulnerabilities (service_id, cve_id, severity, description,
               exploit_available, discovered_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (service_id, cve_id, severity, description, 1 if exploit_available else 0, now),
            store="audit",
        )
        rows = self._storage.execute("SELECT last_insert_rowid() as id", store="audit")
        return rows[0]["id"]

    # ── Edges ──────────────────────────────────────────────────────────

    def add_edge(self, source_type: str, source_id: int,
                 target_type: str, target_id: int,
                 edge_type: str, weight: float = 1.0,
                 confidence: float = 1.0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO asset_edges (source_type, source_id, target_type, target_id,
               edge_type, weight, confidence, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_type, source_id, target_type, target_id, edge_type)
               DO UPDATE SET last_seen = excluded.last_seen,
                   confidence = excluded.confidence""",
            (source_type, source_id, target_type, target_id,
             edge_type, weight, confidence, now, now),
            store="audit",
        )

    # ── Observations ───────────────────────────────────────────────────

    def add_observation(self, asset_type: str, asset_id: int,
                        source: str, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute(
            """INSERT INTO asset_observations (asset_type, asset_id, source, observed_at, attrs_json)
               VALUES (?, ?, ?, ?, ?)""",
            (asset_type, asset_id, source, now, json.dumps(payload)),
            store="audit",
        )

    # ── Queries ────────────────────────────────────────────────────────

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        if not sql.strip().upper().startswith(("SELECT", "WITH", "EXPLAIN", "PRAGMA")):
            raise ValueError("Only read queries (SELECT/WITH) are permitted")
        return [dict(r) for r in self._storage.execute(sql, params, store="audit")]

    def find_neighbors(self, asset_type: str, asset_id: int,
                       edge_type: Optional[str] = None) -> list[dict[str, Any]]:
        if edge_type:
            return self.query(
                """SELECT target_type as neighbor_type, target_id as neighbor_id,
                          edge_type, weight, confidence
                   FROM asset_edges
                   WHERE source_type = ? AND source_id = ? AND edge_type = ?
                   UNION ALL
                   SELECT source_type, source_id, edge_type, weight, confidence
                   FROM asset_edges
                   WHERE target_type = ? AND target_id = ? AND edge_type = ?
                   ORDER BY weight DESC""",
                (asset_type, asset_id, edge_type, asset_type, asset_id, edge_type),
            )
        return self.query(
            """SELECT target_type as neighbor_type, target_id as neighbor_id,
                      edge_type, weight, confidence
               FROM asset_edges
               WHERE source_type = ? AND source_id = ?
               UNION ALL
               SELECT source_type, source_id, edge_type, weight, confidence
               FROM asset_edges
               WHERE target_type = ? AND target_id = ?
               ORDER BY weight DESC""",
            (asset_type, asset_id, asset_type, asset_id),
        )

    def find_paths(self, source_type: str, source_id: int,
                   target_type: str, target_id: int,
                   max_hops: int = 4) -> list[dict[str, Any]]:
        return self.query(
            """WITH RECURSIVE path_cte AS (
                SELECT source_type, source_id, target_type, target_id, edge_type,
                       weight, 1 as depth, edge_type as path_edges
                FROM asset_edges
                WHERE source_type = ? AND source_id = ?
                UNION ALL
                SELECT e.source_type, e.source_id, e.target_type, e.target_id,
                       e.edge_type, p.weight * e.weight, p.depth + 1,
                       p.path_edges || ' > ' || e.edge_type
                FROM asset_edges e
                JOIN path_cte p ON e.source_type = p.target_type AND e.source_id = p.target_id
                WHERE p.depth < ?
            )
            SELECT * FROM path_cte
            WHERE target_type = ? AND target_id = ?
            ORDER BY depth, weight DESC""",
            (source_type, source_id, max_hops, target_type, target_id),
        )

    # ── Lifecycle ──────────────────────────────────────────────────────

    def close(self) -> None:
        pass  # Storage is owned by the runtime, not the graph
