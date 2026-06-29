"""Signal Budget — rate-limit tool operations based on telemetry footprint.

Treats host-level OS telemetry as an environmental constraint, not a detection
vector to evade. Every operation consumes signal budget units. When the budget
is exhausted, operations are denied until the budget replenishes over time.

This is NOT evasion. It's operational discipline — the agent accepts that
every operation emits forensic artifacts and throttles itself to stay within
a configurable noise threshold.

Budget model:
- Total budget: 1000 units (configurable)
- Replenish rate: N units per minute (configurable)
- Each operation's cost = signal_score from SignalForecaster
- Low-noise ops (score < 10) don't consume budget
- Burst mode: temporary budget expansion for time-boxed intense scans
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.tools.system.signal_forecaster import (
    AuditEventType,
    SignalForecast,
    SignalForecaster,
)

logger = logging.getLogger(__name__)


@dataclass
class BudgetState:
    current: float
    maximum: float
    replenish_per_minute: float
    last_replenished: float
    total_consumed: float = 0.0
    operations_denied: int = 0
    operations_allowed: int = 0
    burst_active: bool = False
    burst_expires_at: float = 0.0


@dataclass
class ForecastedOperation:
    """An operation that has been forecasted and budget-checked."""
    tool: str
    operation: str
    forecast: SignalForecast
    budget_cost: float
    budget_remaining: float
    allowed: bool
    denied_reason: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "operation": self.operation,
            "events": [e.value for e in self.forecast.events],
            "signal_score": self.forecast.signal_score,
            "budget_cost": self.budget_cost,
            "budget_remaining": self.budget_remaining,
            "allowed": self.allowed,
            "denied_reason": self.denied_reason,
            "timestamp": self.timestamp,
            "is_loud": self.forecast.is_loud,
            "forensic_artifacts": self.forecast.forensic_artifacts,
        }


class SignalBudget:
    """Rate-limit tool operations based on their telemetry footprint.

    The budget refills over time. Quiet operations cost little. Loud
    operations (persistence, accessibility, CDP) cost a lot and may
    be denied if the budget is exhausted.

    Usage:
        budget = SignalBudget()
        forecast = forecaster.forecast_shell("nmap -sV 10.0.0.0/24")
        allowed, remaining = budget.consume(forecast)
    """

    def __init__(
        self,
        max_budget: float = 1000.0,
        replenish_per_minute: float = 50.0,
    ) -> None:
        self.state = BudgetState(
            current=max_budget,
            maximum=max_budget,
            replenish_per_minute=replenish_per_minute,
            last_replenished=time.monotonic(),
        )
        self._forecaster = SignalForecaster()
        self._history: list[ForecastedOperation] = []

    def _replenish(self) -> None:
        """Refill budget based on elapsed time since last replenish."""
        now = time.monotonic()
        elapsed = now - self.state.last_replenished
        minutes = elapsed / 60.0
        refill = minutes * self.state.replenish_per_minute

        if refill > 0:
            self.state.current = min(
                self.state.maximum,
                self.state.current + refill,
            )
            self.state.last_replenished = now

        if self.state.burst_active and now > self.state.burst_expires_at:
            self.state.burst_active = False
            self.state.maximum = 1000.0
            self.state.current = min(self.state.current, self.state.maximum)
            logger.info("Burst mode expired — budget reset to %.0f", self.state.maximum)

    def consume(self, forecast: SignalForecast) -> tuple[bool, float]:
        """Attempt to consume budget for a forecasted operation.

        Returns (allowed, remaining_budget).
        """
        self._replenish()

        cost = forecast.signal_score

        # Silent operations don't count against budget
        if forecast.is_silent:
            self._record(forecast, cost, True)
            return True, self.state.current

        if self.state.current >= cost:
            self.state.current -= cost
            self.state.total_consumed += cost
            self.state.operations_allowed += 1
            self._record(forecast, cost, True)
            return True, self.state.current

        self.state.operations_denied += 1
        reason = (
            f"Budget exhausted: need {cost:.0f}, have {self.state.current:.0f}. "
            f"Refills at {self.state.replenish_per_minute:.0f}/min"
        )
        self._record(forecast, cost, False, reason)
        return False, self.state.current

    def enable_burst(self, extra_budget: float = 500.0, duration_s: float = 300.0) -> None:
        """Enable burst mode — temporary budget expansion for intense scanning.

        Use for time-boxed operations like subnet scanning or credential spraying.
        Burst auto-expires after `duration_s` seconds.
        """
        self.state.maximum += extra_budget
        self.state.current += extra_budget
        self.state.burst_active = True
        self.state.burst_expires_at = time.monotonic() + duration_s
        logger.info(
            "Burst mode enabled: +%.0f budget for %.0fs (now %.0f)",
            extra_budget, duration_s, self.state.current,
        )

    def _record(
        self,
        forecast: SignalForecast,
        cost: float,
        allowed: bool,
        denied_reason: str = "",
    ) -> None:
        entry = ForecastedOperation(
            tool=forecast.operation.split(".")[0],
            operation=forecast.operation,
            forecast=forecast,
            budget_cost=cost,
            budget_remaining=self.state.current,
            allowed=allowed,
            denied_reason=denied_reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._history.append(entry)
        if len(self._history) > 500:
            self._history.pop(0)

    def get_history(self, limit: int = 50) -> list[dict]:
        return [h.to_dict() for h in self._history[-limit:]]

    def get_state(self) -> dict:
        self._replenish()
        return {
            "current_budget": self.state.current,
            "maximum_budget": self.state.maximum,
            "replenish_per_minute": self.state.replenish_per_minute,
            "total_consumed": self.state.total_consumed,
            "operations_allowed": self.state.operations_allowed,
            "operations_denied": self.state.operations_denied,
            "burst_active": self.state.burst_active,
        }

    def forecast_for(self, tool: str, operation: str, **context) -> SignalForecast:
        """Generate a forecast for a specific tool operation."""
        kw = context.get("command", "")
        path = context.get("path", "")
        pid = context.get("pid", 0)
        host = context.get("host", "")
        port = context.get("port", 0)

        if tool == "filesystem":
            return self._forecaster.forecast_filesystem(operation, path)
        elif tool == "shell":
            return self._forecaster.forecast_shell(kw or operation)
        elif tool == "process":
            return self._forecaster.forecast_process(operation, pid)
        elif tool == "network":
            return self._forecaster.forecast_network(operation, host, port)
        elif tool == "keychain":
            return self._forecaster.forecast_keychain(operation)
        elif tool == "browser":
            return self._forecaster.forecast_browser(operation)
        elif tool == "ui":
            return self._forecaster.forecast_ui(operation)
        elif tool == "ipc":
            return self._forecaster.forecast_ipc(operation)

        return SignalForecast(operation=f"{tool}.{operation}", signal_score=10.0)
