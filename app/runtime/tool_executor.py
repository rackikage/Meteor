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
        "filesystem.write": ("write_file", ["path", "content"], "Write to a file"),
        "filesystem.list": ("list_dir", ["path"], "List directory contents"),
        "filesystem.stat": ("stat", ["path"], "Get file metadata"),
        "filesystem.grep": ("grep", ["pattern", "path"], "Search file contents"),
        "filesystem.glob": ("glob", ["pattern"], "Find files by pattern"),
        "filesystem.mkdir": ("mkdir", ["path"], "Create directory"),
        "filesystem.remove": ("remove", ["path"], "Delete a file"),
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
