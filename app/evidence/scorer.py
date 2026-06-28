"""Evidence scorer — confidence scoring based on source quality.

Meteor Doctrine #7: Evidence precedes conclusions. Every claim must have
evidence with a confidence score. This module provides the scoring logic
that determines how much weight to give each piece of evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.evidence.contract import ConfidenceLevel, EvidenceRecord


class EvidenceScorer:
    """Scores evidence based on source quality, recency, and relevance."""

    def score_source(self, source: str) -> float:
        """Score a source based on its type and reliability.

        Returns a score between 0.0 and 1.0.
        """
        source_lower = source.lower()

        if source_lower.startswith("http://") or source_lower.startswith("https://"):
            if "gov" in source_lower or "edu" in source_lower:
                return 0.95
            elif "wikipedia" in source_lower:
                return 0.85
            elif "github" in source_lower or "stackoverflow" in source_lower:
                return 0.80
            else:
                return 0.70

        elif source_lower.startswith("file://") or source_lower.endswith((".txt", ".md", ".pdf")):
            return 0.75

        elif source_lower == "memory" or source_lower.startswith("conversation"):
            return 0.60

        elif source_lower == "model" or source_lower == "inference":
            return 0.50

        else:
            return 0.40

    def score_recency(self, timestamp: str, max_age_days: int = 365) -> float:
        """Score evidence based on how recent it is.

        Returns a score between 0.0 and 1.0.
        """
        try:
            evidence_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_days = (now - evidence_time).days

            if age_days < 0:
                return 1.0
            elif age_days > max_age_days:
                return 0.3
            else:
                return 1.0 - (age_days / max_age_days) * 0.7

        except (ValueError, TypeError):
            return 0.5

    def score_relevance(self, content: str, query: str) -> float:
        """Score how relevant the evidence is to the query.

        Simple keyword overlap scoring. Returns a score between 0.0 and 1.0.
        """
        if not query or not content:
            return 0.0

        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        overlap = query_words & content_words
        relevance = len(overlap) / len(query_words)

        return min(relevance, 1.0)

    def compute_confidence(
        self,
        source: str,
        timestamp: str,
        content: str,
        query: str = "",
    ) -> ConfidenceLevel:
        """Compute overall confidence level from multiple factors.

        Combines source quality, recency, and relevance into a single
        confidence level.
        """
        source_score = self.score_source(source)
        recency_score = self.score_recency(timestamp)
        relevance_score = self.score_relevance(content, query) if query else 0.7

        overall_score = (
            source_score * 0.4 +
            recency_score * 0.3 +
            relevance_score * 0.3
        )

        if overall_score >= 0.8:
            return ConfidenceLevel.HIGH
        elif overall_score >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif overall_score >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.NONE

    def create_evidence_record(
        self,
        source: str,
        content: str,
        trace: str,
        query: str = "",
        timestamp: str = None,
        metadata: dict = None,
    ) -> EvidenceRecord:
        """Create an evidence record with computed confidence."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        confidence = self.compute_confidence(source, timestamp, content, query)

        return EvidenceRecord(
            source=source,
            content=content,
            confidence=confidence,
            timestamp=timestamp,
            trace=trace,
            metadata=metadata or {},
        )
