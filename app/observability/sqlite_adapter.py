"""SQLite observability adapter — structured logging, audit trails, health checks.

Meteor Doctrine #9: Every capability must be smoke-tested. This adapter provides
the observability infrastructure that makes testing and monitoring possible.

Meteor Doctrine #10: Every component must be replaceable. The ObservabilityAdapter
contract is stable; this SQLite implementation can be swapped for OpenTelemetry,
Datadog, or any other backend without changing calling code.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from app.observability.contract import (
    AuditEntry,
    HealthCheckResult,
    LogLevel,
    ObservabilityAdapter,
)
from app.storage.sqlite_adapter import SQLiteAdapter

logger = logging.getLogger(__name__)


class SQLiteObservabilityAdapter(ObservabilityAdapter):
    """SQLite-backed observability with structured logging and audit trails.

    - Logging: Structured JSON logs to stdout (configurable level)
    - Audit: Persistent audit trail in SQLite (every policy decision, tool call, etc.)
    - Health: Aggregated health checks across all runtime components
    """

    def __init__(
        self,
        storage: SQLiteAdapter,
        log_level: str = "INFO",
        audit_enabled: bool = True,
    ) -> None:
        self.storage = storage
        self.audit_enabled = audit_enabled
        self._log_level = getattr(logging, log_level.upper(), logging.INFO)
        self._component_health: dict[str, callable] = {}

        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure structured JSON logging."""
        root_logger = logging.getLogger()
        root_logger.setLevel(self._log_level)

        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self._log_level)
        console_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(console_handler)

    def log(self, level: LogLevel, message: str, metadata: Optional[dict] = None) -> None:
        """Log a structured message."""
        log_level = getattr(logging, level.value.upper(), logging.INFO)
        extra = metadata or {}

        logger.log(log_level, message, extra=extra)

    def audit(self, entry: AuditEntry) -> None:
        """Record an audit entry to the audit store."""
        if not self.audit_enabled:
            return

        self.storage.execute(
            """
            INSERT INTO audit_log (event, layer, subject, action, decision, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.event,
                entry.layer,
                entry.subject,
                entry.action,
                entry.decision,
                entry.timestamp,
                json.dumps(entry.metadata),
            ),
            store="audit",
        )

        logger.debug(
            "Audit: event=%s, layer=%s, subject=%s, action=%s, decision=%s",
            entry.event,
            entry.layer,
            entry.subject,
            entry.action,
            entry.decision,
        )

    def register_health_check(self, component: str, health_fn: callable) -> None:
        """Register a health check function for a component."""
        self._component_health[component] = health_fn

    def health(self) -> HealthCheckResult:
        """Run all registered health checks and return aggregated result."""
        component_results = {}
        all_healthy = True

        for component, health_fn in self._component_health.items():
            try:
                result = health_fn()
                component_results[component] = result
                if not result.get("healthy", False):
                    all_healthy = False
            except Exception as e:
                component_results[component] = {"healthy": False, "error": str(e)}
                all_healthy = False

        storage_health = self.storage.health()
        if not storage_health["healthy"]:
            all_healthy = False

        detail = "All systems operational" if all_healthy else "One or more components unhealthy"

        return HealthCheckResult(
            component="runtime",
            healthy=all_healthy,
            detail=detail,
            metadata={
                "components": component_results,
                "storage": storage_health,
                "audit_enabled": self.audit_enabled,
                "log_level": logging.getLevelName(self._log_level),
            },
        )

    def get_audit_log(self, limit: int = 100, event: Optional[str] = None) -> list[AuditEntry]:
        """Retrieve recent audit entries."""
        if event:
            rows = self.storage.execute(
                """
                SELECT event, layer, subject, action, decision, timestamp, metadata
                FROM audit_log
                WHERE event = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (event, limit),
                store="audit",
            )
        else:
            rows = self.storage.execute(
                """
                SELECT event, layer, subject, action, decision, timestamp, metadata
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
                store="audit",
            )

        entries = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            entries.append(
                AuditEntry(
                    event=row["event"],
                    layer=row["layer"],
                    subject=row["subject"],
                    action=row["action"],
                    decision=row["decision"],
                    timestamp=row["timestamp"],
                    metadata=metadata,
                )
            )

        return entries


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "metadata"):
            log_entry["metadata"] = record.metadata

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def build_sqlite_observability_adapter(
    storage: SQLiteAdapter,
    log_level: str = "INFO",
    audit_enabled: bool = True,
) -> SQLiteObservabilityAdapter:
    """Factory function to build a SQLiteObservabilityAdapter."""
    return SQLiteObservabilityAdapter(storage, log_level, audit_enabled)
