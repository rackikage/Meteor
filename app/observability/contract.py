from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class AuditEntry:
    event: str
    layer: str
    subject: str
    action: str
    decision: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    component: str
    healthy: bool
    detail: str
    metadata: dict = field(default_factory=dict)


class ObservabilityAdapter:
    """Abstract interface. All observability backends must implement this contract."""

    def log(self, level: LogLevel, message: str, metadata: dict = None) -> None:
        raise NotImplementedError

    def audit(self, entry: AuditEntry) -> None:
        raise NotImplementedError

    def health(self) -> HealthCheckResult:
        raise NotImplementedError
