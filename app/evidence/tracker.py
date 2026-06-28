"""Evidence tracker — manages evidence for runtime claims.

Meteor Doctrine #7: Evidence precedes conclusions. This tracker maintains
evidence records for all claims made by the runtime. It integrates with
the retrieval layer to automatically attach evidence to responses.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.evidence.contract import ConfidenceLevel, EvidencedClaim, EvidenceRecord
from app.evidence.scorer import EvidenceScorer
from app.retrieval.contract import RetrievedDocument

logger = logging.getLogger(__name__)


class EvidenceTracker:
    """Tracks and manages evidence for runtime claims.

    Integrates with retrieval to automatically find and score evidence
    for claims made during inference.
    """

    def __init__(self) -> None:
        self.scorer = EvidenceScorer()
        self._claims: list[EvidencedClaim] = []

    def create_claim(
        self,
        claim_text: str,
        evidence: list[EvidenceRecord] = None,
        metadata: dict = None,
    ) -> EvidencedClaim:
        """Create a new evidenced claim."""
        claim = EvidencedClaim(
            claim_text=claim_text,
            confidence=self._compute_claim_confidence(evidence or []),
            evidence=evidence or [],
            metadata=metadata or {},
        )
        self._claims.append(claim)
        return claim

    def find_evidence_for_claim(
        self,
        claim_text: str,
        retrieved_documents: list[RetrievedDocument],
        trace_prefix: str = "retrieval",
    ) -> list[EvidenceRecord]:
        """Find and score evidence for a claim from retrieved documents."""
        evidence_records = []

        for i, doc in enumerate(retrieved_documents):
            trace = f"{trace_prefix}:source={doc.source},score={doc.score:.3f},rank={i+1}"

            record = self.scorer.create_evidence_record(
                source=doc.source,
                content=doc.content,
                trace=trace,
                query=claim_text,
                metadata={
                    "retrieval_score": doc.score,
                    "rank": i + 1,
                    **doc.metadata,
                },
            )

            evidence_records.append(record)

        logger.debug(
            "Found %d evidence records for claim: '%s'",
            len(evidence_records),
            claim_text[:50],
        )

        return evidence_records

    def annotate_response_with_evidence(
        self,
        response_text: str,
        retrieved_documents: list[RetrievedDocument],
        metadata: dict = None,
    ) -> EvidencedClaim:
        """Annotate a model response with evidence from retrieved documents."""
        evidence = self.find_evidence_for_claim(
            claim_text=response_text,
            retrieved_documents=retrieved_documents,
            trace_prefix="response",
        )

        claim = self.create_claim(
            claim_text=response_text,
            evidence=evidence,
            metadata=metadata or {},
        )

        logger.info(
            "Annotated response with %d evidence records, confidence=%s",
            len(evidence),
            claim.confidence.value,
        )

        return claim

    def _compute_claim_confidence(self, evidence: list[EvidenceRecord]) -> ConfidenceLevel:
        """Compute overall confidence for a claim based on its evidence."""
        if not evidence:
            return ConfidenceLevel.NONE

        confidence_scores = {
            ConfidenceLevel.HIGH: 4,
            ConfidenceLevel.MEDIUM: 3,
            ConfidenceLevel.LOW: 2,
            ConfidenceLevel.NONE: 1,
        }

        total_score = sum(confidence_scores[e.confidence] for e in evidence)
        avg_score = total_score / len(evidence)

        if avg_score >= 3.5:
            return ConfidenceLevel.HIGH
        elif avg_score >= 2.5:
            return ConfidenceLevel.MEDIUM
        elif avg_score >= 1.5:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.NONE

    def get_claims(self, limit: int = 100) -> list[EvidencedClaim]:
        """Get recent claims."""
        return self._claims[-limit:]

    def get_claims_by_confidence(self, confidence: ConfidenceLevel) -> list[EvidencedClaim]:
        """Get claims filtered by confidence level."""
        return [c for c in self._claims if c.confidence == confidence]

    def clear(self) -> None:
        """Clear all tracked claims."""
        self._claims.clear()
        logger.info("Evidence tracker cleared")
