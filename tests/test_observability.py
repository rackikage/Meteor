"""Tests for the observability adapter layer.

Verifies: SQLite observability adapter, structured logging, audit trails, health checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import MeteorConfig
from app.observability.contract import (
    AuditEntry,
    HealthCheckResult,
    LogLevel,
    ObservabilityAdapter,
)
from app.observability.sqlite_adapter import (
    SQLiteObservabilityAdapter,
    build_sqlite_observability_adapter,
)
from app.storage.sqlite_adapter import build_sqlite_adapter


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


@pytest.fixture
def observability_adapter(tmp_path):
    """Create a temporary observability adapter for testing."""
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    storage = build_sqlite_adapter(config.storage, tmp_path)
    adapter = build_sqlite_observability_adapter(storage, log_level="DEBUG", audit_enabled=True)
    yield adapter
    storage.close()


def test_observability_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        ObservabilityAdapter()


def test_log_level_values() -> None:
    assert LogLevel.DEBUG.value == "debug"
    assert LogLevel.INFO.value == "info"
    assert LogLevel.WARNING.value == "warning"
    assert LogLevel.ERROR.value == "error"


def test_audit_entry_defaults() -> None:
    entry = AuditEntry(
        event="test",
        layer="policy",
        subject="runtime",
        action="invoke",
        decision="allow",
        timestamp="2024-01-01T00:00:00",
    )
    assert entry.metadata == {}


def test_health_check_result_defaults() -> None:
    result = HealthCheckResult(
        component="test",
        healthy=True,
        detail="All good",
    )
    assert result.metadata == {}


def test_audit_entry_written(observability_adapter: SQLiteObservabilityAdapter) -> None:
    entry = AuditEntry(
        event="policy_check",
        layer="policy",
        subject="runtime",
        action="invoke",
        decision="allow",
        timestamp="2024-01-01T00:00:00",
        metadata={"reason": "test"},
    )
    observability_adapter.audit(entry)

    entries = observability_adapter.get_audit_log(limit=10)
    assert len(entries) == 1
    assert entries[0].event == "policy_check"
    assert entries[0].decision == "allow"


def test_audit_disabled(tmp_path) -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    storage = build_sqlite_adapter(config.storage, tmp_path)
    adapter = build_sqlite_observability_adapter(storage, audit_enabled=False)

    entry = AuditEntry(
        event="test",
        layer="test",
        subject="test",
        action="test",
        decision="test",
        timestamp="2024-01-01T00:00:00",
    )
    adapter.audit(entry)

    entries = adapter.get_audit_log(limit=10)
    assert len(entries) == 0

    storage.close()


def test_register_health_check(observability_adapter: SQLiteObservabilityAdapter) -> None:
    def mock_health():
        return {"healthy": True, "detail": "Mock component OK"}

    observability_adapter.register_health_check("mock_component", mock_health)

    health = observability_adapter.health()
    assert "mock_component" in health.metadata["components"]
    assert health.metadata["components"]["mock_component"]["healthy"] is True


def test_health_check_aggregation(observability_adapter: SQLiteObservabilityAdapter) -> None:
    def healthy_component():
        return {"healthy": True}

    def unhealthy_component():
        return {"healthy": False, "error": "Something broke"}

    observability_adapter.register_health_check("healthy", healthy_component)
    observability_adapter.register_health_check("unhealthy", unhealthy_component)

    health = observability_adapter.health()
    assert health.healthy is False
    assert "One or more components unhealthy" in health.detail


def test_get_audit_log_with_filter(observability_adapter: SQLiteObservabilityAdapter) -> None:
    for event in ["policy_check", "tool_call", "policy_check"]:
        entry = AuditEntry(
            event=event,
            layer="test",
            subject="test",
            action="test",
            decision="allow",
            timestamp="2024-01-01T00:00:00",
        )
        observability_adapter.audit(entry)

    entries = observability_adapter.get_audit_log(limit=10, event="policy_check")
    assert len(entries) == 2
    assert all(e.event == "policy_check" for e in entries)


def test_observability_health(observability_adapter: SQLiteObservabilityAdapter) -> None:
    health = observability_adapter.health()
    assert isinstance(health, HealthCheckResult)
    assert health.component == "runtime"
    assert "storage" in health.metadata
    assert "audit_enabled" in health.metadata
