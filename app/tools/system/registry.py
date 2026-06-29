"""Central registry for all system tools — policy-gated access control."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ToolAccess(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    MANAGE = "manage"


@dataclass
class ToolCapability:
    name: str
    access_level: ToolAccess
    description: str
    requires_approval: bool = False
    requires_root: bool = False


@dataclass
class SystemTool:
    name: str
    version: str
    description: str
    capabilities: list = None
    enabled: bool = True
    policy_checked: int = 0

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


class SystemToolRegistry:
    def __init__(self, storage: Optional[Any] = None, budget: Optional[Any] = None) -> None:
        self._tools: dict[str, SystemTool] = {}
        self._instances: dict[str, Any] = {}
        self._audit_log: list[dict] = []
        self._approval_callbacks: list[Callable[[str, str, dict], bool]] = []
        self._auto_approve_patterns: list[str] = []
        self._storage = storage
        self._budget = budget

    def register(self, name: str, instance: Any, description: str, version: str = "1.0.0", capabilities: Optional[list] = None) -> SystemTool:
        from dataclasses import dataclass, field
        tool = SystemTool(name=name, version=version, description=description, capabilities=capabilities or [])
        self._tools[name] = tool
        self._instances[name] = instance
        logger.info("System tool registered: %s v%s", name, version)
        return tool

    def get(self, name: str) -> Any:
        tool = self._tools.get(name)
        if not tool or not tool.enabled:
            raise RuntimeError(f"System tool '{name}' is not available or disabled")
        return self._instances[name]

    def disable(self, name: str) -> bool:
        if name in self._tools:
            self._tools[name].enabled = False
            return True
        return False

    def enable(self, name: str) -> bool:
        if name in self._tools:
            self._tools[name].enabled = True
            return True
        return False

    def list_tools(self) -> list[dict]:
        return [{"name": t.name, "version": t.version, "description": t.description, "enabled": t.enabled} for t in self._tools.values()]

    def check_policy(self, tool_name: str, operation: str, context: dict) -> bool:
        self._tools[tool_name].policy_checked += 1
        path = context.get("path", "") or context.get("command", "") or ""
        allowed = True
        denied_reason = ""

        # SQL policy gate
        if self._storage:
            try:
                rows = self._storage.execute(
                    """
                    SELECT action_gate FROM system_policies
                    WHERE (tool = ? OR tool = '*')
                      AND (operation = ? OR operation = '*')
                      AND (path_pattern IS NULL OR ? GLOB path_pattern)
                    ORDER BY priority DESC
                    LIMIT 1
                    """,
                    (tool_name, operation, path),
                    store="audit",
                )
                if rows:
                    allowed = rows[0]["action_gate"] == "allow"
                    if not allowed:
                        denied_reason = f"SQL policy deny: {tool_name}.{operation} on {path}"
            except Exception:
                allowed = True

        # Signal budget gate
        if allowed and self._budget:
            forecast = self._budget.forecast_for(tool_name, operation, **context)
            budget_allowed, remaining = self._budget.consume(forecast)
            if not budget_allowed:
                allowed = False
                denied_reason = f"Signal budget exhausted: need {forecast.signal_score:.0f}, have {remaining:.0f}"

        self._audit_log.append({
            "tool": tool_name, "operation": operation, "context": context,
            "path": path, "allowed": allowed,
            "denied_reason": denied_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return allowed

    def require_approval(self, tool_name: str, operation: str, details: dict) -> bool:
        for pattern in self._auto_approve_patterns:
            if pattern in f"{tool_name}:{operation}":
                return True
        for cb in self._approval_callbacks:
            if not cb(tool_name, operation, details):
                return False
        return True

    def on_approval_request(self, callback: Callable[[str, str, dict], bool]) -> None:
        self._approval_callbacks.append(callback)

    def auto_approve(self, pattern: str) -> None:
        self._auto_approve_patterns.append(pattern)

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        return self._audit_log[-limit:]


_registry: Optional[SystemToolRegistry] = None


def get_registry() -> SystemToolRegistry:
    global _registry
    if _registry is None:
        _registry = SystemToolRegistry()
    return _registry
