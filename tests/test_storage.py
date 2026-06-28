"""Tests for the storage adapter layer.

Verifies: SQLite adapter, migrations, execute(), health checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import MeteorConfig
from app.storage.contract import StorageAdapter
from app.storage.sqlite_adapter import SQLiteAdapter, build_sqlite_adapter


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


@pytest.fixture
def storage_adapter(tmp_path):
    """Create a temporary SQLite adapter for testing."""
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    adapter = build_sqlite_adapter(config.storage, tmp_path)
    yield adapter
    adapter.close()


def test_storage_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        StorageAdapter()


def test_sqlite_adapter_creates_databases(storage_adapter: SQLiteAdapter) -> None:
    health = storage_adapter.health()
    assert health["healthy"] is True
    assert "memory" in health["stores"]
    assert "audit" in health["stores"]
    assert "index_meta" in health["stores"]


def test_sqlite_adapter_runs_migrations(storage_adapter: SQLiteAdapter) -> None:
    migrations = storage_adapter.migrate("memory")
    assert len(migrations) > 0
    assert migrations[0].version == 1
    assert "create_memory_tables" in migrations[0].name


def test_sqlite_adapter_execute_insert_and_select(storage_adapter: SQLiteAdapter) -> None:
    storage_adapter.execute(
        "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        ("test-1", "session-1", "user", "hello", "2024-01-01T00:00:00"),
        store="memory",
    )

    rows = storage_adapter.execute(
        "SELECT * FROM conversations WHERE session_id = ?",
        ("session-1",),
        store="memory",
    )

    assert len(rows) == 1
    assert rows[0]["id"] == "test-1"
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "hello"


def test_sqlite_adapter_execute_unknown_store_raises(storage_adapter: SQLiteAdapter) -> None:
    with pytest.raises(ValueError, match="Unknown store"):
        storage_adapter.execute("SELECT 1", store="nonexistent")


def test_sqlite_adapter_health_all_healthy(storage_adapter: SQLiteAdapter) -> None:
    health = storage_adapter.health()
    assert health["healthy"] is True
    for store_name, store_health in health["stores"].items():
        assert store_health["healthy"] is True


def test_sqlite_adapter_migrate_returns_records(storage_adapter: SQLiteAdapter) -> None:
    migrations = storage_adapter.migrate("audit")
    assert len(migrations) > 0
    assert all(m.version > 0 for m in migrations)
    assert all(m.name for m in migrations)
    assert all(m.applied_at for m in migrations)


def test_sqlite_adapter_audit_log_insert(storage_adapter: SQLiteAdapter) -> None:
    storage_adapter.execute(
        "INSERT INTO audit_log (event, layer, subject, action, decision, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        ("policy_check", "policy", "runtime", "invoke", "allow", "2024-01-01T00:00:00"),
        store="audit",
    )

    rows = storage_adapter.execute(
        "SELECT * FROM audit_log WHERE event = ?",
        ("policy_check",),
        store="audit",
    )

    assert len(rows) == 1
    assert rows[0]["decision"] == "allow"


def test_sqlite_adapter_close(storage_adapter: SQLiteAdapter) -> None:
    storage_adapter.close()
    assert len(storage_adapter._connections) == 0
