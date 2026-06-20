from __future__ import annotations

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


class StorageAdapter:
    """Abstract interface. All storage backends must implement this contract."""

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        raise NotImplementedError

    def migrate(self) -> list[MigrationRecord]:
        raise NotImplementedError

    def health(self) -> dict:
        raise NotImplementedError
