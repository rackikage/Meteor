from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.memory.contract import MemoryAdapter, MemoryEntry, MemoryType


class SQLiteMemoryAdapter(MemoryAdapter):
    """Durable local memory adapter backed by SQLite."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path.resolve(strict=False)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def write(self, entry: MemoryEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_entries (memory_type, content, session_id, timestamp, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry.memory_type.value,
                    entry.content,
                    entry.session_id,
                    entry.timestamp,
                    json.dumps(entry.metadata, sort_keys=True),
                ),
            )

    def read(self, session_id: str, memory_type: MemoryType, limit: int = 20) -> list[MemoryEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT memory_type, content, session_id, timestamp, metadata_json
                FROM memory_entries
                WHERE session_id = ? AND memory_type = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, memory_type.value, limit),
            ).fetchall()

        entries: list[MemoryEntry] = []
        for row in rows:
            entries.append(
                MemoryEntry(
                    memory_type=MemoryType(row["memory_type"]),
                    content=row["content"],
                    session_id=row["session_id"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata_json"] or "{}"),
                )
            )
        return entries

    def health(self) -> dict:
        try:
            with self._connect() as conn:
                count = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
        except sqlite3.Error as exc:
            return {
                "component": "memory",
                "healthy": False,
                "wired": True,
                "backend": "sqlite",
                "path": str(self._db_path),
                "detail": str(exc),
            }

        return {
            "component": "memory",
            "healthy": True,
            "wired": True,
            "backend": "sqlite",
            "path": str(self._db_path),
            "entries": count,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_entries_session_type
                ON memory_entries (session_id, memory_type, id)
                """
            )
