"""Tests for the MCP env-scoped policy (P1) and rich JSON schemas (P2).

Pure logic — no network, no MCP transport. Covers the offensive-gated default,
read-only filtering, CIDR scoping, the arsenal.run danger extension, and the
typed/optional schema shapes surfaced to MCP clients.
"""

from __future__ import annotations

from app.mcp.policy import McpPolicy, is_mutating, is_offensive
from app.mcp.server import _input_schema
from app.runtime.danger import classify_danger
from app.runtime.tool_executor import ToolExecutor


CAPS = ToolExecutor.CAPABILITIES


def _visible(pol) -> int:
    return sum(1 for t in CAPS if pol.is_visible(*t.split(".", 1)))


# ── Default posture: offensive-gated ────────────────────────────────────────

class TestDefaultPosture:
    def setup_method(self):
        self.p = McpPolicy.from_env(env={})

    def test_local_and_recon_allowed(self):
        assert self.p.gate("graph", "query", {"sql": "SELECT 1"}) is None
        assert self.p.gate("nmap", "scan", {"target": "10.0.0.1"}) is None
        assert self.p.gate("arsenal", "detect", {}) is None
        assert self.p.gate("filesystem", "read", {"path": "/etc/hostname"}) is None

    def test_grinder_and_weapons_refused(self):
        assert self.p.gate("grinder", "grind_subnet", {"cidr": "10.0.0.0/24"})
        msg = self.p.gate("sqlmap", "scan", {"url": "http://x"})
        assert msg and "ALLOWED_CIDR" in msg

    def test_everything_still_listed(self):
        # Offensive-gated lists tools (they refuse on call with guidance).
        assert _visible(self.p) == len(CAPS)


# ── READ_ONLY ───────────────────────────────────────────────────────────────

class TestReadOnly:
    def setup_method(self):
        self.p = McpPolicy.from_env(env={"METEOR_MCP_READ_ONLY": "1"})

    def test_reduces_tool_count(self):
        assert _visible(self.p) < len(CAPS)

    def test_mutating_hidden_and_refused(self):
        for tool, op, params in (
            ("shell", "run", {"command": "ls"}),
            ("filesystem", "write", {"path": "/x", "content": "y"}),
            ("nmap", "scan", {"target": "1.2.3.4"}),
            ("sqlmap", "scan", {"url": "http://x"}),
        ):
            assert not self.p.is_visible(tool, op)
            assert self.p.gate(tool, op, params)

    def test_reads_still_allowed(self):
        assert self.p.is_visible("filesystem", "read")
        assert self.p.gate("filesystem", "read", {"path": "/etc/hostname"}) is None
        assert self.p.gate("graph", "query", {"sql": "SELECT 1"}) is None


# ── ALLOWED_CIDR ─────────────────────────────────────────────────────────────

class TestCidrScope:
    def setup_method(self):
        self.p = McpPolicy.from_env(env={"METEOR_MCP_ALLOWED_CIDR": "10.0.0.0/24"})

    def test_in_scope_offensive_allowed(self):
        assert self.p.gate("grinder", "grind_subnet", {"cidr": "10.0.0.0/24"}) is None
        assert self.p.gate("grinder", "grind_host", {"target": "10.0.0.5"}) is None
        assert self.p.gate("sqlmap", "scan", {"url": "http://10.0.0.7/a"}) is None

    def test_out_of_scope_refused(self):
        assert self.p.gate("grinder", "grind_subnet", {"cidr": "192.168.1.0/24"})
        assert self.p.gate("sqlmap", "scan", {"url": "http://8.8.8.8/a"})
        # scope also constrains non-offensive active tools once a CIDR is set
        assert self.p.gate("nmap", "scan", {"target": "8.8.8.8"})


def test_allow_danger_unlocks_offensive():
    p = McpPolicy.from_env(env={"METEOR_MCP_ALLOW_DANGER": "1"})
    assert p.gate("grinder", "grind_subnet", {"cidr": "10.0.0.0/24"}) is None
    assert p.gate("hydra", "bruteforce", {"target": "x", "service": "ssh"}) is None


# ── classification helpers ──────────────────────────────────────────────────

def test_offensive_classification():
    assert is_offensive("grinder", "grind_host")
    assert is_offensive("sqlmap", "scan")
    assert is_offensive("arsenal", "run")
    assert not is_offensive("arsenal", "detect")
    assert not is_offensive("nmap", "scan")       # recon, allowed by default
    assert not is_offensive("exiftool", "extract")  # local/forensic


def test_mutating_classification():
    assert is_mutating("shell", "run")
    assert is_mutating("filesystem", "write")
    assert is_mutating("nmap", "scan")
    assert not is_mutating("filesystem", "read")
    assert not is_mutating("graph", "query")


# ── danger extension for arsenal.run ────────────────────────────────────────

def test_arsenal_run_danger():
    assert classify_danger("arsenal", "run", {"tool": "rm", "args": "-rf /"})
    assert classify_danger("arsenal", "run", {"tool": "mkfs.ext4", "args": "/dev/sda"})
    assert classify_danger("arsenal", "run", {"tool": "nmap", "args": "-sV 10.0.0.1"}) is None


# ── P2 rich schemas ──────────────────────────────────────────────────────────

def test_weapon_optional_params_typed():
    sq = _input_schema("sqlmap.scan", ["url"])
    assert sq["properties"]["level"]["type"] == "integer"
    assert sq["properties"]["risk"]["type"] == "integer"
    assert "data" in sq["properties"] and "extra" in sq["properties"]
    assert sq["required"] == ["url"]
    assert sq["additionalProperties"] is False

    nu = _input_schema("nuclei.scan", ["target"])
    assert {"templates", "severity"} <= set(nu["properties"])


def test_grinder_scan_enum_and_process_pid_int():
    gs = _input_schema("grinder.grind_subnet", ["cidr"])
    assert gs["properties"]["scan"]["enum"] == ["common", "subset", "sweep"]
    pk = _input_schema("process.kill", ["pid"])
    assert pk["properties"]["pid"]["type"] == "integer"


def test_schema_fallback_for_plain_tool():
    fb = _input_schema("clipboard.paste", [])
    assert fb["properties"] == {}
    assert "additionalProperties" not in fb  # stays permissive when undeclared
