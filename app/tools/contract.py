from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ToolAccessLevel(str, Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


@dataclass
class ToolInput:
    tool_name: str
    parameters: dict
    session_id: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ToolOutput:
    tool_name: str
    result: dict
    success: bool
    error: str = ""
    metadata: dict = field(default_factory=dict)


class ToolAdapter:
    """Abstract interface. All tool implementations must implement this contract."""
    access_level: ToolAccessLevel = ToolAccessLevel.READ_ONLY

    def execute(self, input: ToolInput) -> ToolOutput:
        raise NotImplementedError

    def health(self) -> dict:
        raise NotImplementedError
