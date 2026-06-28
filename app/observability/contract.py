from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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


class ObservabilityAdapter(ABC):
    """Abstract interface. All observability backends must implement this contract."""

    @abstractmethod
    def log(self, level: LogLevel, message: str, metadata: Optional[dict] = None) -> None:
        ...

    @abstractmethod
    def audit(self, entry: AuditEntry) -> None:
        ...

    @abstractmethod
    def health(self) -> HealthCheckResult:
        ...
