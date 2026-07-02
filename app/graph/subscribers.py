"""Graph event subscribers — wire an AssetEventBus to auto-persist discoveries
into a SQLiteAssetGraph.

Shared by the full desktop runtime (`app/api/main.py`) and the headless MCP
context (`app/mcp/context.py`) so both persist grinder/scanner discoveries the
same way, from a single definition.
"""

from __future__ import annotations

from app.graph.event_bus import AssetEventBus
from app.graph.sqlite_graph import SQLiteAssetGraph


def wire_graph_subscribers(graph: SQLiteAssetGraph, event_bus: AssetEventBus) -> None:
    """Subscribe host/service/vuln/credential topics to graph upserts."""

    def _on_host(payload: dict) -> None:
        graph.upsert_host(
            ip=payload["ip"],
            hostname=payload.get("hostname"),
            os=payload.get("os"),
            subnet_id=payload.get("subnet_id"),
            source=payload.get("source", "discovery"),
        )

    def _on_service(payload: dict) -> None:
        host_id = payload.get("host_id")
        if not host_id:
            host_id = graph.upsert_host(ip=payload["ip"])
        svc_id = graph.upsert_service(
            host_id=host_id,
            port=payload["port"],
            name=payload.get("name", "unknown"),
            banner=payload.get("banner", ""),
        )
        graph.add_edge("host", host_id, "service", svc_id, "RUNS_SERVICE")

    def _on_vuln(payload: dict) -> None:
        svc_id = payload["service_id"]
        graph.upsert_vulnerability(
            service_id=svc_id,
            cve_id=payload["cve_id"],
            severity=payload.get("severity"),
            exploit_available=payload.get("exploit_available", False),
        )
        graph.add_edge("service", svc_id, "vulnerability", 0, "HAS_VULNERABILITY")

    def _on_cred(payload: dict) -> None:
        host_id = payload.get("host_id")
        cred_id = graph.upsert_credential(
            host_id=host_id,
            username=payload["username"],
            secret_type=payload["secret_type"],
            secret_value=payload.get("secret_value", ""),
            source=payload.get("source", "discovery"),
        )
        if host_id:
            graph.add_edge("host", host_id, "credential", cred_id, "CONTAINS_CREDENTIAL")

    event_bus.subscribe("host.discovered", _on_host)
    event_bus.subscribe("service.discovered", _on_service)
    event_bus.subscribe("vulnerability.matched", _on_vuln)
    event_bus.subscribe("credential.found", _on_cred)
