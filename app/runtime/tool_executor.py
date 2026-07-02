"""Tool Executor — model-invoked system tool execution with permission gating.

Meteor Doctrine #2: Every tool is policy-gated. This executor bridges the
model's reasoning with the system's capabilities. The model requests a tool
operation, the executor validates it against policy and budget, executes it,
and returns structured results the model can reason over.

The loop:
1. Model decides: "I need to read /tmp/log.txt"
2. Executor validates: policy check + budget check
3. Executor runs: FilesystemAgent.read_file("/tmp/log.txt")
4. Executor returns: {"status": "ok", "result": "...", "signal_score": 10}
5. Model uses the result in its next reasoning step
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from app.tools.system.registry import get_registry
from app.tools.system.signal_budget import SignalBudget

logger = logging.getLogger(__name__)


class ToolResultStatus(str, Enum):
    OK = "ok"
    DENIED = "denied"
    ERROR = "error"
    BUDGET_EXHAUSTED = "budget_exhausted"
    POLICY_DENIED = "policy_denied"


@dataclass
class ToolRequest:
    """A structured request from the model to use a system tool."""
    tool: str
    operation: str
    params: dict = field(default_factory=dict)
    session_id: str = ""
    request_id: str = ""


@dataclass
class ToolResult:
    """Result of a tool execution, returned to the model."""
    tool: str
    operation: str
    status: ToolResultStatus
    result: Any = None
    error: str = ""
    signal_score: float = 0.0
    duration_ms: float = 0.0
    evidence: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_prompt_context(self) -> str:
        """Format this result as context for the model's next reasoning step."""
        if self.status == ToolResultStatus.OK:
            return (
                f"Tool result [{self.tool}.{self.operation}]:\n"
                f"{self.result}\n"
                f"(signal: {self.signal_score:.0f})"
            )
        else:
            return (
                f"Tool error [{self.tool}.{self.operation}]:\n"
                f"{self.status.value}: {self.error}"
            )


class ToolExecutor:
    """Execute system tools on behalf of the model.

    Every execution passes through:
    1. Tool validation (does this tool + operation exist?)
    2. Policy check (SQL policy table)
    3. Budget check (signal budget)
    4. Execution (actual tool invocation)
    5. Result formatting (for model consumption)

    The executor never runs a tool without explicit policy+budget approval.
    """

    # Tool operation mapping — maps model-friendly names to tool methods
    # Format: tool.operation -> (method_name, param_map, description)
    CAPABILITIES = {
        "filesystem.read": ("read_file", ["path"], "Read a file"),
        "filesystem.write": ("write_file", ["path", "content"], "Write/overwrite a whole file"),
        "filesystem.edit": ("edit", ["path", "old_string", "new_string"], "Surgical in-place edit: replace old_string with new_string (unique unless replace_all)"),
        "filesystem.append": ("append_file", ["path", "content"], "Append text to a file"),
        "filesystem.read_range": ("read_range", ["path", "start_line", "end_line"], "Read a line range from a file"),
        "filesystem.list": ("list_dir", ["path"], "List directory contents"),
        "filesystem.walk": ("walk", ["path"], "Recursively walk a directory tree"),
        "filesystem.stat": ("stat", ["path"], "Get file metadata"),
        "filesystem.grep": ("grep", ["pattern", "path"], "Search file contents"),
        "filesystem.glob": ("glob", ["pattern"], "Find files by pattern"),
        "filesystem.mkdir": ("mkdir", ["path"], "Create directory"),
        "filesystem.remove": ("remove", ["path"], "Delete a file"),
        "filesystem.remove_tree": ("remove_tree", ["path"], "Recursively delete a directory tree"),
        "filesystem.copy": ("copy", ["src", "dst"], "Copy a file"),
        "filesystem.move": ("move", ["src", "dst"], "Move a file"),
        "filesystem.md5": ("md5", ["path"], "MD5 hash of file"),
        "filesystem.sha256": ("sha256", ["path"], "SHA256 hash of file"),
        "filesystem.which": ("which", ["executable"], "Find executable on PATH"),
        "shell.run": ("run_sync", ["command"], "Run a shell command"),
        "process.list": ("list_processes", [], "List running processes"),
        "process.stats": ("system_stats", [], "Get system resource stats"),
        "process.kill": ("kill", ["pid"], "Terminate a process"),
        "clipboard.copy": ("copy", ["text"], "Copy to clipboard"),
        "clipboard.paste": ("paste", [], "Paste from clipboard"),
        "notify.send": ("send", ["title", "message"], "Send notification"),
        "keychain.retrieve": ("retrieve", ["service", "account"], "Get credential"),
        "keychain.store": ("store", ["service", "account", "secret"], "Store credential"),
        "keychain.delete": ("delete", ["service", "account"], "Delete credential"),
        "keychain.list": ("list_services", [], "List stored services"),
        "scheduler.add": ("add_task", ["name", "command", "schedule"], "Schedule a task"),
        "scheduler.list": ("list_tasks", [], "List scheduled tasks"),
        "scheduler.remove": ("remove_task", ["name"], "Remove schedule task"),
        "browser.read": ("get_page_text", [], "Read current browser page text"),
        "browser.fill": ("fill_field", ["selector", "value"], "Fill a form field"),
        "browser.click": ("click_element", ["selector"], "Click an element"),
        "browser.js": ("execute_js", ["script"], "Run JS in browser"),
        "nmap.scan": ("scan", ["target"], "Nmap TCP scan (default top 1000 ports)"),
        "nmap.service_version": ("service_version", ["target"], "Nmap -sV service/version detection"),
        "nmap.discover": ("discover", ["cidr"], "Nmap host discovery on a CIDR"),
        "nmap.script": ("script", ["target", "script"], "Nmap NSE script run (e.g. vuln, default)"),
        "pentest.kernel_posture": ("kernel_posture", [], "Local kernel/sysctl firewall posture"),
        "pentest.firewall_analyze": ("firewall_analyze", [], "Graph-based perimeter exposure"),
        "pentest.probe": ("probe", ["target"], "Async TCP probe engine"),
        "pentest.posture": ("posture", [], "Combined kernel + graph firewall posture"),
        "network.scope": ("scope", [], "Discover local gateway, CIDR, and priority targets"),
        "grinder.grind_host": ("grind_host", ["target"], "Autonomous deep scan of one host into the asset graph"),
        "grinder.grind_subnet": ("grind_subnet", ["cidr"], "Autonomous scan of a whole subnet into the graph (scan=common|subset|sweep)"),
        "grinder.grind_sector": ("grind_sector", [], "Scan every in-scope host known to the asset graph"),
        "graph.schema": ("schema", [], "Asset graph schema reference (tables + columns)"),
        "graph.tables": ("tables", [], "List asset graph tables"),
        "graph.counts": ("counts", [], "Row counts per asset graph table"),
        "graph.query": ("query", ["sql"], "Run a read-only SELECT/WITH query over the asset graph"),
        "web.search": ("search", ["query"], "General web search (DuckDuckGo)"),
        "web.cves": ("cves", ["service"], "Look up CVEs for a service/banner (NVD)"),
        "web.exploits": ("exploits", ["service"], "Search Exploit-DB for a service/banner"),
        "web.research": ("research", ["ip", "port", "service"], "Full service intel: CVEs + exploits + web hits"),
        "web.exploit_surface": (
            "exploit_surface", ["ip", "port", "service"],
            "CVE + Exploit-DB intel with attack score and recommended next tools (research only, no payloads)",
        ),
    }

    def __init__(self, budget: Optional[SignalBudget] = None) -> None:
        self._budget = budget or SignalBudget()
        self._history: list[ToolResult] = []

    def get_capabilities(self) -> list[dict]:
        """Return available tools for the model's system prompt."""
        return [
            {
                "tool": tool_op,
                "description": desc,
            }
            for tool_op, (_, _, desc) in self.CAPABILITIES.items()
        ]

    def get_capabilities_prompt(self) -> str:
        """Generate a capabilities section for the model's system prompt."""
        lines = ["Available tools:"]
        for tool_op, (_, params, desc) in sorted(self.CAPABILITIES.items()):
            tool, op = tool_op.split(".", 1)
            params_str = ", ".join(params) if params else "none"
            lines.append(f"  {tool}.{op}({params_str}) — {desc}")
        return "\n".join(lines)

    def execute(self, tool: str, operation: str, params: Optional[dict] = None, session_id: str = "") -> ToolResult:
        """Execute a tool operation on behalf of the model.

        Returns a ToolResult that can be formatted into the model's context.
        """
        import time
        start = time.monotonic()

        tool_op = f"{tool}.{operation}"
        params = params or {}

        # 1. Validate capability exists
        if tool_op not in self.CAPABILITIES:
            return ToolResult(
                tool=tool, operation=operation,
                status=ToolResultStatus.ERROR,
                error=f"Unknown capability: {tool_op}. Available: {list(self.CAPABILITIES.keys())[:10]}...",
                duration_ms=0,
            )

        method_name, param_keys, _ = self.CAPABILITIES[tool_op]

        # 2. Validate required params
        missing = [k for k in param_keys if k not in params]
        if missing:
            return ToolResult(
                tool=tool, operation=operation,
                status=ToolResultStatus.ERROR,
                error=f"Missing required params: {missing}",
                duration_ms=0,
            )

        # 3. Policy check (via registry)
        registry = get_registry()
        context = {"path": params.get("path", ""), "command": params.get("command", ""), "source": tool, "action": operation}
        if not registry.check_policy(tool, operation, context):
            elapsed = (time.monotonic() - start) * 1000
            return ToolResult(
                tool=tool, operation=operation,
                status=ToolResultStatus.POLICY_DENIED,
                error=f"Policy denied: {tool}.{operation}",
                duration_ms=elapsed,
            )

        # 4. Budget check
        forecast = self._budget.forecast_for(tool, operation, path=context.get("path", ""), command=context.get("command", ""))
        allowed, remaining = self._budget.consume(forecast)
        if not allowed:
            elapsed = (time.monotonic() - start) * 1000
            return ToolResult(
                tool=tool, operation=operation,
                status=ToolResultStatus.BUDGET_EXHAUSTED,
                error=f"Budget exhausted: need {forecast.signal_score:.0f}, have {remaining:.0f}",
                signal_score=forecast.signal_score,
                duration_ms=elapsed,
            )

        # 5. Execute the tool
        try:
            result = self._invoke_tool(tool, method_name, params)
            elapsed = (time.monotonic() - start) * 1000

            tool_result = ToolResult(
                tool=tool,
                operation=operation,
                status=ToolResultStatus.OK,
                result=result,
                signal_score=forecast.signal_score,
                duration_ms=elapsed,
            )
        except PermissionError as e:
            elapsed = (time.monotonic() - start) * 1000
            return ToolResult(
                tool=tool, operation=operation,
                status=ToolResultStatus.DENIED,
                error=str(e),
                signal_score=forecast.signal_score,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return ToolResult(
                tool=tool, operation=operation,
                status=ToolResultStatus.ERROR,
                error=str(e),
                signal_score=forecast.signal_score,
                duration_ms=elapsed,
            )

        self._history.append(tool_result)
        logger.info(
            "Tool executed: %s.%s → %s (%.0fms, signal=%.0f)",
            tool, operation, tool_result.status.value, elapsed, forecast.signal_score,
        )
        return tool_result

    def _invoke_tool(self, tool: str, method_name: str, params: dict) -> Any:
        """Dispatch to the correct tool instance and method."""
        registry = get_registry()

        try:
            instance = registry.get(tool)
        except RuntimeError:
            raise PermissionError(f"Tool '{tool}' is not registered or is disabled")

        method = getattr(instance, method_name, None)
        if method is None:
            raise ValueError(f"Method '{method_name}' not found on tool '{tool}'")

        # Map param names to method signature positions
        return method(**{k: v for k, v in params.items() if k not in ("tool", "operation")})

    def get_history(self, limit: int = 50) -> list[dict]:
        return [
            {
                "tool": r.tool,
                "operation": r.operation,
                "status": r.status.value,
                "signal_score": r.signal_score,
                "duration_ms": r.duration_ms,
            }
            for r in self._history[-limit:]
        ]

    def get_budget_state(self) -> dict:
        return self._budget.get_state()


# Merge the arsenal capabilities (installed-tool detection + heavy-hitter weapon
# wrappers) into the capability map so both the agent loop and the MCP server
# advertise and dispatch them. Kept out of the class literal to keep the arsenal
# an optional, self-contained layer.
try:
    from app.arsenal.weapons import ARSENAL_CAPABILITIES
    ToolExecutor.CAPABILITIES.update(ARSENAL_CAPABILITIES)
except Exception as _exc:  # noqa: BLE001 — arsenal is optional
    logger.warning("Arsenal capabilities not loaded: %s", _exc)


# ── Rich JSON schemas for MCP (optional/typed params) ───────────────────────
# The (method, required_params, desc) tuples above only express required string
# params. CAPABILITY_SCHEMAS carries the fuller JSON-Schema for tools that have
# optional or non-string params; app/mcp/server.py emits it in list_tools().
# Tools without an entry fall back to all-required-strings. Keyed tool.operation.
_STR = {"type": "string"}


def _schema(properties: dict, required: list) -> dict:
    return {"properties": properties, "required": required}


BASE_CAPABILITY_SCHEMAS: dict[str, dict] = {
    "filesystem.edit": _schema(
        {"path": {**_STR, "description": "File to edit"},
         "old_string": {**_STR, "description": "Exact text to replace"},
         "new_string": {**_STR, "description": "Replacement text"},
         "replace_all": {"type": "boolean", "description": "Replace every occurrence (default false)"}},
        ["path", "old_string", "new_string"]),
    "filesystem.read_range": _schema(
        {"path": _STR,
         "start_line": {"type": "integer", "description": "1-based start line"},
         "end_line": {"type": "integer", "description": "1-based end line (inclusive)"}},
        ["path", "start_line", "end_line"]),
    "process.kill": _schema(
        {"pid": {"type": "integer", "description": "Process id to terminate"}}, ["pid"]),
    "nmap.scan": _schema(
        {"target": {**_STR, "description": "IP, host, or CIDR"},
         "ports": {**_STR, "description": "Port spec '22,80' or '1-1000' (default top 1000)"}},
        ["target"]),
    "nmap.service_version": _schema(
        {"target": _STR, "ports": {**_STR, "description": "Port spec (default 1-1000)"}}, ["target"]),
    "nmap.script": _schema(
        {"target": _STR,
         "script": {**_STR, "description": "NSE script name, e.g. 'vuln' or 'default'"},
         "ports": {**_STR, "description": "Port spec (default 1-1000)"}},
        ["target", "script"]),
    "grinder.grind_host": _schema(
        {"target": {**_STR, "description": "Single host IP to deep-scan"}}, ["target"]),
    "grinder.grind_subnet": _schema(
        {"cidr": {**_STR, "description": "Subnet CIDR, e.g. 10.0.0.0/24"},
         "scan": {"type": "string", "enum": ["common", "subset", "sweep"],
                  "description": "Port-set breadth (default common)"}},
        ["cidr"]),
    "grinder.grind_sector": _schema(
        {"cidr": {**_STR, "description": "Optional subnet; omit to scan every in-scope host"}}, []),
    "graph.query": _schema(
        {"sql": {**_STR, "description": "Read-only SELECT/WITH query over the asset graph"}}, ["sql"]),
    "web.exploit_surface": _schema(
        {"ip": {**_STR, "description": "Target host IP (authorized scope only)"},
         "port": {"type": "integer", "description": "Service port"},
         "service": {**_STR, "description": "Service name, e.g. http, ssh"},
         "banner": {**_STR, "description": "Optional banner string"}},
        ["ip", "port", "service"]),
}

CAPABILITY_SCHEMAS: dict[str, dict] = dict(BASE_CAPABILITY_SCHEMAS)
try:
    from app.arsenal.weapons import ARSENAL_SCHEMAS
    CAPABILITY_SCHEMAS.update(ARSENAL_SCHEMAS)
except Exception as _exc:  # noqa: BLE001 — arsenal is optional
    logger.warning("Arsenal schemas not loaded: %s", _exc)
