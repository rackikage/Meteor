from __future__ import annotations

from datetime import UTC, datetime

from app.evidence.contract import ConfidenceLevel, EvidenceRecord
from app.models.contract import ModelOutput
from app.policy.contract import PolicyDecision
from app.retrieval.contract import RetrievalResult


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def evidence_from_policy(decision: PolicyDecision, trace: str) -> EvidenceRecord:
    return EvidenceRecord(
        source="policy",
        content=decision.reason,
        confidence=ConfidenceLevel.HIGH,
        timestamp=utc_now(),
        trace=trace,
        metadata={
            "subject": decision.subject.value,
            "action": decision.action.value,
            "audited": decision.audited,
        },
    )


def evidence_from_retrieval(result: RetrievalResult) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    for index, document in enumerate(result.documents):
        records.append(
            EvidenceRecord(
                source=document.source,
                content=document.content,
                confidence=ConfidenceLevel.MEDIUM if document.score >= 0.5 else ConfidenceLevel.LOW,
                timestamp=utc_now(),
                trace=f"retrieval.documents[{index}]",
                metadata={"score": document.score, **document.metadata},
            )
        )
    return records


def evidence_from_model(output: ModelOutput) -> EvidenceRecord:
    wired = bool(output.metadata.get("wired"))
    return EvidenceRecord(
        source="model_adapter",
        content=f"finish_reason={output.finish_reason}",
        confidence=ConfidenceLevel.MEDIUM if wired else ConfidenceLevel.LOW,
        timestamp=utc_now(),
        trace="model.complete",
        metadata=output.metadata,
    )
