from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RuntimeStatus(str, Enum):
    OK = "ok"
    NOT_IMPLEMENTED = "not_implemented"
    POLICY_DENIED = "policy_denied"
    ERROR = "error"


@dataclass
class RuntimeRequest:
    prompt: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RuntimeResponse:
    response_text: str
    status: RuntimeStatus
    evidence: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
