"""Meteor Agent — autonomous infiltration loop.

Recursively scans, identifies, researches, and pivots through networks.
The agent integrates the Grinder, EventBus, AssetGraph, WebSearcher,
StrategyEngine, and PluginRegistry into a closed adaptive loop:

  1. Scan target → discover hosts/services          (Grinder)
  2. Consult LLM strategy engine → adapt next ports  (StrategyEngine)
  3. Research each service → CVE/exploit intel        (WebSearcher)
  4. Run plugin analyze hooks → annotate intel        (PluginRegistry)
  5. Score attack surface → prioritize targets
  6. Pivot to LLM-recommended targets → repeat        (StrategyEngine)
  7. Run plugin report hooks → final report           (PluginRegistry)
  8. Record outcome → strategy memory for next run    (StrategyEngine)

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
from app.agent.strategy import (
    BehaviorVector, StrategyEngine, ScanStrategy, DEFAULT_STRATEGY, bv_from_scan,
)
from app.graph.event_bus import AssetEventBus
from app.graph.sqlite_graph import SQLiteAssetGraph
from app.dispatcher.grinder import InfiltrationGrinder
from app.plugins.loader import PluginRegistry
from app.tools.pentest.ports import DEFAULT_DEPTH_PORTS

logger = logging.getLogger(__name__)

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
    strategy_reason: str = ""
    llm_adapted: bool = False
    plugins_active: int = 0


class MeteorAgent:
    """Autonomous network infiltration and intelligence agent.

    The LLM strategy engine (Ollama) adapts port selection and pivot targets
    between scan phases based on partial results.  A plugin registry allows
    custom Python modules to inject logic at scan, analyze, and report hooks.

    Usage:
        agent = MeteorAgent(graph, bus, grinder, strategy=StrategyEngine())
        report = await agent.infiltrate("10.0.0.0/24", depth=2)
    """

    def __init__(
        self,
        graph: SQLiteAssetGraph,
        event_bus: AssetEventBus,
        grinder: InfiltrationGrinder,
        searcher: Optional[WebSearcher] = None,
        strategy: Optional[StrategyEngine] = None,
        plugins: Optional[PluginRegistry] = None,
        max_depth: int = 3,
    ) -> None:
        self._graph = graph
        self._bus = event_bus
        self._grinder = grinder
        self._searcher = searcher or WebSearcher()
        self._strategy = strategy or StrategyEngine()
        self._plugins = plugins or PluginRegistry()
        self._max_depth = max_depth
        self._visited: set[str] = set()

    async def infiltrate(
        self,
        target: str,
        depth: int = 2,
        ports: Optional[list[int]] = None,
    ) -> AgentReport:
        """Autonomously infiltrate a target with LLM-adaptive strategy.

        Args:
            target: IP, CIDR, or hostname
            depth:  Pivot hops (0 = surface only)
            ports:  Manual port override; None = LLM / depth-default

        Returns:
            AgentReport enriched by strategy decisions and plugin hooks
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
            plugins_active=len(self._plugins),
        )

        await self._bus.publish("scan.started", {
            "target": target, "depth": depth, "agent": "MeteorAgent",
        })

        if "/" in target:
            self._graph.upsert_subnet(target)

        # ── Phase 0: Initial surface scan ────────────────────────────
        layer_ports = ports or DEFAULT_DEPTH_PORTS.get(0, [22, 80, 443])

        # Allow plugins to add/modify the initial port list
        layer_ports = self._plugins.run_scan_hooks(target, layer_ports)

        if "/" in target:
            stats = await self._grinder.grind_subnet(target, ports=layer_ports)
            report.hosts_discovered = stats.hosts_discovered
            report.services_discovered = stats.services_discovered
        else:
            stats = await self._grinder.grind_host(target, ports=layer_ports)
            report.hosts_discovered = 1 if stats.services_discovered > 0 else 0
            report.services_discovered = stats.services_discovered

        report.depth_reached = 1

        # ── Phase 1: Consult LLM — adapt strategy from phase 0 data ─
        hosts_q = self._graph.query(
            "SELECT id, ip FROM hosts WHERE source = 'grinder' ORDER BY last_seen DESC LIMIT 50"
        )
        svc_list = self._collect_services(hosts_q)

        initial_bv = bv_from_scan(
            hosts=[h["ip"] for h in hosts_q],
            services=svc_list,
            cves=[],
            ports=layer_ports,
            depth=0,
        )
        strategy: ScanStrategy = await self._strategy.decide(
            hosts_found=[h["ip"] for h in hosts_q],
            services=svc_list,
            cves=[],
            depth=0,
            bv=initial_bv,
        )
        report.strategy_reason = strategy.reason
        report.llm_adapted = strategy.llm_adapted

        logger.info(
            "Strategy (%s): %s",
            "LLM" if strategy.llm_adapted else "default",
            strategy.reason[:120],
        )

        # ── Phase 2: Research discovered services ────────────────────
        intelligence: list[ServiceIntel] = []
        all_cves: list[dict] = []

        # Prioritise services the LLM flagged
        svc_list = self._sort_by_priority(svc_list, strategy.priority_services)

        for svc in svc_list[:40]:
            ip = svc["ip"]
            if ip in self._visited:
                continue
            self._visited.add(ip)

            intel = await self._searcher.research_service(
                ip=ip,
                port=svc["port"],
                service=svc["name"],
                banner=svc.get("banner", ""),
            )

            # Run plugin analyze hooks
            intel_dict = self._plugins.run_analyze_hooks({
                "ip": ip, "port": svc["port"], "service": svc["name"],
                "banner": svc.get("banner", ""),
                "cves": [vars(c) for c in intel.cves],
                "exploits": [vars(e) for e in intel.exploits],
                "attack_surface_score": intel.attack_surface_score,
            })

            # Persist CVEs to graph
            svc_id = svc.get("id")
            if svc_id:
                for cve in intel.cves:
                    vuln_id = self._graph.upsert_vulnerability(
                        service_id=svc_id, cve_id=cve.cve_id,
                        severity=cve.severity, exploit_available=cve.exploit_available,
                    )
                    self._graph.add_edge("service", svc_id, "vulnerability",
                                         vuln_id, "HAS_VULNERABILITY")
                    await self._bus.publish("vulnerability.matched", {
                        "service_id": svc_id, "cve_id": cve.cve_id,
                        "severity": cve.severity,
                    })
                    if cve.severity == "CRITICAL":
                        report.critical_vulns += 1
                    elif cve.severity == "HIGH":
                        report.high_vulns += 1
                    all_cves.append({"cve_id": cve.cve_id, "severity": cve.severity,
                                     "description": cve.description})

                    self._graph.add_observation(
                        "service", svc_id, "meteor_agent",
                        {"attack_score": intel.attack_surface_score,
                         "plugin_notes": intel_dict.get("custom_tag", "")},
                    )

            report.exploits_found += len(intel.exploits)
            intelligence.append(intel)

        report.intelligence = intelligence

        # ── Phase 3: LLM decides pivot strategy based on full intel ──
        # Build full BV now that we have CVE data
        current_bv = bv_from_scan(
            hosts=[h["ip"] for h in hosts_q],
            services=svc_list,
            cves=all_cves,
            ports=layer_ports,
            depth=depth,
        )
        if depth > 1 and report.hosts_discovered > 0:
            pivot_strategy = await self._strategy.decide(
                hosts_found=[h["ip"] for h in hosts_q],
                services=svc_list,
                cves=all_cves,
                depth=1,
                bv=current_bv,
            )
            report.strategy_reason = pivot_strategy.reason
            report.llm_adapted = pivot_strategy.llm_adapted

            # LLM-recommended pivots first, then adjacency fallback
            pivot_targets = list(pivot_strategy.pivot_targets)
            if not pivot_targets:
                pivot_targets = self._adjacency_pivots(hosts_q, depth)

            next_ports = (
                [p for p in pivot_strategy.next_ports if p not in pivot_strategy.skip_ports]
                if pivot_strategy.llm_adapted
                else DEFAULT_DEPTH_PORTS.get(1, [22, 80, 443, 445])
            )
            next_ports = self._plugins.run_scan_hooks("pivot", next_ports)

            pivot_chains: list[list[str]] = []
            for ip in pivot_targets[:20]:
                if ip in self._visited:
                    continue
                self._visited.add(ip)
                try:
                    await self._grinder.grind_host(ip, ports=next_ports)
                    pivot_chains.append([target, ip])
                except Exception:
                    pass

            report.pivot_chains = pivot_chains
            report.depth_reached = min(depth, self._max_depth)

        # ── Phase 4: Plugin report hooks ─────────────────────────────
        report_dict = self._plugins.run_report_hooks({
            "target": target,
            "hosts_discovered": report.hosts_discovered,
            "services_discovered": report.services_discovered,
            "critical_vulns": report.critical_vulns,
            "high_vulns": report.high_vulns,
            "exploits_found": report.exploits_found,
            "strategy_reason": report.strategy_reason,
            "llm_adapted": report.llm_adapted,
        })
        # Merge any plugin-added fields back (non-destructive)
        for k, v in report_dict.items():
            if not hasattr(report, k):
                logger.debug("Plugin added report field: %s", k)

        # ── Phase 5: Record outcome for future strategy memory ────────
        self._strategy.record_outcome(
            hosts=report.hosts_discovered,
            services=report.services_discovered,
            critical_vulns=report.critical_vulns,
            ports_used=layer_ports,
            depth=depth,
            bv=current_bv,
        )

        report.wall_time_ms = (time.monotonic() - t0) * 1000
        report.completed_at = datetime.now(timezone.utc).isoformat()

        await self._bus.publish("scan.completed", {
            "target": target,
            "hosts_discovered": report.hosts_discovered,
            "services_discovered": report.services_discovered,
            "vulnerabilities": report.critical_vulns + report.high_vulns,
            "exploits_found": report.exploits_found,
            "depth_reached": report.depth_reached,
            "llm_adapted": report.llm_adapted,
        })

        return report

    # ── Helpers ──────────────────────────────────────────────────────

    def _collect_services(self, hosts: list[dict]) -> list[dict]:
        """Collect services for all hosts from graph."""
        services = []
        for host in hosts:
            rows = self._graph.query(
                "SELECT id, port, name, banner FROM services WHERE host_id = ?",
                (host["id"],),
            )
            for r in rows:
                services.append({
                    "id": r["id"],
                    "ip": host["ip"],
                    "port": r["port"],
                    "name": r["name"],
                    "banner": r.get("banner", ""),
                })
        return services

    @staticmethod
    def _sort_by_priority(
        services: list[dict], priority: list[str]
    ) -> list[dict]:
        """Reorder services so priority_services float to the top."""
        if not priority:
            return services
        p_set = {s.lower() for s in priority}
        high = [s for s in services if s.get("name", "").lower() in p_set]
        low = [s for s in services if s.get("name", "").lower() not in p_set]
        return high + low

    def _adjacency_pivots(self, hosts: list[dict], depth: int) -> list[str]:
        """Fallback pivot targets: IPs adjacent to discovered hosts."""
        pivots = []
        for host in hosts:
            ip = host["ip"]
            for offset in range(1, min(depth * 10, 30)):
                nxt = self._next_ip(ip, offset)
                if nxt and nxt not in self._visited:
                    pivots.append(nxt)
        return pivots

    @staticmethod
    def _next_ip(ip: str, offset: int) -> Optional[str]:
        try:
            parts = [int(p) for p in ip.split(".")]
            if len(parts) != 4:
                return None
            num = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
            num += offset
            if num > 0xFFFFFFFF:
                return None
            return (
                f"{(num >> 24) & 0xFF}.{(num >> 16) & 0xFF}."
                f"{(num >> 8) & 0xFF}.{num & 0xFF}"
            )
        except Exception:
            return None
