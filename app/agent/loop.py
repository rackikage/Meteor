"""Meteor Agent — autonomous infiltration loop.

Recursively scans, identifies, researches, and pivots through networks.
The agent integrates the Grinder, EventBus, AssetGraph, and WebSearcher
into a closed infiltration loop:

  1. Scan target → discover hosts/services
  2. Research each service → CVE/exploit intelligence
  3. Score attack surface → prioritize high-value targets
  4. Pivot to new hosts → repeat up to max_depth

Meteor Doctrine #7: Evidence precedes conclusions. Every action is traced.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.agent.web_search import ServiceIntel, WebSearcher
from app.graph.event_bus import AssetEventBus
from app.graph.sqlite_graph import SQLiteAssetGraph
from app.dispatcher.grinder import InfiltrationGrinder

logger = logging.getLogger(__name__)

DEFAULT_DEPTH_PORTS = {
    0: [22, 80, 443, 445, 3389, 8080, 8443],   # first pass: key services
    1: [21, 23, 25, 53, 110, 111, 135, 139, 143, 993, 995, 3306, 5432, 5900, 6379, 27017],
    2: list(range(1, 1025)),                     # full sweep if deep enough
}


@dataclass
class AgentReport:
    target: str
    depth_reached: int
    hosts_discovered: int
    services_discovered: int
    critical_vulns: int
    high_vulns: int
    exploits_found: int
    pivot_chains: list[list[str]]
    intelligence: list[ServiceIntel] = field(default_factory=list)
    wall_time_ms: float = 0.0
    started_at: str = ""
    completed_at: str = ""


class MeteorAgent:
    """Autonomous network infiltration and intelligence agent.

    Usage:
        agent = MeteorAgent(graph, bus, grinder)
        report = await agent.infiltrate("10.0.0.0/24", depth=2)
    """

    def __init__(
        self,
        graph: SQLiteAssetGraph,
        event_bus: AssetEventBus,
        grinder: InfiltrationGrinder,
        searcher: Optional[WebSearcher] = None,
        max_depth: int = 3,
    ) -> None:
        self._graph = graph
        self._bus = event_bus
        self._grinder = grinder
        self._searcher = searcher or WebSearcher()
        self._max_depth = max_depth
        self._visited: set[str] = set()

    async def infiltrate(self, target: str, depth: int = 2,
                         ports: Optional[list[int]] = None) -> AgentReport:
        """Autonomously infiltrate a target network.

        Args:
            target: IP, CIDR, or hostname
            depth: How many pivot hops to explore (0 = surface only)
            ports: Port list override (defaults to depth-appropriate ports)

        Returns:
            AgentReport with full intelligence
        """
        t0 = time.monotonic()
        self._visited.clear()

        report = AgentReport(
            target=target,
            depth_reached=0,
            hosts_discovered=0,
            services_discovered=0,
            critical_vulns=0,
            high_vulns=0,
            exploits_found=0,
            pivot_chains=[],
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        await self._bus.publish("scan.started", {
            "target": target, "depth": depth, "agent": "MeteorAgent",
        })

        # Register the target subnet in the graph
        if "/" in target:
            self._graph.upsert_subnet(target)

        # ── Layer 0: Surface scan ────────────────────────────────────
        layer_ports = ports or DEFAULT_DEPTH_PORTS.get(0, [22, 80, 443])

        if "/" in target:
            stats = await self._grinder.grind_subnet(target, ports=layer_ports)
            report.hosts_discovered = stats.hosts_discovered
            report.services_discovered = stats.services_discovered
        else:
            stats = await self._grinder.grind_host(target, ports=layer_ports)
            report.hosts_discovered = 1 if stats.services_discovered > 0 else 0
            report.services_discovered = stats.services_discovered

        report.depth_reached = 1

        # ── Research discovered services ─────────────────────────────
        hosts = self._graph.query(
            "SELECT id, ip FROM hosts WHERE source = 'grinder' ORDER BY last_seen DESC LIMIT 50"
        )
        intelligence: list[ServiceIntel] = []

        for host in hosts:
            hid = host["id"]
            ip = host["ip"]
            if ip in self._visited:
                continue
            self._visited.add(ip)

            services = self._graph.query(
                "SELECT id, port, name, banner FROM services WHERE host_id = ?", (hid,)
            )
            for svc in services:
                intel = await self._searcher.research_service(
                    ip=ip, port=svc["port"], service=svc["name"],
                    banner=svc.get("banner", ""),
                )
                intelligence.append(intel)

                # Write to graph
                for cve in intel.cves:
                    vuln_id = self._graph.upsert_vulnerability(
                        service_id=svc["id"], cve_id=cve.cve_id,
                        severity=cve.severity, exploit_available=cve.exploit_available,
                    )
                    self._graph.add_edge("service", svc["id"], "vulnerability",
                                         vuln_id, "HAS_VULNERABILITY")
                    await self._bus.publish("vulnerability.matched", {
                        "service_id": svc["id"], "cve_id": cve.cve_id,
                        "severity": cve.severity,
                    })

                    if cve.severity == "CRITICAL":
                        report.critical_vulns += 1
                    elif cve.severity == "HIGH":
                        report.high_vulns += 1

                report.exploits_found += len(intel.exploits)

                # Add observations for timeline
                self._graph.add_observation(
                    "service", svc["id"], "meteor_agent",
                    {"attack_score": intel.attack_surface_score},
                )

        report.intelligence = intelligence

        # ── Pivot: find new targets from discovered hosts ────────────
        if depth > 1 and report.hosts_discovered > 0:
            next_ports = ports or DEFAULT_DEPTH_PORTS.get(1, [21, 22, 23, 80, 443, 445, 3389])

            for host in hosts:
                ip = host["id"]
                ip_addr = host["ip"]
                # Discover adjacent hosts via common gateway patterns
                for offset in range(1, min(depth * 10, 50)):
                    next_ip = self._next_ip(ip_addr, offset)
                    if next_ip and next_ip not in self._visited:
                        self._visited.add(next_ip)
                        try:
                            await self._grinder.grind_host(next_ip, ports=next_ports)
                        except Exception:
                            pass

            report.depth_reached = min(depth, self._max_depth)

        report.wall_time_ms = (time.monotonic() - t0) * 1000
        report.completed_at = datetime.now(timezone.utc).isoformat()

        await self._bus.publish("scan.completed", {
            "target": target,
            "hosts_discovered": report.hosts_discovered,
            "services_discovered": report.services_discovered,
            "vulnerabilities": report.critical_vulns + report.high_vulns,
            "exploits_found": report.exploits_found,
            "depth_reached": report.depth_reached,
        })

        return report

    @staticmethod
    def _next_ip(ip: str, offset: int) -> Optional[str]:
        """Calculate the next IP address for lateral scanning."""
        try:
            parts = [int(p) for p in ip.split(".")]
            if len(parts) != 4:
                return None
            num = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
            num += offset
            if num > 0xFFFFFFFF:
                return None
            return f"{(num >> 24) & 0xFF}.{(num >> 16) & 0xFF}.{(num >> 8) & 0xFF}.{num & 0xFF}"
        except Exception:
            return None
