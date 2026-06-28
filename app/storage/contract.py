from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class StoreType(str, Enum):
    MEMORY = "memory"
    AUDIT = "audit"
    INDEX_META = "index_meta"


@dataclass
class MigrationRecord:
    version: int
    name: str
    applied_at: str


class StorageAdapter(ABC):
    """Abstract interface. All storage backends must implement this contract."""

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        ...

    @abstractmethod
    def migrate(self) -> list[MigrationRecord]:
        ...

    @abstractmethod
    def health(self) -> dict:
        ...
