"""Tests for reactive memory triggers.

Verifies: auto-topic detection, debug episodic creation, correction cross-referencing,
topic counter updates, session stats tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import MeteorConfig
from app.memory.triggers import install_memory_triggers, uninstall_memory_triggers
from app.storage.sqlite_adapter import build_sqlite_adapter


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


@pytest.fixture
def memory_triggers_setup(tmp_path):
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    storage = build_sqlite_adapter(config.storage, tmp_path)
    install_memory_triggers(storage)
    yield storage
    uninstall_memory_triggers(storage)
    storage.close()


class TestAutoTopicDetection:

    def test_debugging_topic_detected(self, memory_triggers_setup):
        storage = memory_triggers_setup
        storage.execute(
            "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            ("c1", "s1", "user", "I have an error in my code", "2024-01-01T00:00:00"),
            store="memory",
        )
        rows = storage.execute(
            "SELECT metadata FROM conversations WHERE id = ?", ("c1",), store="memory"
        )
        metadata = rows[0]["metadata"]
        assert metadata is not None

    def test_programming_topic_detected(self, memory_triggers_setup):
        storage = memory_triggers_setup
        storage.execute(
            "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            ("c2", "s1", "user", "How do I import a Python function?", "2024-01-01T00:00:00"),
            store="memory",
        )
        rows = storage.execute(
            "SELECT metadata FROM conversations WHERE id = ?", ("c2",), store="memory"
        )
        import json
        metadata = json.loads(rows[0]["metadata"])
        assert metadata.get("auto_topic") == "programming"

    def test_search_topic_detected(self, memory_triggers_setup):
        storage = memory_triggers_setup
        storage.execute(
            "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            ("c3", "s1", "user", "Can you find the search results for me?", "2024-01-01T00:00:00"),
            store="memory",
        )
        rows = storage.execute(
            "SELECT metadata FROM conversations WHERE id = ?", ("c3",), store="memory"
        )
        import json
        metadata = json.loads(rows[0]["metadata"])
        assert metadata.get("auto_topic") == "search"

    def test_general_topic_default(self, memory_triggers_setup):
        storage = memory_triggers_setup
        storage.execute(
            "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            ("c4", "s1", "user", "Hello, how are you today?", "2024-01-01T00:00:00"),
            store="memory",
        )
        rows = storage.execute(
            "SELECT metadata FROM conversations WHERE id = ?", ("c4",), store="memory"
        )
        import json
        metadata = json.loads(rows[0]["metadata"])
        assert metadata.get("auto_topic") == "general"


class TestDebugEpisodicCreation:

    def test_debug_creates_episodic(self, memory_triggers_setup):
        storage = memory_triggers_setup
        storage.execute(
            "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            ("c5", "s1", "user", "My app crashed with a segfault error", "2024-01-01T00:00:00"),
            store="memory",
        )
        episodic = storage.execute(
            "SELECT * FROM episodic_memory WHERE session_id = ? AND event_type = ?",
            ("s1", "debugging_session"),
            store="memory",
        )
        assert len(episodic) == 1
        assert "crashed" in episodic[0]["content"].lower()

    def test_non_debug_does_not_create_episodic(self, memory_triggers_setup):
        storage = memory_triggers_setup
        storage.execute(
            "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            ("c6", "s2", "user", "What is the weather like?", "2024-01-01T00:00:00"),
            store="memory",
        )
        episodic = storage.execute(
            "SELECT * FROM episodic_memory WHERE session_id = ? AND event_type = ?",
            ("s2", "debugging_session"),
            store="memory",
        )
        assert len(episodic) == 0


class TestCorrectionCrossReference:

    def test_correction_creates_episodic(self, memory_triggers_setup):
        storage = memory_triggers_setup
        storage.execute(
            "INSERT INTO corrections (id, session_id, original, corrected, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("corr1", "s3", "Hi there!", "Hello there!", "More formal tone", "2024-01-01T00:00:00"),
            store="memory",
        )
        episodic = storage.execute(
            "SELECT * FROM episodic_memory WHERE session_id = ? AND event_type = ?",
            ("s3", "correction_applied"),
            store="memory",
        )
        assert len(episodic) == 1
        assert "Hi there" in episodic[0]["content"]
        assert "Hello there" in episodic[0]["content"]


class TestTopicCounter:

    def test_topic_counter_increments(self, memory_triggers_setup):
        storage = memory_triggers_setup

        for i in range(3):
            storage.execute(
                "INSERT INTO conversations (id, session_id, role, content, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"c_debug_{i}",
                    "s4",
                    "user",
                    f"I found error {i}",
                    "2024-01-01T00:00:00",
                    '{"auto_topic": "debugging"}',
                ),
                store="memory",
            )

        rows = storage.execute(
            "SELECT * FROM project_memory WHERE project_name = ? AND key = ?",
            ("user_profile", "topic_debugging"),
            store="memory",
        )
        assert len(rows) > 0


class TestSessionStats:

    def test_episodic_updates_session_stats(self, memory_triggers_setup):
        storage = memory_triggers_setup
        storage.execute(
            "INSERT INTO episodic_memory (id, session_id, event_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
            ("e1", "s5", "user_login", "User logged in", "2024-01-01T00:00:00"),
            store="memory",
        )
        stats = storage.execute(
            "SELECT * FROM project_memory WHERE project_name = ? AND key = ?",
            ("session_stats", "last_event_type"),
            store="memory",
        )
        assert len(stats) > 0
        assert stats[0]["value"] == "user_login"
