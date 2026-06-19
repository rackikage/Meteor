from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class EvidenceRecord:
    source: str
    content: str
    confidence: ConfidenceLevel
    timestamp: str
    trace: str
    metadata: dict = field(default_factory=dict)


@dataclass
class EvidencedClaim:
    claim_text: str
    confidence: ConfidenceLevel
    evidence: list[EvidenceRecord] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def has_evidence(self) -> bool:
        return len(self.evidence) > 0
