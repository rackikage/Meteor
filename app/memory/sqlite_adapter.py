"""SQLite memory adapter — persistent memory with 4 memory types.

Meteor Doctrine #5: Memory is infrastructure. This adapter provides durable
local memory storage for conversation history, episodic events, project state,
and user corrections. All memory stays on the user's machine.

Meteor Doctrine #8: Contracts outlive implementations. The MemoryAdapter
contract is stable; this SQLite implementation can be swapped for Redis,
PostgreSQL, or any other backend without changing calling code.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.memory.contract import MemoryAdapter, MemoryEntry, MemoryType
from app.storage.sqlite_adapter import SQLiteAdapter

logger = logging.getLogger(__name__)


class SQLiteMemoryAdapter(MemoryAdapter):
    """SQLite-backed memory with 4 memory types.

    - Conversation: chat history (role, content, session)
    - Episodic: events and experiences (event_type, content, session)
    - Project: key-value state per project (project_name, key, value)
    - Correction: user corrections to model behavior (original, corrected, reason)
    """

    def __init__(self, storage: SQLiteAdapter) -> None:
        self.storage = storage

    def write(self, entry: MemoryEntry) -> None:
        """Write a memory entry to the appropriate table."""
        if entry.memory_type == MemoryType.CONVERSATION:
            self._write_conversation(entry)
        elif entry.memory_type == MemoryType.EPISODIC:
            self._write_episodic(entry)
        elif entry.memory_type == MemoryType.PROJECT:
            self._write_project(entry)
        elif entry.memory_type == MemoryType.CORRECTION:
            self._write_correction(entry)
        else:
            raise ValueError(f"Unknown memory type: {entry.memory_type}")

    def read(self, session_id: str, memory_type: MemoryType) -> list[MemoryEntry]:
        """Read memory entries for a session and type."""
        if memory_type == MemoryType.CONVERSATION:
            return self._read_conversation(session_id)
        elif memory_type == MemoryType.EPISODIC:
            return self._read_episodic(session_id)
        elif memory_type == MemoryType.PROJECT:
            return self._read_project(session_id)
        elif memory_type == MemoryType.CORRECTION:
            return self._read_correction(session_id)
        else:
            raise ValueError(f"Unknown memory type: {memory_type}")

    def _write_conversation(self, entry: MemoryEntry) -> None:
        """Write a conversation memory entry."""
        role = entry.metadata.get("role", "user")
        entry_id = str(uuid.uuid4())

        self.storage.execute(
            """
            INSERT INTO conversations (id, session_id, role, content, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                entry.session_id,
                role,
                entry.content,
                entry.timestamp,
                json.dumps(entry.metadata),
            ),
            store="memory",
        )

        logger.debug(
            "Wrote conversation: session=%s, role=%s, len=%d",
            entry.session_id,
            role,
            len(entry.content),
        )

    def _read_conversation(self, session_id: str) -> list[MemoryEntry]:
        """Read conversation history for a session."""
        rows = self.storage.execute(
            """
            SELECT id, session_id, role, content, created_at, metadata
            FROM conversations
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
            store="memory",
        )

        entries = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            metadata["role"] = row["role"]
            entries.append(
                MemoryEntry(
                    memory_type=MemoryType.CONVERSATION,
                    content=row["content"],
                    session_id=row["session_id"],
                    timestamp=row["created_at"],
                    metadata=metadata,
                )
            )

        return entries

    def _write_episodic(self, entry: MemoryEntry) -> None:
        """Write an episodic memory entry."""
        event_type = entry.metadata.get("event_type", "general")
        entry_id = str(uuid.uuid4())

        self.storage.execute(
            """
            INSERT INTO episodic_memory (id, session_id, event_type, content, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                entry.session_id,
                event_type,
                entry.content,
                entry.timestamp,
                json.dumps(entry.metadata),
            ),
            store="memory",
        )

        logger.debug(
            "Wrote episodic: session=%s, event=%s, len=%d",
            entry.session_id,
            event_type,
            len(entry.content),
        )

    def _read_episodic(self, session_id: str) -> list[MemoryEntry]:
        """Read episodic memory for a session."""
        rows = self.storage.execute(
            """
            SELECT id, session_id, event_type, content, created_at, metadata
            FROM episodic_memory
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
            store="memory",
        )

        entries = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            metadata["event_type"] = row["event_type"]
            entries.append(
                MemoryEntry(
                    memory_type=MemoryType.EPISODIC,
                    content=row["content"],
                    session_id=row["session_id"],
                    timestamp=row["created_at"],
                    metadata=metadata,
                )
            )

        return entries

    def _write_project(self, entry: MemoryEntry) -> None:
        """Write a project memory entry (key-value)."""
        project_name = entry.metadata.get("project_name", "default")
        key = entry.metadata.get("key", "state")

        self.storage.execute(
            """
            INSERT OR REPLACE INTO project_memory (project_name, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                project_name,
                key,
                entry.content,
                entry.timestamp,
            ),
            store="memory",
        )

        logger.debug(
            "Wrote project: project=%s, key=%s, len=%d",
            project_name,
            key,
            len(entry.content),
        )

    def _read_project(self, session_id: str) -> list[MemoryEntry]:
        """Read all project memory entries."""
        rows = self.storage.execute(
            """
            SELECT project_name, key, value, updated_at
            FROM project_memory
            ORDER BY updated_at DESC
            """,
            store="memory",
        )

        entries = []
        for row in rows:
            entries.append(
                MemoryEntry(
                    memory_type=MemoryType.PROJECT,
                    content=row["value"],
                    session_id=session_id,
                    timestamp=row["updated_at"],
                    metadata={"project_name": row["project_name"], "key": row["key"]},
                )
            )

        return entries

    def _write_correction(self, entry: MemoryEntry) -> None:
        """Write a correction memory entry."""
        original = entry.metadata.get("original", "")
        corrected = entry.content
        reason = entry.metadata.get("reason", "")
        entry_id = str(uuid.uuid4())

        self.storage.execute(
            """
            INSERT INTO corrections (id, session_id, original, corrected, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                entry.session_id,
                original,
                corrected,
                reason,
                entry.timestamp,
            ),
            store="memory",
        )

        logger.debug(
            "Wrote correction: session=%s, reason=%s",
            entry.session_id,
            reason,
        )

    def _read_correction(self, session_id: str) -> list[MemoryEntry]:
        """Read corrections for a session."""
        rows = self.storage.execute(
            """
            SELECT id, session_id, original, corrected, reason, created_at
            FROM corrections
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
            store="memory",
        )

        entries = []
        for row in rows:
            entries.append(
                MemoryEntry(
                    memory_type=MemoryType.CORRECTION,
                    content=row["corrected"],
                    session_id=row["session_id"],
                    timestamp=row["created_at"],
                    metadata={"original": row["original"], "reason": row["reason"]},
                )
            )

        return entries

    def health(self) -> dict:
        """Return health status of the memory adapter."""
        storage_health = self.storage.health()
        memory_healthy = storage_health["stores"].get("memory", {}).get("healthy", False)

        return {
            "healthy": memory_healthy,
            "backend": "sqlite",
            "memory_types": ["conversation", "episodic", "project", "correction"],
            "storage_health": storage_health,
        }


def build_sqlite_memory_adapter(storage: SQLiteAdapter) -> SQLiteMemoryAdapter:
    """Factory function to build a SQLiteMemoryAdapter."""
    return SQLiteMemoryAdapter(storage)
