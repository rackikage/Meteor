"""SQL persistence for system tools — audit trails for filesystem, shell, process, etc."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.storage.sqlite_adapter import SQLiteAdapter


class SystemDataModel:
    def __init__(self, storage: SQLiteAdapter) -> None:
        self._storage = storage

    def log_filesystem(self, operation: str, path: str, size: int = 0, duration_ms: float = 0.0, status: str = "ok") -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute("INSERT INTO filesystem_audit (operation, path, size, duration_ms, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)", (operation, path, size, duration_ms, status, now), store="audit")

    def log_shell(self, command: str, returncode: int, stdout: str, stderr: str, duration_ms: float, work_dir: str = "", timed_out: bool = False) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute("INSERT INTO shell_history (command, returncode, stdout_preview, stderr_preview, duration_ms, work_dir, timed_out, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (command[:500], returncode, stdout[:200], stderr[:200], duration_ms, work_dir, int(timed_out), now), store="audit")

    def log_notification(self, title: str, message: str, urgency: str = "normal", delivered: bool = True) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute("INSERT INTO notification_history (title, message, urgency, delivered, timestamp) VALUES (?, ?, ?, ?, ?)", (title, message, urgency, int(delivered), now), store="audit")

    def save_scheduled_task(self, name: str, command: str, schedule: str, enabled: bool = True) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute("INSERT OR REPLACE INTO scheduled_tasks (name, command, schedule, enabled, created_at) VALUES (?, ?, ?, ?, ?)", (name, command, schedule, int(enabled), now), store="audit")

    def log_ipc(self, source: str, target: str, action: str, payload: str = "", response_status: str = "", duration_ms: float = 0.0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._storage.execute("INSERT INTO ipc_messages (source, target, action, payload, response_status, duration_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)", (source, target, action, payload[:500], response_status, duration_ms, now), store="audit")

    def get_shell_history(self, limit: int = 50) -> list[dict]:
        rows = self._storage.execute("SELECT * FROM shell_history ORDER BY timestamp DESC LIMIT ?", (limit,), store="audit")
        return [dict(r) for r in rows]

    def get_notification_history(self, limit: int = 50) -> list[dict]:
        rows = self._storage.execute("SELECT * FROM notification_history ORDER BY timestamp DESC LIMIT ?", (limit,), store="audit")
        return [dict(r) for r in rows]
