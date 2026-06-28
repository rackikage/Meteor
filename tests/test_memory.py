"""Tests for the memory adapter layer.

Verifies: SQLite memory adapter, 4 memory types, read/write operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import MeteorConfig
from app.memory.contract import MemoryAdapter, MemoryEntry, MemoryType
from app.memory.sqlite_adapter import SQLiteMemoryAdapter, build_sqlite_memory_adapter
from app.storage.sqlite_adapter import build_sqlite_adapter


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


@pytest.fixture
def memory_adapter(tmp_path):
    """Create a temporary memory adapter for testing."""
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    storage = build_sqlite_adapter(config.storage, tmp_path)
    adapter = build_sqlite_memory_adapter(storage)
    yield adapter
    storage.close()


def test_memory_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        MemoryAdapter()


def test_memory_type_values() -> None:
    assert MemoryType.CONVERSATION.value == "conversation"
    assert MemoryType.EPISODIC.value == "episodic"
    assert MemoryType.PROJECT.value == "project"
    assert MemoryType.CORRECTION.value == "correction"


def test_memory_entry_defaults() -> None:
    entry = MemoryEntry(
        memory_type=MemoryType.CONVERSATION,
        content="test",
        session_id="session-1",
        timestamp="2024-01-01T00:00:00",
    )
    assert entry.metadata == {}


def test_write_and_read_conversation(memory_adapter: SQLiteMemoryAdapter) -> None:
    entry = MemoryEntry(
        memory_type=MemoryType.CONVERSATION,
        content="Hello, how are you?",
        session_id="session-1",
        timestamp="2024-01-01T00:00:00",
        metadata={"role": "user"},
    )
    memory_adapter.write(entry)

    entries = memory_adapter.read("session-1", MemoryType.CONVERSATION)
    assert len(entries) == 1
    assert entries[0].content == "Hello, how are you?"
    assert entries[0].metadata["role"] == "user"


def test_write_and_read_episodic(memory_adapter: SQLiteMemoryAdapter) -> None:
    entry = MemoryEntry(
        memory_type=MemoryType.EPISODIC,
        content="User completed onboarding",
        session_id="session-1",
        timestamp="2024-01-01T00:00:00",
        metadata={"event_type": "onboarding_complete"},
    )
    memory_adapter.write(entry)

    entries = memory_adapter.read("session-1", MemoryType.EPISODIC)
    assert len(entries) == 1
    assert entries[0].content == "User completed onboarding"
    assert entries[0].metadata["event_type"] == "onboarding_complete"


def test_write_and_read_project(memory_adapter: SQLiteMemoryAdapter) -> None:
    entry = MemoryEntry(
        memory_type=MemoryType.PROJECT,
        content='{"theme": "dark", "language": "en"}',
        session_id="session-1",
        timestamp="2024-01-01T00:00:00",
        metadata={"project_name": "my-app", "key": "settings"},
    )
    memory_adapter.write(entry)

    entries = memory_adapter.read("session-1", MemoryType.PROJECT)
    assert len(entries) == 1
    assert entries[0].content == '{"theme": "dark", "language": "en"}'
    assert entries[0].metadata["project_name"] == "my-app"
    assert entries[0].metadata["key"] == "settings"


def test_write_and_read_correction(memory_adapter: SQLiteMemoryAdapter) -> None:
    entry = MemoryEntry(
        memory_type=MemoryType.CORRECTION,
        content="Use 'Hello' instead of 'Hi'",
        session_id="session-1",
        timestamp="2024-01-01T00:00:00",
        metadata={"original": "Hi there", "reason": "More formal tone"},
    )
    memory_adapter.write(entry)

    entries = memory_adapter.read("session-1", MemoryType.CORRECTION)
    assert len(entries) == 1
    assert entries[0].content == "Use 'Hello' instead of 'Hi'"
    assert entries[0].metadata["original"] == "Hi there"
    assert entries[0].metadata["reason"] == "More formal tone"


def test_multiple_conversation_entries(memory_adapter: SQLiteMemoryAdapter) -> None:
    for i in range(3):
        entry = MemoryEntry(
            memory_type=MemoryType.CONVERSATION,
            content=f"Message {i}",
            session_id="session-1",
            timestamp=f"2024-01-01T00:0{i}:00",
            metadata={"role": "user" if i % 2 == 0 else "assistant"},
        )
        memory_adapter.write(entry)

    entries = memory_adapter.read("session-1", MemoryType.CONVERSATION)
    assert len(entries) == 3
    assert entries[0].content == "Message 0"
    assert entries[2].content == "Message 2"


def test_read_empty_session(memory_adapter: SQLiteMemoryAdapter) -> None:
    entries = memory_adapter.read("nonexistent-session", MemoryType.CONVERSATION)
    assert entries == []


def test_memory_health(memory_adapter: SQLiteMemoryAdapter) -> None:
    health = memory_adapter.health()
    assert health["healthy"] is True
    assert health["backend"] == "sqlite"
    assert "conversation" in health["memory_types"]
    assert "episodic" in health["memory_types"]
    assert "project" in health["memory_types"]
    assert "correction" in health["memory_types"]
