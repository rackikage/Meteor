from __future__ import annotations

from abc import ABC, abstractmethod
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


class MemoryAdapter(ABC):
    """Abstract interface. All memory backends must implement this contract."""

    @abstractmethod
    def write(self, entry: MemoryEntry) -> None:
        ...

    @abstractmethod
    def read(self, session_id: str, memory_type: MemoryType) -> list[MemoryEntry]:
        ...

    @abstractmethod
    def health(self) -> dict:
        ...
