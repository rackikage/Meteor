from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MemoryType(str, Enum):
    CONVERSATION = "conversation"
    EPISODIC = "episodic"
    PROJECT = "project"
    CORRECTION = "correction"


@dataclass
class MemoryEntry:
    memory_type: MemoryType
    content: str
    session_id: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


class MemoryAdapter:
    """Abstract interface. All memory backends must implement this contract."""

    def write(self, entry: MemoryEntry) -> None:
        raise NotImplementedError

    def read(self, session_id: str, memory_type: MemoryType) -> list[MemoryEntry]:
        raise NotImplementedError

    def health(self) -> dict:
        raise NotImplementedError
