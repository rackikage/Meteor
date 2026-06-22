from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.evidence.contract import EvidenceRecord


class RuntimeStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    POLICY_DENIED = "policy_denied"
    ERROR = "error"


@dataclass
class RuntimeRequest:
    prompt: str
    session_id: str = "default"
    top_k: int = 5
    store_in_memory: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class RuntimeResponse:
    response_text: str
    status: RuntimeStatus
    evidence: list[EvidenceRecord] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
