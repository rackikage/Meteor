"""Tests for the evidence layer.

Verifies: evidence scoring, evidence tracking, confidence computation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.evidence.contract import ConfidenceLevel, EvidencedClaim, EvidenceRecord
from app.evidence.scorer import EvidenceScorer
from app.evidence.tracker import EvidenceTracker
from app.retrieval.contract import RetrievedDocument


def test_confidence_level_values() -> None:
    assert ConfidenceLevel.HIGH.value == "high"
    assert ConfidenceLevel.MEDIUM.value == "medium"
    assert ConfidenceLevel.LOW.value == "low"
    assert ConfidenceLevel.NONE.value == "none"


def test_evidence_record_defaults() -> None:
    record = EvidenceRecord(
        source="test",
        content="test content",
        confidence=ConfidenceLevel.HIGH,
        timestamp="2024-01-01T00:00:00",
        trace="test:trace",
    )
    assert record.metadata == {}


def test_evidenced_claim_has_evidence() -> None:
    claim = EvidencedClaim(
        claim_text="test",
        confidence=ConfidenceLevel.HIGH,
    )
    assert claim.has_evidence is False

    claim.evidence.append(
        EvidenceRecord(
            source="test",
            content="test",
            confidence=ConfidenceLevel.HIGH,
            timestamp="2024-01-01T00:00:00",
            trace="test",
        )
    )
    assert claim.has_evidence is True


def test_scorer_source_gov_edu() -> None:
    scorer = EvidenceScorer()
    assert scorer.score_source("https://example.gov/page") == 0.95
    assert scorer.score_source("https://example.edu/page") == 0.95


def test_scorer_source_wikipedia() -> None:
    scorer = EvidenceScorer()
    assert scorer.score_source("https://wikipedia.org/article") == 0.85


def test_scorer_source_tech() -> None:
    scorer = EvidenceScorer()
    assert scorer.score_source("https://github.com/repo") == 0.80
    assert scorer.score_source("https://stackoverflow.com/q/123") == 0.80


def test_scorer_source_generic_web() -> None:
    scorer = EvidenceScorer()
    assert scorer.score_source("https://example.com/page") == 0.70


def test_scorer_source_file() -> None:
    scorer = EvidenceScorer()
    assert scorer.score_source("file:///path/to/file.txt") == 0.75
    assert scorer.score_source("document.md") == 0.75


def test_scorer_source_memory() -> None:
    scorer = EvidenceScorer()
    assert scorer.score_source("memory") == 0.60
    assert scorer.score_source("conversation:session-1") == 0.60


def test_scorer_source_model() -> None:
    scorer = EvidenceScorer()
    assert scorer.score_source("model") == 0.50
    assert scorer.score_source("inference") == 0.50


def test_scorer_source_unknown() -> None:
    scorer = EvidenceScorer()
    assert scorer.score_source("unknown") == 0.40


def test_scorer_recency_recent() -> None:
    scorer = EvidenceScorer()
    recent = datetime.now(timezone.utc).isoformat()
    assert scorer.score_recency(recent) == 1.0


def test_scorer_recency_old() -> None:
    scorer = EvidenceScorer()
    old = "2020-01-01T00:00:00"
    score = scorer.score_recency(old, max_age_days=365)
    assert score <= 0.5


def test_scorer_relevance_high() -> None:
    scorer = EvidenceScorer()
    score = scorer.score_relevance(
        "Python is a programming language used for web development",
        "Python programming",
    )
    assert score > 0.5


def test_scorer_relevance_low() -> None:
    scorer = EvidenceScorer()
    score = scorer.score_relevance(
        "The weather is nice today",
        "Python programming",
    )
    assert score < 0.3


def test_scorer_compute_confidence_high() -> None:
    scorer = EvidenceScorer()
    confidence = scorer.compute_confidence(
        source="https://example.gov/doc",
        timestamp=datetime.now(timezone.utc).isoformat(),
        content="Python programming language",
        query="Python",
    )
    assert confidence == ConfidenceLevel.HIGH


def test_scorer_compute_confidence_low() -> None:
    scorer = EvidenceScorer()
    confidence = scorer.compute_confidence(
        source="unknown",
        timestamp="2020-01-01T00:00:00",
        content="unrelated content",
        query="Python",
    )
    assert confidence in (ConfidenceLevel.LOW, ConfidenceLevel.NONE)


def test_scorer_create_evidence_record() -> None:
    scorer = EvidenceScorer()
    record = scorer.create_evidence_record(
        source="https://example.com",
        content="test content",
        trace="test:trace",
        query="test",
    )
    assert isinstance(record, EvidenceRecord)
    assert record.source == "https://example.com"
    assert record.confidence in ConfidenceLevel


def test_tracker_create_claim() -> None:
    tracker = EvidenceTracker()
    claim = tracker.create_claim("test claim")
    assert claim.claim_text == "test claim"
    assert claim.confidence == ConfidenceLevel.NONE
    assert not claim.has_evidence


def test_tracker_create_claim_with_evidence() -> None:
    tracker = EvidenceTracker()
    evidence = [
        EvidenceRecord(
            source="test",
            content="test",
            confidence=ConfidenceLevel.HIGH,
            timestamp="2024-01-01T00:00:00",
            trace="test",
        )
    ]
    claim = tracker.create_claim("test claim", evidence=evidence)
    assert claim.has_evidence
    assert claim.confidence == ConfidenceLevel.HIGH


def test_tracker_find_evidence_for_claim() -> None:
    tracker = EvidenceTracker()
    docs = [
        RetrievedDocument(
            content="Python is a programming language",
            source="https://example.com",
            score=0.9,
            metadata={"rank": 1},
        ),
    ]
    evidence = tracker.find_evidence_for_claim("What is Python?", docs)
    assert len(evidence) == 1
    assert evidence[0].source == "https://example.com"


def test_tracker_annotate_response_with_evidence() -> None:
    tracker = EvidenceTracker()
    docs = [
        RetrievedDocument(
            content="Python is a programming language",
            source="https://example.com",
            score=0.9,
        ),
    ]
    claim = tracker.annotate_response_with_evidence(
        response_text="Python is a programming language used for web development.",
        retrieved_documents=docs,
    )
    assert claim.has_evidence
    assert len(claim.evidence) == 1


def test_tracker_get_claims() -> None:
    tracker = EvidenceTracker()
    tracker.create_claim("claim 1")
    tracker.create_claim("claim 2")
    claims = tracker.get_claims(limit=10)
    assert len(claims) == 2


def test_tracker_get_claims_by_confidence() -> None:
    tracker = EvidenceTracker()
    tracker.create_claim("claim 1", evidence=[
        EvidenceRecord(
            source="test",
            content="test",
            confidence=ConfidenceLevel.HIGH,
            timestamp="2024-01-01T00:00:00",
            trace="test",
        )
    ])
    tracker.create_claim("claim 2")

    high_claims = tracker.get_claims_by_confidence(ConfidenceLevel.HIGH)
    assert len(high_claims) == 1

    none_claims = tracker.get_claims_by_confidence(ConfidenceLevel.NONE)
    assert len(none_claims) == 1


def test_tracker_clear() -> None:
    tracker = EvidenceTracker()
    tracker.create_claim("claim 1")
    tracker.create_claim("claim 2")
    tracker.clear()
    assert len(tracker.get_claims()) == 0
