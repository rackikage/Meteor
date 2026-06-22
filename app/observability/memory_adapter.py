from __future__ import annotations

from app.observability.contract import AuditEntry, HealthCheckResult, LogLevel, ObservabilityAdapter


class InMemoryObservabilityAdapter(ObservabilityAdapter):
    """Small local observability adapter for tests and single-process runtime use."""

    def __init__(self) -> None:
        self.logs: list[dict] = []
        self.audits: list[AuditEntry] = []

    def log(self, level: LogLevel, message: str, metadata: dict | None = None) -> None:
        self.logs.append({"level": level.value, "message": message, "metadata": metadata or {}})

    def audit(self, entry: AuditEntry) -> None:
        self.audits.append(entry)

    def health(self) -> HealthCheckResult:
        return HealthCheckResult(
            component="observability",
            healthy=True,
            detail="In-memory observability active.",
            metadata={"logs": len(self.logs), "audits": len(self.audits)},
        )
