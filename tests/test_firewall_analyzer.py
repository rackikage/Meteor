"""Tests for graph-based firewall posture analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.tools.pentest.firewall_analyzer import (
    ADMIN_PORTS,
    analyze_graph,
    analyze_service_rows,
    format_firewall_analysis_markdown,
)


@dataclass
class FakeQueryResult:
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0

    def __post_init__(self):
        self.row_count = len(self.rows)


class FakeGraphTool:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def query(self, sql: str, params=None):
        return FakeQueryResult(rows=list(self._rows))


class TestFirewallAnalyzer:

    def test_admin_ports_include_mikrotik(self):
        assert 8291 in ADMIN_PORTS
        assert ADMIN_PORTS[8291] == "mikrotik-winbox"

    def test_empty_graph(self):
        report = analyze_service_rows([])
        assert any(f["category"] == "graph_coverage" for f in report["findings"])
        assert report["services_analyzed"] == 0

    def test_ssh_exposure(self):
        rows = [
            {"ip": "192.168.1.1", "port": 22, "name": "ssh"},
            {"ip": "192.168.1.50", "port": 22, "name": "ssh"},
        ]
        report = analyze_service_rows(rows)
        assert report["admin_port_hits"] == 2
        titles = [f["title"] for f in report["findings"]]
        assert any("ssh" in t.lower() for t in titles)
        ssh_f = next(f for f in report["findings"] if "ssh" in f["title"].lower())
        assert "lesson" in ssh_f or ssh_f.get("lesson") == "" or ssh_f.get("lesson")

    def test_mikrotik_high_severity(self):
        rows = [{"ip": "192.168.1.1", "port": 8291, "name": "winbox"}]
        report = analyze_service_rows(rows)
        router = next(f for f in report["findings"] if f["category"] == "router_management")
        assert router["severity"] == "high"

    def test_analyze_graph_gateway_hit(self):
        rows = [
            {"ip": "192.168.1.1", "port": 80, "name": "http"},
            {"ip": "192.168.1.1", "port": 8291, "name": "winbox"},
        ]
        tool = FakeGraphTool(rows)
        report = analyze_graph(tool, gateway="192.168.1.1", cidr="192.168.1.0/24")
        assert report["scope"]["gateway"] == "192.168.1.1"
        assert any(f["category"] == "network_scope" for f in report["findings"])
        assert "educational" in report
        md = format_firewall_analysis_markdown(report)
        assert "Perimeter" in md
        assert "L2/L3" in md or "l2_l3" in report["educational"]

    def test_gateway_not_in_graph(self):
        tool = FakeGraphTool([{"ip": "10.0.0.5", "port": 443, "name": "https"}])
        report = analyze_graph(tool, gateway="192.168.1.1")
        not_scanned = next(f for f in report["findings"] if f["title"] == "Gateway not scanned")
        assert not_scanned["severity"] == "info"
