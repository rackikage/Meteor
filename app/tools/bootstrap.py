"""Tool bootstrap — register every tool with permissive local ownership.

The user owns this machine, so on-box operations run without approval gates:
- FilesystemAgent widened to the whole root ("/")
- ShellSandbox with empty blocklist and no allowed-commands filter
- Full nmap, pentest, and network scope tools wired in
- An allow-* SQL policy rule seeded at priority 0 (overrides the default deny)

Called once from MeteorRuntime.initialize() before the orchestrator is built.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any, Optional

from app.tools.system.registry import SystemToolRegistry, get_registry

logger = logging.getLogger(__name__)


# ── Thin wrapper tools that expose subprocess capabilities as first-class ──

class NmapTool:
    """Nmap wrapper. Every operation shells out to /usr/bin/nmap."""

    def __init__(self, binary: Optional[str] = None, default_timeout: float = 300.0) -> None:
        self._binary = binary or shutil.which("nmap") or "nmap"
        self._timeout = default_timeout

    def _run(self, args: list[str]) -> dict:
        cmd = [self._binary, *args]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)
            return {
                "command": " ".join(cmd),
                "returncode": proc.returncode,
                "stdout": proc.stdout[:200_000],
                "stderr": proc.stderr[:20_000],
            }
        except subprocess.TimeoutExpired:
            return {"command": " ".join(cmd), "returncode": -1, "stdout": "", "stderr": "timeout"}
        except FileNotFoundError:
            return {"command": " ".join(cmd), "returncode": -1, "stdout": "", "stderr": "nmap not installed"}

    def scan(self, target: str, ports: str = "1-1000") -> dict:
        return self._run(["-T4", "-Pn", "-p", str(ports), str(target)])

    def service_version(self, target: str, ports: str = "1-1000") -> dict:
        return self._run(["-sV", "-T4", "-Pn", "-p", str(ports), str(target)])

    def discover(self, cidr: str) -> dict:
        return self._run(["-sn", "-T4", str(cidr)])

    def script(self, target: str, script: str = "default", ports: str = "1-1000") -> dict:
        return self._run(["-sC" if script == "default" else f"--script={script}", "-T4", "-Pn", "-p", str(ports), str(target)])

    def health(self) -> dict:
        installed = shutil.which(self._binary) is not None
        return {"healthy": installed, "binary": self._binary, "backend": "nmap"}


class PentestTool:
    """Proxy to the existing PentestToolExecutor so pentest is a first-class model tool."""

    def kernel_posture(self) -> dict:
        from app.tools.pentest.tool_executor import get_pentest_executor
        return get_pentest_executor().execute("kernel_posture").to_dict()

    def firewall_analyze(self, cidr: str = "", gateway: str = "") -> dict:
        from app.runtime.asset_context import get_asset_context
        from app.tools.pentest.tool_executor import get_pentest_executor
        ctx = get_asset_context()
        return get_pentest_executor().execute(
            "firewall_analyze",
            graph_tool=ctx.graph_tool,
            gateway=gateway or None,
            cidr=cidr or None,
        ).to_dict()

    def probe(self, target: str, ports: Optional[list[int]] = None) -> dict:
        from app.runtime.asset_context import get_asset_context
        from app.tools.pentest.tool_executor import get_pentest_executor
        ctx = get_asset_context()
        return get_pentest_executor().execute(
            "probe",
            target=target,
            ports=ports,
            event_bus=ctx.event_bus,
        ).to_dict()

    def posture(self, cidr: str = "", gateway: str = "") -> dict:
        from app.runtime.asset_context import get_asset_context
        from app.tools.pentest.tool_executor import get_pentest_executor
        ctx = get_asset_context()
        return get_pentest_executor().execute(
            "posture",
            graph_tool=ctx.graph_tool,
            gateway=gateway or None,
            cidr=cidr or None,
        ).to_dict()

    def health(self) -> dict:
        return {"healthy": True, "backend": "pentest"}


class WebIntelTool:
    """Live web intel — CVE lookup (NVD), Exploit-DB search, and general web
    search. Wraps the async WebSearcher with sync entry points so the model can
    call it like any other tool."""

    def __init__(self) -> None:
        from app.agent.web_search import WebSearcher
        self._searcher = WebSearcher()

    @staticmethod
    def _run(coro):
        import asyncio
        from dataclasses import asdict, is_dataclass

        def _conv(obj):
            if is_dataclass(obj):
                return asdict(obj)
            if isinstance(obj, list):
                return [_conv(o) for o in obj]
            return obj

        result = asyncio.run(coro)
        return _conv(result)

    def search(self, query: str) -> dict:
        hits = self._run(self._searcher._web_search(str(query)))
        return {"query": query, "hits": hits}

    def cves(self, service: str, banner: str = "") -> dict:
        entries = self._run(self._searcher._search_cves(str(service), str(banner)))
        return {"service": service, "cves": entries}

    def exploits(self, service: str, banner: str = "") -> dict:
        matches = self._run(self._searcher._search_exploits(str(service), str(banner)))
        return {"service": service, "exploits": matches}

    def research(self, ip: str, port: int, service: str, banner: str = "") -> dict:
        return self._run(self._searcher.research_service(str(ip), int(port), str(service), str(banner)))

    def health(self) -> dict:
        return {"healthy": True, "backend": "web_intel"}


class NetworkScopeTool:
    """Local network scope discovery — gateway, CIDR, priority targets."""

    def scope(self) -> dict:
        from app.tools.pentest.network_scope import discover_network_scope
        scope = discover_network_scope()
        return {
            "gateway": scope.gateway,
            "cidr": scope.cidr,
            "priority_targets": list(scope.priority_targets),
            "summary": scope.summary_lines(),
        }

    def health(self) -> dict:
        return {"healthy": True, "backend": "network_scope"}


class GrinderTool:
    """Autonomous network exploration — sync wrappers over InfiltrationGrinder.

    Discoveries persist to the asset graph via the event bus, so a follow-up
    `graph.query` sees whatever the grind turned up. Resolves the grinder from
    the shared asset context, so it runs headless under meteor-mcp too."""

    @staticmethod
    def _grinder():
        from app.runtime.asset_context import get_asset_context
        return get_asset_context().grinder

    @staticmethod
    def _run(coro) -> dict:
        import asyncio
        from dataclasses import asdict
        return asdict(asyncio.run(coro))

    def grind_host(self, target: str) -> dict:
        return self._run(self._grinder().grind_host(str(target)))

    def grind_subnet(self, cidr: str, scan: str = "common") -> dict:
        return self._run(self._grinder().grind_subnet(str(cidr), scan=str(scan)))

    def grind_sector(self, cidr: str = "") -> dict:
        return self._run(self._grinder().grind_sector(cidr=str(cidr) or None))

    def health(self) -> dict:
        return {"healthy": True, "backend": "grinder"}


class GraphTool:
    """Asset-graph introspection and read-only SQL over grinder discoveries.

    Resolves GraphQueryTool from the shared asset context (headless under MCP)."""

    @staticmethod
    def _tool():
        from app.runtime.asset_context import get_asset_context
        return get_asset_context().graph_tool

    def schema(self) -> str:
        return self._tool().schema()

    def tables(self) -> list:
        return self._tool().tables()

    def counts(self) -> dict:
        return self._tool().stats()

    def query(self, sql: str) -> dict:
        from dataclasses import asdict
        return asdict(self._tool().query(str(sql)))

    def health(self) -> dict:
        return {"healthy": True, "backend": "graph"}


# ── Bootstrap ────────────────────────────────────────────────────────────

def bootstrap_tools(storage: Any = None) -> SystemToolRegistry:
    """Instantiate every tool with permissive local config, register them,
    and seed allow-all SQL policy rules for this machine.

    Idempotent — safe to call more than once (re-registers over existing entries).
    """
    registry = get_registry()

    # 1. Filesystem — widen access to the whole box.
    from app.tools.system.filesystem import FilesystemAgent
    fs = FilesystemAgent(allowed_dirs=["/"], max_file_size=1 * 1024 * 1024 * 1024)
    registry.register("filesystem", fs, "Filesystem read/write/traverse — full disk", version="1.0")

    # 2. Shell — no blocklist, generous timeout, /bin/bash under the hood.
    from app.tools.system.shell import ShellConfig, ShellSandbox
    shell = ShellSandbox(ShellConfig(
        default_timeout_s=120.0,
        max_timeout_s=3600.0,
        max_output_bytes=20 * 1024 * 1024,
        allowed_commands=None,
        blocked_commands=[],
        work_dir="/",
    ))
    registry.register("shell", shell, "Full shell access — no blocklist", version="1.0")

    # 3. Process manager.
    from app.tools.system.process import ProcessManager
    registry.register("process", ProcessManager(), "Process list/kill/stats", version="1.0")

    # 4. Optional tools — instantiate defensively; missing deps shouldn't break the runtime.
    for slug, module_path, class_name, description in (
        ("clipboard", "app.tools.system.clipboard", "ClipboardBridge", "Clipboard read/write"),
        ("notify", "app.tools.system.notifications", "NotificationService", "Desktop notifications"),
        ("keychain", "app.tools.system.keychain", "KeychainManager", "Credential storage"),
        ("scheduler", "app.tools.system.scheduler", "SchedulerService", "Cron / systemd tasks"),
        ("browser", "app.tools.system.browser_bridge", "BrowserBridge", "Chromium via playwright"),
    ):
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls is None:
                # Fall back to the first class whose name ends in a known suffix.
                candidates = [attr for attr in dir(module)
                              if attr.endswith(("Bridge", "Store", "Hook", "Center", "Manager", "Service"))]
                if candidates:
                    cls = getattr(module, candidates[0])
            if cls is not None:
                registry.register(slug, cls(), description, version="1.0")
            else:
                logger.warning("Optional tool %s: no class found in %s", slug, module_path)
        except Exception as exc:
            logger.info("Optional tool %s unavailable: %s", slug, exc)

    # 5. Custom wrapper tools — nmap, pentest, network scope.
    registry.register("nmap", NmapTool(), "Nmap TCP/host discovery/service/NSE", version="1.0")
    registry.register("pentest", PentestTool(), "Kernel/firewall posture and probe engine", version="1.0")
    registry.register("network", NetworkScopeTool(), "Local network scope (gateway/CIDR)", version="1.0")
    registry.register("grinder", GrinderTool(), "Autonomous host/subnet/sector grinding into the asset graph", version="1.0")
    registry.register("graph", GraphTool(), "Asset graph schema/tables/counts + read-only SQL", version="1.0")
    try:
        registry.register("web", WebIntelTool(), "Live web intel — CVE/NVD, Exploit-DB, web search", version="1.0")
    except Exception as exc:
        logger.info("Web intel tool unavailable: %s", exc)

    # 5b. Arsenal — installed-tool detection + first-class weapon wrappers
    # (sqlmap, nuclei, hydra, …). Registers into this same registry so the app
    # loop and the MCP server both get them.
    try:
        from app.arsenal.weapons import register_arsenal
        register_arsenal(registry)
    except Exception as exc:
        logger.info("Arsenal tools unavailable: %s", exc)

    # 6. Approval hooks — user owns the machine; auto-approve everything.
    registry.auto_approve("*:*")

    # 7. Seed SQL policy rules — priority 0 wins over the default deny (100).
    if storage is not None:
        _seed_allow_all_policy(storage)

    logger.info("Tool bootstrap complete: %d tools registered", len(registry.list_tools()))
    return registry


def _seed_allow_all_policy(storage: Any) -> None:
    """Insert allow-* rules at priority 0 into both policy tables."""
    try:
        storage.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                priority INTEGER NOT NULL DEFAULT 100,
                subject TEXT NOT NULL,
                action TEXT NOT NULL,
                condition_sql TEXT NOT NULL DEFAULT '1=1',
                decision TEXT NOT NULL DEFAULT 'deny',
                reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            store="audit",
        )
        existing = storage.execute(
            "SELECT id FROM policy_rules WHERE reason = ?",
            ("Local ownership: allow all",),
            store="audit",
        )
        if not existing:
            storage.execute(
                """
                INSERT INTO policy_rules (priority, subject, action, condition_sql, decision, reason)
                VALUES (0, '*', '*', '1=1', 'allow', ?)
                """,
                ("Local ownership: allow all",),
                store="audit",
            )
            logger.info("Seeded allow-all policy rule at priority 0")
    except Exception as exc:
        logger.warning("Could not seed allow-all policy rule: %s", exc)

    try:
        storage.execute(
            """
            CREATE TABLE IF NOT EXISTS system_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL DEFAULT '*',
                operation TEXT NOT NULL DEFAULT '*',
                path_pattern TEXT,
                action_gate TEXT NOT NULL DEFAULT 'allow',
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            store="audit",
        )
        existing = storage.execute(
            "SELECT id FROM system_policies WHERE tool = '*' AND operation = '*'",
            store="audit",
        )
        if not existing:
            storage.execute(
                """
                INSERT INTO system_policies (tool, operation, path_pattern, action_gate, priority)
                VALUES ('*', '*', NULL, 'allow', 100)
                """,
                store="audit",
            )
    except Exception as exc:
        logger.warning("Could not seed system_policies allow-all: %s", exc)
